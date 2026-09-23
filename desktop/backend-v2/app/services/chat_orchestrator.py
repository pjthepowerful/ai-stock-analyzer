"""
Chat response orchestration — ported faithfully from the original backend's
`/api/chat` handler (desktop/backend/server.py). This is genuinely tuned
behavior (Plus-gating for deep analysis, live news/web-search injection,
AI price-hallucination correction, ticker extraction for chart mentions) —
not boilerplate — so it's preserved as-is rather than reimagined. Only the
HTTP-layer plumbing around it (routing, request typing, status codes) is new.

Every `engine.*` call below is the SAME function the original backend calls.
"""
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional

from ..bridge import auth, engine

KNOWN_TICKERS = set([
    "AAPL","MSFT","NVDA","GOOGL","AMZN","META","TSLA","AMD","NFLX","SPY","QQQ","JPM","V","BA","HD",
    "CRM","AVGO","LLY","COST","WMT","DIS","XOM","CVX","GS","BAC","INTC","PYPL","COIN","PLTR","UBER",
    "SHOP","SOFI","MARA","CELH","NIO","RIVN","F","GM","KO","PEP","NKE","ADBE","CSCO","IBM","QCOM",
    "TXN","MU","MA","SQ","HOOD","MS","C","WFC","UNH","JNJ","MRK","PFE","ABBV","TGT","SBUX","MCD",
    "CMG","DASH","BKNG","ABNB","LULU","SLB","COP","CAT","GE","HON","DE","UPS","FDX","LMT","SNAP",
    "RBLX","DKNG","MSTR","RIOT","NET","DDOG","SNOW","PANW","CRWD","TTD","SMCI","ARM","IONQ","TMDX",
    "DUOL","FCEL","ONON","HIMS","CAVA","TOST","ELF","LCID","DELL","ROKU","NOW","INTU","PINS","CVNA",
    "MRNA","BRK-B","RKLB","AXON",
])

# Per-process fallback history cache, mirroring the original — only used when
# the frontend doesn't send its own per-chat history array.
_user_sessions: dict[int, list[dict]] = {}


def get_user_history(user_id: int) -> list:
    if user_id not in _user_sessions:
        _user_sessions[user_id] = auth.get_chat_history(user_id, limit=20) or []
    return _user_sessions[user_id]


def trim_history(user_id: int, max_len: int = 30):
    if user_id in _user_sessions and len(_user_sessions[user_id]) > max_len:
        _user_sessions[user_id] = _user_sessions[user_id][-max_len:]


def friendly_error(err: str) -> str:
    e = (err or "").lower()
    if "no data" in e or "delisted" in e or "symbol may be" in e:
        return ("I couldn't pull data for that ticker. It might be misspelled, "
                 "newly listed, delisted, or not a US-listed stock. Double-check the symbol and try again.")
    if "rate" in e or "too many" in e:
        return "The market data source is busy right now (rate-limited). Give it a few seconds and try again."
    if "alpaca" in e or "connect" in e or "credential" in e or "unauthorized" in e:
        return "I couldn't reach your brokerage account. Check your Alpaca API keys in Settings → Connections."
    if "buying power" in e or "insufficient" in e:
        return "That order needs more buying power than the account has. Try a smaller share count."
    if "timeout" in e or "timed out" in e:
        return "That took too long and timed out. The data source may be slow right now — please try again."
    return f"Something went wrong: {err}"


def _ai_unavailable(raw: str) -> str:
    e = raw.lower()
    if "invalid api key" in e or "invalid_api_key" in e or "401" in e:
        return ("Paula's language model isn't reachable right now — the server's AI key was "
                "rejected. Stock data and charts still work in Analyze; chat answers will be "
                "back once the key is fixed.")
    if "rate" in e or "429" in e:
        return "Paula's AI is rate-limited at the moment. Give it a minute and ask again."
    return "Paula couldn't generate an answer just now. Try again in a moment."


