"""The Microsoft Project XML (MSPDI) reader, one rule per test, on minimal synthetic
documents. Field codes and units follow Microsoft's MSPDI schema as MPXJ reads it;
docs/METHODOLOGY.md ("Microsoft Project files") is the prose version of these rules.
"""

import json

import pytest

from backend import mspdi
from backend.mspdi import iso_duration_hours, parse_mspdi, tenths_of_minutes_hours
from backend.schedule import parse_schedule
from tests.conftest import REPO_ROOT

SAMPLE_XML = REPO_ROOT / "examples" / "sample-schedule.xml"


def task(uid, name="T", start="2026-03-02T08:00:00", finish="2026-03-02T16:00:00", duration="PT8H0M0S",
         level=1, links=(), **fields):
    """One <Task>. `links` are (pred_uid, type_code, lag_tenths, lag_format)."""
    f = {"Active": 1, "Manual": 0, "IsNull": 0, "OutlineLevel": level, "Summary": 0, "Milestone": 0,
         "ConstraintType": 0, "Critical": 0, "TotalSlack": 0, "FreeSlack": 0, "PercentComplete": 0}
    f.update(fields)
    body = "".join(f"<{k}>{v}</{k}>" for k, v in f.items() if v is not None)
    rels = "".join(
        f"<PredecessorLink><PredecessorUID>{p}</PredecessorUID><Type>{t}</Type><LinkLag>{lag}</LinkLag>"
        f"<LagFormat>{fmt}</LagFormat></PredecessorLink>" for p, t, lag, fmt in links)
    return (f"<Task><UID>{uid}</UID><ID>{uid}</ID><Name>{name}</Name><Start>{start}</Start><Finish>{finish}</Finish>"
            f"<Duration>{duration}</Duration>{body}{rels}</Task>")


WEEK_5DAY = "".join(
    f"<WeekDay><DayType>{d}</DayType><DayWorking>{0 if d in (1, 7) else 1}</DayWorking>"
    + ("" if d in (1, 7) else "<WorkingTimes><WorkingTime><FromTime>08:00:00</FromTime><ToTime>16:00:00</ToTime></WorkingTime></WorkingTimes>")
    + "</WeekDay>" for d in range(1, 8))


def calendar(uid=1, name="Standard", weekdays=WEEK_5DAY, base=-1, extra=""):
    return (f"<Calendar><UID>{uid}</UID><Name>{name}</Name><IsBaseCalendar>{1 if base == -1 else 0}</IsBaseCalendar>"
            f"<BaseCalendarUID>{base}</BaseCalendarUID><WeekDays>{weekdays}</WeekDays>{extra}</Calendar>")


def doc(tasks="", project="", calendars=None, resources="", assignments=""):
    cals = calendar() if calendars is None else calendars
    return (f'<?xml version="1.0" encoding="UTF-8"?><Project xmlns="http://schemas.microsoft.com/project">'
            f"<SaveVersion>14</SaveVersion><Name>t.xml</Name><Title>Demo</Title><CalendarUID>1</CalendarUID>"
            f"<MinutesPerDay>480</MinutesPerDay><MinutesPerWeek>2400</MinutesPerWeek><CriticalSlackLimit>0</CriticalSlackLimit>"
            f"<StatusDate>2026-03-02T08:00:00</StatusDate>{project}"
            f"<Calendars>{cals}</Calendars><Tasks>{tasks}</Tasks><Resources>{resources}</Resources>"
            f"<Assignments>{assignments}</Assignments></Project>").encode()


def parse(**kw):
    return parse_mspdi(doc(**kw))


def act(data, uid):
    return next(a for a in data["activities"] if a["task_id"] == uid)


# ── Units ────────────────────────────────────────────────────────────────────

def test_iso_durations_are_hours():
    assert iso_duration_hours("PT8H0M0S") == 8
    assert iso_duration_hours("PT1H30M0S") == 1.5
    assert iso_duration_hours("P2D") == 48          # MPXJ: 24 h per day
    assert iso_duration_hours("PT0H0M0S") == 0
    assert iso_duration_hours("garbage") is None    # Project ignores malformed values
    assert iso_duration_hours(None) is None


def test_slack_and_lag_fields_are_tenths_of_a_minute():
    assert tenths_of_minutes_hours("4800") == 8
    assert tenths_of_minutes_hours("-4800") == -8
    assert tenths_of_minutes_hours("") is None


