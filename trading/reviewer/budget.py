"""Owner authorization, price table and the review/spend ledger.

Cost enforcement (local, conservative):
- Before a call, the WORST CASE is reserved: authorized max_input_tokens x input price +
  max_output_tokens x output price (output includes thinking tokens; max_tokens caps it).
- The reservation is written in the same SQLite write transaction that checks the per-run and
  monthly caps, so two processes cannot both pass the check.
- After a call the reservation is replaced by the cost computed from the provider's reported
  token usage x this price table. Error responses that the provider does not bill (rejected
  requests, rate limits, overload) are charged 0.
- If the outcome is UNCERTAIN (timeout, dropped connection, 5xx), the full reservation stays
  charged and no automatic repeat happens until the owner acknowledges it.
Limitations: the price table is local and can go stale; the provider invoice is the truth; the
ledger only sees calls made by this code. Set a spend limit in the provider console as well.
"""

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from trading import jobs

AUTH_PATH = jobs.RESEARCH_DIR / "MODEL_REVIEW_AUTHORIZATION.json"
DB_PATH = jobs.PROJECT_ROOT / "data" / "reviews" / "reviews.sqlite"

# USD per 1M tokens (input, output). Source: Anthropic first-party list prices as cached in the
# claude-api reference on 2026-10-06. Re-check https://platform.claude.com pricing before authorizing.
PRICES = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-opus-5-5": (4.00, 20.00),
    "claude-fable-5-1": (10.00, 50.00),
}
PRICE_SOURCE = "Anthropic list prices as cached 2026-10-06 (verify before authorizing)"
SUPPORTED = {"anthropic": tuple(PRICES)}
EFFORTS = ("low", "medium", "high")
# Code-level ceilings: an authorization file cannot exceed these without a code change.
HARD_LIMITS = {"max_input_tokens": 60_000, "max_output_tokens": 16_000, "max_calls_per_run": 2,
               "max_attempts_per_call": 3, "max_usd_per_run": 2.00, "max_usd_per_month": 25.00}
PROPOSED = {"provider": "anthropic", "model": "<owner chooses>", "effort": "medium",
            "max_input_tokens": 30_000, "max_output_tokens": 8_000, "max_calls_per_run": 1,
            "max_attempts_per_call": 3, "max_usd_per_run": 0.50, "max_usd_per_month": 5.00}
REQUIRED = tuple(PROPOSED) + ("authorized_by", "authorized_utc")


class BudgetDenied(Exception):
    pass


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def load_authorization(path: Path | None = None) -> tuple[dict | None, list[str]]:
    """Returns (authorization, problems). Never creates or edits the file."""
    path = path or AUTH_PATH
    if not path.is_file():
        return None, [f"no owner authorization file ({jobs._rel(path)})"]
    try:
        auth = json.loads(path.read_text(encoding="utf-8-sig"))      # tolerate a Notepad byte-order mark
    except (OSError, ValueError) as exc:
        return None, [f"authorization file unreadable: {type(exc).__name__}"]
    if auth.get("revoked_utc") or str(auth.get("status", "")).upper() == "REVOKED":
        return None, [f"paid model calls DISABLED: the owner revoked this authorization at "
                      f"{auth.get('revoked_utc', '?')}; a new explicit owner authorization is required"]
    problems = [f"authorization missing field {k!r}" for k in REQUIRED if k not in auth]
    if problems:
        return None, problems
    if auth["provider"] not in SUPPORTED:
        problems.append(f"provider {auth['provider']!r} not supported (supported: {sorted(SUPPORTED)})")
    elif auth["model"] not in SUPPORTED[auth["provider"]]:
        problems.append(f"model {auth['model']!r} has no price entry (supported: {list(PRICES)})")
    if auth["effort"] not in EFFORTS:
        problems.append(f"effort must be one of {EFFORTS}")
    for k, ceiling in HARD_LIMITS.items():
        v = auth.get(k)
        if not isinstance(v, (int, float)) or isinstance(v, bool) or v <= 0:
            problems.append(f"{k} must be a positive number")
        elif v > ceiling:
            problems.append(f"{k}={v} exceeds the code ceiling {ceiling}")
    exp = auth.get("expires_utc")
    if exp and str(exp) < now():
        problems.append(f"authorization expired at {exp}")
    if not problems and worst_case_usd(auth) > auth["max_usd_per_run"]:
        problems.append(f"one worst-case call costs ${worst_case_usd(auth):.4f}, above max_usd_per_run "
                        f"${auth['max_usd_per_run']:.2f}; lower the token limits or raise the run budget")
    return (None, problems) if problems else (auth, [])


def worst_case_usd(auth: dict) -> float:
    pin, pout = PRICES[auth["model"]]
    return (auth["max_input_tokens"] * pin + auth["max_output_tokens"] * pout) / 1e6


def cost_usd(model: str, usage: dict) -> float:
    pin, pout = PRICES[model]
    return (usage.get("input_tokens", 0) * pin + usage.get("output_tokens", 0) * pout
            + usage.get("cache_creation_input_tokens", 0) * pin * 1.25
            + usage.get("cache_read_input_tokens", 0) * pin * 0.10) / 1e6


_LOCK = threading.Lock()


