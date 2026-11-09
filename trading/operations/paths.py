"""Where Milestone 1 runtime records live: outside OneDrive, under %LOCALAPPDATA%\\TradingProject.

Code and documentation stay in the project. TRADING_OPS_DIR overrides the location (tests use it);
any location inside the project folder or inside a OneDrive folder is refused.
"""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class RuntimeDirRefused(RuntimeError):
    pass


def runtime_dir() -> Path:
    override = os.environ.get("TRADING_OPS_DIR")
    if override:
        p = Path(override)
    else:
        base = os.environ.get("LOCALAPPDATA")
        if not base:
            raise RuntimeDirRefused("LOCALAPPDATA is not set; cannot place records outside OneDrive")
        p = Path(base) / "TradingProject" / "operations"
    check_outside_onedrive(p)
    return p


def check_outside_onedrive(p: Path) -> None:
    resolved = p.resolve()
    parts = [x.lower() for x in resolved.parts]
    if any(x.startswith("onedrive") for x in parts):
        raise RuntimeDirRefused(f"{resolved} is inside a OneDrive folder; refused")
    try:
        resolved.relative_to(PROJECT_ROOT.resolve())
    except ValueError:
        return
    raise RuntimeDirRefused(f"{resolved} is inside the project folder; refused")


def db_path() -> Path:
    return runtime_dir() / "operations.sqlite"


def reports_dir() -> Path:
    return runtime_dir() / "reports"


def kill_switch_path() -> Path:
    return runtime_dir() / "KILL_SWITCH.json"
