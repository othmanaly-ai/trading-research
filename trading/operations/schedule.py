"""Session clock: phases of one XNYS session, in UTC with ET labels.

Regular day (times shift with early closes; DST is handled by the exchange calendar):
    PRE_OPEN_CHECKS   08:45 -> 09:30 ET   (final pre-open check at 09:25)
    DECISION_WINDOW   09:30 -> 15:55 ET   (one entry-permission decision per minute)
    CLOSING           15:55 -> 16:00 ET   (exposure check: broker evidence of no positions/orders)
    AFTER_CLOSE       16:00 -> 16:20 ET   (waits for the 15-min SIP delay + 5-min margin)
    REPORT_DUE        from 16:20 ET
With no approved strategy, the decision window is the whole session up to the closing phase.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from trading.sessions import sessions_between

ET = ZoneInfo("America/New_York")
PRE_OPEN_LEAD = timedelta(minutes=45)
FINAL_CHECK_LEAD = timedelta(minutes=5)
CLOSING_LEAD = timedelta(minutes=5)
REPORT_DELAY = timedelta(minutes=20)

NO_SESSION, BEFORE_PRE_OPEN, PRE_OPEN_CHECKS = "NO_SESSION", "BEFORE_PRE_OPEN", "PRE_OPEN_CHECKS"
DECISION_WINDOW, CLOSING, AFTER_CLOSE, REPORT_DUE = "DECISION_WINDOW", "CLOSING", "AFTER_CLOSE", "REPORT_DUE"

ON_TIME, LATE_PRE_OPEN, LATE_START, AFTER_SESSION = "ON_TIME", "LATE_PRE_OPEN", "LATE_START", "AFTER_SESSION"


@dataclass(frozen=True)
class SessionPlan:
    date: date
    trading_day: bool
    early_close: bool = False
    open_utc: datetime | None = None
    close_utc: datetime | None = None

    @property
    def preopen_utc(self):
        return self.open_utc - PRE_OPEN_LEAD

    @property
    def final_check_utc(self):
        return self.open_utc - FINAL_CHECK_LEAD

    @property
    def closing_utc(self):
        return self.close_utc - CLOSING_LEAD

    @property
    def report_utc(self):
        return self.close_utc + REPORT_DELAY

    def decision_minutes(self) -> list[datetime]:
        if not self.trading_day:
            return []
        n = int((self.closing_utc - self.open_utc).total_seconds() // 60)
        return [self.open_utc + timedelta(minutes=i) for i in range(n)]

    def as_dict(self) -> dict:
        if not self.trading_day:
            return {"date": str(self.date), "trading_day": False}
        f = lambda t: {"utc": t.isoformat(), "et": t.astimezone(ET).strftime("%H:%M")}
        return {"date": str(self.date), "trading_day": True, "early_close": self.early_close,
                "pre_open": f(self.preopen_utc), "final_check": f(self.final_check_utc), "open": f(self.open_utc),
                "closing": f(self.closing_utc), "close": f(self.close_utc), "report": f(self.report_utc),
                "decision_minutes": len(self.decision_minutes())}


def plan_for(d: date) -> SessionPlan:
    s = sessions_between(d, d)
    if not s:
        return SessionPlan(d, False)
    return SessionPlan(d, True, s[0].early_close, s[0].open_utc, s[0].close_utc)


def et_date(now_utc: datetime) -> date:
    if now_utc.tzinfo is None:
        raise ValueError("now_utc must be timezone-aware")
    return now_utc.astimezone(ET).date()


def phase_at(plan: SessionPlan, now: datetime) -> str:
    if not plan.trading_day:
        return NO_SESSION
    if now < plan.preopen_utc:
        return BEFORE_PRE_OPEN
    if now < plan.open_utc:
        return PRE_OPEN_CHECKS
    if now < plan.closing_utc:
        return DECISION_WINDOW
    if now < plan.close_utc:
        return CLOSING
    if now < plan.report_utc:
        return AFTER_CLOSE
    return REPORT_DUE


def start_classification(plan: SessionPlan, now: datetime) -> str:
    """How a runner start relates to the session. Only ON_TIME can lead to a PASS."""
    if not plan.trading_day:
        return NO_SESSION
    if now < plan.final_check_utc:
        return ON_TIME
    if now < plan.open_utc:
        return LATE_PRE_OPEN
    if now < plan.closing_utc:
        return LATE_START
    return AFTER_SESSION


def minute_floor(now: datetime) -> datetime:
    return now.replace(second=0, microsecond=0)


def utc(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc)
