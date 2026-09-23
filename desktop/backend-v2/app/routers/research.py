"""
Per-ticker research for the Analyze screen: the earnings forecast, earnings
snapshot, and the research row (news, post-earnings drift, SEC fundamentals).
Thin wrappers over the repo-root forecast.py / earnings.py / research.py,
which are unchanged. Sign-in required, as in the original — these fan out to
several paid/rate-limited data sources per call.
"""
from typing import Optional

from fastapi import APIRouter, Header, HTTPException

from ..bridge import engine
from ..deps import current_user_required

router = APIRouter(prefix="/api", tags=["research"])


def _clean(ticker: str) -> str:
    t = ticker.strip().upper()
    if not t or len(t) > 10 or not t.replace(".", "").replace("-", "").isalnum():
        raise HTTPException(422, "Not a valid ticker")
    return t


@router.get("/forecast/{ticker}")
def forecast(ticker: str, authorization: Optional[str] = Header(None)):
    current_user_required(authorization)
    import forecast as fc
    return {"ok": True, **fc.forecast(_clean(ticker))}


@router.get("/earnings/{ticker}")
def earnings(ticker: str, authorization: Optional[str] = Header(None)):
    current_user_required(authorization)
    import earnings as earn
    return {"ok": True, **earn.snapshot(_clean(ticker))}


@router.get("/research/{ticker}")
def research(ticker: str, authorization: Optional[str] = Header(None)):
    current_user_required(authorization)
    import research as res

    t = _clean(ticker)
    acct = engine.alpaca_account() or {}
    held = {p["ticker"]: p for p in (engine.alpaca_positions() or []) if p.get("ticker")}
    row = res.evaluate(t, price=(held.get(t) or {}).get("current_price"), equity=acct.get("equity"))

    # research.cik_for() reports "not an SEC filer" whenever the SEC ticker map
    # is empty — including when the SEC refused the download because
    # SEC_USER_AGENT has no contact address. Say which one it actually is.
    fund = row.get("fundamentals") or {}
    if not fund.get("available") and not getattr(res, "_CIK_CACHE", None):
        why = "SEC lookup blocked — set SEC_USER_AGENT in the backend .env to include a contact email"
        fund["reason"] = why
        row["fundamental_notes"] = [why]
    return {"ok": True, **row}
