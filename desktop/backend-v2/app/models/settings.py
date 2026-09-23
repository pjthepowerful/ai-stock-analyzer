from typing import Optional

from pydantic import BaseModel


class SettingsRequest(BaseModel):
    # Secrets: blank means "keep what's stored".
    alpaca_key: str = ""
    alpaca_secret: str = ""
    groq_key: str = ""
    polygon_key: str = ""
    # None means "not sent — keep what's stored".
    display_name: Optional[str] = None
    settings: Optional[dict] = None