class ReviewStore:
    def __init__(self, path: Path | None = None):
        path = path or DB_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=10)
        self.db.row_factory = sqlite3.Row
        with _LOCK:
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.executescript("""
            CREATE TABLE IF NOT EXISTS reviews (
                id TEXT PRIMARY KEY, cache_key TEXT, experiment TEXT, provider TEXT, model TEXT,
                prompt_version TEXT, evidence_fingerprint TEXT, package_json TEXT, run_ref TEXT,
                created_utc TEXT, started_utc TEXT, finished_utc TEXT, status TEXT, attempts_json TEXT,
                http_status INTEGER, request_id TEXT, stop_reason TEXT, input_tokens INTEGER,
                output_tokens INTEGER, cache_creation_tokens INTEGER, cache_read_tokens INTEGER,
                cost_usd REAL, cost_basis TEXT, reserved_usd REAL, charged_usd REAL DEFAULT 0, month TEXT,
                error TEXT, response_text TEXT, review_json TEXT, validation_json TEXT,
                acknowledged_utc TEXT, mock INTEGER DEFAULT 0);
            CREATE UNIQUE INDEX IF NOT EXISTS one_completed_review ON reviews(cache_key) WHERE status='completed';
            CREATE TABLE IF NOT EXISTS verifications (
                provider TEXT, model TEXT, prompt_version TEXT, review_id TEXT, verified_utc TEXT,
                PRIMARY KEY (provider, model, prompt_version));
            """)
            self.db.commit()

    def close(self):
        self.db.close()

    def recover_in_flight(self) -> int:
        """A call left in flight by a dead process is UNCERTAIN, never completed; its reservation stays."""
        cur = self.db.execute("UPDATE reviews SET status='uncertain', finished_utc=?, error='process stopped "
                              "during the call; provider may have billed it' WHERE status='in_flight'", (now(),))
        self.db.commit()
        return cur.rowcount

    def get(self, review_id: str):
        r = self.db.execute("SELECT * FROM reviews WHERE id=?", (review_id,)).fetchone()
        return row_dict(r) if r else None

    def cached(self, cache_key: str):
        r = self.db.execute("SELECT * FROM reviews WHERE cache_key=? AND status='completed'", (cache_key,)).fetchone()
        return row_dict(r) if r else None

    def unresolved(self, cache_key: str):
        """Latest billed-but-unusable or uncertain attempt that the owner has not acknowledged."""
        r = self.db.execute("SELECT * FROM reviews WHERE cache_key=? AND status IN ('uncertain','failed') "
                            "AND charged_usd > 0 AND acknowledged_utc IS NULL ORDER BY rowid DESC LIMIT 1",
                            (cache_key,)).fetchone()
        return row_dict(r) if r else None

    def month_spent(self, m: str | None = None) -> float:
        return self.db.execute("SELECT COALESCE(SUM(charged_usd),0) FROM reviews WHERE month=?",
                               (m or month(),)).fetchone()[0]

    def reserve(self, review_id: str, fields: dict, reservation: float, auth: dict, run_spent: float) -> None:
        """Check caps and write the reservation atomically. Raises BudgetDenied."""
        if self.db.in_transaction:
            self.db.commit()
        self.db.execute("BEGIN IMMEDIATE")
        try:
            spent = self.month_spent()
            if run_spent + reservation > auth["max_usd_per_run"] + 1e-12:
                raise BudgetDenied(f"run budget: ${run_spent:.4f} spent + ${reservation:.4f} worst case > "
                                   f"${auth['max_usd_per_run']:.2f}")
            if spent + reservation > auth["max_usd_per_month"] + 1e-12:
                raise BudgetDenied(f"monthly budget: ${spent:.4f} charged this month + ${reservation:.4f} "
                                   f"worst case > ${auth['max_usd_per_month']:.2f}")
            cols = dict(fields, id=review_id, status="in_flight", reserved_usd=reservation, charged_usd=reservation,
                        month=month(), started_utc=now())
            self.db.execute(f"INSERT INTO reviews ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                            list(cols.values()))
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def insert(self, review_id: str, fields: dict) -> None:
        cols = dict(fields, id=review_id)
        self.db.execute(f"INSERT INTO reviews ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                        list(cols.values()))
        self.db.commit()

    def finish(self, review_id: str, **fields) -> None:
        fields.setdefault("finished_utc", now())
        sets = ", ".join(f"{k}=?" for k in fields)
        self.db.execute(f"UPDATE reviews SET {sets} WHERE id=?", [*fields.values(), review_id])
        self.db.commit()

    def acknowledge(self, review_id: str) -> bool:
        cur = self.db.execute("UPDATE reviews SET acknowledged_utc=? WHERE id=? AND status IN ('uncertain','failed') "
                              "AND acknowledged_utc IS NULL", (now(), review_id))
        self.db.commit()
        return cur.rowcount == 1

    def verified(self, provider: str, model: str, prompt_version: str) -> dict | None:
        r = self.db.execute("SELECT * FROM verifications WHERE provider=? AND model=? AND prompt_version=?",
                            (provider, model, prompt_version)).fetchone()
        return dict(r) if r else None

    def mark_verified(self, provider: str, model: str, prompt_version: str, review_id: str) -> None:
        self.db.execute("INSERT OR REPLACE INTO verifications VALUES (?,?,?,?,?)",
                        (provider, model, prompt_version, review_id, now()))
        self.db.commit()

    def recent(self, limit: int = 20) -> list[dict]:
        return [row_dict(r, light=True) for r in
                self.db.execute("SELECT * FROM reviews ORDER BY rowid DESC LIMIT ?", (limit,))]


def row_dict(r, light: bool = False) -> dict:
    d = dict(r)
    for k in ("attempts_json", "review_json", "validation_json", "package_json"):
        d[k.replace("_json", "")] = json.loads(d.pop(k)) if d.get(k) else None
    if light:
        d.pop("package", None)
        d.pop("response_text", None)
    d["mock"] = bool(d.get("mock"))
    return d
