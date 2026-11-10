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


# ---------------------------------------------------------------- Windows app-container file virtualization
# A process started inside a packaged Windows app (for example a terminal of the Claude desktop app) does not
# write %LOCALAPPDATA% directly: Windows stores its writes in that app's private copy under
# %LOCALAPPDATA%\Packages\<app>\LocalCache\Local\..., and from then on serves that copy to every process inside the
# app. A runner started outside the app writes the real file. The two then silently diverge (confirmed on
# 2026-11-10: the city server read a copy frozen on 2026-11-08 while the runner wrote the real file).


def _under_packages(p: Path) -> bool:
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        return False
    try:
        rel = Path(p).relative_to(Path(os.path.abspath(base)) / "Packages")
    except ValueError:
        return False
    return len(rel.parts) > 2 and rel.parts[1] == "LocalCache"


def private_copies(p: Path) -> list[Path]:
    """App-private copies of `p` that exist under LOCALAPPDATA/Packages/*/LocalCache/Local."""
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        return []
    try:
        rel = Path(os.path.abspath(p)).relative_to(Path(os.path.abspath(base)))
    except ValueError:
        return []
    pk = Path(os.path.abspath(base)) / "Packages"
    if not pk.is_dir():
        return []
    return [c for c in (d / "LocalCache" / "Local" / rel for d in pk.iterdir() if d.is_dir()) if c.exists()]


def view_redirected(p: Path) -> Path | None:
    """The app-private copy this process actually sees when it opens `p`, or None (it sees the real file).
    Inside an app container Windows resolves the path itself to the private copy."""
    p = Path(os.path.abspath(p))
    if not p.exists():
        return None
    try:
        real = Path(os.path.realpath(p))
    except OSError:
        real = p
    if real != p and _under_packages(real):
        return real
    for c in private_copies(p):
        try:
            if os.path.samefile(p, c):
                return c
        except OSError:
            continue
    return None


def writes_redirected(folder: Path) -> bool:
    """Would a file this process creates in `folder` land in an app-private copy? (probe file, removed again)"""
    import uuid
    probe = Path(folder) / f".write-probe-{os.getpid()}-{uuid.uuid4().hex[:8]}"
    try:
        probe.write_text("probe", encoding="utf-8")
    except OSError:
        return False
    try:
        return bool(private_copies(probe)) or view_redirected(probe) is not None
    finally:
        try:
            probe.unlink()
        except OSError:
            pass


def virtualization_problem(folder: Path | None = None) -> str | None:
    """A plain-language reason why this process must not use the runtime records, or None."""
    rd = Path(folder) if folder else runtime_dir()
    seen = view_redirected(rd / "operations.sqlite")
    if seen is not None:
        return (f"this process reads an app-private copy of the dry-run records ({seen}), not the real file the runner "
                "writes. It was started inside a packaged app (for example a Claude desktop terminal). Run operations "
                "commands from a normal PowerShell window.")
    probe_dir = rd
    while not probe_dir.is_dir() and probe_dir.parent != probe_dir:
        probe_dir = probe_dir.parent
    if writes_redirected(probe_dir):
        return ("this process was started inside a packaged app (for example a Claude desktop terminal): Windows would "
                "store its records in that app's private copy, invisible to the runner and the city. Run operations "
                "commands from a normal PowerShell window.")
    return None
