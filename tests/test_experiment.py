"""Period lock, variant budget and logging, on SYNTHETIC fixtures with short
made-up periods. Not market evidence."""

import csv
import json
from dataclasses import replace
from datetime import date

import pytest

from trading.experiment import (
    LOG_FIELDS, ExperimentRefused, run_experiment, variant_id,
)
from trading.experiment_lock import LockMismatch, build_lock
from trading.risk import RiskLimits
from trading.sessions import sessions_between
from trading.strategies.intraday_momentum import Params

from tests.synthetic import make_days

PERIODS = {
    "development": (date(2026, 9, 1), date(2026, 9, 30)),
    "validation": (date(2026, 10, 1), date(2026, 10, 30)),
    "final": (date(2026, 11, 2), date(2026, 11, 30)),
}


@pytest.fixture(scope="module")
def days():
    return make_days(sessions_between(date(2026, 6, 1), date(2026, 12, 15)), seed=5)


@pytest.fixture
def lock_path(tmp_path):
    path = tmp_path / "LOCK.json"
    path.write_text(json.dumps(build_lock(periods=PERIODS, history_root=tmp_path / "none",
                                          inspection_log=tmp_path / "none.csv")))
    return path


@pytest.fixture
def run(days, tmp_path, lock_path):
    def _run(period, **kw):
        return run_experiment(days, period, n_random=200, log_dir=tmp_path,
                              results_dir=tmp_path / "results", periods=PERIODS,
                              lock_path=lock_path, **kw)
    return _run


def attempts(tmp_path):
    with (tmp_path / "experiment_attempts.csv").open(newline="") as f:
        return list(csv.DictReader(f))


def test_missing_lock_refused_and_logged(days, tmp_path):
    with pytest.raises(LockMismatch, match="no experiment lock"):
        run_experiment(days, "development", n_random=10, log_dir=tmp_path, results_dir=tmp_path / "r",
                       periods=PERIODS, lock_path=tmp_path / "absent.json")
    assert attempts(tmp_path)[-1]["status"] == "refused"


def test_changed_definition_refused(days, tmp_path, lock_path):
    with pytest.raises(LockMismatch, match="risk_limits"):
        run_experiment(days, "development", limits=RiskLimits(max_drawdown=0.10), n_random=10,
                       log_dir=tmp_path, results_dir=tmp_path / "r", periods=PERIODS, lock_path=lock_path)
    assert "risk_limits" in attempts(tmp_path)[-1]["detail"]


def test_experiment_id_changes_with_limits_and_primary_params():
    from trading.experiment_lock import experiment_id, fingerprint
    from trading.risk import OWNER_BASELINE_2026_11_03
    from trading.strategies.intraday_momentum import Params
    ids = {experiment_id(fingerprint(RiskLimits())),
           experiment_id(fingerprint(OWNER_BASELINE_2026_11_03, primary=Params(long_only=False))),
           experiment_id(fingerprint(OWNER_BASELINE_2026_11_03, primary=Params(long_only=True)))}
    assert len(ids) == 3


def test_attempts_ledger_records_completed_and_refused(run, tmp_path):
    report = run("development")
    with pytest.raises(ExperimentRefused):
        run("final")
    rows = attempts(tmp_path)
    assert [r["status"] for r in rows] == ["completed", "refused"]
    assert rows[0]["experiment_id"] == report["experiment_id"]
    assert report["held_out_inspection"] == {"validation": 0, "final": 0}


def read_log(tmp_path):
    with (tmp_path / "variants.csv").open(newline="") as f:
        return list(csv.DictReader(f))


def test_final_locked_without_flag(run):
    with pytest.raises(ExperimentRefused, match="locked"):
        run("final")


def test_validation_requires_development_first(run):
    with pytest.raises(ExperimentRefused, match="development before validation"):
        run("validation")


def test_full_sequence_logs_and_flags_reuse(run, tmp_path):
    dev = run("development")
    assert dev["risk_placeholder"] is False                 # owner limits (v1.3)
    assert dev["random_direction"]["method"].startswith("random long/flat")
    assert set(dev["results_by_cost"]) == {"base", "stress", "severe"}
    assert set(dev["pass_rules"]) == {"1_positive_after_costs", "2_beats_baselines",
                                      "3_drawdown_within_limit", "4_survives_top10_removal",
                                      "5_neighbors_same_sign"}
    run("validation")
    first = run("final", final_test=True)
    second = run("final", final_test=True)
    assert first["final_test_reused"] is False and second["final_test_reused"] is True
    rows = read_log(tmp_path)
    assert [r["period"] for r in rows] == ["development", "validation", "final", "final"]
    saved = json.loads((tmp_path / "results" / f"{second['run_id']}.json").read_text())
    assert saved["final_test_reused"] is True


def test_variant_budget_enforced(run, tmp_path):
    with (tmp_path / "variants.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        w.writeheader()
        for k in range(10):
            w.writerow({"variant_id": variant_id(replace(Params(), sizing_mult=1 + k)),
                        "period": "development"})
    with pytest.raises(ExperimentRefused, match="budget"):
        run("development")
    # Re-running an already-logged variant is not a new variant.
    run("development", params=replace(Params(), sizing_mult=1))


def test_variant_id_changes_with_params():
    assert variant_id(Params()) != variant_id(replace(Params(), stop_mult=1.5))
    assert variant_id(Params()) == variant_id(Params())


def test_closed_experiment_refuses_further_runs(run, tmp_path):
    (tmp_path / "STATUS.json").write_text(json.dumps({"status": "CLOSED: failed at development"}))
    with pytest.raises(ExperimentRefused, match="closed"):
        run("development")
    assert attempts(tmp_path)[-1]["status"] == "refused"
