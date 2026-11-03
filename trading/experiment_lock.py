"""Experiment lock: what experiment 001 is, fixed before any evaluation runs.

Create:  .venv\\Scripts\\python -m trading.experiment_lock --write

The lock records the hypothesis, spec version and hash, the primary parameters,
cost models, pass rules, metrics, periods, variant budget and risk limits, plus
what real data had been retrieved or inspected when it was written. The runner
refuses to evaluate if the current definition no longer matches the lock. A
deliberate change means a new experiment id, never an edited lock.
"""

import argparse
import csv
import hashlib
import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from trading.costs import COST_LEVELS
from trading.experiment import EXPERIMENT_DIR, PERIODS, VARIANT_BUDGET
from trading.history import HISTORY_DIR, period_of, read_manifest
from trading.risk import RiskLimits
from trading.strategies.intraday_momentum import Params
from trading.strategies.registry import spec_info

LOCK_PATH = EXPERIMENT_DIR / "EXPERIMENT_LOCK.json"
PASS_RULES = "SPEC section 14 rules 1-5; rule 1 stress test read strictly as net >= 0 (17.4)"
HYPOTHESIS = ("The SPY return from the previous close to 10:00 ET predicts the direction of the "
              "return over the final 30 minutes of the session, by enough to remain positive after "
              "modeled costs.")
METRICS = ["net return (base/stress/severe)", "max drawdown", "time in market", "trades",
           "unique sessions", "average win/loss", "profit factor", "Sharpe with bootstrap CI",
           "results by year", "result without top 10 trades", "parameter neighbors",
           "always-long and random-direction baselines", "no-trade baseline"]


class LockMismatch(RuntimeError):
    pass


def fingerprint(limits: RiskLimits, periods: dict = PERIODS) -> dict:
    """The parts that may not change within one experiment id."""
    spec = spec_info("intraday_momentum", Params())
    return {
        "spec_version": spec["spec_version"], "spec_sha256": spec["spec_sha256"],
        "costs": [asdict(c) for c in COST_LEVELS],
        "periods": {k: [str(a), str(b)] for k, (a, b) in periods.items()},
        "variant_budget": VARIANT_BUDGET, "pass_rules": PASS_RULES,
        "risk_limits": asdict(limits),
    }


def experiment_id(fp: dict) -> str:
    return "001-" + hashlib.sha256(json.dumps(fp, sort_keys=True).encode()).hexdigest()[:10]


def data_inspection_status(history_root: Path = HISTORY_DIR,
                           inspection_log: Path = EXPERIMENT_DIR / "inspection_runs.csv") -> dict:
    """Which periods have real data stored, and which were looked at in historical replays."""
    manifest = read_manifest("SPY", "sip", "all", history_root)
    stored = manifest["summary"]["by_period"] if manifest else {p: 0 for p in PERIODS}
    inspected = {p: 0 for p in PERIODS}
    if inspection_log.is_file():
        with inspection_log.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                for key in ("first_session", "last_session"):
                    p = period_of(datetime.fromisoformat(row[key]).date())
                    if p:
                        inspected[p] += 1
    return {"sessions_stored_by_period": stored, "inspection_replays_touching_period": inspected}


def build_lock(limits: RiskLimits = RiskLimits(), periods: dict = PERIODS,
               history_root: Path = HISTORY_DIR, inspection_log: Path | None = None) -> dict:
    fp = fingerprint(limits, periods)
    return {
        "experiment_id": experiment_id(fp),
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "hypothesis": HYPOTHESIS,
        "primary_params": Params().as_dict(),
        "metrics": METRICS,
        "risk_limits_are_placeholders": limits.placeholder,
        "data_status_at_lock": data_inspection_status(
            history_root, inspection_log or EXPERIMENT_DIR / "inspection_runs.csv"),
        "fingerprint": fp,
    }


def check_lock(limits: RiskLimits, periods: dict = PERIODS, lock_path: Path = LOCK_PATH) -> dict:
    if not lock_path.is_file():
        raise LockMismatch(f"no experiment lock at {lock_path}; create it before evaluating")
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    current = fingerprint(limits, periods)
    diffs = sorted(k for k in current if current[k] != lock["fingerprint"].get(k))
    if diffs:
        raise LockMismatch(f"experiment definition changed since lock {lock['experiment_id']}: {diffs}. "
                           "Record a new experiment instead of editing this one.")
    return lock


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Write or check the experiment 001 lock")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--supersede", metavar="REASON",
                        help="archive the current lock (with this reason) and write a new one")
    args = parser.parse_args(argv)
    if args.supersede:
        if LOCK_PATH.exists():
            old = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
            old["superseded_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            old["superseded_reason"] = args.supersede
            archive = EXPERIMENT_DIR / "locks" / f"{old['experiment_id']}.json"
            archive.parent.mkdir(exist_ok=True)
            archive.write_text(json.dumps(old, indent=2), encoding="utf-8")
            LOCK_PATH.unlink()
            print(f"Archived {old['experiment_id']} to {archive}")
        args.write = True
    if args.write:
        if LOCK_PATH.exists():
            print(f"Lock already exists at {LOCK_PATH}; not overwriting. Use --supersede REASON "
                  "to record a new experiment.")
            return 1
        lock = build_lock()
        LOCK_PATH.write_text(json.dumps(lock, indent=2), encoding="utf-8")
        print(f"Wrote {lock['experiment_id']} to {LOCK_PATH}")
        return 0
    try:
        lock = check_lock(RiskLimits())
    except LockMismatch as exc:
        print(f"MISMATCH: {exc}")
        return 1
    print(f"Lock {lock['experiment_id']} matches the current definition.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