# ── Links ────────────────────────────────────────────────────────────────────

def test_link_type_codes_map_to_p6_relationship_types():
    links = [(1, 0, 0, 7), (2, 1, 0, 7), (3, 2, 0, 7), (4, 3, 0, 7)]
    d = parse(tasks=task(1) + task(2) + task(3) + task(4) + task(5, links=links))
    assert [p["type"] for p in act(d, 5)["predecessors"]] == ["PR_FF", "PR_FS", "PR_SF", "PR_SS"]


def test_lag_is_tenths_of_a_minute_in_working_time():
    d = parse(tasks=task(1) + task(2, links=[(1, 1, 4800, 7)]))
    p = act(d, 2)["predecessors"][0]
    assert p["lag_hrs"] == 8 and p["lag_elapsed"] is False and p["lag_pct"] is None


def test_percent_lag_is_a_share_of_the_predecessor_duration():
    # LagFormat 19 = %, and LinkLag then holds the percentage itself (MPXJ readPredecessor).
    d = parse(tasks=task(1, duration="PT40H0M0S") + task(2, links=[(1, 1, 50, 19)]))
    p = act(d, 2)["predecessors"][0]
    assert p["lag_pct"] == 50 and p["lag_hrs"] == 20


def test_elapsed_lag_counts_on_the_24_hour_clock():
    """A 24 h elapsed lag (LagFormat 6, eh) from Friday 16:00 lands Saturday 16:00, so a
    successor starting Monday 08:00 has zero working-time free float and is driven. The
    same 24 h as a working lag would land Wednesday 16:00, after the successor."""
    pred = task(1, start="2026-03-02T08:00:00", finish="2026-03-06T16:00:00", duration="PT40H0M0S")
    elapsed = parse(tasks=pred + task(2, start="2026-03-09T08:00:00", links=[(1, 1, 14400, 6)]))
    working = parse(tasks=pred + task(2, start="2026-03-09T08:00:00", links=[(1, 1, 14400, 5)]))
    e, w = act(elapsed, 2)["predecessors"][0], act(working, 2)["predecessors"][0]
    assert e["lag_elapsed"] is True and e["lag_hrs"] == 24 and e["driving"] is True
    assert w["lag_elapsed"] is False and w["driving"] is False and w["free_float_hrs"] < 0


def test_links_on_summary_tasks_are_reported_not_scheduled():
    tasks = (task(1, "Phase A", level=1, Summary=1) + task(2, level=2)
             + task(3, "Phase B", level=1, Summary=1, links=[(1, 1, 0, 7)]) + task(4, level=2, links=[(1, 1, 0, 7)]))
    d = parse(tasks=tasks)
    assert act(d, 4)["predecessors"] == []
    assert [(s["pred_id"], s["succ_id"], s["succ_is_summary"]) for s in d["project"]["summary_links"]] == [(1, 3, True), (1, 4, False)]


def test_cross_project_links_are_left_out_with_a_warning():
    tasks = task(1) + ("<Task><UID>2</UID><ID>2</ID><Name>T</Name><Start>2026-03-02T08:00:00</Start><Finish>2026-03-02T16:00:00</Finish>"
                       "<Duration>PT8H0M0S</Duration><OutlineLevel>1</OutlineLevel><PredecessorLink><PredecessorUID>99</PredecessorUID>"
                       "<Type>1</Type><CrossProject>1</CrossProject><CrossProjectName>other.mpp\\3</CrossProjectName></PredecessorLink></Task>")
    d = parse(tasks=tasks)
    assert act(d, 2)["predecessors"] == []
    assert any("other project files" in w for w in d["warnings"])


# ── Constraints, milestones, status ─────────────────────────────────────────

@pytest.mark.parametrize("code,expected", [
    (0, None), (1, "CS_ALAP"), (2, "CS_MANDSTART"), (3, "CS_MANDFIN"),
    (4, "CS_MSOA"), (5, "CS_MSOB"), (6, "CS_MEOA"), (7, "CS_MEOB"),
])
def test_constraint_types_map_to_p6_constraints(code, expected):
    d = parse(tasks=task(1, ConstraintType=code, ConstraintDate="2026-04-01T08:00:00"))
    a = act(d, 1)
    assert a["cstr_type"] == expected
    # ASAP has no constraint; ALAP has no date in P6 either.
    assert a["cstr_date"] == (None if code in (0, 1) else "2026-04-01 08:00:00")
    assert a["cstr_type2"] is None


