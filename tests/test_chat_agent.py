"""Contract tests for the chat agent's Claude tool loop (chat/agent.py).

Hermetic: the real Anthropic SDK builds and parses every request, but a mock
HTTP transport answers it, so nothing reaches the network or needs an API key.
They need the optional chat dependencies (`uv sync --group chat`) and are
skipped without them.
"""

import importlib
import itertools
import json
from collections import defaultdict, deque

import pytest

anthropic = pytest.importorskip("anthropic")
httpx2 = pytest.importorskip("httpx2")
pytest.importorskip("dotenv")

from chat import agent  # noqa: E402

SAMPLING_PARAMS = ("temperature", "top_p", "top_k")


def _message(content, stop_reason, stop_details=None):
    return {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "model": agent.MODEL,
        "content": content,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "stop_details": stop_details,
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }


def _thinking(signature):
    return {"type": "thinking", "thinking": "", "signature": signature}


def _tool_use(tool_id, name, tool_input=None):
    return {"type": "tool_use", "id": tool_id, "name": name, "input": tool_input or {}}


def _text(text):
    return {"type": "text", "text": text}


def _refusal(content=(), category="bio"):
    details = {"type": "refusal", "category": category, "explanation": None}
    return _message(list(content), "refusal", details)


TOOL_ROUND = _message(
    [_thinking("sig-1"), _tool_use("toolu_1", "list_scenarios")], "tool_use"
)
ANSWER = _message([_thinking("sig-2"), _text("GDP rises 0.3%.")], "end_turn")


@pytest.fixture
def api(monkeypatch):
    """Serve canned responses in order and record every request body and the
    response served to it."""
    state = {"responses": [], "requests": [], "served": []}

    def handler(request):
        state["requests"].append(json.loads(request.content))
        state["served"].append(state["responses"].pop(0))
        return httpx2.Response(200, json=state["served"][-1])

    real_client = anthropic.Anthropic

    def client_factory(**kwargs):
        return real_client(
            api_key="test-key",
            max_retries=0,
            http_client=anthropic.DefaultHttpxClient(
                transport=httpx2.MockTransport(handler)
            ),
            **kwargs,
        )

    monkeypatch.setattr(agent.anthropic, "Anthropic", client_factory)
    return state


def _assert_valid_history(messages):
    """Invariants any history handed back to the UI must satisfy, so the next
    request is accepted: no empty assistant turn, and every tool_use is answered
    by a tool_result in the next message."""
    for i, m in enumerate(messages):
        if m["role"] != "assistant":
            continue
        assert m["content"], f"message {i} is an empty assistant turn"
        ids = {b["id"] for b in m["content"] if b["type"] == "tool_use"}
        if ids:
            nxt = messages[i + 1]
            answered = {b["tool_use_id"] for b in nxt["content"]}
            assert ids <= answered, f"message {i} has unanswered tool_use blocks"


def _assert_replayed_thinking_is_bound(requests, served):
    """A stricter form of the preserved-thinking check, applied to every
    thinking block replayed in any request: the system prompt, the tools (in
    order) and every message before the block's turn are identical (same JSON,
    same key order) to the request that produced it, and the turn itself equals
    the content the API returned. Returns how many replayed blocks were
    checked."""
    produced = {}
    for body, response in zip(requests, served):
        for block in response["content"]:
            if block["type"] == "thinking":
                produced[block["signature"]] = (body, response["content"])
    checked = 0
    for body in requests:
        for i, m in enumerate(body["messages"]):
            if m["role"] != "assistant" or isinstance(m["content"], str):
                continue
            for block in m["content"]:
                if block["type"] != "thinking":
                    continue
                origin, content = produced[block["signature"]]
                assert json.dumps(body["messages"][:i]) == json.dumps(
                    origin["messages"]
                ), f"history before the turn at message {i} was edited"
                assert m["content"] == content, f"turn at message {i} was edited"
                assert json.dumps(body["system"]) == json.dumps(origin["system"])
                assert json.dumps(body["tools"]) == json.dumps(origin["tools"])
                checked += 1
    return checked


@pytest.mark.parametrize("override", [None, "claude-sonnet-5-5"])
def test_model_default_and_environment_override(monkeypatch, override):
    if override is None:
        monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
    else:
        monkeypatch.setenv("ANTHROPIC_MODEL", override)
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)
    try:
        assert importlib.reload(agent).MODEL == (override or "claude-opus-5-5")
    finally:
        monkeypatch.undo()
        importlib.reload(agent)