def taste_analysis(result: dict) -> dict:
    """Free/guest users get the headline numbers from a deep analysis, not the
    full breakdown (entry/stop/target, chart, reasoning) — that's Plus."""
    data = result.get("data") or {}
    ticker = (result.get("ticker") or data.get("ticker") or "").upper()
    price = data.get("price")
    signal = data.get("action") or data.get("signal") or (data.get("trade") or {}).get("side")
    score = data.get("score")
    bits = [f"**{ticker}** is at ${float(price):,.2f}" if price is not None else f"**{ticker}**"]
    if signal:
        bits.append(f"current signal: **{signal}**")
    if score is not None:
        bits.append(f"score **{score}/100**")
    teaser = " · ".join(bits)
    msg = (f"{teaser}\n\nThat's the quick read. The full breakdown — setup scores, "
           f"entry/stop/target levels, the chart, and Paula's reasoning — is part of Paula Plus.")
    return {"ok": True, "type": "taste", "taste": True, "plus_upsell": True, "ticker": ticker, "message": msg}


def _clean_source_url(url: str) -> str:
    if not url or not isinstance(url, str):
        return ""
    u = url.strip()
    if not u.lower().startswith(("http://", "https://")):
        return ""
    if re.search(r"/goto\?|/url\?|[?&]url=CAES|google\.[^/]+/url", u):
        return ""
    return u


def _source_domain(url: str) -> str:
    m = re.search(r"https?://(?:www\.)?([^/]+)", url or "")
    return m.group(1) if m else ""


def _fmt_web_result(w: dict) -> str:
    base = f"- {w.get('title', '')}: {w.get('content', '')}"
    u = _clean_source_url(w.get("url", ""))
    if u:
        return base + f" (source: {_source_domain(u)} — {u})"
    dom = _source_domain(w.get("url", ""))
    return base + (f" (source: {dom})" if dom else "")


def _fix_prices(text: str, real_price: float, min_diff: float = 0.20) -> str:
    def _repl(match):
        try:
            mentioned = float(match.group(1).replace(",", ""))
            if mentioned > 1 and abs(mentioned - real_price) / real_price > min_diff:
                return f"${real_price:.2f}"
        except Exception:
            pass
        return match.group(0)
    return re.sub(r"\$(\d{1,5}(?:,\d{3})*\.?\d{0,2})", _repl, text)


