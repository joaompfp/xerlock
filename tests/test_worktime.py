"""Working-time arithmetic: the unit P6 measures float, lag and duration in.

A wrong answer here silently corrupts every driving flag, the longest-path trace and
the CPLI, so the cases pin weekends, holidays, 24-hour days and negative spans.
"""

from datetime import datetime as dt

import pytest

from backend.worktime import WorkCalendar

FIVE_DAY = {str(d): [] for d in range(1, 8)}
for d in "23456":  # Monday..Friday
    FIVE_DAY[d] = [{"start": "08:00", "finish": "16:00"}]


@pytest.fixture
def cal():
    # 2026-04-03 (Friday) is a holiday; 2026-04-04 (Saturday) is a worked exception.
    return WorkCalendar(FIVE_DAY, [
        {"date": "2026-04-03", "periods": []},
        {"date": "2026-04-04", "periods": [{"start": "08:00", "finish": "12:00"}]},
    ])


def test_weekend_is_not_working_time(cal):
    # Friday finish to Monday start: 64 clock hours, zero working hours.
    assert cal.working_hours_between(dt(2026, 3, 6, 16), dt(2026, 3, 9, 8)) == 0


def test_overnight_is_not_working_time(cal):
    assert cal.working_hours_between(dt(2026, 3, 9, 16), dt(2026, 3, 10, 8)) == 0


def test_full_week(cal):
    assert cal.working_hours_between(dt(2026, 3, 9, 8), dt(2026, 3, 13, 16)) == 40


def test_partial_days(cal):
    assert cal.working_hours_between(dt(2026, 3, 9, 12), dt(2026, 3, 10, 10)) == 6


def test_negative_span(cal):
    assert cal.working_hours_between(dt(2026, 3, 10, 10), dt(2026, 3, 9, 12)) == -6


def test_holiday_and_worked_exception(cal):
    # Thu 2 Apr 08:00 -> Mon 6 Apr 16:00: Thu 8 + Fri holiday 0 + Sat exception 4 + Mon 8.
    assert cal.working_hours_between(dt(2026, 4, 2, 8), dt(2026, 4, 6, 16)) == 20


def test_twenty_four_hour_calendar():
    allday = WorkCalendar({str(d): [{"start": "00:00", "finish": "00:00"}] for d in range(1, 8)}, [])
    assert allday.working_hours_between(dt(2026, 3, 6, 16), dt(2026, 3, 9, 8)) == 64


def test_add_working_hours_skips_weekend(cal):
    # 5d lag from Friday 16:00 lands on the following Friday 16:00.
    assert cal.add_working_hours(dt(2026, 3, 6, 16), 40) == dt(2026, 3, 13, 16)
    assert cal.add_working_hours(dt(2026, 3, 6, 12), 8) == dt(2026, 3, 9, 12)


def test_add_negative_hours_is_a_lead(cal):
    assert cal.add_working_hours(dt(2026, 3, 9, 12), -8) == dt(2026, 3, 6, 12)


def test_add_then_measure_round_trips(cal):
    t0 = dt(2026, 3, 30, 10)
    t1 = cal.add_working_hours(t0, 37)
    assert cal.working_hours_between(t0, t1) == 37
