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


# ── Snapping: where P6 places a date that logic puts in non-working time ─────

def test_next_work_start_leaves_a_working_instant_alone(cal):
    assert cal.next_work_start(dt(2026, 3, 9, 10)) == dt(2026, 3, 9, 10)
    assert cal.next_work_start(dt(2026, 3, 9, 8)) == dt(2026, 3, 9, 8)


def test_next_work_start_moves_a_period_end_to_the_next_period(cal):
    # A start at Friday 16:00 is no work at all: the first working moment is Monday 08:00.
    assert cal.next_work_start(dt(2026, 3, 6, 16)) == dt(2026, 3, 9, 8)
    assert cal.next_work_start(dt(2026, 3, 7, 12)) == dt(2026, 3, 9, 8)
    assert cal.next_work_start(dt(2026, 3, 9, 0)) == dt(2026, 3, 9, 8)


def test_next_work_finish_keeps_a_period_end(cal):
    # A finish at Friday 16:00 is where a day's work ends: it stays.
    assert cal.next_work_finish(dt(2026, 3, 6, 16)) == dt(2026, 3, 6, 16)
    # In non-working time, P6 moves a forward-pass finish *forward* to the next start.
    assert cal.next_work_finish(dt(2026, 3, 6, 17)) == dt(2026, 3, 9, 8)
    assert cal.next_work_finish(dt(2026, 3, 9, 8)) == dt(2026, 3, 9, 8)


def test_prev_work_finish_moves_a_period_start_back(cal):
    # A late finish at Monday 08:00 means nothing worked on Monday: Friday 16:00.
    assert cal.prev_work_finish(dt(2026, 3, 9, 8)) == dt(2026, 3, 6, 16)
    assert cal.prev_work_finish(dt(2026, 3, 8, 12)) == dt(2026, 3, 6, 16)
    assert cal.prev_work_finish(dt(2026, 3, 9, 16)) == dt(2026, 3, 9, 16)
    assert cal.prev_work_finish(dt(2026, 3, 9, 10)) == dt(2026, 3, 9, 10)


def test_prev_work_start_keeps_a_period_start(cal):
    assert cal.prev_work_start(dt(2026, 3, 9, 8)) == dt(2026, 3, 9, 8)
    assert cal.prev_work_start(dt(2026, 3, 8, 12)) == dt(2026, 3, 6, 16)


def test_snapping_respects_holidays_and_worked_exceptions(cal):
    # Friday 3 April is a holiday; Saturday 4 April is worked 08:00-12:00.
    assert cal.next_work_start(dt(2026, 4, 2, 16)) == dt(2026, 4, 4, 8)
    assert cal.prev_work_finish(dt(2026, 4, 6, 8)) == dt(2026, 4, 4, 12)


def test_snapping_on_a_24_hour_calendar_is_the_identity():
    from backend.worktime import ALL_HOURS
    t = dt(2026, 3, 7, 3, 30)
    assert ALL_HOURS.next_work_start(t) == t
    assert ALL_HOURS.prev_work_finish(t) == t
    assert ALL_HOURS.prev_work_finish(dt(2026, 3, 7)) == dt(2026, 3, 7)


# ── The running totals give exactly what walking day by day gives ──────────────────
# The reference is the original day-by-day walk; the calendar arithmetic skips whole
# days in bulk (see WorkCalendar._cover), and must not change a single answer.

import random
from datetime import date, datetime, timedelta


def _ref_between(cal, t0, t1):
    if t1 < t0:
        return -_ref_between(cal, t1, t0)
    total, d = 0, t0.date()
    while d <= t1.date():
        day0 = datetime.combine(d, datetime.min.time())
        lo = (t0 - day0).total_seconds() / 60 if d == t0.date() else 0
        hi = (t1 - day0).total_seconds() / 60 if d == t1.date() else 1440
        for s, f in cal.spans_on(d):
            total += max(0, min(f, hi) - max(s, lo))
        d += timedelta(days=1)
    return total / 60


def _ref_add(cal, t, hours):
    if hours == 0:
        return t
    remaining, forward, d = abs(hours) * 60, hours > 0, t.date()
    for _ in range(366 * 30):
        day0 = datetime.combine(d, datetime.min.time())
        here = (t - day0).total_seconds() / 60 if d == t.date() else (0 if forward else 1440)
        spans = cal.spans_on(d)
        for s, f in (spans if forward else reversed(spans)):
            if forward:
                s = max(s, here)
                if s >= f:
                    continue
                if f - s >= remaining:
                    return day0 + timedelta(minutes=s + remaining)
            else:
                f = min(f, here)
                if f <= s:
                    continue
                if f - s >= remaining:
                    return day0 + timedelta(minutes=f - remaining)
            remaining -= f - s
        d += timedelta(days=1 if forward else -1)
    return t


def _calendars():
    split = {str(d): [] for d in range(1, 8)}
    for d in "23456":
        split[d] = [{"start": "07:00", "finish": "12:00"}, {"start": "13:00", "finish": "17:30"}]
    nights = {str(d): [{"start": "22:00", "finish": "00:00"}] for d in range(1, 8)}
    rng = random.Random(7)
    holidays = [{"date": (date(2026, 1, 1) + timedelta(days=rng.randrange(700))).isoformat(), "periods": []} for _ in range(40)]
    worked = [{"date": (date(2026, 1, 3) + timedelta(days=7 * rng.randrange(100))).isoformat(),
               "periods": [{"start": "08:00", "finish": "12:00"}]} for _ in range(10)]
    yield WorkCalendar(FIVE_DAY, holidays + worked)
    yield WorkCalendar(split, holidays)
    yield WorkCalendar(nights, [])
    yield WorkCalendar({str(d): [{"start": "00:00", "finish": "00:00"}] for d in range(1, 8)}, [])


def test_bulk_days_match_the_day_by_day_walk():
    rng = random.Random(42)
    for cal in _calendars():
        for _ in range(1000):
            t0 = datetime(2026, 1, 1) + timedelta(minutes=rng.randrange(0, 700 * 1440, 15))
            t1 = t0 + timedelta(minutes=rng.randrange(-200 * 1440, 200 * 1440, 15))
            assert cal.working_hours_between(t0, t1) == pytest.approx(_ref_between(cal, t0, t1), abs=1e-9)
            h = rng.choice([rng.randrange(-2000, 2000), rng.uniform(-900, 900), rng.choice([8, -8, 0.5, -0.5])])
            got, want = cal.add_working_hours(t0, h), _ref_add(cal, t0, h)
            assert abs((got - want).total_seconds()) < 1e-3, (t0, h, got, want)
