"""Experiment 002 runner: lock, comparators, diagnostics and the development evaluation.

Run:  .venv\\Scripts\\python -m trading.orb_experiment --write-lock      (once, after commit)
      .venv\\Scripts\\python -m trading.orb_experiment --run development

Only the development stage exists here. Validation and final runs are refused until the
owner reviews the development report (spec v1.0 section 6).
"""

import argparse
import csv
import hashlib
import json
import math
import subprocess
import sys
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from trading.backtest import DayData
from trading.costs import BASE, COST_LEVELS, SEVERE, STRESS, CostModel
from trading.engine import MINUTE, PROVISIONAL, UNRESOLVED, first_bad_minute, run_strategy
from trading.experiment import PERIODS
from trading.history import HistoryError, load_days
from trading.metrics import summarize
from trading.risk import OWNER_BASELINE_2026_11_03, RiskLimits
from trading.sessions import sessions_between
from trading.strategies.opening_range_breakout import (
    CONFIGURATIONS, PRIMARY, ROBUSTNESS, AlwaysLongB3, OpeningRangeBreakout, ORBConfig, opening_range,
)
from trading.strategies.registry import spec_info

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXP_DIR = PROJECT_ROOT / "research" / "002_opening_range_breakout"
LOCK_PATH = EXP_DIR / "EXPERIMENT_LOCK.json"
RESULTS_DIR = PROJECT_ROOT / "results" / "experiment_002"
LIMITS = OWNER_BASELINE_2026_11_03
START_EQUITY = 100_000.0
DIAG_NOTIONAL = 5_000.0
REFERENCE_BALANCE = 100_000.0
SEEDS = (20261104, 20261105)
N_RUNS = 10_000
BUDGET = {"development": 4, "validation": 1, "final": 1}
PASS_RULES = "spec v1.0 section 6: D1-D6 (D6 engineering screen), V1-V3 gates, V4 report-only"
LOG_FIELDS = ["timestamp_utc", "git_commit", "experiment_id", "run_id", "period", "configuration",
              "variant_id", "status", "net_return_base", "halted_base", "trades", "detail"]


class Refused(RuntimeError):
    pass


