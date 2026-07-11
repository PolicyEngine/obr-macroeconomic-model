"""FastAPI backend for the OBR macro-model chat.

POST /api/chat  { "messages": [{role, content}, ...] }  ->  { "reply": "...", "messages": [...] }
GET  /          serves the minimal chat UI.

Run:  uv run uvicorn chat.server:app --reload --port 8000   (from the repo root)
Uvicorn binds to 127.0.0.1 by default; pass --host explicitly to expose it.
"""
from __future__ import annotations

import json
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Literal, Union

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from chat.agent import respond

app = FastAPI(title="OBR macro model chat")
HERE = Path(__file__).resolve().parent

# ---- request limits (proportionate for a local demo server) ----------------
MAX_MESSAGES = 40         # per conversation sent to the API
MAX_TEXT_CHARS = 8_000    # per plain-text message
MAX_BLOCK_CHARS = 50_000  # per serialized tool-use/tool-result turn (server-generated,
                          # round-tripped by the UI, so allowed to be larger)

RATE_LIMIT = 20           # requests ...
RATE_WINDOW_S = 60        # ... per this many seconds, per client IP
MAX_TRACKED_IPS = 10_000  # bound on the rate-limit dict so it can't grow forever
_hits: dict[str, deque] = defaultdict(deque)

# Content-block types the API accepts per role. The UI round-trips server
# responses verbatim, so assistant turns can carry tool_use/thinking blocks;
# user turns can only carry text and tool_result blocks. We can't cheaply
# verify a tool_use block is one the server itself produced (that would need
# per-session state), so instead the shapes and sizes are validated strictly.
ALLOWED_BLOCK_TYPES = {
    "user": {"text", "tool_result"},
    "assistant": {"text", "thinking", "redacted_thinking", "tool_use"},
}


def _check_rate_limit(ip: str) -> None:
    """Simple in-process sliding-window rate limiter (bounded memory)."""
    now = time.monotonic()
    window = _hits[ip]
    while window and now - window[0] > RATE_WINDOW_S:
        window.popleft()
    if len(window) >= RATE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail=f"Too many requests — limit is {RATE_LIMIT} per minute. "
                   "Please wait a moment and try again.",
        )
    window.append(now)
    # Evict idle IPs so _hits stays bounded.
    if len(_hits) > MAX_TRACKED_IPS:
        for k in [k for k, w in _hits.items() if not w or now - w[-1] > RATE_WINDOW_S]:
            _hits.pop(k, None)


def _validate_blocks(role: str, content: list) -> None:
    """Validate a list-of-content-blocks message the client round-tripped."""
    allowed = ALLOWED_BLOCK_TYPES[role]
    for block in content:
        if not isinstance(block, dict):
            raise HTTPException(status_code=422, detail="Malformed content block.")
        btype = block.get("type")
        if btype not in allowed:
            raise HTTPException(
                status_code=422,
                detail=f"Content block type '{btype}' is not allowed in a "
                       f"{role} message.",
            )
        if btype == "text" and len(str(block.get("text", ""))) > MAX_TEXT_CHARS:
            raise HTTPException(
                status_code=413,
                detail=f"Message too long — the limit is {MAX_TEXT_CHARS} characters.",
            )
        if btype == "tool_result" and not isinstance(block.get("tool_use_id"), str):
            raise HTTPException(status_code=422, detail="Malformed tool_result block.")
    if len(json.dumps(content, default=str)) > MAX_BLOCK_CHARS:
        raise HTTPException(
            status_code=413,
            detail="Conversation history too large — please start a new chat.",
        )


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    # str for typed text; list of content blocks for tool-use turns the UI round-trips
    content: Union[str, list]


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(..., min_length=1, max_length=MAX_MESSAGES)


@app.post("/api/chat")
def chat(req: ChatRequest, request: Request):
    _check_rate_limit(request.client.host if request.client else "unknown")

    msgs = []
    for m in req.messages:
        if isinstance(m.content, str):
            if len(m.content) > MAX_TEXT_CHARS:
                raise HTTPException(
                    status_code=413,
                    detail=f"Message too long — the limit is {MAX_TEXT_CHARS} characters.",
                )
        else:
            _validate_blocks(m.role, m.content)
        msgs.append({"role": m.role, "content": m.content})

    reply, messages = respond(msgs)
    return {"reply": reply, "messages": messages}


@app.get("/")
def index():
    return FileResponse(HERE / "static" / "index.html")
