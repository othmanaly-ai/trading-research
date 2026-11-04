"""Test isolation: no test may read or write the real review ledger or owner authorization file,
and no test may see a real API key."""

import pytest


@pytest.fixture(autouse=True)
def _isolate_reviewer(tmp_path, monkeypatch):
    from trading.reviewer import budget
    monkeypatch.setattr(budget, "DB_PATH", tmp_path / "reviews" / "reviews.sqlite")
    monkeypatch.setattr(budget, "AUTH_PATH", tmp_path / "MODEL_REVIEW_AUTHORIZATION.json")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
