"""Order-submission guard.

Every code path that would send an order to a broker must call
``require_order_submission_allowed()`` first. Submission is disabled by
default and is only ever permitted in paper mode.
"""

import os


class OrderSubmissionDisabled(RuntimeError):
    pass


def trading_mode() -> str:
    return os.environ.get("TRADING_MODE", "paper").strip().lower()


def order_submission_enabled() -> bool:
    flag = os.environ.get("ORDER_SUBMISSION_ENABLED", "false").strip().lower()
    return flag == "true" and trading_mode() == "paper"


def require_order_submission_allowed() -> None:
    if trading_mode() != "paper":
        raise OrderSubmissionDisabled(
            f"TRADING_MODE is {trading_mode()!r}; only 'paper' is supported."
        )
    if not order_submission_enabled():
        raise OrderSubmissionDisabled(
            "Order submission is disabled (ORDER_SUBMISSION_ENABLED is not 'true')."
        )
