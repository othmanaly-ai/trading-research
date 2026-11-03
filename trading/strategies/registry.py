"""Versioned strategy specifications.

Each strategy points at its approved SPEC.md. The file's hash is recorded with
every run and shown in the dashboard, so a silently edited spec is visible.
"""

import hashlib
import re
from pathlib import Path

from trading.strategies.intraday_momentum import Params

PROJECT_ROOT = Path(__file__).resolve().parents[2]

STRATEGIES = {
    "intraday_momentum": {
        "title": "Experiment 001: Intraday momentum",
        "spec_path": "research/001_intraday_momentum/SPEC.md",
        "params_class": Params,
        "target_defined": False,      # v1.1 has a stop and a time exit, no profit target
    },
}


def spec_hash(path: Path) -> str:
    """sha256 of the spec text with line endings normalized (Git may convert them)."""
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def spec_info(strategy: str, params: Params) -> dict:
    from trading.experiment import variant_id     # local import: experiment imports a lot

    entry = STRATEGIES[strategy]
    path = PROJECT_ROOT / entry["spec_path"]
    match = re.search(r"Spec version:\s*(\d+(?:\.\d+)*)", path.read_text(encoding="utf-8"))
    return {
        "strategy": strategy,
        "title": entry["title"],
        "spec_path": entry["spec_path"],
        "spec_version": match.group(1) if match else "unversioned",
        "spec_sha256": spec_hash(path),
        "variant_id": variant_id(params),
        "params": params.as_dict(),
        "target_defined": entry["target_defined"],
    }
