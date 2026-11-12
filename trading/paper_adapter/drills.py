"""Fresh-process crash drills through the REAL paper adapter over the SIMULATED Alpaca API (offline).

The same drills, crash points and checks as `trading.execution_lab.crashdrill`, but the execution core talks to
`AlpacaPaperOrderAdapter` -> `SimulatedPaperTransport` -> the durable fake broker. Every step is a new process with a
new adapter (it keeps nothing between steps), so recovery must come from the ledger file and broker lookups.
No network (audit hook in every step). Writes pass a guard that accepts ONLY the simulated transport; the real
order-submission guard is untouched and no environment flag is set.

    python -m trading.paper_adapter.drills run-all --out results/execution_lab/paper_sim_drills.json
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from trading.execution_lab import crashdrill

PORT = "paper_adapter+simulated_alpaca"


def port_factory(broker):
    from trading.paper_adapter.alpaca_orders import AlpacaPaperOrderAdapter
    from trading.paper_adapter.simulated import SimulatedPaperTransport, simulated_only_guard
    tr = SimulatedPaperTransport(broker)
    return AlpacaPaperOrderAdapter(tr, guard=simulated_only_guard(tr))


def run_drill(name: str, d: Path) -> dict:
    return crashdrill.run_drill(name, d, port=PORT, module="trading.paper_adapter.drills")


def run_all(out: Path | None = None) -> dict:
    res = {"recorded_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "label": "OFFLINE: fresh-process crash drills via the paper adapter over a SIMULATED Alpaca API "
                    "(models documented responses; not Alpaca's real behaviour)", "drills": []}
    for name in crashdrill.DRILLS:
        with tempfile.TemporaryDirectory(prefix=f"xpaper-{name}-") as td:
            res["drills"].append(run_drill(name, Path(td)))
    res["passed"] = all(c["passed"] for d in res["drills"] for c in d["checks"])
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Crash drills through the paper adapter (offline, simulated Alpaca API)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("step"); s.add_argument("--dir", required=True); s.add_argument("--step", required=True)
    r = sub.add_parser("run-all"); r.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    if a.cmd == "step":
        print(json.dumps(crashdrill.run_step(Path(a.dir), a.step, port_factory), default=str))
        return 0
    res = run_all(Path(a.out) if a.out else None)
    for d in res["drills"]:
        print(f"{'PASS' if all(c['passed'] for c in d['checks']) else 'FAIL'}  {d['drill']}: {d['title']}")
    return 0 if res["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