def test_zero_duration_milestone_is_a_finish_milestone():
    d = parse(tasks=task(1, duration="PT0H0M0S", finish="2026-03-02T08:00:00", Milestone=1)
              + task(2, duration="PT40H0M0S", Milestone=1))
    assert act(d, 1)["task_type"] == "TT_FinMile"
    # Project lets a task with a duration be shown as a milestone; it is still a task.
    assert act(d, 2)["task_type"] == "TT_Task"
    assert d["project"]["total_milestones"] == 1


def test_status_is_derived_from_actual_dates():
    d = parse(tasks=task(1) + task(2, ActualStart="2026-02-20T08:00:00")
              + task(3, ActualStart="2026-02-20T08:00:00", ActualFinish="2026-02-27T16:00:00"))
    assert [act(d, i)["status"] for i in (1, 2, 3)] == ["TK_NotStart", "TK_Active", "TK_Complete"]
    assert act(d, 3)["act_end"] == "2026-02-27 16:00:00"
    assert (d["project"]["total_not_started"], d["project"]["total_active"], d["project"]["total_complete"]) == (1, 1, 1)


def test_percent_complete_is_projects_duration_percent():
    d = parse(tasks=task(1, PercentComplete=40, PhysicalPercentComplete=10))
    assert act(d, 1)["pct_complete"] == 40 and act(d, 1)["pct_complete_type"] == "CP_Drtn"


# ── Stored values ─────────────────────────────────────────────────────────────

def test_dates_float_and_critical_flag_are_read_not_recomputed():
    d = parse(tasks=task(1, start="2026-03-02T08:00:00", finish="2026-03-06T16:00:00", duration="PT40H0M0S",
                         LateStart="2026-03-09T08:00:00", LateFinish="2026-03-13T16:00:00",
                         TotalSlack=24000, FreeSlack=12000, Critical=1))
    a = act(d, 1)
    assert (a["early_start"], a["early_end"]) == ("2026-03-02 08:00:00", "2026-03-06 16:00:00")
    assert (a["late_start"], a["late_end"]) == ("2026-03-09 08:00:00", "2026-03-13 16:00:00")
    assert a["total_float_hrs"] == 40 and a["free_float_hrs"] == 20
    # Project's own flag, whatever the float says: it is the file's claim, cross-checkable.
    assert a["is_critical"] is True and a["driving_path_flag"] is False


def test_missing_total_slack_is_unknown_not_zero():
    d = parse(tasks=task(1, TotalSlack=None))
    assert act(d, 1)["total_float_hrs"] is None


def test_baseline_0_gives_the_planned_dates():
    bl = "<Baseline><Number>1</Number><Start>2026-01-01T08:00:00</Start><Finish>2026-01-02T16:00:00</Finish></Baseline>" \
         "<Baseline><Number>0</Number><Start>2026-02-02T08:00:00</Start><Finish>2026-02-03T16:00:00</Finish></Baseline>"
    d = parse(tasks=task(1).replace("</Task>", bl + "</Task>") + task(2))
    assert (act(d, 1)["target_start"], act(d, 1)["target_end"]) == ("2026-02-02 08:00:00", "2026-02-03 16:00:00")
    assert act(d, 2)["target_start"] is None


def test_manual_and_deadline_are_carried_as_optional_fields():
    d = parse(tasks=task(1, Manual=1, Deadline="2026-06-30T16:00:00") + task(2))
    assert act(d, 1)["manual"] is True and act(d, 1)["deadline"] == "2026-06-30 16:00:00"
    assert act(d, 2)["manual"] is False and act(d, 2)["deadline"] is None


# ── Populations ───────────────────────────────────────────────────────────────

def test_inactive_tasks_are_excluded_and_counted():
    d = parse(tasks=task(1) + task(2, Active=0) + task(3, links=[(2, 1, 0, 7), (1, 1, 0, 7)]))
    assert [a["task_id"] for a in d["activities"]] == [1, 3]
    assert [p["task_id"] for p in act(d, 3)["predecessors"]] == [1]
    assert d["project"]["inactive_activities"] == 1
    assert d["project"]["total_activities"] == 2


def test_null_tasks_are_skipped():
    d = parse(tasks=task(1) + "<Task><UID>2</UID><ID>2</ID><IsNull>1</IsNull></Task>")
    assert [a["task_id"] for a in d["activities"]] == [1]


