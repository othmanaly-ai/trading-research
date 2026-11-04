"""Development-only diagnostics for experiment 001-fd13f1fdef (no held-out data).

Run:  .venv\\Scripts\\python research\\001_intraday_momentum\\diagnose_development.py

Part A independently recomputes every trade from the stored CSV files (not through
the engine's DayData) to check signal timing, fills, stops, sizing, costs and the
equity chain. Part B describes where the result comes from. Nothing here tunes or
selects parameters.
"""

import math
import statistics
import sys
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from trading.backtest import run_backtest                                    # noqa: E402
from trading.costs import BASE                                               # noqa: E402
from trading.experiment import EXPERIMENT_LIMITS, EXPERIMENT_PRIMARY, PERIODS  # noqa: E402
from trading.history import HISTORY_DIR, load_days                           # noqa: E402
from trading.sessions import sessions_between                               # noqa: E402

SERIES = HISTORY_DIR / "SPY" / "sip" / "all"
MIN = pd.Timedelta(minutes=1)


def raw_minutes(d):
    f = pd.read_csv(SERIES / "minute" / f"{d}.csv")
    f["t"] = pd.to_datetime(f["timestamp_utc"], utc=True)
    return f.set_index("t")


def main():
    start, end = PERIODS["development"]
    sessions = sessions_between(start - timedelta(days=60), end + timedelta(days=7))
    days = load_days("SPY", "sip", "all", sessions)
    res = run_backtest(days, sessions, start, end, EXPERIMENT_PRIMARY, BASE, EXPERIMENT_LIMITS, 100_000.0)
    daily = pd.read_csv(SERIES / "daily.csv").set_index("session_date")["close"]
    stored = [s for s in sessions if s.date in days]
    idx = {s.date: k for k, s in enumerate(stored)}

    # last-30 return per stored session, from raw files: open of C-30 bar to close of C-1 bar
    last30 = {}
    for s in stored:
        m = raw_minutes(s.date)
        c = pd.Timestamp(s.close_utc)
        a, b = c - 30 * MIN, c - MIN
        last30[s.date] = (m.at[b, "close"] / m.at[a, "open"] - 1) if a in m.index and b in m.index else None

    # ---- Part A: independent recomputation ----------------------------------------
    k_side, fee = BASE.per_side_bp / 1e4, BASE.sell_fee_bp / 1e4
    equity, checks, problems = 100_000.0, 0, []
    for d in res.days:
        t = d.trade
        if t is None:
            continue
        s = d.session
        m = raw_minutes(s.date)
        o, c = pd.Timestamp(s.open_utc), pd.Timestamp(s.close_utc)
        prev = stored[idx[s.date] - 1].date
        r1 = m.at[o + 29 * MIN, "close"] / daily[str(prev)] - 1
        hist = [last30[stored[j].date] for j in range(idx[s.date] - 20, idx[s.date])]
        sigma = statistics.stdev(hist)
        entry_t = c - 29 * MIN                       # decision C-30, one-minute delay
        price = m.at[entry_t, "open"]
        dp = m.at[c - 31 * MIN, "close"]             # last price known at the decision
        stop = price - 2 * sigma * price
        rt = dp * (2 * BASE.per_side_bp + BASE.sell_fee_bp) / 1e4
        vol = m.loc[c - 60 * MIN: c - 31 * MIN, "volume"].median()
        shares = math.floor(min(0.001 * equity / (2 * sigma * dp + rt), 0.05 * equity / dp,
                                0.10 * equity / dp, 0.01 * vol))
        after = m[(m.index >= entry_t) & (m.index < c)]
        hit = after[after["low"] <= stop]
        if len(hit):
            ht = hit.index[0]
            exit_t, exit_px, reason = ht + MIN, min(after.at[ht, "open"], stop), "stop"
        else:
            exit_t, exit_px, reason = c, m.at[c - MIN, "close"], "time exit"
        entry_fill, exit_fill = price * (1 + k_side), exit_px * (1 - k_side)
        net = shares * (exit_fill - entry_fill) - shares * exit_fill * fee
        checks += 1
        for name, mine, eng in [("r1", r1, t.r1), ("sigma30", sigma, t.sigma30), ("entry_time", entry_t, t.entry_time),
                                ("entry_price", price, t.entry_price), ("stop", stop, t.stop_price),
                                ("shares", shares, t.shares), ("exit_time", exit_t, t.exit_time),
                                ("exit_price", exit_px, t.exit_price), ("exit_reason", reason, t.exit_reason),
                                ("net_pnl", net, t.net_pnl), ("equity_before", equity, t.equity_before)]:
            same = mine == eng if isinstance(mine, (str, pd.Timestamp, int)) else math.isclose(mine, eng, rel_tol=1e-9, abs_tol=1e-9)
            if not same:
                problems.append((str(s.date), name, mine, eng))
        if r1 <= 0:
            problems.append((str(s.date), "long trade on non-positive r1", r1, None))
        equity += net
    print(f"PART A: {checks} trades recomputed independently; mismatches: {len(problems)}")
    for p in problems[:10]:
        print("   ", p)
    print(f"  equity chain end: independent ${equity:,.2f} vs engine ${res.end_equity:,.2f}")

    # ---- Part B: where the result comes from --------------------------------------
    sig, fwd = [], []
    for s in stored:
        if not (start <= s.date <= end) or idx[s.date] < 20 or last30[s.date] is None:
            continue
        m = raw_minutes(s.date)
        o = pd.Timestamp(s.open_utc)
        if o + 29 * MIN not in m.index:
            continue
        sig.append(m.at[o + 29 * MIN, "close"] / daily[str(stored[idx[s.date] - 1].date)] - 1)
        fwd.append(last30[s.date])
    sig, fwd = np.array(sig), np.array(fwd) * 1e4            # forward last-30 return in bp
    def stats(x):
        return f"mean {x.mean():+.2f} bp, se {x.std(ddof=1)/math.sqrt(len(x)):.2f}, n={len(x)}"
    print("PART B: last-30-minute SPY return (bp), development sessions with a valid signal")
    print("  all sessions:      ", stats(fwd))
    print("  r1 > 0 (traded):   ", stats(fwd[sig > 0]))
    print("  r1 < 0 (not traded):", stats(fwd[sig < 0]))
    print(f"  correlation(r1, last-30 return) = {np.corrcoef(sig, fwd)[0, 1]:+.4f}")
    q = pd.qcut(sig, 5, labels=False)
    print("  by r1 quintile (low to high):", [f"{fwd[q == i].mean():+.2f}" for i in range(5)])

    trades = res.trades
    net = np.array([t.net_pnl for t in trades])
    gross = np.array([t.gross_pnl for t in trades])
    order = np.sort(net)
    print("CONCENTRATION")
    print(f"  net ${net.sum():,.2f} = gross ${gross.sum():,.2f} - costs ${gross.sum() - net.sum():,.2f}")
    print(f"  median trade ${np.median(net):+.2f}; losing trades {np.mean(net <= 0):.1%}")
    print(f"  10 worst trades ${order[:10].sum():,.2f}; 10 best ${order[-10:].sum():,.2f}; "
          f"without the 10 worst ${net.sum() - order[:10].sum():,.2f}; without 10 best and 10 worst "
          f"${net.sum() - order[:10].sum() - order[-10:].sum():,.2f}")
    months = pd.Series(net, index=[pd.Timestamp(t.date).to_period("M") for t in trades]).groupby(level=0).sum()
    print(f"  months: {len(months)}, negative {np.mean(months < 0):.0%}; worst month {months.idxmin()} ${months.min():,.2f}; "
          f"best {months.idxmax()} ${months.max():,.2f}")
    stops = [t for t in trades if t.exit_reason == "stop"]
    print(f"  stops: {len(stops)} trades, net ${sum(t.net_pnl for t in stops):,.2f}; "
          f"time exits ${sum(t.net_pnl for t in trades if t.exit_reason != 'stop'):,.2f}")


if __name__ == "__main__":
    main()
