from pydantic import BaseModel


class SettingsRequest(BaseModel):
    alpaca_key: str = ""
    alpaca_secret: str = ""
    groq_key: str = ""
    polygon_key: str = ""
    display_name: str = ""
    settings: dict = {}
