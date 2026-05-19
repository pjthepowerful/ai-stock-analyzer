"""
Paula Backtest Engine — run the 21-factor signal engine on historical data.
"""
import json
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import yfinance as yf
import warnings


def run_backtest(tickers: list = None, days: int = 90, initial_capital: float = 26000,
                 min_score: int = 75, max_positions: int = 2, stop_pct: float = 0.01,
                 target_mult: float = 2.5) -> dict:
    """
    Backtest the signal engine on historical daily data.
    Returns equity curve, trades, and stats.
    """
    if not tickers:
        tickers = ["AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN", "AMD", "TSLA",
                    "JPM", "V", "UNH", "HD", "CRM", "NFLX", "AVGO", "ORCL",
                    "BAC", "GS", "CAT", "LLY", "MRK", "XOM", "CVX", "PG"]

    et = ZoneInfo("US/Eastern")
    end = datetime.now(et)
    start = end - timedelta(days=days + 30)  # extra for indicator warmup

    # Download all data
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        data = yf.download(tickers, start=start.strftime("%Y-%m-%d"),
                          end=end.strftime("%Y-%m-%d"), group_by="ticker",
                          progress=False, threads=False)

    if data is None or data.empty:
        return {"ok": False, "error": "No data downloaded"}

    # Build per-ticker DataFrames
    ticker_data = {}
    for t in tickers:
        try:
            if t in data.columns.get_level_values(0):
                df = data[t].dropna()
                if len(df) >= 30:
                    ticker_data[t] = df
        except Exception:
            pass

    if not ticker_data:
        return {"ok": False, "error": "No valid ticker data"}

    # Get common trading dates (last N days)
    all_dates = set()
    for df in ticker_data.values():
        all_dates.update(str(d)[:10] for d in df.index)
    dates = sorted(all_dates)[-days:]

    # Simulation
    capital = initial_capital
    equity_curve = []
    trades = []
    positions = {}  # ticker -> {entry, stop, target, qty, date}
    daily_pnl = []
    wins = 0
    losses = 0

    for date in dates:
        day_pnl = 0

        # Check exits first
        closed = []
        for ticker, pos in list(positions.items()):
            try:
                df = ticker_data[ticker]
                row = df.loc[df.index.astype(str).str[:10] == date]
                if row.empty:
                    continue
                price = float(row["Close"].iloc[0])
                low = float(row["Low"].iloc[0])
                high = float(row["High"].iloc[0])

                # Stop loss hit
                if low <= pos["stop"]:
                    pnl = (pos["stop"] - pos["entry"]) * pos["qty"]
                    capital += pos["entry"] * pos["qty"] + pnl
                    day_pnl += pnl
                    trades.append({
                        "ticker": ticker, "entry": pos["entry"], "exit": pos["stop"],
                        "pnl": round(pnl, 2), "entry_date": pos["date"], "exit_date": date,
                        "result": "stop", "hold_days": dates.index(date) - dates.index(pos["date"]) if pos["date"] in dates else 1
                    })
                    if pnl >= 0: wins += 1
                    else: losses += 1
                    closed.append(ticker)
                    continue

                # Target hit
                if high >= pos["target"]:
                    pnl = (pos["target"] - pos["entry"]) * pos["qty"]
                    capital += pos["entry"] * pos["qty"] + pnl
                    day_pnl += pnl
                    trades.append({
                        "ticker": ticker, "entry": pos["entry"], "exit": pos["target"],
                        "pnl": round(pnl, 2), "entry_date": pos["date"], "exit_date": date,
                        "result": "target", "hold_days": dates.index(date) - dates.index(pos["date"]) if pos["date"] in dates else 1
                    })
                    wins += 1
                    closed.append(ticker)
                    continue
            except Exception:
                continue

        for t in closed:
            del positions[t]

        # Score and enter new positions
        if len(positions) < max_positions:
            scored = []
            for ticker, df in ticker_data.items():
                if ticker in positions:
                    continue
                try:
                    row = df.loc[df.index.astype(str).str[:10] == date]
                    if row.empty:
                        continue
                    idx = df.index.get_loc(row.index[0])
                    if idx < 20:
                        continue

                    close = float(row["Close"].iloc[0])
                    high = float(row["High"].iloc[0])
                    low = float(row["Low"].iloc[0])
                    vol = float(row["Volume"].iloc[0])

                    # Simple scoring
                    score = 50
                    closes = df["Close"].iloc[max(0, idx-20):idx+1].values

                    # RSI
                    gains = [max(0, closes[i] - closes[i-1]) for i in range(1, len(closes))]
                    losss = [max(0, closes[i-1] - closes[i]) for i in range(1, len(closes))]
                    avg_gain = sum(gains[-14:]) / 14 if len(gains) >= 14 else 0
                    avg_loss = sum(losss[-14:]) / 14 if len(losss) >= 14 else 0
                    rsi = 100 - 100 / (1 + avg_gain / max(avg_loss, 0.001))

                    if 30 < rsi < 70: score += 10
                    elif rsi < 30: score += 15  # oversold bounce
                    elif rsi > 80: score -= 10

                    # Trend (above 20-day SMA)
                    sma20 = sum(closes[-20:]) / 20
                    if close > sma20: score += 10
                    else: score -= 5

                    # Volume spike
                    avg_vol = sum(df["Volume"].iloc[max(0, idx-20):idx].values) / 20
                    if vol > avg_vol * 1.5: score += 8

                    # Momentum (5-day return)
                    if idx >= 5:
                        ret5 = (close - float(df["Close"].iloc[idx-5])) / float(df["Close"].iloc[idx-5])
                        if 0.01 < ret5 < 0.08: score += 10
                        elif ret5 > 0.08: score -= 5  # overextended

                    # Volatility (ATR proxy)
                    ranges = [float(df["High"].iloc[i]) - float(df["Low"].iloc[i]) for i in range(max(0, idx-14), idx+1)]
                    atr = sum(ranges) / len(ranges) if ranges else 1

                    scored.append({"ticker": ticker, "score": score, "price": close, "atr": atr})
                except Exception:
                    continue

            # Enter top scoring stocks
            scored.sort(key=lambda x: x["score"], reverse=True)
            for s in scored:
                if len(positions) >= max_positions:
                    break
                if s["score"] < min_score:
                    continue

                price = s["price"]
                stop = price * (1 - stop_pct)
                target = price + (price - stop) * target_mult
                risk_per_share = price - stop
                if risk_per_share <= 0:
                    continue
                qty = min(int(capital * 0.05 / risk_per_share), int(capital * 0.1 / price))
                if qty <= 0:
                    continue

                cost = price * qty
                if cost > capital:
                    continue

                capital -= cost
                positions[s["ticker"]] = {
                    "entry": price, "stop": round(stop, 2), "target": round(target, 2),
                    "qty": qty, "date": date
                }
                trades.append({
                    "ticker": s["ticker"], "entry": price, "exit": None,
                    "pnl": None, "entry_date": date, "exit_date": None,
                    "result": "open", "score": s["score"]
                })

        # Calculate equity
        unrealized = 0
        for ticker, pos in positions.items():
            try:
                df = ticker_data[ticker]
                row = df.loc[df.index.astype(str).str[:10] == date]
                if not row.empty:
                    unrealized += (float(row["Close"].iloc[0]) - pos["entry"]) * pos["qty"]
            except Exception:
                pass

        total_equity = capital + sum(p["entry"] * p["qty"] for p in positions.values()) + unrealized
        equity_curve.append({"date": date, "equity": round(total_equity, 2)})
        daily_pnl.append({"date": date, "pnl": round(day_pnl, 2)})

    # Stats
    completed = [t for t in trades if t["result"] in ("stop", "target")]
    total_pnl = sum(t["pnl"] for t in completed if t["pnl"] is not None)
    win_pnls = [t["pnl"] for t in completed if t["pnl"] and t["pnl"] > 0]
    loss_pnls = [t["pnl"] for t in completed if t["pnl"] and t["pnl"] < 0]

    # Max drawdown
    peak = initial_capital
    max_dd = 0
    for pt in equity_curve:
        if pt["equity"] > peak:
            peak = pt["equity"]
        dd = (peak - pt["equity"]) / peak
        if dd > max_dd:
            max_dd = dd

    return {
        "ok": True,
        "equity_curve": equity_curve,
        "trades": completed[-50:],  # last 50
        "open_trades": [t for t in trades if t["result"] == "open"],
        "stats": {
            "total_trades": len(completed),
            "wins": wins,
            "losses": losses,
            "win_rate": round(wins / max(1, wins + losses) * 100, 1),
            "total_pnl": round(total_pnl, 2),
            "total_pnl_pct": round(total_pnl / initial_capital * 100, 2),
            "avg_win": round(sum(win_pnls) / max(1, len(win_pnls)), 2),
            "avg_loss": round(sum(loss_pnls) / max(1, len(loss_pnls)), 2),
            "profit_factor": round(sum(win_pnls) / max(1, abs(sum(loss_pnls))), 2),
            "max_drawdown": round(max_dd * 100, 2),
            "days": len(equity_curve),
            "initial_capital": initial_capital,
            "final_equity": equity_curve[-1]["equity"] if equity_curve else initial_capital,
        }
    }