def _git_commit() -> str:
    try:
        head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=PROJECT_ROOT,
                              capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=PROJECT_ROOT,
                               capture_output=True, text=True, check=True).stdout.strip()
        return head + ("+dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def variant_id(cfg: ORBConfig) -> str:
    return hashlib.sha256(json.dumps(cfg.as_dict(), sort_keys=True).encode()).hexdigest()[:12]


# ---- lock --------------------------------------------------------------------------

def fingerprint() -> dict:
    spec = spec_info("opening_range_breakout", PRIMARY)
    return {
        "spec_version": spec["spec_version"], "spec_sha256": spec["spec_sha256"],
        "configurations": [c.as_dict() for c in CONFIGURATIONS],
        "costs": [asdict(c) for c in COST_LEVELS], "risk_limits": asdict(LIMITS),
        "periods": {k: [str(a), str(b)] for k, (a, b) in PERIODS.items()},
        "budget": BUDGET, "pass_rules": PASS_RULES, "seeds": list(SEEDS), "runs": N_RUNS,
        "diagnostic": {"notional_per_trade": DIAG_NOTIONAL, "reference_balance": REFERENCE_BALANCE},
        "exit": "scheduled exit at the open of the bar starting C - 1",
    }


def experiment_id(fp: dict) -> str:
    return "002-" + hashlib.sha256(json.dumps(fp, sort_keys=True).encode()).hexdigest()[:10]


def write_lock(path: Path = LOCK_PATH) -> dict:
    if path.exists():
        raise Refused(f"lock already exists at {path}")
    fp = fingerprint()
    lock = {"experiment_id": experiment_id(fp), "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "tested_code_commit": _git_commit(), "fingerprint": fp,
            "data_status_at_lock": {"development": "stored (reused from experiment 001)",
                                    "validation": "never retrieved", "final": "never retrieved"}}
    if lock["tested_code_commit"].endswith("+dirty") or lock["tested_code_commit"] == "unknown":
        raise Refused("commit the specification and implementation before writing the lock")
    path.write_text(json.dumps(lock, indent=2), encoding="utf-8")
    return lock


def check_lock(path: Path = LOCK_PATH) -> dict:
    if not path.is_file():
        raise Refused(f"no experiment 002 lock at {path}")
    lock = json.loads(path.read_text(encoding="utf-8"))
    cur = fingerprint()
    diffs = sorted(k for k in cur if cur[k] != lock["fingerprint"].get(k))
    if diffs:
        raise Refused(f"experiment 002 definition changed since lock {lock['experiment_id']}: {diffs}")
    return lock


# ---- diagnostics (fixed $5,000 per trade, no halts; invariant 1) --------------------

def session_arrays(day: DayData):
    """Per-minute open/low/close arrays from the open (NaN where no bar) and the first bad index."""
    o, c = pd.Timestamp(day.session.open_utc), pd.Timestamp(day.session.close_utc)
    n = int((c - o) / MINUTE)
    idx = ((day.bars.index - o) / MINUTE).astype(int)
    keep = (idx >= 0) & (idx < n)
    arr = {k: np.full(n, np.nan) for k in ("open", "low", "close")}
    for k in arr:
        arr[k][idx[keep]] = day.bars[k].to_numpy()[keep]
    fb = int((first_bad_minute(day) - o) / MINUTE)
    return arr, fb, n


def diagnostic_trades(day: DayData, nxt: DayData | None, L: float, costs: CostModel, first: int, last: int):
    """For entry minutes first..last (indices from the open): dollar P&L of a fixed $5,000 long with
    stop L, exit at the C - 1 open (carry or provisional if missing), and holding minutes, stop
    distance (bp) and dollar costs. Invalid entries (Checks(m) fails, no bar, open <= L) are NaN."""
    arr, fb, n = session_arrays(day)
    op, lo, cl = arr["open"], arr["low"], arr["close"]
    m = np.arange(first, last + 1)
    valid = (fb >= m) & ~np.isnan(op[m]) & (op[m] > L)
    hit = np.zeros(n, dtype=bool)
    hit[: n - 1] = np.nan_to_num(lo[: n - 1], nan=np.inf) <= L
    next_hit = np.full(n + 1, n, dtype=int)
    for j in range(n - 2, -1, -1):
        next_hit[j] = j if hit[j] else next_hit[j + 1]
    k = next_hit[m]
    stopped = k <= n - 2
    if not np.isnan(op[n - 1]):
        sched_px, sched_t, sched_flag = op[n - 1], n - 1, 0
    elif nxt is not None and len(nxt.bars):
        sched_px, sched_t, sched_flag = float(nxt.bars.iloc[0]["open"]), n + 1, 1       # carried
    else:
        lastbar = int(np.nanmax(np.where(~np.isnan(cl), np.arange(n), np.nan)))
        sched_px, sched_t, sched_flag = cl[lastbar], lastbar + 1, 2                    # provisional
    kk = np.minimum(k, n - 1)
    exit_px = np.where(stopped, np.minimum(op[kk], L), sched_px)
    exit_t = np.where(stopped, k + 1, sched_t)
    side = costs.per_side_bp / 1e4
    entry_fill = op[m] * (1 + side)
    exit_fill = exit_px * (1 - side)
    units = DIAG_NOTIONAL / entry_fill
    dollars = units * (exit_fill - entry_fill) - units * exit_fill * costs.sell_fee_bp / 1e4
    cost = units * (op[m] * side + exit_px * side + exit_fill * costs.sell_fee_bp / 1e4)
    out = {"pnl": dollars, "hold": (exit_t - m).astype(float), "stop_bp": (op[m] - L) / op[m] * 1e4,
           "cost": cost, "flag": np.where(stopped, 0, sched_flag)}
    for key in out:
        out[key] = np.where(valid, out[key], np.nan)
    return out


def diagnostics(days, sessions, start, end, strategy_entries: int, costs: CostModel = BASE,
                seeds=SEEDS, n_runs: int = N_RUNS) -> dict:
    """Strategy vs B1 and B2 under the identical fixed-size, no-halt analysis."""
    orb = OpeningRangeBreakout(PRIMARY)
    rows, strat = [], []
    for i, s in enumerate(sessions):
        if not start <= s.date <= end or s.date not in days:
            continue
        day = days[s.date]
        nxt = days.get(sessions[i + 1].date) if i + 1 < len(sessions) else None
        fb = first_bad_minute(day)
        rng = opening_range(day, 30, fb)
        if rng is None:
            continue
        n = int((pd.Timestamp(s.close_utc) - pd.Timestamp(s.open_utc)) / MINUTE)
        first, last = 31, n - 60
        d = diagnostic_trades(day, nxt, rng[1], costs, first, last)
        dec = orb.decide(day)
        e_idx = None
        if dec.plan is not None:
            b = day.bars
            w = b[(b.index >= dec.plan.window_start) & (b.index <= dec.plan.window_end)]
            if len(w):
                e_idx = int((w.index[0] - pd.Timestamp(s.open_utc)) / MINUTE)
        rows.append((d, e_idx, last - first + 1))
        if e_idx is not None and not math.isnan(d["pnl"][e_idx - first]):
            strat.append({k: d[k][e_idx - first] for k in d})
    S = len(rows)
    width = max(r[2] for r in rows)
    mats = {k: np.full((S, width), np.nan) for k in ("pnl", "hold", "stop_bp", "cost")}
    counts = np.array([r[2] for r in rows])
    for si, (d, _, cnt) in enumerate(rows):
        for k in mats:
            mats[k][si, :cnt] = d[k]
    p = strategy_entries / S
    strat_total = float(np.nansum([t["pnl"] for t in strat]))
    out = {
        "or_eligible_sessions": S, "participation_p": p, "strategy_entries_full_account": strategy_entries,
        "normalization": "account return = total net dollar P&L / $100,000; $5,000 notional per trade at entry fill",
        "strategy": {"trades": len(strat), "total_pnl": strat_total, "account_return": strat_total / REFERENCE_BALANCE,
                     "mean_hold_min": float(np.mean([t["hold"] for t in strat])) if strat else None,
                     "median_hold_min": float(np.median([t["hold"] for t in strat])) if strat else None,
                     "mean_stop_bp": float(np.mean([t["stop_bp"] for t in strat])) if strat else None,
                     "median_stop_bp": float(np.median([t["stop_bp"] for t in strat])) if strat else None,
                     "total_cost": float(np.sum([t["cost"] for t in strat])), "participation": len(strat) / S},
        "B1": {}, "B2": {},
    }
    for seed in seeds:
        rng = np.random.Generator(np.random.PCG64(seed))
        totals, trades, unmatched, hold, stop_bp, cost = [], [], [], [], [], []
        for chunk in range(0, n_runs, 500):
            r = min(500, n_runs - chunk)
            u1, u2 = rng.random((r, S)), rng.random((r, S))
            part = u1 < p
            col = np.floor(u2 * counts).astype(int)
            pnl = mats["pnl"][np.arange(S), col]
            v = part & ~np.isnan(pnl)
            totals += list(np.where(v, pnl, 0.0).sum(axis=1))
            trades += list(v.sum(axis=1))
            unmatched += list((part & np.isnan(pnl)).sum(axis=1))
            for lst, k in ((hold, "hold"), (stop_bp, "stop_bp"), (cost, "cost")):
                vals = mats[k][np.arange(S), col]
                lst += list(np.where(v, vals, np.nan).sum(axis=1) / np.maximum(v.sum(axis=1), 1)
                            if k != "cost" else np.where(v, vals, 0.0).sum(axis=1))
        totals = np.array(totals)
        out["B1"][str(seed)] = {
            "runs": n_runs, "median_total_pnl": float(np.median(totals)),
            "median_account_return": float(np.median(totals)) / REFERENCE_BALANCE,
            "p95_total_pnl": float(np.percentile(totals, 95)),
            "strategy_percentile": float(np.mean(totals < strat_total) * 100),
            "ties": int(np.sum(totals == strat_total)),
            "mean_trades": float(np.mean(trades)), "mean_unmatched": float(np.mean(unmatched)),
            "mean_unmatched_rate": float(np.mean(unmatched) / max(np.mean(trades) + np.mean(unmatched), 1)),
            "mean_hold_min": float(np.nanmean(hold)), "mean_stop_bp": float(np.nanmean(stop_bp)),
            "mean_total_cost": float(np.mean(cost)),
        }
        # B2: one random minute before the strategy's entry, on strategy sessions only.
        rng2 = np.random.Generator(np.random.PCG64(seed))
        b2_rows = [(si, e - 31) for si, (_, e, _) in enumerate(rows) if e is not None]
        b2_totals, no_room = [], sum(1 for _, w in b2_rows if w <= 0)
        u = rng2.random((n_runs, len(b2_rows)))
        widths = np.array([w for _, w in b2_rows])
        sidx = np.array([si for si, _ in b2_rows])
        col = np.floor(u * np.maximum(widths, 1)).astype(int)
        vals = mats["pnl"][sidx, col]
        vals = np.where(widths > 0, vals, np.nan)
        b2_totals = np.nansum(vals, axis=1)
        out["B2"][str(seed)] = {"runs": n_runs, "median_total_pnl": float(np.median(b2_totals)),
                                "strategy_percentile": float(np.mean(b2_totals < strat_total) * 100),
                                "sessions_without_room": no_room,
                                "mean_unmatched": float(np.mean(np.isnan(vals).sum(axis=1) - no_room)),
                                "note": "conditional on later information (a breakout occurred); context only"}
    return out


# ---- full-account runs and acceptance ------------------------------------------------

def _account(res) -> dict:
    s = summarize(res)
    return {"net_return": res.end_equity / res.start_equity - 1, "net_pnl": res.end_equity - res.start_equity,
            "gross_pnl": float(sum(t.gross_pnl for t in res.trades)),
            "modeled_costs": float(sum(t.gross_pnl - t.net_pnl for t in res.trades)),
            "trades": len(res.trades), "unique_sessions": s["unique_sessions"],
            "halted": res.halted, "halt_event": res.halt_event,
            "max_drawdown_intraday": res.max_drawdown_intraday, "max_drawdown_end_of_day": s["max_drawdown"],
            "time_in_market": s["time_in_market"], "avg_notional_to_equity": s["avg_notional_to_equity"],
            "win_rate": s["win_rate"], "avg_win": s["avg_win"], "avg_loss": s["avg_loss"],
            "profit_factor": s["profit_factor"], "sharpe": s["sharpe"], "sharpe_ci95": s["sharpe_ci95"],
            "avg_holding_minutes": s["avg_holding_minutes"], "by_year": s["by_year"], "skips": s["skips"],
            "exit_reasons": s["exit_reasons"],
            "unresolved_trades": sum(1 for t in res.trades if UNRESOLVED in t.flags or PROVISIONAL in t.flags),
            "provisional_trades": [{"date": str(t.date), "net_pnl": t.net_pnl} for t in res.provisional_trades],
            "net_pnl_excluding_provisional": float(sum(t.net_pnl for t in res.trades if PROVISIONAL not in t.flags)),
            "top10_winners_pnl": float(sum(sorted([t.net_pnl for t in res.trades if t.net_pnl > 0])[-10:])),
            "m2_sessions": sorted(d for d, i in res.session_info.items() if i.get("m2_stop")),
            "m2_detail": {d: i["failed_check_minute_utc"] for d, i in res.session_info.items() if i.get("m2_stop")}}


def run_development(days: dict, log_dir: Path = EXP_DIR, results_dir: Path = RESULTS_DIR,
                    lock_path: Path = LOCK_PATH, n_runs: int = N_RUNS) -> dict:
    status_path = log_dir / "STATUS.json"
    if status_path.is_file() and json.loads(status_path.read_text()).get("status", "").startswith("CLOSED"):
        raise Refused("experiment 002 is closed")
    lock = check_lock(lock_path)
    start, end = PERIODS["development"]
    sessions = sessions_between(start - timedelta(days=10), end + timedelta(days=7))
    now = datetime.now(timezone.utc)
    run_id = now.strftime("%Y%m%dT%H%M%SZ")
    commit = _git_commit()

    def full(strategy, costs, exit_mode="c1_open"):
        return run_strategy(days, sessions, start, end, strategy, costs, LIMITS, START_EQUITY, exit_mode)

    primary = {c.name: _account(full(OpeningRangeBreakout(PRIMARY), c)) for c in (BASE, STRESS, SEVERE)}
    b3 = _account(full(AlwaysLongB3(PRIMARY), BASE))
    moc = _account(full(OpeningRangeBreakout(PRIMARY), BASE, exit_mode="moc"))
    robustness = {cfg.name: _account(full(OpeningRangeBreakout(cfg), BASE)) for cfg in ROBUSTNESS}
    diag = diagnostics(days, sessions, start, end, primary["base"]["trades"], BASE, SEEDS, n_runs)
    b, st = primary["base"], primary["stress"]
    rules = {
        "D1": {"pass": b["net_return"] > 0 and st["net_return"] >= 0,
               "base_net_return": b["net_return"], "stress_net_return": st["net_return"]},
        "D2": {"pass": not b["halted"] and not st["halted"] and max(b["max_drawdown_intraday"], st["max_drawdown_intraday"]) <= 0.03,
               "halted_base": b["halted"], "halted_stress": st["halted"],
               "max_dd_base": b["max_drawdown_intraday"], "max_dd_stress": st["max_drawdown_intraday"]},
        "D3": {"pass": b["net_return"] > b3["net_return"], "strategy": b["net_return"], "B3": b3["net_return"]},
        "D4": {"pass": b["net_pnl"] - b["top10_winners_pnl"] > 0, "net_pnl": b["net_pnl"],
               "top10_winners": b["top10_winners_pnl"], "remainder": b["net_pnl"] - b["top10_winners_pnl"]},
        "D5": {"pass": all(r["net_return"] > 0 and not r["halted"] for r in robustness.values()),
               **{k: {"net_return": v["net_return"], "halted": v["halted"]} for k, v in robustness.items()}},
        "D6": {"pass": diag["B1"][str(SEEDS[0])]["strategy_percentile"] >= 95,
               "percentile": diag["B1"][str(SEEDS[0])]["strategy_percentile"],
               "label": "engineering screening criterion; not a significance test or future-profit probability"},
    }
    report = {"run_id": run_id, "experiment_id": lock["experiment_id"], "git_commit": commit,
              "tested_code_commit_in_lock": lock["tested_code_commit"], "period": "development",
              "dates": [str(start), str(end)], "risk_limits": asdict(LIMITS), "primary": primary,
              "B3": b3, "moc_sensitivity": moc, "robustness": robustness, "diagnostics": diag,
              "rules": rules, "all_pass": all(r["pass"] for r in rules.values())}
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / f"{run_id}.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    path = log_dir / "experiment_runs.csv"
    new = not path.is_file()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        if new:
            w.writeheader()
        for cfg, res in [(PRIMARY, primary["base"])] + [(c, robustness[c.name]) for c in ROBUSTNESS]:
            w.writerow({"timestamp_utc": now.isoformat(timespec="seconds"), "git_commit": commit,
                        "experiment_id": lock["experiment_id"], "run_id": run_id, "period": "development",
                        "configuration": cfg.name, "variant_id": variant_id(cfg), "status": "completed",
                        "net_return_base": res["net_return"], "halted_base": res["halted"],
                        "trades": res["trades"], "detail": "all D-rules pass" if report["all_pass"] else "development failed"})
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Experiment 002 runner")
    parser.add_argument("--write-lock", action="store_true")
    parser.add_argument("--run", choices=["development", "validation", "final"])
    args = parser.parse_args(argv)
    try:
        if args.write_lock:
            lock = write_lock()
            print(f"Wrote {lock['experiment_id']} (tested code commit {lock['tested_code_commit']})")
            return 0
        if args.run in ("validation", "final"):
            raise Refused(f"{args.run} runs are not permitted until the owner reviews the development report")
        if args.run == "development":
            start, end = PERIODS["development"]
            sessions = sessions_between(start - timedelta(days=10), end + timedelta(days=7))
            days = load_days("SPY", "sip", "all", sessions)
            report = run_development(days)
            print(json.dumps({"run_id": report["run_id"], "experiment_id": report["experiment_id"],
                              "all_pass": report["all_pass"],
                              "rules": {k: v["pass"] for k, v in report["rules"].items()}}, indent=2))
            return 0
        print(json.dumps({"lock": check_lock()["experiment_id"], "status": "matches"}))
        return 0
    except (Refused, HistoryError) as exc:
        print(f"REFUSED: {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
