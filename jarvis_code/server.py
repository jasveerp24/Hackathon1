"""
server.py -- exposes the Python orchestrator over HTTP so the React Native app can call it.

Run:  pip install fastapi uvicorn anthropic
      uvicorn server:app --host 0.0.0.0 --port 8000 --reload

--host 0.0.0.0 matters: it lets your PHONE (same Wi-Fi) reach your laptop.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from orchestrator import Orchestrator  # the file from before, unchanged
import agents  # noqa: F401  (importing registers your agents with the orchestrator)

app = FastAPI(title="JARVIS backend")

# Allow the app to call us (needed for web/Expo-web; harmless for native)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# One Orchestrator PER SESSION: each instance holds that user's history and
# their pending "are you sure?" step. A single shared one would mix up users.
SESSIONS: dict[str, Orchestrator] = {}


class ChatIn(BaseModel):
    session_id: str   # generated once by the app, e.g. a random id
    text: str         # what speech-to-text heard


class ChatOut(BaseModel):
    reply: str
    awaiting_confirmation: bool  # lets the app show Yes/No buttons instead of waiting for speech


@app.post("/chat", response_model=ChatOut)
def chat(body: ChatIn) -> ChatOut:
    jarvis = SESSIONS.setdefault(body.session_id, Orchestrator())
    reply = jarvis.handle(body.text)
    return ChatOut(reply=reply, awaiting_confirmation=jarvis.pending is not None)


@app.get("/health")
def health() -> dict:
    return {"ok": True}
