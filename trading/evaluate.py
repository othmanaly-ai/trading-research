"""Run the locked experiment 001 evaluation on stored historical data.

Run:  .venv\\Scripts\\python -m trading.evaluate --period development

Loads stored, validated SPY bars (trading.history) and calls run_experiment, which
checks the experiment lock, enforces the period lock and variant budget, and logs
every attempt. Validation and final runs require their own explicit approval.
"""

import argparse
import json
import sys
from datetime import timedelta

from trading.experiment import EXPERIMENT_PRIMARY, PERIODS, ExperimentRefused, run_experiment
from trading.experiment_lock import LockMismatch
from trading.history import HistoryError, load_days
from trading.sessions import sessions_between


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run the locked experiment 001 evaluation")
    parser.add_argument("--period", choices=["development"], required=True,
                        help="validation/final are not runnable from here until approved")
    parser.add_argument("--feed", default="sip")
    parser.add_argument("--adjustment", default="all")
    args = parser.parse_args(argv)
    start, end = PERIODS[args.period]
    sessions = sessions_between(start - timedelta(days=60), end + timedelta(days=7))
    try:
        days = load_days("SPY", args.feed, args.adjustment, sessions)
        report = run_experiment(days, args.period, EXPERIMENT_PRIMARY)
    except (HistoryError, ExperimentRefused, LockMismatch) as exc:
        print(f"NOT RUN: {exc}")
        return 2
    print(json.dumps({k: report[k] for k in ("run_id", "experiment_id", "variant_id", "period", "dates",
                                             "all_pass_rules", "pass_rules", "held_out_inspection")},
                     indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