@pytest.mark.parametrize("model", ["claude-opus-5-5", "claude-sonnet-5-5"])
def test_request_shape_is_valid_for_claude_5_5(api, monkeypatch, model):
    monkeypatch.setattr(agent, "MODEL", model)
    api["responses"] = [ANSWER]
    agent.respond([{"role": "user", "content": "What does TCPRO mean?"}])

    (body,) = api["requests"]
    assert body["model"] == agent.MODEL
    # Thinking counts toward max_tokens; leave room for it and the reply.
    assert body["max_tokens"] >= 16000
    # Opus 5.5 rejects non-default sampling, disabled/budgeted thinking and
    # forced tool use with a 400.
    for param in SAMPLING_PARAMS:
        assert param not in body
    assert body["thinking"] == {"type": "adaptive"}
    assert body.get("tool_choice", {"type": "auto"})["type"] in ("auto", "none")
    # Effort is set explicitly: the Opus 5.5 default (medium) differs from
    # earlier Opus models (high).
    assert body["output_config"]["effort"] == "medium"
    # No assistant prefill: the conversation sent ends on a user turn.
    assert body["messages"][-1]["role"] == "user"


@pytest.mark.parametrize(
    "model",
    [
        "claude-opus-5-5",
        "claude-sonnet-5-5",
        "claude-opus-5",
        # Values the previous README put in .env, which still override the
        # default. Omitting thinking turns it off on these models.
        "claude-opus-4-8",
        "claude-sonnet-4-6",
    ],
)
def test_every_model_override_keeps_adaptive_thinking(api, monkeypatch, model):
    monkeypatch.setattr(agent, "MODEL", model)
    api["responses"] = [ANSWER]
    agent.respond([{"role": "user", "content": "q"}])

    (body,) = api["requests"]
    assert body["model"] == model
    assert body["thinking"] == {"type": "adaptive"}


@pytest.mark.parametrize(
    "history",
    [
        [],
        [{"role": "assistant", "content": "prefill"}],
        [{"role": "assistant", "content": [_text("prefill")]}],
    ],
)
def test_invalid_history_never_reaches_the_provider(monkeypatch, history):
    def unexpected_client(*args, **kwargs):
        pytest.fail("An empty history or assistant prefill must not reach the provider")

    monkeypatch.setattr(agent.anthropic, "Anthropic", unexpected_client)
    reply, messages = agent.respond(history)

    assert "user message" in reply
    assert messages is history


def test_tool_loop_appends_and_replays_thinking_unchanged(api):
    api["responses"] = [TOOL_ROUND, ANSWER]
    history = [{"role": "user", "content": "What happens to GDP?"}]
    reply, messages = agent.respond(history)

    assert reply == "GDP rises 0.3%."
    first, second = api["requests"]
    # Append-only: each request's history is a prefix of the next, so earlier
    # thinking blocks stay valid under the preserved-thinking check.
    assert second["messages"][: len(first["messages"])] == first["messages"]
    replayed = second["messages"][1]
    assert replayed["role"] == "assistant"
    assert replayed["content"][0]["type"] == "thinking"
    assert replayed["content"][0]["signature"] == "sig-1"
    (result,) = second["messages"][2]["content"]
    assert result["type"] == "tool_result"
    assert result["tool_use_id"] == "toolu_1"
    assert "scenarios" in json.loads(result["content"])
    # The history returned holds plain JSON with only the fields the API sent,
    # so serializing it for the UI adds nothing (no unset fields as nulls).
    assert messages[1]["content"] == TOOL_ROUND["content"]
    assert messages[3]["content"] == ANSWER["content"]
    _assert_valid_history(messages)
    assert _assert_replayed_thinking_is_bound(api["requests"], api["served"]) == 1


def _search_round(tag):
    """A tool round whose blocks mix fields the API set (a null citations, a
    caller) with fields it left unset (toolset_name), plus a non-ASCII input."""
    return _message(
        [
            _thinking(f"sig-{tag}"),
            {"type": "text", "text": "Searching.", "citations": None},
            {
                "type": "tool_use",
                "id": f"toolu_{tag}",
                "name": "search_variables",
                "input": {"query": "consumption – £", "limit": 3},
                "caller": {"type": "direct"},
            },
        ],
        "tool_use",
    )


def _server_client(monkeypatch):
    pytest.importorskip("fastapi")
    from starlette.testclient import TestClient

    from chat import server

    monkeypatch.setattr(server, "_hits", defaultdict(deque))
    return TestClient(server.app)


def _chat_turns(client, questions):
    """Drive the UI's loop: append the typed question, post the history, keep
    the history the server returns."""
    history = []
    for question in questions:
        history.append({"role": "user", "content": question})
        response = client.post("/api/chat", json={"messages": history})
        assert response.status_code == 200
        history = response.json()["messages"]
    return history


