"""Experiment 001 runner: period lock, variant budget, logging (SPEC sections 11-14).

Every run appends a row to research/001_intraday_momentum/variants.csv. The
final-test period refuses to run without final_test=True, and any repeat run
on it is flagged in the report.
"""

import csv
import hashlib
import json
import subprocess
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from trading.backtest import DayData, StressOptions, run_backtest
from trading.costs import BASE, COST_LEVELS
from trading.metrics import percentile_of, random_direction_returns, summarize
from trading.risk import RiskLimits
from trading.sessions import sessions_between
from trading.strategies.intraday_momentum import Params

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXPERIMENT_DIR = PROJECT_ROOT / "research" / "001_intraday_momentum"
RESULTS_DIR = PROJECT_ROOT / "results" / "experiment_001"

PERIODS = {
    "development": (date(2016, 1, 4), date(2021, 12, 31)),
    "validation": (date(2022, 1, 3), date(2024, 6, 28)),
    "final": (date(2024, 7, 1), date(2026, 10, 30)),
}
PREREQUISITE = {"validation": "development", "final": "validation"}
VARIANT_BUDGET = {"development": 10, "validation": 2, "final": 1}
WARMUP_DAYS = 60
LOG_FIELDS = ["run_id", "timestamp_utc", "git_commit", "variant_id", "period", "params",
              "risk_placeholder", "net_return_base", "net_return_stress", "net_return_severe",
              "max_drawdown_base", "trades", "sharpe_base", "beats_always_long",
              "random_percentile", "all_pass_rules", "final_test_reused"]


ATTEMPT_FIELDS = ["timestamp_utc", "git_commit", "experiment_id", "period", "variant_id", "params",
                  "status", "detail"]


class ExperimentRefused(RuntimeError):
    pass


def variant_id(params: Params) -> str:
    return hashlib.sha256(json.dumps(params.as_dict(), sort_keys=True).encode()).hexdigest()[:12]


def _git_commit() -> str:
    try:
        head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=PROJECT_ROOT,
                              capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=PROJECT_ROOT,
                               capture_output=True, text=True, check=True).stdout.strip()
        return head + ("+dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _read_log(log_path: Path) -> list[dict]:
    if not log_path.is_file():
        return []
    with log_path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _check_allowed(rows: list[dict], period: str, vid: str, final_test: bool) -> bool:
    """Raise if the run breaks the period lock or variant budget. Returns 'final reused'."""
    if period not in VARIANT_BUDGET:
        raise ExperimentRefused(f"unknown period {period!r}")
    if period == "final" and not final_test:
        raise ExperimentRefused("final test period is locked; pass final_test=True deliberately")
    seen = {r["variant_id"] for r in rows if r["period"] == period}
    if vid not in seen and len(seen) >= VARIANT_BUDGET[period]:
        raise ExperimentRefused(
            f"variant budget for {period} used up ({VARIANT_BUDGET[period]} variants)")
    needed = PREREQUISITE.get(period)
    if needed and not any(r["variant_id"] == vid and r["period"] == needed for r in rows):
        raise ExperimentRefused(f"variant {vid} must be run on {needed} before {period}")
    return period == "final" and any(r["period"] == "final" for r in rows)


def _pass_rules(base, stress, always_long, pct, limits, neighbors) -> dict:
    return {
        "1_positive_after_costs": base["net_return"] > 0 and stress["net_return"] >= 0,
        "2_beats_baselines": base["net_return"] > always_long["net_return"] and pct >= 95,
        "3_drawdown_within_limit": base["max_drawdown"] <= limits.max_drawdown,
        "4_survives_top10_removal": base["pnl_without_top10"] > 0,
        "5_neighbors_same_sign": all(v > 0 for v in neighbors.values()),
    }


def _evaluate(days: dict[date, DayData], period: str, params: Params, limits: RiskLimits,
              start_equity: float, final_test: bool, n_random: int, seed: int,
              log_dir: Path, results_dir: Path, periods: dict, lock: dict) -> dict:
    log_path = log_dir / "variants.csv"
    rows = _read_log(log_path)
    vid = variant_id(params)
    reused = _check_allowed(rows, period, vid, final_test)

    start, end = periods[period]
    sessions = sessions_between(start - timedelta(days=WARMUP_DAYS), end + timedelta(days=7))

    def bt(p=params, costs=BASE, lim=limits, override=None):
        return run_backtest(days, sessions, start, end, p, costs, lim, start_equity,
                            StressOptions(seed=seed), override)

    by_cost = {c.name: summarize(bt(costs=c)) for c in COST_LEVELS}
    base = by_cost["base"]

    always_long = summarize(bt(override=lambda d, s: 1))
    no_kill = replace(limits, max_drawdown=1.0)
    longs, shorts = bt(lim=no_kill, override=lambda d, s: 1), bt(lim=no_kill, override=lambda d, s: -1)
    lt = {t.date: t.net_pnl / t.equity_before for t in longs.trades}
    st = {t.date: t.net_pnl / t.equity_before for t in shorts.trades}
    common = sorted(lt.keys() & st.keys())
    rand = random_direction_returns([lt[d] for d in common], [st[d] for d in common], n_random, seed)
    pct = percentile_of(base["net_return"], rand) if len(common) else float("nan")

    neighbors = {}
    for name, p in {
        "entry_minus_15min": replace(params, entry_offset_min=params.entry_offset_min + 15),
        "entry_plus_15min": replace(params, entry_offset_min=params.entry_offset_min - 15),
        "stop_1.5": replace(params, stop_mult=1.5),
        "stop_2.5": replace(params, stop_mult=2.5),
    }.items():
        neighbors[name] = summarize(bt(p=p))["net_return"]

    rules = _pass_rules(base, by_cost["stress"], always_long, pct, limits, neighbors)
    now = datetime.now(timezone.utc)
    report = {
        "run_id": f"{now.strftime('%Y%m%dT%H%M%S%fZ')}-{vid}",
        "timestamp_utc": now.isoformat(timespec="seconds"),
        "git_commit": _git_commit(),
        "variant_id": vid,
        "period": period,
        "dates": [str(start), str(end)],
        "params": params.as_dict(),
        "risk_limits": limits.__dict__,
        "risk_placeholder": limits.placeholder,
        "start_equity": start_equity,
        "results_by_cost": by_cost,
        "baseline_always_long": always_long,
        "baseline_no_trade_return": 0.0,
        "random_direction": {"runs": n_random, "days": len(common), "strategy_percentile": pct,
                             "p95": float(_pct(rand, 95)), "median": float(_pct(rand, 50))},
        "neighbors_net_return": neighbors,
        "pass_rules": rules,
        "all_pass_rules": all(rules.values()),
        "final_test_reused": reused,
        "experiment_id": lock["experiment_id"],
        "held_out_inspection": _held_out_inspection(log_dir),
        "variants_tried": {p: len({r["variant_id"] for r in rows if r["period"] == p} | (
            {vid} if p == period else set())) for p in VARIANT_BUDGET},
    }

    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / f"{report['run_id']}.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8")
    log_dir.mkdir(parents=True, exist_ok=True)
    new_file = not log_path.is_file()
    with log_path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        if new_file:
            w.writeheader()
        w.writerow({
            "run_id": report["run_id"], "timestamp_utc": report["timestamp_utc"],
            "git_commit": report["git_commit"], "variant_id": vid, "period": period,
            "params": json.dumps(params.as_dict(), sort_keys=True),
            "risk_placeholder": limits.placeholder,
            "net_return_base": base["net_return"],
            "net_return_stress": by_cost["stress"]["net_return"],
            "net_return_severe": by_cost["severe"]["net_return"],
            "max_drawdown_base": base["max_drawdown"], "trades": base["trades"],
            "sharpe_base": base["sharpe"],
            "beats_always_long": base["net_return"] > always_long["net_return"],
            "random_percentile": pct, "all_pass_rules": report["all_pass_rules"],
            "final_test_reused": reused,
        })
    return report


