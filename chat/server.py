"""FastAPI backend for the OBR macro-model chat.

POST /api/chat  { "messages": [{role, content}, ...] }  ->  { "reply": "...", "messages": [...] }
GET  /          serves the minimal chat UI.

Run:  uv run uvicorn chat.server:app --reload --port 8000   (from the repo root)
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel

from chat.agent import respond

app = FastAPI(title="OBR macro model chat")
HERE = Path(__file__).resolve().parent


class ChatRequest(BaseModel):
    messages: list  # [{role: "user"|"assistant", content: str | blocks}, ...]


@app.post("/api/chat")
def chat(req: ChatRequest):
    reply, messages = respond(req.messages)
    return {"reply": reply, "messages": messages}


@app.get("/")
def index():
    return FileResponse(HERE / "static" / "index.html")
