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
_hits: dict[str, deque] = defaultdict(deque)


def _check_rate_limit(ip: str) -> None:
    """Simple in-process sliding-window rate limiter."""
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
        elif len(json.dumps(m.content, default=str)) > MAX_BLOCK_CHARS:
            raise HTTPException(
                status_code=413,
                detail="Conversation history too large — please start a new chat.",
            )
        msgs.append({"role": m.role, "content": m.content})

    reply, messages = respond(msgs)
    return {"reply": reply, "messages": messages}


@app.get("/")
def index():
    return FileResponse(HERE / "static" / "index.html")
