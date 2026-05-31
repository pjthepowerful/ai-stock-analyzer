"""Pure, dependency-free decision logic for analysis signal cards.

Kept separate from trading.py (which imports yfinance/groq/alpaca) so the
framing logic can be unit-tested in isolation. No third-party imports here.
"""

import re


# Phrases that indicate the user is asking about EXITING a position they hold,
# rather than asking to open a new short.
EXIT_WORDS = (
    "sell", "exit", "get out", "dump", "unload", "take profit",
    "should i sell", "close my", "close position", "i own",
    "i bought", "i hold", "i'm holding", "im holding", "my position",
)


def classify_analysis_side(action: str, message: str, holds_long: bool) -> str:
    """Map a trade-signal action to a card side for the *analysis* view.

    A low score must never be presented as a SHORT entry setup — the app is
    long-biased, and a user asking "should I sell my AAPL?" holds a LONG.

    Returns one of:
      - "LONG"    : bullish setup (BUY / STRONG_BUY)
      - "EXIT"    : bearish AND the user holds it (or is asking to sell) — close the long
      - "AVOID"   : bearish AND the user doesn't hold it — stay flat, no short entry
      - "NEUTRAL" : everything else (HOLD / NO_DATA)
    """
    msg = (message or "").lower()
    asking_to_exit = any(w in msg for w in EXIT_WORDS)
    is_bearish = action in ("SELL", "STRONG_SELL")
    if is_bearish and (asking_to_exit or holds_long):
        return "EXIT"
    if is_bearish:
        return "AVOID"
    if action in ("BUY", "STRONG_BUY"):
        return "LONG"
    return "NEUTRAL"


def compute_price_math(message: str, current_price: float) -> dict | None:
    """Pre-compute the arithmetic for common 'what if price hits X' questions.

    The LLM is bad at arithmetic, so instead of letting it compute (and get
    things like "a gain of $211 from $211"), we detect the question here and
    return exact numbers it can simply quote. Returns None if no price-move
    question is detected.

    Handles:
      - "if NVDA hits 230 what's that from here?"  -> move from current to 230
      - "what's my gain from 142 to 158?"          -> move between two prices
      - "100 shares of NVDA"                        -> position value
    """
    if not current_price or current_price <= 0:
        current_price = current_price or 0.0
    msg = (message or "").lower()
    nums = [float(n.replace(",", "")) for n in re.findall(r"\$?([\d,]+(?:\.\d+)?)", msg)]

    # "X to Y" explicit two-price move (e.g. "from 142 to 158")
    m_range = re.search(r"(?:from\s+)?\$?([\d,]+(?:\.\d+)?)\s+to\s+\$?([\d,]+(?:\.\d+)?)", msg)
    if m_range:
        a = float(m_range.group(1).replace(",", ""))
        b = float(m_range.group(2).replace(",", ""))
        if a > 0:
            pct = (b - a) / a * 100
            return {
                "kind": "move_between",
                "from": round(a, 2), "to": round(b, 2),
                "dollar_change": round(b - a, 2),
                "pct_change": round(pct, 2),
                "phrasing": f"From ${a:,.2f} to ${b:,.2f} is {'+' if b>=a else ''}{pct:.2f}% (${b-a:+,.2f} per share).",
            }

    # Position value: "<qty> shares" + a price available
    m_shares = re.search(r"(\d[\d,]*)\s*shares?", msg)
    if m_shares and current_price > 0:
        qty = int(m_shares.group(1).replace(",", ""))
        value = qty * current_price
        return {
            "kind": "position_value",
            "qty": qty, "price": round(current_price, 2),
            "value": round(value, 2),
            "phrasing": f"{qty:,} shares at ${current_price:,.2f} would be worth ${value:,.2f}.",
        }

    # "hits/reaches/goes to/at X" target from current price
    m_target = re.search(r"(?:hits?|reach(?:es)?|goes? to|gets? to|at|to)\s+\$?([\d,]+(?:\.\d+)?)", msg)
    if m_target and current_price > 0 and ("hit" in msg or "reach" in msg or "goes to" in msg or "get to" in msg or "what's that" in msg or "from here" in msg):
        tgt = float(m_target.group(1).replace(",", ""))
        if tgt > 0:
            pct = (tgt - current_price) / current_price * 100
            return {
                "kind": "move_to_target",
                "from": round(current_price, 2), "to": round(tgt, 2),
                "dollar_change": round(tgt - current_price, 2),
                "pct_change": round(pct, 2),
                "phrasing": f"From ${current_price:,.2f} to ${tgt:,.2f} is {'+' if tgt>=current_price else ''}{pct:.2f}% (${tgt-current_price:+,.2f} per share).",
            }

    return None
