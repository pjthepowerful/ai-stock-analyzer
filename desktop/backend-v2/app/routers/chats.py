"""
Saved chats — the same synced_chats table and last-write-wins protocol the
original app uses, so a chat started in either app shows up in the other.

Shape: {"chats": [{id, title, created, messages: [{role, content, time?}]}],
        "updated_at": <ms epoch>}
"""
from typing import Optional

from fastapi import APIRouter, Header
from pydantic import BaseModel

from ..bridge import auth, engine
from ..deps import current_user_required

router = APIRouter(tags=["chats"])


@router.get("/api/chats/sync")
def get_chats(authorization: Optional[str] = Header(None)):
    user = current_user_required(authorization)
    data = auth.get_synced_chats(user["id"])
    return {"ok": True, "chats": data["chats"], "updated_at": data["updated_at"]}


class SyncRequest(BaseModel):
    chats: list[dict]
    updated_at: int


@router.put("/api/chats/sync")
def put_chats(req: SyncRequest, authorization: Optional[str] = Header(None)):
    user = current_user_required(authorization)
    if auth.save_synced_chats(user["id"], req.chats, req.updated_at):
        return {"ok": True, "applied": True, "updated_at": req.updated_at}
    # The server copy is the same age or newer (another device wrote in
    # between) — hand it back so the client adopts it instead of clobbering.
    latest = auth.get_synced_chats(user["id"])
    return {"ok": True, "applied": False, "chats": latest["chats"], "updated_at": latest["updated_at"]}


class TitleRequest(BaseModel):
    message: str


_TITLE_PROMPT = (
    "You are a title generator. Output ONLY a 2-5 word title. Nothing else. No sentences. "
    "No punctuation. No quotes. No explanation. Just the title words.\n\nExamples:\n"
    "Input: 'market regime' → Market Regime Check\nInput: 'top gainers' → Top Gainers Today\n"
    "Input: 'analyze AAPL' → AAPL Analysis\nInput: 'What should I buy?' → Trade Ideas\n"
    "Input: 'How did we do today?' → Daily Recap"
)


@router.post("/api/chat/title")
def chat_title(req: TitleRequest, authorization: Optional[str] = Header(None)):
    # Auth-gated: it spends Groq quota.
    current_user_required(authorization)
    msg = req.message.strip()
    fallback = msg if len(msg) <= 30 else msg[:28].rstrip() + "…"
    if not engine._llm_key() or not msg:
        return {"ok": True, "title": fallback or "New chat"}
    try:
        resp = engine.Groq().chat.completions.create(
            model=engine.GROQ_MODEL_FAST,
            messages=[
                {"role": "system", "content": _TITLE_PROMPT},
                {"role": "user", "content": msg[:100]},
            ],
            max_tokens=16,
            temperature=0.1,
        )
        title = (resp.choices[0].message.content or "").strip()
        title = title.split("\n")[0].strip().strip("\"'").rstrip(".")
        if title and len(title.split()) <= 8 and len(title) <= 40:
            return {"ok": True, "title": title}
    except Exception:
        pass
    return {"ok": True, "title": fallback}
