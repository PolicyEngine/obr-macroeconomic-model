# OBR macro model — chat (LLM ↔ model backend)

A Claude agent that answers natural-language questions about the OBR model
emulator, modelled on PolicyEngine UK Chat: **FastAPI backend + a tool-using
Claude agent + a minimal chat UI.** The LLM calls tools that read the project's
pre-computed model data, so answers are instant (no slow solver runs).

## Architecture
- `agent.py` — the tools (`model_overview`, `list_scenarios`, `scenario_impact`,
  `search_variables`, `get_equation`) wrapping `dashboard/public/data/*.json`,
  plus the manual Claude tool-use loop (`claude-opus-5-5`, adaptive thinking at
  explicit medium effort with a 16,000-token limit for thinking and the reply).
- `server.py` — FastAPI: `POST /api/chat`, and `GET /` serves the UI.
- `static/index.html` — minimal chat page.

## Setup
1. Put your Anthropic key in `.env` at the repo root (gitignored):
   ```
   ANTHROPIC_API_KEY=sk-ant-...
   ANTHROPIC_MODEL=claude-opus-5-5   # optional; or claude-sonnet-5-5 to cut cost
   ```
   You need API **credits** — add them at console.anthropic.com/settings/billing.
   An `ANTHROPIC_MODEL` line left in `.env` by an earlier setup (such as
   `claude-opus-4-8`) still overrides the default; update or delete it.
2. Install the optional chat dependencies: `uv sync --locked --group chat`.
   The group requires `anthropic>=1.0` (which supports `output_config`) and
   `uv.lock` pins the SDK and server dependencies used by the offline tests.

Every request sends adaptive thinking (`thinking: {"type": "adaptive"}`),
medium effort and a 16,000-token limit for thinking and the reply. On Opus 5.5
and Sonnet 5.5 sending adaptive thinking is the same as omitting the parameter;
older models such as Opus 4.8 and Sonnet 4.6 run without thinking unless it is
sent.

Each reply's content blocks are kept with only the fields the API returned, so
the history the server hands the UI gains no fields. The UI posts it back on the
next turn, and later requests replay earlier turns, including their thinking
blocks, with the fields and values the API returned. (The browser's JSON
handling would turn a number such as `3.0` in a tool input into `3`; this app's
tool inputs are strings and an integer.)

## Run (from the repo root)
```bash
uv run --group chat uvicorn chat.server:app --reload --port 8000
```
The server binds to `127.0.0.1` (uvicorn's default) so it is only reachable
locally; pass `--host 0.0.0.0` explicitly if you really want to expose it on
your network. Requests are lightly capped (40 messages / 8,000 chars per typed
message, 20 requests per minute per IP) since the endpoint proxies to the
Anthropic API.

Open http://localhost:8000 and ask, e.g. *"What happens to GDP if corporation tax
rises 5pp?"* or *"What does TCPRO mean?"*

## Notes
- Tools read pre-computed data; a live "run any custom shock" tool would call the
  Python solver (~1–2 min) and is the natural next addition.
- Answers are emulator output under the user's assumptions — not OBR forecasts;
  the agent is instructed to say so.
- If the model declines a request, the chat displays a notice and removes that
  request and its tool rounds from the API history so the user can rephrase it.
- The agent requires histories to end with a user turn. Empty histories and
  assistant prefill are rejected locally without calling the model.

## Tests
Run `uv run --group chat pytest -q tests/test_chat_agent.py`. These tests use the
real SDK with a mock HTTP transport; they need no API key and make no model API
calls.