# ── WBS ───────────────────────────────────────────────────────────────────────

def test_outline_levels_build_the_wbs_and_summary_tasks_are_nodes():
    tasks = (task(0, "Demo", level=0, Summary=1) + task(10, "Phase A", level=1, Summary=1, WBS="1")
             + task(11, "Area 1", level=2, Summary=1, WBS="1.1") + task(1, level=3) + task(2, level=3)
             + task(20, "Phase B", level=1, Summary=1, WBS="2") + task(3, level=2))
    d = parse(tasks=tasks)
    assert [a["task_id"] for a in d["activities"]] == [1, 2, 3]
    assert d["project"]["total_wbs"] == 4
    root = d["wbs_tree"][0]
    assert root["wbs_id"] == 0 and root["level"] == 0 and [c["wbs_name"] for c in root["children"]] == ["Phase A", "Phase B"]
    assert root["children"][0]["children"][0]["activity_count"] == 2
    assert act(d, 1)["wbs_path"] == "Phase A / Area 1" and act(d, 3)["wbs_path"] == "Phase B"
    assert root["children"][0]["wbs_short_name"] == "1"


def test_a_file_without_a_project_summary_task_gets_the_project_as_root():
    d = parse(tasks=task(10, "Phase A", level=1, Summary=1) + task(1, level=2) + task(2, level=1))
    root = d["wbs_tree"][0]
    assert root["wbs_id"] == 0 and root["wbs_name"] == "Demo"
    assert act(d, 2)["wbs_id"] == 0 and act(d, 1)["wbs_path"] == "Phase A"


# ── Project, data date, options ──────────────────────────────────────────────

def test_status_date_is_the_data_date_and_its_absence_is_said():
    d = parse(tasks=task(1))
    assert d["project"]["data_date"] == "2026-03-02 08:00:00" and d["warnings"] == []
    nd = parse_mspdi(doc(tasks=task(1)).replace(b"<StatusDate>2026-03-02T08:00:00</StatusDate>", b""))
    assert nd["project"]["data_date"] is None
    assert any("status date" in w for w in nd["warnings"])
    assert nd["project"]["cpli"] is None


def test_project_fields_and_options():
    d = parse(tasks=task(1), project="<HonorConstraints>1</HonorConstraints><MultipleCriticalPaths>1</MultipleCriticalPaths>")
    p = d["project"]
    assert p["source_format"] == "mspdi" and p["proj_short_name"] == "Demo"
    assert p["schedule_options"]["present"] is True
    assert p["schedule_options"]["lag_calendar"] == "rcal_Successor"
    assert p["schedule_options"]["critical_type"] == "CT_TotFloat" and p["schedule_options"]["critical_float_hrs"] == 0
    assert p["msp_options"]["honor_constraints"] is True and p["msp_options"]["multiple_critical_paths"] is True
    assert p["msp_options"]["minutes_per_day"] == 480
    assert act(d, 1)["calendar_hrs_per_day"] == 8


def test_critical_slack_limit_is_in_days_of_the_project_day():
    d = parse_mspdi(doc(tasks=task(1)).replace(b"<CriticalSlackLimit>0<", b"<CriticalSlackLimit>2<").replace(b"<MinutesPerDay>480<", b"<MinutesPerDay>600<"))
    assert d["project"]["schedule_options"]["critical_float_hrs"] == 20
    assert act(d, 1)["calendar_hrs_per_day"] == 10


def test_recalculation_is_reported_as_not_available():
    d = parse(tasks=task(1))
    r = d["project"]["recalculation"]
    assert r["supported"] is False and r["reason"] == mspdi.RECALC_UNAVAILABLE
    assert r["compared"] == 0 and r["differences"] == []
    assert d["project"]["critical_path_test"] is None


def test_resources_come_from_assignments():
    res = "<Resource><UID>0</UID></Resource><Resource><UID>5</UID><Name>Crane</Name></Resource>"
    asg = "<Assignment><UID>1</UID><TaskUID>1</TaskUID><ResourceUID>5</ResourceUID></Assignment>" \
          "<Assignment><UID>2</UID><TaskUID>2</TaskUID><ResourceUID>-65535</ResourceUID></Assignment>"
    d = parse(tasks=task(1) + task(2), resources=res, assignments=asg)
    assert d["project"]["has_resources"] is True
    assert act(d, 1)["resource_names"] == ["Crane"] and act(d, 2)["resource_names"] == []


