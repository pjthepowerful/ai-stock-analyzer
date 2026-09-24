"""
Backtest for the earnings strategy.
===================================

WHAT CAN AND CANNOT BE TESTED — READ THIS FIRST
------------------------------------------------
Two of the five signals in `forecast.py` CANNOT be backtested with free data,
and this harness refuses to pretend otherwise.

Yahoo's `eps_revisions` and `eps_trend` endpoints return a CURRENT SNAPSHOT.
The request carries a symbol and nothing else — there is no date parameter and
no history. So there is no way to reconstruct what analysts believed before a
print that happened last year. Scoring a 2024 event with 2026 revision counts
would be using information from after the event to predict it, and it would
produce a spectacular and completely fake result.

Those two legs carry 0.65 of the earnings lean's weight. That is the honest
headline of any backtest here: **most of the beat forecast is unvalidated and
cannot be validated without paid point-in-time estimate data.**

What IS testable, because it can be reconstructed strictly from information
available before the event:

  * beat history      — quarters that reported before date T
  * reaction history  — how the stock moved on those earlier beats
  * run-up into print — price data, genuinely historical
  * the drift strategy itself — buy the reaction after a beat, hold N days

WHY THE BASELINE MATTERS MORE THAN THE HEADLINE NUMBER
-------------------------------------------------------
A strategy returning +3% per trade sounds good until you learn that every
earnings event in the same window returned +3%. Then the signal is worth
nothing and you are just long stocks. Every result here is reported against
the baseline of ALL events in the same universe and period, because the
difference is the only part that is evidence of an edge.

WHAT THIS STILL GETS WRONG
---------------------------
Stated plainly so the numbers are read with the right amount of doubt:

  * **Survivorship.** The universe is names that exist today. Companies that
    delisted, went to zero or were acquired are missing, and they are
    disproportionately the losers. This biases every result upward, and on a
    small-cap universe the bias is large.
  * **Costs.** Small caps have wide spreads. Results are reported both gross
    and net of a round-trip cost, and the net figure is the real one.
  * **Fills.** Entry assumes the close of the reaction day. A real order at
    that moment moves the price on an illiquid name.
  * **Sample size.** A few hundred events across a couple of years is thin.
    Differences under a couple of points are noise.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
from datetime import datetime

MIN_PRIOR_QUARTERS = int(os.environ.get("BT_MIN_PRIOR_QUARTERS", 4))
BEAT_THRESHOLD = float(os.environ.get("BT_BEAT_PCT", 5.0))
ROUND_TRIP_COST_PCT = float(os.environ.get("BT_COST_PCT", 0.5))
HOLD_DAYS = [1, 5, 20, 60]


# ── Data ───────────────────────────────────────────────────────────────────

def load_history(ticker: str):
    """(closes_by_date, sorted_dates, earnings_rows). Network — not stubbable
    away, which is why the caller catches and skips."""
    import yfinance as yf
    import earnings as _earn

    hist = yf.Ticker(ticker).history(period="max", auto_adjust=True)
    if hist is None or getattr(hist, "empty", True):
        return None, None, None
    closes = {}
    for idx, row in hist.iterrows():
        try:
            c = float(row["Close"])
            if c == c and c > 0:
                closes[str(idx.date())] = c
        except Exception:
            continue
    if not closes:
        return None, None, None
    rows = _earn._rows(_earn._earnings_frame(ticker))
    return closes, sorted(closes), rows


def _fwd(session_dates: list, i: int, base: float, closes: dict, n: int) -> float | None:
    """Return from close index i out n sessions.

    `session_dates` is the SORTED DATE LIST, not the holding periods. Passing
    the wrong list here does not raise — it silently returns None for every
    lookup and the whole backtest reports zero events.
    """
    days = session_dates
    j = i + n
    if j >= len(days) or not base:
        return None
    return (closes[days[j]] - base) / base * 100.0


def events_for(ticker: str, closes: dict, days: list, rows: list) -> list[dict]:
    """Every past earnings event, with POINT-IN-TIME features.

    The discipline that makes or breaks this: a feature attached to the event
    at date T may only use quarters and prices strictly before T. Get that
    wrong anywhere and the whole backtest becomes a measure of hindsight.
    """
    done = [(dt, sur) for dt, est, rep, sur in rows if sur is not None]
    done.sort(key=lambda x: x[0])           # OLDEST first: history accumulates

    out = []
    for n, (when, surprise) in enumerate(done):
        # Only quarters BEFORE this one may inform the features.
        prior = done[:n]
        if len(prior) < MIN_PRIOR_QUARTERS:
            continue

        key = when.strftime("%Y-%m-%d")
        after = next((d for d in days if d >= key), None)
        before = None
        for d in reversed(days):
            if d < key:
                before = d
                break
        if not after or not before or after == before:
            continue
        i_after = days.index(after)
        # A report after the close moves the NEXT session.
        i_react = i_after + 1 if i_after + 1 < len(days) else i_after
        p_before, p_react = closes[before], closes[days[i_react]]
        if not p_before or not p_react:
            continue
        reaction = (p_react - p_before) / p_before * 100.0

        # ── Point-in-time features ──
        prior_surprises = [s for _, s in prior]
        beats = [s for s in prior_surprises if s > 0]
        prior_beat_rate = len(beats) / len(prior_surprises) * 100.0

        # How the stock reacted to those EARLIER beats only.
        beat_ups = 0
        beat_total = 0
        for pw, ps in prior:
            if ps <= 0:
                continue
            pk = pw.strftime("%Y-%m-%d")
            pa = next((d for d in days if d >= pk), None)
            pb = None
            for d in reversed(days):
                if d < pk:
                    pb = d
                    break
            if not pa or not pb or pa == pb:
                continue
            ia = days.index(pa)
            ir = ia + 1 if ia + 1 < len(days) else ia
            if days[ir] >= key:             # never peek at or past this event
                continue
            if closes[pb] and closes[days[ir]] > closes[pb]:
                beat_ups += 1
            beat_total += 1
        prior_beat_up_rate = (beat_ups / beat_total * 100.0) if beat_total else None

        i_before = days.index(before)
        runup = None
        if i_before >= 20:
            base = closes[days[i_before - 20]]
            if base:
                runup = (p_before - base) / base * 100.0

        ev = {
            "ticker": ticker, "date": key,
            "surprise_pct": surprise,
            "reaction_pct": reaction,
            "prior_beat_rate": round(prior_beat_rate, 1),
            "prior_beat_up_rate": (round(prior_beat_up_rate, 1)
                                   if prior_beat_up_rate is not None else None),
            "prior_quarters": len(prior_surprises),
            "runup_pct": round(runup, 1) if runup is not None else None,
        }
        # Forward returns from the reaction close — the drift entry point.
        for n_days in HOLD_DAYS:
            ev[f"fwd_{n_days}"] = _fwd(days, i_react, p_react, closes, n_days)
        out.append(ev)
    return out


# ── Statistics ─────────────────────────────────────────────────────────────

def _stats(vals: list, cost: float = 0.0) -> dict:
    vals = [v for v in vals if v is not None]
    if not vals:
        return {"n": 0}
    net = [v - cost for v in vals]
    wins = [v for v in net if v > 0]
    return {
        "n": len(net),
        "hit_rate": round(len(wins) / len(net) * 100, 1),
        "mean": round(statistics.mean(net), 2),
        "median": round(statistics.median(net), 2),
        "stdev": round(statistics.stdev(net), 2) if len(net) > 1 else None,
    }


def _edge(sub: dict, base: dict) -> dict:
    """A result is only evidence if it beats the baseline of doing it on
    everything. This is the number that matters."""
    if not sub.get("n") or not base.get("n"):
        return {"mean_edge": None, "hit_edge": None}
    return {"mean_edge": round(sub["mean"] - base["mean"], 2),
            "hit_edge": round(sub["hit_rate"] - base["hit_rate"], 1)}


def analyse(events: list, cost: float = ROUND_TRIP_COST_PCT) -> dict:
    out = {
        "events": len(events),
        "tickers": len({e["ticker"] for e in events}),
        "period": [min(e["date"] for e in events), max(e["date"] for e in events)]
                  if events else None,
        "round_trip_cost_pct": cost,
        "holds": {},
        "cannot_test": [
            "estimate revisions (eps_revisions) — Yahoo returns only a current "
            "snapshot, so there is no way to know what analysts thought before a "
            "past print. This leg carries 0.45 of the earnings lean.",
            "consensus drift (eps_trend) — same limitation. 0.20 of the lean.",
        ],
        "known_biases": [
            "survivorship: the universe is names that exist today, so delisted "
            "losers are missing and every figure is biased upward",
            "fills: entry assumes the reaction-day close, which a real order on "
            "an illiquid small cap would move",
        ],
    }
    if not events:
        return out

    beats = [e for e in events if (e["surprise_pct"] or 0) >= BEAT_THRESHOLD]
    misses = [e for e in events if (e["surprise_pct"] or 0) <= -BEAT_THRESHOLD]

    for n in HOLD_DAYS:
        k = f"fwd_{n}"
        base = _stats([e[k] for e in events], cost)
        after_beat = _stats([e[k] for e in beats], cost)

        # Does the point-in-time reaction history add anything on top?
        friendly = _stats([e[k] for e in beats
                           if (e["prior_beat_up_rate"] or 0) >= 60], cost)
        hostile = _stats([e[k] for e in beats
                          if e["prior_beat_up_rate"] is not None
                          and e["prior_beat_up_rate"] <= 40], cost)
        # And does a big run-up into the print really hurt?
        extended = _stats([e[k] for e in beats
                           if (e["runup_pct"] or 0) >= 25], cost)

        out["holds"][f"{n}d"] = {
            "baseline_all_events": base,
            "after_a_beat": {**after_beat, **_edge(after_beat, base)},
            "beat_and_history_friendly": {**friendly, **_edge(friendly, base)},
            "beat_but_history_hostile": {**hostile, **_edge(hostile, base)},
            "beat_but_already_ran_25pct": {**extended, **_edge(extended, base)},
            "after_a_miss": {**_stats([e[k] for e in misses], cost),
                             **_edge(_stats([e[k] for e in misses], cost), base)},
        }

    # Does a serial beater keep beating? The only directly testable part of the
    # beat forecast.
    high = [e for e in events if e["prior_beat_rate"] >= 75]
    low = [e for e in events if e["prior_beat_rate"] <= 40]
    def _rate(evs):
        if not evs:
            return None
        return round(sum(1 for e in evs
                         if (e["surprise_pct"] or 0) > 0) / len(evs) * 100, 1)
    out["does_beat_history_predict_beats"] = {
        "after_a_75pct_beat_rate": {"n": len(high), "went_on_to_beat_pct": _rate(high)},
        "after_a_40pct_beat_rate": {"n": len(low), "went_on_to_beat_pct": _rate(low)},
        "all_events": {"n": len(events), "went_on_to_beat_pct": _rate(events)},
    }
    return out


# ── Runner ─────────────────────────────────────────────────────────────────

def run(tickers: list[str], cost: float = ROUND_TRIP_COST_PCT,
        progress=None) -> tuple[dict, list]:
    all_events = []
    failed = []
    for i, t in enumerate(tickers):
        t = str(t).upper().strip()
        try:
            closes, days, rows = load_history(t)
            if not closes or not rows:
                failed.append((t, "no data"))
            else:
                all_events += events_for(t, closes, days, rows)
        except Exception as e:
            failed.append((t, f"{type(e).__name__}: {str(e)[:60]}"))
        if progress:
            progress(i + 1, len(tickers), t)
    res = analyse(all_events, cost)
    res["skipped"] = len(failed)
    return res, all_events


def _print(res: dict):
    print("\n" + "=" * 68)
    print("EARNINGS BACKTEST")
    print("=" * 68)
    print(f"{res['events']} events across {res['tickers']} tickers"
          + (f", {res['period'][0]} to {res['period'][1]}" if res.get("period") else ""))
    print(f"round-trip cost applied: {res['round_trip_cost_pct']}%")
    if res.get("skipped"):
        print(f"{res['skipped']} tickers skipped (no data)")

    print("\nWHAT THIS BACKTEST CANNOT TEST")
    for line in res["cannot_test"]:
        print(f"  ! {line}")

    bh = res.get("does_beat_history_predict_beats")
    if bh:
        print("\nDOES A HABIT OF BEATING PREDICT THE NEXT BEAT?")
        for k, v in bh.items():
            if v.get("went_on_to_beat_pct") is not None:
                print(f"  {k:<28} {v['went_on_to_beat_pct']:>6}%  (n={v['n']})")

    for hold, d in res.get("holds", {}).items():
        print(f"\nHOLDING {hold} FROM THE REACTION CLOSE")
        base = d["baseline_all_events"]
        print(f"  {'baseline (every event)':<34} "
              f"mean {base.get('mean', 0):>7}%  hit {base.get('hit_rate', 0):>5}%  n={base.get('n', 0)}")
        for name in ("after_a_beat", "beat_and_history_friendly",
                     "beat_but_history_hostile", "beat_but_already_ran_25pct",
                     "after_a_miss"):
            s = d[name]
            if not s.get("n"):
                continue
            edge = s.get("mean_edge")
            print(f"  {name:<34} mean {s['mean']:>7}%  hit {s['hit_rate']:>5}%  "
                  f"n={s['n']:<5} edge vs baseline {edge:+}" if edge is not None
                  else f"  {name:<34} mean {s['mean']:>7}%  n={s['n']}")

    print("\nKNOWN BIASES")
    for line in res["known_biases"]:
        print(f"  - {line}")
    print("\nEdge vs baseline is the only column that is evidence of anything.")
    print("=" * 68 + "\n")


def main():
    ap = argparse.ArgumentParser(description="Backtest the earnings strategy.")
    ap.add_argument("--tickers", help="comma-separated, or omit to use --file")
    ap.add_argument("--file", help="file with one ticker per line")
    ap.add_argument("--cost", type=float, default=ROUND_TRIP_COST_PCT,
                    help="round-trip cost in percent (default 0.5)")
    ap.add_argument("--out", help="write full results + events to this JSON file")
    args = ap.parse_args()

    tickers = []
    if args.tickers:
        tickers = [t.strip() for t in args.tickers.split(",") if t.strip()]
    elif args.file:
        with open(args.file) as fh:
            tickers = [ln.strip() for ln in fh if ln.strip() and not ln.startswith("#")]
    else:
        try:
            from universe import liquid_universe
            tickers = liquid_universe()
        except Exception:
            ap.error("no tickers: pass --tickers or --file")

    def _p(done, total, label):
        if done == 1 or done % 10 == 0 or done == total:
            print(f"  [{done}/{total}] {label}", flush=True)

    print(f"Fetching {len(tickers)} tickers (this is slow — one download each)…")
    res, events = run(tickers, cost=args.cost, progress=_p)
    _print(res)

    if args.out:
        with open(args.out, "w") as fh:
            json.dump({"summary": res, "events": events}, fh, indent=2, default=str)
        print(f"Full results written to {args.out}")


if __name__ == "__main__":
    main()
