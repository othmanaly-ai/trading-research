"""NYSE trading sessions from an exchange calendar (holidays and early closes)."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import exchange_calendars as xcals
import pandas as pd

CALENDAR_NAME = "XNYS"
MARKET_TZ = "America/New_York"

# Alpaca's free (Basic) plan withholds the latest 15 minutes of SIP data, so a
# session only counts as "completed" once its close is at least this old.
DATA_DELAY = timedelta(minutes=15)


@dataclass(frozen=True)
class Session:
    date: date
    open_utc: datetime
    close_utc: datetime
    early_close: bool

    @property
    def regular_minutes(self) -> int:
        return int((self.close_utc - self.open_utc).total_seconds() // 60)


def _calendar():
    return xcals.get_calendar(CALENDAR_NAME)


def _session(cal, s: pd.Timestamp, early: set) -> Session:
    return Session(
        date=s.date(),
        open_utc=cal.session_open(s).to_pydatetime().astimezone(timezone.utc),
        close_utc=cal.session_close(s).to_pydatetime().astimezone(timezone.utc),
        early_close=s in early,
    )


def sessions_between(start: date, end: date) -> list[Session]:
    """All sessions from start to end inclusive, in order."""
    cal = _calendar()
    early = set(cal.early_closes)
    return [_session(cal, s, early) for s in cal.sessions_in_range(str(start), str(end))]


def completed_sessions(now_utc: datetime, count: int) -> list[Session]:
    """The last `count` sessions whose close is at least DATA_DELAY before now_utc."""
    if now_utc.tzinfo is None:
        raise ValueError("now_utc must be timezone-aware")
    cal = _calendar()
    cutoff = pd.Timestamp(now_utc).tz_convert("UTC") - DATA_DELAY
    start = (cutoff - pd.Timedelta(days=count * 3 + 14)).tz_localize(None).normalize()
    end = cutoff.tz_localize(None).normalize()
    sessions = cal.sessions_in_range(max(start, cal.first_session), min(end, cal.last_session))
    closes = cal.closes.loc[sessions]
    done = [s for s in sessions if closes.loc[s] <= cutoff]
    if len(done) < count:
        raise ValueError(f"only {len(done)} completed sessions found")
    early = set(cal.early_closes)
    return [_session(cal, s, early) for s in done[-count:]]