# ── Calendars ─────────────────────────────────────────────────────────────────

def test_weekdays_decode_to_the_calendar_model():
    d = parse(tasks=task(1))
    c = d["calendars"][0]
    assert c["clndr_id"] == "1" and c["default_flag"] is True and c["clndr_type"] == "CA_Base"
    assert c["weekdays"]["1"] == [] and c["weekdays"]["2"] == [{"start": "08:00", "finish": "16:00"}]
    assert c["day_hr_cnt"] == 8 and c["week_hr_cnt"] == 40 and c["assigned_count"] == 1


def test_exceptions_list_single_days_and_ranges():
    exc = ("<Exceptions>"
           "<Exception><TimePeriod><FromDate>2026-04-03T00:00:00</FromDate><ToDate>2026-04-03T23:59:00</ToDate></TimePeriod>"
           "<Occurrences>1</Occurrences><Name>Good Friday</Name><Type>1</Type><DayWorking>0</DayWorking></Exception>"
           "<Exception><TimePeriod><FromDate>2026-06-06T00:00:00</FromDate><ToDate>2026-06-07T23:59:00</ToDate></TimePeriod>"
           "<Occurrences>2</Occurrences><Name>Weekend shift</Name><Type>1</Type><DayWorking>1</DayWorking>"
           "<WorkingTimes><WorkingTime><FromTime>09:00:00</FromTime><ToTime>13:00:00</ToTime></WorkingTime></WorkingTimes></Exception>"
           "</Exceptions>")
    d = parse(tasks=task(1), calendars=calendar(extra=exc))
    assert d["calendars"][0]["exceptions"] == [
        {"date": "2026-04-03", "periods": []},
        {"date": "2026-06-06", "periods": [{"start": "09:00", "finish": "13:00"}]},
        {"date": "2026-06-07", "periods": [{"start": "09:00", "finish": "13:00"}]},
    ]


def test_weekly_recurring_exception_is_expanded():
    # Type 6, DaysOfWeek bitmap 2 = Monday, every 2 weeks, from Mon 5 Jan 2026 to 31 Jan.
    exc = ("<Exceptions><Exception><TimePeriod><FromDate>2026-01-05T00:00:00</FromDate><ToDate>2026-01-31T23:59:00</ToDate></TimePeriod>"
           "<Occurrences>2</Occurrences><Type>6</Type><Period>2</Period><DaysOfWeek>2</DaysOfWeek><DayWorking>0</DayWorking></Exception></Exceptions>")
    d = parse(tasks=task(1), calendars=calendar(extra=exc))
    assert [e["date"] for e in d["calendars"][0]["exceptions"]] == ["2026-01-05", "2026-01-19"]


def test_monthly_relative_exception_is_expanded():
    # Type 5: the MonthPosition 0 (first) MonthItem 3 (Monday) of every month, Jan-Mar 2026.
    exc = ("<Exceptions><Exception><TimePeriod><FromDate>2026-01-01T00:00:00</FromDate><ToDate>2026-03-31T23:59:00</ToDate></TimePeriod>"
           "<Type>5</Type><Period>1</Period><MonthItem>3</MonthItem><MonthPosition>0</MonthPosition><DayWorking>0</DayWorking></Exception></Exceptions>")
    d = parse(tasks=task(1), calendars=calendar(extra=exc))
    assert [e["date"] for e in d["calendars"][0]["exceptions"]] == ["2026-01-05", "2026-02-02", "2026-03-02"]


def test_yearly_absolute_exception_is_expanded():
    # Type 2: Month 11 (0-based: December) MonthDay 25, 2026-2027.
    exc = ("<Exceptions><Exception><TimePeriod><FromDate>2026-01-01T00:00:00</FromDate><ToDate>2027-12-31T23:59:00</ToDate></TimePeriod>"
           "<Type>2</Type><Month>11</Month><MonthDay>25</MonthDay><DayWorking>0</DayWorking></Exception></Exceptions>")
    d = parse(tasks=task(1), calendars=calendar(extra=exc))
    assert [e["date"] for e in d["calendars"][0]["exceptions"]] == ["2026-12-25", "2027-12-25"]


def test_legacy_daytype_0_exceptions_are_read_when_no_exceptions_list():
    legacy = ("<WeekDay><DayType>0</DayType><DayWorking>0</DayWorking><TimePeriod><FromDate>2026-05-01T00:00:00</FromDate>"
              "<ToDate>2026-05-01T23:59:59</ToDate></TimePeriod></WeekDay>")
    d = parse(tasks=task(1), calendars=calendar(weekdays=WEEK_5DAY + legacy))
    assert d["calendars"][0]["exceptions"] == [{"date": "2026-05-01", "periods": []}]


