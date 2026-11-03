from datetime import date, datetime, timezone

import pytest

from trading.sessions import completed_sessions


def utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


def test_thanksgiving_skipped_and_black_friday_early_close():
    # 2026-11-27 18:30 UTC = 13:30 ET, 30 min after the 13:00 ET early close.
    sessions = completed_sessions(utc(2026, 11, 27, 18, 30), 3)
    assert [s.date for s in sessions] == [date(2026, 11, 24), date(2026, 11, 25), date(2026, 11, 27)]
    friday = sessions[-1]
    assert friday.early_close
    assert friday.close_utc == utc(2026, 11, 27, 18, 0)
    assert friday.regular_minutes == 210
    assert not sessions[0].early_close
    assert sessions[0].regular_minutes == 390


def test_session_not_completed_until_data_delay_passes():
    # 21:10 UTC on a normal EST day is 10 minutes after the 16:00 ET close.
    sessions = completed_sessions(utc(2026, 11, 24, 21, 10), 1)
    assert sessions[0].date == date(2026, 11, 23)
    sessions = completed_sessions(utc(2026, 11, 24, 21, 15), 1)
    assert sessions[0].date == date(2026, 11, 24)


def test_dst_changes_utc_open():
    summer = completed_sessions(utc(2026, 7, 1, 23, 0), 1)[0]
    winter = completed_sessions(utc(2026, 12, 1, 23, 0), 1)[0]
    assert summer.open_utc.hour == 13 and summer.open_utc.minute == 30
    assert winter.open_utc.hour == 14 and winter.open_utc.minute == 30


def test_weekend_and_observed_holiday():
    # 2026-07-04 is a Saturday, so the market closes Friday 2026-07-03.
    sessions = completed_sessions(utc(2026, 7, 6, 12, 0), 2)
    assert [s.date for s in sessions] == [date(2026, 7, 1), date(2026, 7, 2)]


def test_requires_timezone_aware_now():
    with pytest.raises(ValueError):
        completed_sessions(datetime(2026, 11, 3, 12), 1)
