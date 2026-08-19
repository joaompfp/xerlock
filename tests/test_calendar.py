"""Calendar decoding.

P6 packs work patterns and holiday exceptions into a single `clndr_data` blob.
Decoding it is what lets a reviewer see stripped holidays and invented workdays —
findings that are invisible to date-based checks — so the parser is pinned here,
including the nested-group shape that once silently produced empty weekdays.
"""

from datetime import date

from backend.main import parse_calendar_data, build_calendars

# The real shape P6 emits: a params group, then a *children group* holding nodes.
BLOB = (
    "(0||CalendarData()("
    "  (0||DaysOfWeek()("
    "    (0||1()())"
    "    (0||2()((0||0(s|08:00|f|12:00)())(0||1(s|13:00|f|17:00)())))"
    "    (0||3()((0||0(s|08:00|f|16:00)())))"
    "    (0||4()())"
    "    (0||5()())"
    "    (0||6()())"
    "    (0||7()())))"
    "  (0||Exceptions()("
    "    (0||0(d|46115)())"
    "    (0||1(d|46183)((0||0(s|08:00|f|16:00)())))))))"
)


def test_weekday_patterns_survive_the_nested_child_group():
    """Regression: the children of a weekday sit inside their own parenthesised
    group after the params. A parser that treats that group as a leaf returns
    zero periods for every day and silently reports a 0-day working week."""
    weekdays, _ = parse_calendar_data(BLOB)
    assert weekdays["1"] == []                       # Sunday, non-working
    assert weekdays["4"] == []                       # explicitly empty
    assert weekdays["2"] == [{"start": "08:00", "finish": "12:00"},
                             {"start": "13:00", "finish": "17:00"}]
    assert weekdays["3"] == [{"start": "08:00", "finish": "16:00"}]
    assert sum(1 for p in weekdays.values() if p) == 2


def test_exception_serials_decode_against_the_p6_epoch():
    """Exception dates are day serials from 1899-12-30 (the Excel epoch)."""
    _, exceptions = parse_calendar_data(BLOB)
    assert [e["date"] for e in exceptions] == ["2026-04-03", "2026-06-10"]
    assert (date.fromisoformat("2026-04-03") - date(1899, 12, 30)).days == 46115


def test_working_exception_is_distinguishable_from_a_holiday():
    """A holiday has no periods; a *working* exception carries them. That
    distinction is the whole point — it exposes a public holiday marked to be
    worked through."""
    _, exceptions = parse_calendar_data(BLOB)
    holiday, worked = exceptions
    assert holiday["periods"] == []
    assert worked["periods"] == [{"start": "08:00", "finish": "16:00"}]


def test_all_weekday_keys_present_even_for_a_blank_blob():
    """Downstream code indexes weekdays 1..7 directly; missing keys would raise."""
    weekdays, exceptions = parse_calendar_data("")
    assert sorted(weekdays) == ["1", "2", "3", "4", "5", "6", "7"]
    assert all(v == [] for v in weekdays.values())
    assert exceptions == []


def test_malformed_blob_degrades_instead_of_raising():
    weekdays, exceptions = parse_calendar_data("(0||CalendarData()((0||DaysOfWeek(")
    assert sorted(weekdays) == ["1", "2", "3", "4", "5", "6", "7"]
    assert exceptions == []


# ── Against the shipped sample ───────────────────────────────────────────────

def test_sample_calendar_register(schedule):
    assert len(schedule.calendars) == 1
    cal = schedule.calendars[0]
    assert cal["clndr_name"] == "Standard 5-Day"
    assert cal["day_hr_cnt"] == 8.0
    assert cal["default_flag"] is True
    working_days = [k for k, v in cal["weekdays"].items() if v]
    assert working_days == ["2", "3", "4", "5", "6"]  # Mon-Fri, P6 keys 1=Sunday


def test_sample_calendar_exceptions_include_a_worked_holiday(schedule):
    exceptions = schedule.calendars[0]["exceptions"]
    assert [e["date"] for e in exceptions] == [
        "2026-04-03", "2026-05-01", "2026-06-10", "2026-12-25"]
    worked = [e for e in exceptions if e["periods"]]
    assert len(worked) == 1 and worked[0]["date"] == "2026-06-10"


def test_exceptions_are_date_sorted(schedule):
    dates = [e["date"] for e in schedule.calendars[0]["exceptions"]]
    assert dates == sorted(dates)


def test_calendar_assignment_counts_match_activities(schedule):
    """assigned_count drives the 'unused calendar' hint; it must agree with the
    activities' own clndr_id."""
    total = sum(c["assigned_count"] for c in schedule.calendars)
    assert total == len(schedule.activities)
    cal = schedule.calendars[0]
    actual = sum(1 for a in schedule.activities if a["clndr_id"] == cal["clndr_id"])
    assert cal["assigned_count"] == actual


def test_build_calendars_without_a_calendar_table():
    assert build_calendars({}, []) == []