def test_derived_calendar_inherits_its_base():
    exc = ("<Exceptions><Exception><TimePeriod><FromDate>2026-05-01T00:00:00</FromDate><ToDate>2026-05-01T23:59:00</ToDate></TimePeriod>"
           "<Type>1</Type><DayWorking>0</DayWorking></Exception></Exceptions>")
    saturday = "<WeekDay><DayType>7</DayType><DayWorking>1</DayWorking><WorkingTimes><WorkingTime><FromTime>08:00:00</FromTime><ToTime>12:00:00</ToTime></WorkingTime></WorkingTimes></WeekDay>"
    cals = calendar(extra=exc) + calendar(uid=2, name="Crew", weekdays=saturday, base=1)
    d = parse(tasks=task(1, CalendarUID=2), calendars=cals)
    crew = next(c for c in d["calendars"] if c["clndr_id"] == "2")
    assert crew["clndr_type"] == "CA_Rsrc" and crew["default_flag"] is False
    assert crew["weekdays"]["2"] == [{"start": "08:00", "finish": "16:00"}]  # inherited
    assert crew["weekdays"]["7"] == [{"start": "08:00", "finish": "12:00"}]  # overridden
    assert [e["date"] for e in crew["exceptions"]] == ["2026-05-01"]
    assert act(d, 1)["clndr_id"] == "2" and act(d, 1)["calendar"] == "Crew"


def test_task_without_a_calendar_uses_the_project_calendar():
    d = parse(tasks=task(1, CalendarUID=-1) + task(2))
    assert act(d, 1)["clndr_id"] == "1" and act(d, 2)["clndr_id"] == "1"


# ── Raw tables ────────────────────────────────────────────────────────────────

def test_raw_tables_are_the_xml_records_verbatim():
    d = parse(tasks=task(1, Notes="keep &amp; verbatim") + task(2, links=[(1, 1, 4800, 7)]))
    t = d["raw_tables"]
    assert set(t) >= {"Project", "Tasks", "PredecessorLinks", "Calendars", "CalendarWeekDays"}
    assert t["Project"]["row_count"] == 1 and "MinutesPerDay" in t["Project"]["fields"]
    tasks = {row[t["Tasks"]["fields"].index("UID")]: row for row in t["Tasks"]["rows"]}
    assert tasks["1"][t["Tasks"]["fields"].index("Notes")] == "keep & verbatim"
    assert tasks["2"][t["Tasks"]["fields"].index("Duration")] == "PT8H0M0S"   # not interpreted
    links = t["PredecessorLinks"]
    assert links["fields"][:2] == ["TaskUID", "PredecessorUID"]
    assert links["rows"] == [["2", "1", "1", "4800", "7"]]
    days = t["CalendarWeekDays"]
    assert days["rows"][1][days["fields"].index("WorkingTimes")] == "08:00-16:00"


def test_ermhdr_carries_the_save_version_and_date():
    d = parse_mspdi(doc(tasks=task(1)).replace(b"<Name>t.xml</Name>", b"<Name>t.xml</Name><LastSaved>2026-03-02T17:30:00</LastSaved>"))
    assert d["ermhdr"]["version"] == "14" and d["ermhdr"]["export_date"] == "2026-03-02T17:30:00"


# ── Refusals ──────────────────────────────────────────────────────────────────

def test_p6_xml_is_refused_with_its_name():
    with pytest.raises(ValueError, match="Primavera P6 XML"):
        parse_mspdi(b'<?xml version="1.0"?><APIBusinessObjects xmlns="http://xmlns.oracle.com/Primavera/P6/V8.3/API/BusinessObjects"/>')


def test_other_xml_is_refused_with_its_root():
    with pytest.raises(ValueError, match="root element is <html>"):
        parse_mspdi(b"<html><body/></html>")


def test_xml_with_a_dtd_is_refused():
    with pytest.raises(ValueError, match="DTD"):
        parse_mspdi(b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "b">]><Project xmlns="http://schemas.microsoft.com/project"/>')


def test_malformed_xml_is_refused():
    with pytest.raises(ValueError, match="well-formed"):
        parse_mspdi(b"<Project xmlns='http://schemas.microsoft.com/project'><Tasks>")


