"""SYNTHETIC/static: the boundary between operational health checks and research inputs.

A path string check alone can be bypassed by importing a constant, so these tests check imports and
the exact data read:
1. Research code (everything in trading/ except monitor/, operations/ and dashboard/ display code)
   never imports monitoring or operations code, nor names their stores.
2. Inside trading/operations, only data_health.py opens the monitoring database, and it reads only
   worker liveness/config and the newest bar *time* per symbol: no prices, volumes or bar contents.
3. What the dry run records about data is health only (alive, feed, age, fresh, reasons).
"""

import ast
import re
from pathlib import Path

from trading.operations import gate

ROOT = Path(__file__).resolve().parents[1]
TRADING = ROOT / "trading"
NON_RESEARCH = {"monitor", "operations", "dashboard"}
# Operational tooling at the package top level (not research): the daily start-up procedure, which
# reads readiness and starts the server/runner. Listed explicitly so any other top-level file stays checked.
NON_RESEARCH_FILES = {"startup.py"}
ALLOWED_MONITOR_IMPORTS = {               # module -> names it may import from trading.monitor.*
    "runner.py": {"DB_PATH"},              # path constant, passed to data_health.read only
    "__main__.py": {"SingleInstanceLock"}, # OS lock reused for "one runner at a time"
}


def _imports(src: str):
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            for a in node.names:
                yield a.name, None
        elif isinstance(node, ast.ImportFrom):
            yield node.module or "", {a.name for a in node.names}


def test_research_code_never_imports_monitoring_or_operations():
    for f in TRADING.rglob("*.py"):
        rel = f.relative_to(TRADING).parts
        if rel[0] in NON_RESEARCH or (len(rel) == 1 and rel[0] in NON_RESEARCH_FILES):
            continue
        src = f.read_text(encoding="utf-8")
        for mod, names in _imports(src):
            assert not mod.startswith(("trading.monitor", "trading.operations")), (f, mod)
            if mod == "trading" and names:
                assert not names & {"monitor", "operations"}, (f, names)
        assert "operations.sqlite" not in src and "TradingProject\\operations" not in src, f


def test_operations_imports_from_monitoring_are_limited():
    for f in (TRADING / "operations").glob("*.py"):
        for mod, names in _imports(f.read_text(encoding="utf-8")):
            if mod.startswith("trading.monitor"):
                allowed = ALLOWED_MONITOR_IMPORTS.get(f.name)
                assert allowed is not None and names and names <= allowed, (f.name, mod, names)


def test_only_data_health_opens_the_monitoring_database_and_reads_no_prices():
    for f in (TRADING / "operations").glob("*.py"):
        src = f.read_text(encoding="utf-8")
        if f.name != "data_health.py":
            assert "FROM bars" not in src and "FROM worker" not in src, f.name
    src = (TRADING / "operations" / "data_health.py").read_text(encoding="utf-8")
    selects = re.findall(r'SELECT (.+?) FROM (\w+)', src)
    assert selects, "expected SQL in data_health.py"
    for cols, table in selects:
        assert table in ("worker", "bars"), table
        if table == "bars":
            assert cols.strip() == "MAX(t_utc)", cols          # newest bar time only
        else:
            assert set(c.strip() for c in cols.split(",")) <= {"state", "heartbeat_utc", "config_json"}, cols
    assert "mode=ro" in src                                     # read-only connection


def test_recorded_data_health_has_no_market_values():
    h = gate.DataHealth(True, "iex", {"SPY": {"age_s": 12.0, "fresh": True}}, ("r",))
    d = h.as_dict()
    assert set(d) == {"worker_alive", "feed", "symbols", "reasons"}
    assert all(set(v) == {"age_s", "fresh"} for v in d["symbols"].values())