async def build_response(
    loop,
    user_msg: str,
    intent: dict,
    result: Optional[dict],
    chat_history: list,
    user: Optional[dict],
    is_plus: bool,
) -> dict:
    """Turns an engine.execute() result into the final chat reply, exactly
    matching the original backend's per-intent-type behavior."""
    resp = ""

    if result and result.get("ok"):
        rtype = result.get("type", "")
        resp = result.get("msg", "")

        if rtype == "confirm_trade":
            return {"ok": True, "type": "confirm_trade", "trade": result.get("trade"), "autopilot": False}

        if rtype == "analysis":
            is_deep = bool(result.get("ticker")) and isinstance(result.get("data"), dict)
            if is_deep and not is_plus:
                return taste_analysis(result)
            if not resp:
                amsg = user_msg
                aml = user_msg.lower()
                if any(w in aml for w in ["news", "latest", "happening", "headline", "why is", "why did", "catalyst", "recent", "what's going on", "whats going on", "update"]):
                    try:
                        atk = result.get("ticker", "")
                        anews = engine.fetch_news(atk, limit=5) if atk else None
                        if anews:
                            al = "\n".join(f"- ({n['date']}) {n['title']} — {n['publisher']}: {n['summary']}" for n in anews)
                            amsg = user_msg + f"\n\n[LIVE NEWS (use these recent headlines, cite dates):\n{al}\n]"
                    except Exception:
                        pass
                ai_text = await loop.run_in_executor(None, engine.ai_response, amsg, result.get("data"), chat_history, "US")
                data = result.get("data", {})
                ticker = result.get("ticker", "")
                resp = ai_text
                price = data.get("price", 0) if data else 0
                if price and ticker:
                    resp = _fix_prices(resp, price)

        elif rtype == "position_size":
            resp = await loop.run_in_executor(None, engine.ai_response, user_msg, {"position_size": result.get("data", {})}, chat_history, "US")

        elif rtype == "compare":
            resp = await loop.run_in_executor(None, engine.ai_response, user_msg, result.get("data", {}), chat_history, "US")

        elif rtype == "list":
            resp = await loop.run_in_executor(
                None, engine.ai_response, user_msg,
                {"list_title": result.get("title", ""), "stocks": result.get("data", [])},
                chat_history, "US",
            )

        elif not resp:
            resp = await _generic_reply(loop, user_msg, result, chat_history)

    elif result and result.get("error"):
        resp = friendly_error(result.get("error", ""))
    else:
        resp = await _fallback_reply(loop, user_msg, result, chat_history)

    # engine.ai_response() reports LLM failures as a plain "AI error: <raw
    # provider JSON>" string. Don't show that to people — and don't save it
    # into their chat history as if Paula had said it.
    ai_failed = isinstance(resp, str) and resp.lstrip().startswith("AI error:")
    if ai_failed:
        print(f"[chat] LLM failure: {resp[:200]}", flush=True)
        resp = _ai_unavailable(resp)

    # Price-hallucination guard on the final text, mirroring the original.
    if resp and result:
        rd = result.get("data") or {}
        real_price = rd.get("price", 0) if isinstance(rd, dict) else 0
        if real_price and real_price > 0:
            resp = _fix_prices(resp, real_price, min_diff=0.25)

    if not ai_failed:
        chat_history.append({"role": "assistant", "content": resp})
    if user and not ai_failed:
        trim_history(user["id"])
        try:
            auth.save_chat(user["id"], "assistant", resp, msg_type=(result or {}).get("type", "chat"), ticker=(result or {}).get("ticker"))
        except Exception:
            pass

    response = {
        "ok": True,
        "message": resp,
        "type": (result or {}).get("type", "chat"),
        "ticker": (result or {}).get("ticker"),
        "tickers": [],
        "trade_signal": (result or {}).get("trade_signal"),
        "signal_data": (result or {}).get("signal_data"),
        "table": (result or {}).get("data") if result and result.get("type") == "list" else None,
        "autopilot": False,
    }

    if result:
        rtype = result.get("type", "")
        if result.get("tickers"):
            response["tickers"] = result["tickers"][:6]
        elif rtype == "list" and result.get("data"):
            response["tickers"] = [r.get("Ticker", r.get("ticker", "")) for r in result["data"] if r.get("Ticker") or r.get("ticker")][:6]
        elif result.get("ticker"):
            response["tickers"] = [result["ticker"]]

    if resp and not response["tickers"]:
        found = re.findall(r"\b([A-Z]{1,5})\b", resp)
        known = set()
        try:
            known = set(engine.FULL_UNIVERSE)
        except Exception:
            pass
        if known:
            response["tickers"] = [t for t in dict.fromkeys(found) if t in known][:6]

    return response