# ── The sample ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def sample_xml():
    return parse_schedule(str(SAMPLE_XML))


@pytest.fixture(scope="module")
def sample_xer():
    return parse_schedule(str(REPO_ROOT / "examples" / "sample-schedule.xer"))


def test_sample_xml_is_the_demo_project(sample_xml):
    p = sample_xml["project"]
    assert p["proj_short_name"] == "DEMO-DC-01" and p["source_format"] == "mspdi"
    assert p["total_activities"] == 24 and p["total_wbs"] == 7 and p["total_milestones"] == 3
    assert p["data_date"] == "2026-03-02 08:00:00" and sample_xml["warnings"] == []
    # The Project-only features the sample adds: one inactive task, one manual task, one
    # summary relationship, one deadline.
    assert p["inactive_activities"] == 1 and len(p["summary_links"]) == 1
    assert [a["task_name"] for a in sample_xml["activities"] if a["manual"]] == ["Ceilings & finishes"]
    assert [a["task_name"] for a in sample_xml["activities"] if a["deadline"]] == ["Practical Completion"]


def test_sample_xml_agrees_with_the_xer_sample_on_the_critical_set(sample_xml, sample_xer):
    """Same project, two tools: the critical activities, the incomplete part of the
    Longest Path and the driving links among incomplete work must agree. Project keeps a
    completed milestone's real finish where P6 resets it to the data date, so the trace
    on the XML stops at the first activity held by the status date (METHODOLOGY)."""
    name = lambda d, key: sorted(a["task_name"] for a in d["activities"] if a[key] and a["status"] != "TK_Complete")
    assert name(sample_xml, "is_critical") == name(sample_xer, "is_critical")
    assert name(sample_xml, "is_longest_path") == name(sample_xer, "is_longest_path")
    assert sample_xml["project"]["total_critical"] == sample_xer["project"]["total_critical"]
    by_name = {a["task_name"]: a for a in sample_xer["activities"]}
    by_id = {a["task_id"]: a for a in sample_xml["activities"]}
    open_links = lambda a: [(p["type"], p["lag_hrs"], p["driving"]) for p in a["predecessors"]
                            if by_id[p["task_id"]]["status"] != "TK_Complete"]
    for a in sample_xml["activities"]:
        if a["status"] == "TK_NotStart":
            assert open_links(a) == [(p["type"], p["lag_hrs"], p["driving"]) for p in by_name[a["task_name"]]["predecessors"]
                                     if by_name[a["task_name"]]["status"] and by_id[p["task_id"]]["status"] != "TK_Complete"], a["task_name"]


def test_sample_xml_cpli_matches_the_xer(sample_xml, sample_xer):
    assert sample_xml["project"]["cpli"]["value"] == sample_xer["project"]["cpli"]["value"] == 1.0
    assert sample_xml["project"]["cpli"]["cpl_hrs"] == sample_xer["project"]["cpli"]["cpl_hrs"]


def test_sample_xml_calendar_matches_the_xer(sample_xml, sample_xer):
    assert sample_xml["calendars"][0]["weekdays"] == sample_xer["calendars"][0]["weekdays"]
    assert sample_xml["calendars"][0]["exceptions"] == sample_xer["calendars"][0]["exceptions"]


def test_served_sample_xml_is_the_example_file():
    served = REPO_ROOT / "frontend" / "public" / "sample-schedule.xml"
    assert served.read_bytes() == SAMPLE_XML.read_bytes()


def test_frontend_xml_fixture_matches_the_parser(sample_xml):
    """healthChecks.test.ts pins finding counts on the XML sample's parse too."""
    from backend.main import ScheduleData
    fixture = REPO_ROOT / "frontend" / "src" / "utils" / "fixtures" / "sample-schedule-xml.json"
    d = ScheduleData(**sample_xml).model_dump()
    expected = json.loads(json.dumps({"project": d["project"], "activities": d["activities"]}))
    assert json.loads(fixture.read_text()) == expected, (
        "frontend XML fixture is stale; regenerate with:\n"
        "  python -c \"import json; from backend.main import parse_schedule; "
        "d=parse_schedule('examples/sample-schedule.xml').model_dump(); "
        "json.dump({'project':d['project'],'activities':d['activities']}, "
        "open('frontend/src/utils/fixtures/sample-schedule-xml.json','w'), indent=1)\""
    )
