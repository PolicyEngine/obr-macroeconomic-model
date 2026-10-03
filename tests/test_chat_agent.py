"""Contract tests for the chat agent's Claude tool loop (chat/agent.py).

Hermetic: the real Anthropic SDK builds and parses every request, but a mock
HTTP transport answers it, so nothing reaches the network or needs an API key.
They need the optional chat dependencies (`uv sync --group chat`) and are
skipped without them.
"""

import importlib
import json

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
    """Serve canned responses in order and record every request body."""
    state = {"responses": [], "requests": []}

    def handler(request):
        state["requests"].append(json.loads(request.content))
        return httpx2.Response(200, json=state["responses"].pop(0))

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


def _field(block, key):
    # History blocks are dicts (from the UI) or SDK objects (from responses).
    return block[key] if isinstance(block, dict) else getattr(block, key)


def _assert_valid_history(messages):
    """Invariants any history handed back to the UI must satisfy, so the next
    request is accepted: no empty assistant turn, and every tool_use is answered
    by a tool_result in the next message."""
    for i, m in enumerate(messages):
        if m["role"] != "assistant":
            continue
        assert m["content"], f"message {i} is an empty assistant turn"
        ids = {_field(b, "id") for b in m["content"] if _field(b, "type") == "tool_use"}
        if ids:
            nxt = messages[i + 1]
            answered = {_field(b, "tool_use_id") for b in nxt["content"]}
            assert ids <= answered, f"message {i} has unanswered tool_use blocks"


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
    if model == "claude-sonnet-5-5":
        assert body["thinking"] == {"type": "adaptive"}
    else:
        assert "thinking" not in body
    assert body.get("tool_choice", {"type": "auto"})["type"] in ("auto", "none")
    # Effort is set explicitly: the Opus 5.5 default (medium) differs from
    # earlier Opus models (high).
    assert body["output_config"]["effort"] == "medium"
    # No assistant prefill: the conversation sent ends on a user turn.
    assert body["messages"][-1]["role"] == "user"


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
    _assert_valid_history(messages)


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
