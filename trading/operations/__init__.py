"""Automatic market-session operation, Milestone 1: DRY_RUN only.

This package contains NO order-submission code and must never import any order-capable client.
Entry permission is evaluated and recorded every decision minute, and in DRY_RUN it is always
denied. Runtime records live outside OneDrive (see paths.py). See docs/AUTO_TRADING_ROADMAP.md and
docs/DRY_RUN_ACCEPTANCE.md.
"""

ENVIRONMENT = "DRY_RUN"
