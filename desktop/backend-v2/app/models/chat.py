from typing import Optional

from pydantic import BaseModel


class ChatHistoryItem(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: Optional[list[ChatHistoryItem]] = None
    model: Optional[str] = None  # "smart" | "fast" — the composer's model picker
    image: Optional[str] = None  # data:image/...;base64,... — a chart or screen to read


class ChatResponse(BaseModel):
    ok: bool = True
    type: str = "chat"           # chat | trade | limit | scan_started | ...
    message: str = ""
    tickers: Optional[list] = None
    autopilot: Optional[bool] = None
    limit_reached: bool = False
