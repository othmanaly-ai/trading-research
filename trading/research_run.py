"""One inspectable research run: stored data -> versioned strategy -> chronological
replay -> modeled fills and costs -> risk checks -> trade journal + evaluation.

Run:  .venv\\Scripts\\python -m trading.research_run --mode historical
      .venv\\Scripts\\python -m trading.research_run --mode demo        (synthetic, labeled DEMO)

The run uses the same builder and ledger as the dashboard, so the journal, the
evaluation and the city all come from one set of records. Outputs go to the
git-ignored results/research/<mode>/<UTC time>/. Historical runs are also
appended to research/001_intraday_momentum/inspection_runs.csv (tracked), so
every variant looked at on real data is recorded. Historical mode refuses to
run without stored, validated data; it never substitutes synthetic data.
"""

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from trading.dashboard import demo_replay, historical_replay
from trading.dashboard.ledger import Ledger
from trading.experiment import _git_commit
from trading.history import HISTORY_DIR, HistoryError
from trading.journal import build_journal, write_journal

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_ROOT = PROJECT_ROOT / "results" / "research"
INSPECTION_LOG = PROJECT_ROOT / "research" / "001_intraday_momentum" / "inspection_runs.csv"
LOG_FIELDS = ["timestamp_utc", "git_commit", "mode", "strategy_id", "variant_id", "spec_version",
              "spec_sha256", "sessions", "first_session", "last_session", "trades", "net_pnl",
              "result_hash", "feed", "data_retrieved_utc"]


def run(mode: str, config_path: Path | None = None, history_root: Path = HISTORY_DIR,
        results_root: Path = RESULTS_ROOT, inspection_log: Path = INSPECTION_LOG) -> dict:
    if mode == "historical":
        replay = historical_replay.build_historical(
            historical_replay.load_config(config_path or historical_replay.DEFAULT_CONFIG), history_root)
    elif mode == "demo":
        replay = demo_replay.build_demo(demo_replay.load_config(config_path or demo_replay.DEFAULT_CONFIG))
    else:
        raise ValueError(f"unknown mode {mode!r}")

    ledger = Ledger(replay.meta)
    for e in replay.events:
        ledger.apply(e.to_dict())

    now = datetime.now(timezone.utc)
    out = results_root / replay.meta["mode"].lower() / now.strftime("%Y%m%dT%H%M%SZ")
    commit = _git_commit()
    provenance = {"mode": replay.meta["mode"], "source": replay.meta["source"], "banner": replay.meta["banner"],
                  "feed": replay.meta["feed"], "cost_model": replay.meta["cost_model"],
                  "sessions": replay.meta["sessions"], "git_commit": commit,
                  "data_provenance": replay.meta.get("provenance"), "run_utc": now.isoformat(timespec="seconds")}
    summary = {"mode": replay.meta["mode"], "output_dir": str(out), "strategies": []}
    for sid in ledger.strategies:
        rows = build_journal(ledger, sid)
        report = ledger.evaluation(sid)
        write_journal(rows, out / f"{sid}_journal.csv", provenance)
        (out / f"{sid}_evaluation.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        spec = next(i for i in replay.meta["instances"] if i["id"] == sid)["spec"]
        summary["strategies"].append({
            "strategy_id": sid, "variant_id": spec["variant_id"], "spec_version": spec["spec_version"],
            "spec_sha256": spec["spec_sha256"], "sessions": len(rows), "trades": report["sample"]["trades"],
            "net_pnl": report["pnl"]["net"], "result_hash": report["result_hash"]})

    if replay.meta["mode"] == "HISTORICAL_REPLAY":
        new = not inspection_log.is_file()
        inspection_log.parent.mkdir(parents=True, exist_ok=True)
        with inspection_log.open("a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=LOG_FIELDS)
            if new:
                w.writeheader()
            for s in summary["strategies"]:
                w.writerow({"timestamp_utc": now.isoformat(timespec="seconds"), "git_commit": commit,
                            "mode": replay.meta["mode"], "strategy_id": s["strategy_id"],
                            "variant_id": s["variant_id"], "spec_version": s["spec_version"],
                            "spec_sha256": s["spec_sha256"], "sessions": s["sessions"],
                            "first_session": replay.meta["sessions"][0]["date"],
                            "last_session": replay.meta["sessions"][-1]["date"], "trades": s["trades"],
                            "net_pnl": s["net_pnl"], "result_hash": s["result_hash"],
                            "feed": replay.meta["feed"],
                            "data_retrieved_utc": (replay.meta.get("provenance") or {}).get("retrieved_utc")})
    return summary


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run one inspectable research replay and write a journal")
    parser.add_argument("--mode", choices=["historical", "demo"], required=True)
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        summary = run(args.mode, args.config)
    except HistoryError as exc:
        print(f"HISTORICAL run not possible: {exc}\nNo synthetic substitute was used.")
        return 2
    print(f"{summary['mode']} run written to {summary['output_dir']}")
    for s in summary["strategies"]:
        print(f"  {s['strategy_id']}: {s['sessions']} sessions, {s['trades']} trades, "
              f"net {s['net_pnl']:+.2f} (after modeled costs), result hash {s['result_hash']}")
    if summary["mode"] == "DEMO_REPLAY":
        print("DEMO: synthetic data and simulated outcomes. Not evidence of anything about markets.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
