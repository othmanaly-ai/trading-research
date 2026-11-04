"""Test isolation: no test may read or write the real review ledger, owner authorization file or
monitoring database, launch a real monitoring worker process, or see a real API key."""

import pytest


@pytest.fixture(autouse=True)
def _isolate_reviewer(tmp_path, monkeypatch):
    from trading.reviewer import budget
    monkeypatch.setattr(budget, "DB_PATH", tmp_path / "reviews" / "reviews.sqlite")
    monkeypatch.setattr(budget, "AUTH_PATH", tmp_path / "MODEL_REVIEW_AUTHORIZATION.json")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


@pytest.fixture(autouse=True)
def _isolate_monitor(tmp_path, monkeypatch):
    from trading.monitor import control
    from trading.monitor import store as mst
    mdir = tmp_path / "monitoring"
    monkeypatch.setattr(mst, "MONITOR_DIR", mdir)
    monkeypatch.setattr(mst, "DB_PATH", mdir / "monitor.sqlite")
    monkeypatch.setattr(mst, "LOCK_PATH", mdir / "worker.lock")
    monkeypatch.setattr(mst, "LOG_PATH", mdir / "worker.log")
    launched = []

    def fake_spawn(cmd, cwd, env, log_path):            # never starts a real process in tests
        launched.append(cmd)
        return 40000 + len(launched)
    monkeypatch.setattr(control, "SPAWN", fake_spawn)
    return launched