async def _generic_reply(loop, user_msg: str, result: Optional[dict], chat_history: list) -> str:
    """Extract every ticker the CURRENT message names and price them, or fall
    through to a plain conversational answer — same logic as the original."""
    chat_data = {}
    try:
        if not (result and result.get("private_company")):
            valid = engine.find_all_tickers(user_msg, limit=5)
            if valid:
                multi, missing = {}, []
                for vt in valid:
                    try:
                        vd = engine.fetch_full(vt)
                        if vd and vd.get("price"):
                            multi[vt] = {"price": vd["price"], "change_pct": vd.get("change_pct", 0), "name": vd.get("name", vt)}
                        else:
                            missing.append(vt)
                    except Exception:
                        missing.append(vt)
                if multi:
                    note = "Use ONLY these exact prices"
                    if missing:
                        note += ". Live data could NOT be retrieved for: " + ", ".join(missing) + " — say so explicitly rather than guessing."
                    chat_data = {"stocks": multi, "note": note}
                elif len(valid) == 1:
                    chat_data = engine.fetch_full(valid[0]) or {}
    except Exception:
        pass

    umsg = user_msg
    if result and result.get("private_company"):
        umsg += "\n\n[Note: this is about a privately-held / pre-IPO company with no public ticker. Answer conversationally — explain its private status, any IPO/funding context, and how someone could get exposure. Do NOT say you lack data or look for a stock price.]"

    ml = user_msg.lower()
    wants_news = any(w in ml for w in ["news", "latest", "happening", "headline", "earnings", "report", "announced", "update on", "what's going on", "whats going on", "why is", "why did", "catalyst", "recent", "today"])
    if wants_news and not (result and result.get("private_company")):
        try:
            nt = next((w for w in re.findall(r"\b([A-Z]{1,5})\b", user_msg) if w in KNOWN_TICKERS), None)
            news = engine.fetch_news(nt, limit=5)
            if news:
                lines = "\n".join(f"- ({n['date']}) {n['title']} — {n['publisher']}: {n['summary']}" for n in news)
                umsg += f"\n\n[LIVE NEWS (use these recent headlines, cite the dates):\n{lines}\n]"
        except Exception:
            pass

    return await loop.run_in_executor(None, engine.ai_response, umsg, chat_data if chat_data else None, chat_history, "US")


async def _fallback_reply(loop, user_msg: str, result: Optional[dict], chat_history: list) -> str:
    """Plain conversational answer when nothing structured matched — same
    web-search/news-injection heuristics as the original."""
    fall_data = None
    fmsg = user_msg
    is_private = bool(result and result.get("private_company"))
    fl = user_msg.lower()

    if is_private:
        fmsg += "\n\n[Note: this is about a privately-held / pre-IPO company with no public ticker. Answer conversationally, and do NOT analyze any unrelated ticker.]"
        try:
            ws = engine.web_search(user_msg, max_results=5)
            if ws:
                wl = "\n".join(_fmt_web_result(w) for w in ws)
                fmsg += f"\n\n[LIVE WEB SEARCH — use this current info. Cite the publisher name as a markdown link only if a real http(s) URL is given:\n{wl}\n]"
        except Exception:
            pass
    else:
        try:
            cur = [t for t in re.findall(r"\b([A-Z]{1,5})\b", user_msg) if t in KNOWN_TICKERS]
            if cur:
                fall_data = engine.fetch_full(cur[0])
            is_news = any(w in fl for w in ["news", "latest", "happening", "headline", "earnings", "why is", "why did", "catalyst", "recent", "update"])
            wants_search = any(p in fl for p in ["look it up", "look up", "search for", "search the web", "google", "can you find", "find out", "look into", "check online", "search online", "what's the latest on", "whats the latest on"])
            if is_news:
                ntk = cur[0] if cur else None
                fnews = engine.fetch_news(ntk, limit=5)
                if fnews:
                    fl2 = "\n".join(f"- ({n['date']}) {n['title']} — {n['publisher']}: {n['summary']}" for n in fnews)
                    fmsg += f"\n\n[LIVE NEWS (use these recent headlines, cite dates):\n{fl2}\n]"
            if wants_search or (not cur and is_news):
                sq = user_msg
                if "earnings" in fl and any(w in fl for w in ["today", "tonight", "this week", "reporting", "calendar", "after hours", "afterhours", "after-hours", "tomorrow"]):
                    dstr = datetime.now(ZoneInfo("US/Eastern")).strftime("%B %d %Y")
                    sq = f"stocks reporting earnings {dstr} calendar"
                ws = engine.web_search(sq, max_results=6)
                if ws:
                    wl = "\n".join(_fmt_web_result(w) for w in ws)
                    fmsg += f"\n\n[LIVE WEB SEARCH — use this current info. Cite the publisher name as a markdown link only if a real http(s) URL is given:\n{wl}\n]"
        except Exception:
            pass

    return await loop.run_in_executor(None, engine.ai_response, fmsg, fall_data, chat_history, "US")
