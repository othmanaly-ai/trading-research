"""Fresh-process crash recovery for the execution core (LOCAL EXECUTION SIMULATION, fake broker, synthetic data).
Each drill step runs as a separate Python process; crashes are real process exits (os._exit) at named points. State is
rebuilt only from the ledger file and the fake broker's durable file. Each step refuses network access (audit hook)."""

import pytest

from trading.execution_lab import crashdrill


@pytest.mark.parametrize("name", list(crashdrill.DRILLS))
def test_fresh_process_crash_drill(name, tmp_path):
    res = crashdrill.run_drill(name, tmp_path)
    bad = [c for c in res["checks"] if not c["passed"]]
    assert not bad, (bad, res["steps"])
    crashed = [s for s in res["steps"] if s["crash_at"]]
    assert crashed and all(s["exit_code"] == crashdrill.__dict__.get("CRASH", 86) for s in crashed)
    assert (tmp_path / "ledger.sqlite").exists() and (tmp_path / "broker.json").exists()
