"""SYNTHETIC: calendar-only checks of the session clock (no network, no market data)."""

from datetime import date, datetime, timedelta, timezone

from trading.operations import schedule as sc


def U(s):
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


def test_regular_day_phases_and_decision_minutes():
    p = sc.plan_for(date(2026, 11, 10))
    assert p.trading_day and not p.early_close
    assert p.open_utc == U("2026-11-10T14:30:00") and p.close_utc == U("2026-11-10T21:00:00")
    assert p.as_dict()["pre_open"]["et"] == "08:45" and p.as_dict()["final_check"]["et"] == "09:25"
    assert p.as_dict()["closing"]["et"] == "15:55" and p.as_dict()["report"]["et"] == "16:20"
    m = p.decision_minutes()
    assert len(m) == 385 and m[0] == p.open_utc and m[-1] == U("2026-11-10T20:54:00")
    for t, ph in [("2026-11-10T13:00:00", sc.BEFORE_PRE_OPEN), ("2026-11-10T13:45:00", sc.PRE_OPEN_CHECKS),
                  ("2026-11-10T14:30:00", sc.DECISION_WINDOW), ("2026-11-10T20:56:00", sc.CLOSING),
                  ("2026-11-10T21:05:00", sc.AFTER_CLOSE), ("2026-11-10T21:20:00", sc.REPORT_DUE)]:
        assert sc.phase_at(p, U(t)) == ph


def test_dst_transitions_move_utc_times_not_et_times():
    before, after = sc.plan_for(date(2026, 3, 6)), sc.plan_for(date(2026, 3, 9))        # spring forward 03-08
    assert before.open_utc.hour == 14 and after.open_utc.hour == 13
    fall_before, fall_after = sc.plan_for(date(2026, 10, 30)), sc.plan_for(date(2026, 11, 2))   # fall back 11-01
    assert fall_before.open_utc.hour == 13 and fall_after.open_utc.hour == 14
    for p in (before, after, fall_before, fall_after):
        assert p.as_dict()["open"]["et"] == "09:30" and p.as_dict()["pre_open"]["et"] == "08:45"


def test_early_close_shifts_closing_and_report():
    p = sc.plan_for(date(2026, 11, 27))
    assert p.early_close and p.as_dict()["close"]["et"] == "13:00"
    assert p.as_dict()["closing"]["et"] == "12:55" and p.as_dict()["report"]["et"] == "13:20"
    assert len(p.decision_minutes()) == 205


def test_holiday_and_weekend_have_no_session():
    for d in (date(2026, 11, 26), date(2026, 11, 7), date(2026, 11, 8)):
        p = sc.plan_for(d)
        assert not p.trading_day and p.decision_minutes() == [] and sc.phase_at(p, U("2026-11-26T15:00:00")) == sc.NO_SESSION


def test_start_classification_late_and_missed():
    p = sc.plan_for(date(2026, 11, 10))
    assert sc.start_classification(p, U("2026-11-10T13:00:00")) == sc.ON_TIME
    assert sc.start_classification(p, U("2026-11-10T14:26:00")) == sc.LATE_PRE_OPEN
    assert sc.start_classification(p, U("2026-11-10T15:05:00")) == sc.LATE_START        # 10:05 ET
    assert sc.start_classification(p, U("2026-11-10T20:58:00")) == sc.AFTER_SESSION


def test_et_date_uses_new_york_not_utc():
    assert sc.et_date(U("2026-11-11T02:00:00")) == date(2026, 11, 10)                  # 21:00 ET the day before
    assert sc.minute_floor(U("2026-11-10T14:31:59.9")) == U("2026-11-10T14:31:00")
    assert sc.plan_for(date(2026, 11, 10)).report_utc - sc.plan_for(date(2026, 11, 10)).close_utc == timedelta(minutes=20)