@pytest.mark.parametrize(
    "tool_rounds",
    list(itertools.product(range(3), repeat=3)),
    ids=lambda rounds: "rounds-" + "-".join(map(str, rounds)),
)
def test_history_round_trips_through_the_server_unchanged(
    api, monkeypatch, tool_rounds
):
    """Every combination of 0-2 tool rounds in each of three HTTP turns. Between
    turns the history goes through FastAPI's JSON encoder, a JSON round trip
    (Python's, standing in for the UI's) and request validation. Every request
    must extend the previous one append-only and replay each earlier thinking
    block with its prefix intact, as the preserved-thinking check on Claude 5.5
    requires."""
    client = _server_client(monkeypatch)
    api["responses"] = [
        response
        for turn, rounds in enumerate(tool_rounds)
        for response in [_search_round(f"{turn}-{r}") for r in range(rounds)]
        + [_message([_thinking(f"sig-{turn}-answer"), _text("Done.")], "end_turn")]
    ]
    history = _chat_turns(client, ["q1", "q2", "q3"])

    requests = api["requests"]
    assert len(requests) == sum(tool_rounds) + 3
    for previous, current in zip(requests, requests[1:]):
        shared = current["messages"][: len(previous["messages"])]
        assert json.dumps(shared) == json.dumps(previous["messages"])
    assert _assert_replayed_thinking_is_bound(requests, api["served"]) > 0
    _assert_valid_history(history)


def test_refusal_rollback_keeps_earlier_thinking_bound(api, monkeypatch):
    """A turn declined after a tool round is rolled back; the next turn still
    replays the earlier turns' thinking blocks with their prefixes intact."""
    client = _server_client(monkeypatch)
    answer = _message([_thinking("sig-answer"), _text("Done.")], "end_turn")
    api["responses"] = [
        _search_round("1"),
        answer,
        _search_round("2"),
        _refusal([_text("partial")]),
        _message([_thinking("sig-3"), _text("Done again.")], "end_turn"),
    ]
    history = _chat_turns(client, ["q1", "declined", "q3"])

    first_turn = api["requests"][1]["messages"] + [
        {"role": "assistant", "content": answer["content"]}
    ]
    assert api["requests"][-1]["messages"] == first_turn + [
        {"role": "user", "content": "q3"}
    ]
    assert _assert_replayed_thinking_is_bound(api["requests"], api["served"]) > 0
    _assert_valid_history(history)


def test_refusal_before_output_rolls_back_the_declined_message(api):
    api["responses"] = [_refusal()]
    earlier = [
        {"role": "user", "content": "What is GDPM?"},
        {"role": "assistant", "content": [{"type": "text", "text": "Real GDP."}]},
    ]
    history = earlier + [{"role": "user", "content": "declined question"}]
    reply, messages = agent.respond(list(history))

    assert "declined" in reply
    assert "bio" not in reply
    assert "removed from the conversation" in reply
    assert messages == earlier


@pytest.mark.parametrize("tool_rounds", [0, 1, 2, 3])
def test_refusal_after_any_number_of_tool_rounds(api, tool_rounds):
    """Whichever round the model declines on, the reply is the refusal notice
    (never the partial text) and the history returns to its state before the
    declined message, so the next request is valid."""
    rounds = [
        _message(
            [_thinking(f"sig-{i}"), _tool_use(f"toolu_{i}", "model_overview")],
            "tool_use",
        )
        for i in range(tool_rounds)
    ]
    api["responses"] = rounds + [_refusal([_text("partial answer")])]
    earlier = [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": [{"type": "text", "text": "Hello."}]},
    ]
    reply, messages = agent.respond(earlier + [{"role": "user", "content": "q"}])

    assert "partial answer" not in reply
    assert "declined" in reply
    assert messages == earlier
    assert len(api["requests"]) == tool_rounds + 1


def test_refusal_without_category_still_handled(api):
    api["responses"] = [_message([], "refusal", None)]
    reply, messages = agent.respond([{"role": "user", "content": "q"}])
    assert reply.startswith("Sorry — the model declined to answer that.")
    assert messages == []


def test_refusal_never_executes_partial_tool_calls(api, monkeypatch):
    api["responses"] = [_refusal([_tool_use("toolu_1", "list_scenarios")])]

    def unexpected_tool_call(*args, **kwargs):
        pytest.fail("A refused response must not execute tools")

    monkeypatch.setattr(agent, "execute_tool", unexpected_tool_call)
    reply, messages = agent.respond([{"role": "user", "content": "q"}])

    assert "declined" in reply
    assert messages == []
    assert len(api["requests"]) == 1


def test_refusal_never_drops_a_tool_result_turn(api):
    """If the history sent ends on tool results rather than a typed message,
    dropping it would orphan the preceding tool_use, so it is kept."""
    api["responses"] = [_refusal()]
    history = [
        {"role": "user", "content": "q"},
        {
            "role": "assistant",
            "content": [{"type": "tool_use", "id": "t1", "name": "x", "input": {}}],
        },
        {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "{}"}],
        },
    ]
    reply, messages = agent.respond(list(history))
    assert messages == history
    assert "removed from the conversation" not in reply