def _held_out_inspection(log_dir: Path) -> dict:
    """Historical replays already run on validation/final sessions: such data is not untouched."""
    from trading.experiment_lock import data_inspection_status
    seen = data_inspection_status(inspection_log=log_dir / "inspection_runs.csv")
    return {p: n for p, n in seen["inspection_replays_touching_period"].items() if p != "development"}


def _log_attempt(log_dir: Path, row: dict) -> None:
    path = log_dir / "experiment_attempts.csv"
    new = not path.is_file()
    log_dir.mkdir(parents=True, exist_ok=True)
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=ATTEMPT_FIELDS)
        if new:
            w.writeheader()
        w.writerow(row)


def run_experiment(days: dict[date, DayData], period: str, params: Params = Params(),
                   limits: RiskLimits = RiskLimits(), start_equity: float = 100_000.0,
                   final_test: bool = False, n_random: int = 10000, seed: int = 0,
                   log_dir: Path = EXPERIMENT_DIR, results_dir: Path = RESULTS_DIR,
                   periods: dict = PERIODS, lock_path: Path | None = None) -> dict:
    """Evaluate one variant on one period, after checking the experiment lock.

    Every attempt, including refused and failed ones, is appended to
    experiment_attempts.csv. `periods` and `lock_path` exist so tests can use
    short synthetic windows and a temporary lock.
    """
    from trading.experiment_lock import LOCK_PATH, LockMismatch, check_lock

    base = {"timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "git_commit": _git_commit(), "period": period, "variant_id": variant_id(params),
            "params": json.dumps(params.as_dict(), sort_keys=True)}
    try:
        lock = check_lock(limits, periods, lock_path or LOCK_PATH)
        report = _evaluate(days, period, params, limits, start_equity, final_test, n_random, seed,
                           log_dir, results_dir, periods, lock)
    except (ExperimentRefused, LockMismatch) as exc:
        _log_attempt(log_dir, base | {"status": "refused", "detail": str(exc)})
        raise
    except Exception as exc:
        _log_attempt(log_dir, base | {"status": "failed", "detail": f"{type(exc).__name__}: {exc}"})
        raise
    _log_attempt(log_dir, base | {"status": "completed", "experiment_id": lock["experiment_id"],
                                  "detail": f"run_id {report['run_id']}"})
    return report


def _pct(values, q):
    return np.percentile(values, q) if len(values) else float("nan")
