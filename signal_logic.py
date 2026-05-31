"""Pure, dependency-free decision logic for analysis signal cards.

Kept separate from trading.py (which imports yfinance/groq/alpaca) so the
framing logic can be unit-tested in isolation. No third-party imports here.
"""

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
