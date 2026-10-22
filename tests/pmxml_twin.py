"""A P6 XML twin of a .xer, written the way P6 exports XML: the .xer's tables as
Project / WBS / Activity / Relationship / Calendar / activity-code / resource elements,
with P6's readable enumerations, ISO dates, fractional percentages and work periods
ending on the minute before the hour (11:59). Tests compare the P6 XML reader against
the .xer reader on the same schedule, and MPXJ's reading of the twin against the .xer.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

from backend.pmxml import CONSTRAINT, CRITICAL_PATH, LAG_CALENDAR, PCT_TYPE, REL_TYPE, STATUS, TASK_TYPE, WEEKDAY
from backend.xer import parse_calendar_data, parse_raw_tables, table_records

NS = "http://xmlns.oracle.com/Primavera/P6/V23.12/API/BusinessObjects"
inv = lambda d: {v: k for k, v in d.items()}  # noqa: E731
FLOAT_TYPE = {"FT_FF": "Finish Float = Late Finish - Early Finish", "FT_SF": "Start Float = Late Start - Early Start",
              "FT_SmallestFloat": "Smallest of Start Float and Finish Float"}


def _iso(v):
    return v.replace(" ", "T") + ":00" if v else None


def _yn(v):
    return {"Y": "1", "N": "0"}.get(v)


def _minus_minute(hhmm):
    h, m = int(hhmm[:2]), int(hhmm[3:5])
    total = (h * 60 + m - 1) % 1440 if (h, m) != (0, 0) else 1439
    return f"{total // 60:02d}:{total % 60:02d}:00"


def _sub(parent, tag, text=None):
    el = ET.SubElement(parent, f"{{{NS}}}{tag}")
    if text is not None:
        el.text = str(text)
    return el


def _fields(parent, pairs):
    for tag, value in pairs:
        if value not in (None, ""):
            _sub(parent, tag, value)


def write_twin(xer_path: Path, out: Path) -> Path:
    tables, _ = parse_raw_tables(xer_path.read_text(encoding="utf-8"))
    rec = lambda name: table_records(tables, name)  # noqa: E731
    root = ET.Element(f"{{{NS}}}APIBusinessObjects")

    for c in rec("CALENDAR"):
        cal = _sub(root, "Calendar")
        _fields(cal, [("HoursPerDay", c.get("day_hr_cnt")), ("HoursPerWeek", c.get("week_hr_cnt")),
                      ("IsDefault", _yn(c.get("default_flag"))), ("Name", c.get("clndr_name")),
                      ("ObjectId", c.get("clndr_id")), ("Type", c.get("clndr_type"))])
        weekdays, exceptions = parse_calendar_data(c.get("clndr_data", ""))
        week = _sub(cal, "StandardWorkWeek")
        for name, num in WEEKDAY.items():
            day = _sub(week, "StandardWorkHours")
            _sub(day, "DayOfWeek", name)
            for p in weekdays.get(num, []):
                wt = _sub(day, "WorkTime")
                _sub(wt, "Start", p["start"] + ":00")
                _sub(wt, "Finish", _minus_minute(p["finish"]))
        hol = _sub(cal, "HolidayOrExceptions")
        for e in exceptions:
            ex = _sub(hol, "HolidayOrException")
            _sub(ex, "Date", e["date"] + "T00:00:00")
            for p in e["periods"]:
                wt = _sub(ex, "WorkTime")
                _sub(wt, "Start", p["start"] + ":00")
                _sub(wt, "Finish", _minus_minute(p["finish"]))

    for t in rec("ACTVTYPE"):
        _fields(_sub(root, "ActivityCodeType"), [("Name", t.get("actv_code_type")), ("ObjectId", t.get("actv_code_type_id"))])
    for c in rec("ACTVCODE"):
        _fields(_sub(root, "ActivityCode"), [("CodeTypeObjectId", c.get("actv_code_type_id")), ("CodeValue", c.get("short_name") or c.get("actv_code_name")),
                                             ("ObjectId", c.get("actv_code_id"))])
    for r in rec("RSRC"):
        _fields(_sub(root, "Resource"), [("Id", r.get("rsrc_short_name")), ("Name", r.get("rsrc_name")), ("ObjectId", r.get("rsrc_id"))])

    codes_by_task = {}
    for a in rec("TASKACTV"):
        codes_by_task.setdefault(a["task_id"], []).append(a)
    for p in rec("PROJECT"):
        pid = p["proj_id"]
        root_wbs = next((w["wbs_id"] for w in rec("PROJWBS") if w["proj_id"] == pid and w.get("proj_node_flag") == "Y"), None)
        proj = _sub(root, "Project")
        so = next((s for s in rec("SCHEDOPTIONS") if s.get("proj_id") == pid), {})
        oos = "Progress Override" if so.get("sched_progress_override") == "Y" else (
            "Retained Logic" if so.get("sched_retained_logic") == "Y" else "Actual Dates")
        _fields(proj, [("ActivityDefaultCalendarObjectId", p.get("clndr_id")),
                       ("CriticalActivityFloatLimit", p.get("critical_drtn_hr_cnt")),
                       ("CriticalActivityPathType", inv(CRITICAL_PATH).get(p.get("critical_path_type"))),
                       ("DataDate", _iso(p.get("last_recalc_date"))), ("Id", p.get("proj_short_name")),
                       ("MustFinishByDate", _iso(p.get("plan_end_date"))),
                       ("Name", next((w["wbs_name"] for w in rec("PROJWBS") if w["wbs_id"] == root_wbs), p.get("proj_short_name"))),
                       ("ObjectId", pid), ("PlannedStartDate", _iso(p.get("plan_start_date")))])
        opts = _sub(proj, "ScheduleOptions")
        _fields(opts, [("CalculateFloatBasedOnFinishDate", _yn(so.get("sched_use_project_end_date_for_float"))),
                       ("ComputeTotalFloatType", FLOAT_TYPE.get(so.get("sched_float_type"))),
                       ("MakeOpenEndedActivitiesCritical", _yn(so.get("sched_open_critical_flag"))),
                       ("OutOfSequenceScheduleType", oos),
                       ("RelationshipLagCalendar", inv(LAG_CALENDAR).get(so.get("sched_calendar_on_relationship_lag"))),
                       ("StartToStartLagCalculationType", {"Y": "Early Start", "N": "Actual Start"}.get(so.get("sched_lag_early_start_flag"))),
                       ("UseExpectedFinishDates", _yn(so.get("sched_use_expect_end_flag")))])
        for w in rec("PROJWBS"):
            if w["proj_id"] != pid or w["wbs_id"] == root_wbs:
                continue
            parent = w.get("parent_wbs_id")
            _fields(_sub(proj, "WBS"), [("Code", w.get("wbs_short_name")), ("Name", w.get("wbs_name")), ("ObjectId", w["wbs_id"]),
                                        ("ParentObjectId", pid if parent == root_wbs else parent),
                                        ("ProjectObjectId", pid), ("SequenceNumber", w.get("seq_num"))])
        for a in rec("TASK"):
            if a["proj_id"] != pid:
                continue
            act = _sub(proj, "Activity")
            pct = lambda v: str(float(v) / 100) if v not in (None, "") else None  # noqa: E731
            _fields(act, [
                ("ActualFinishDate", _iso(a.get("act_end_date"))), ("ActualStartDate", _iso(a.get("act_start_date"))),
                ("CalendarObjectId", a.get("clndr_id")), ("DrivingPathFlag", _yn(a.get("driving_path_flag"))),
                ("EarlyFinishDate", _iso(a.get("early_end_date"))), ("EarlyStartDate", _iso(a.get("early_start_date"))),
                ("ExpectedFinishDate", _iso(a.get("expect_end_date"))), ("FloatPath", a.get("float_path")),
                ("FreeFloat", a.get("free_float_hr_cnt")), ("Id", a.get("task_code")),
                ("LateFinishDate", _iso(a.get("late_end_date"))), ("LateStartDate", _iso(a.get("late_start_date"))),
                ("Name", a.get("task_name")), ("ObjectId", a["task_id"]),
                ("PercentCompleteType", inv(PCT_TYPE).get(a.get("complete_pct_type"))),
                ("PhysicalPercentComplete", pct(a.get("phys_complete_pct"))),
                ("PlannedDuration", a.get("target_drtn_hr_cnt")), ("PlannedFinishDate", _iso(a.get("target_end_date"))),
                ("PlannedStartDate", _iso(a.get("target_start_date"))),
                ("PrimaryConstraintDate", _iso(a.get("cstr_date"))), ("PrimaryConstraintType", inv(CONSTRAINT).get(a.get("cstr_type"))),
                ("ProjectObjectId", pid), ("RemainingDuration", a.get("remain_drtn_hr_cnt")),
                ("RemainingEarlyFinishDate", _iso(a.get("reend_date"))), ("RemainingEarlyStartDate", _iso(a.get("restart_date"))),
                ("SecondaryConstraintDate", _iso(a.get("cstr_date2"))), ("SecondaryConstraintType", inv(CONSTRAINT).get(a.get("cstr_type2"))),
                ("Status", inv(STATUS).get(a.get("status_code"))), ("TotalFloat", a.get("total_float_hr_cnt")),
                ("Type", {**inv(TASK_TYPE), "TT_Mile": "Start Milestone"}.get(a.get("task_type"))),
                ("WBSObjectId", None if a.get("wbs_id") == root_wbs else a.get("wbs_id")),
            ])
            for c in codes_by_task.get(a["task_id"], []):
                code = _sub(act, "Code")
                _fields(code, [("TypeObjectId", c.get("actv_code_type_id")), ("ValueObjectId", c.get("actv_code_id"))])
        for r in rec("TASKPRED"):
            if r.get("proj_id") != pid:
                continue
            _fields(_sub(proj, "Relationship"), [("Lag", r.get("lag_hr_cnt")), ("ObjectId", r.get("task_pred_id")),
                                                 ("PredecessorActivityObjectId", r.get("pred_task_id")), ("PredecessorProjectObjectId", r.get("pred_proj_id")),
                                                 ("SuccessorActivityObjectId", r.get("task_id")), ("SuccessorProjectObjectId", r.get("proj_id")),
                                                 ("Type", inv(REL_TYPE).get(r.get("pred_type")))])
        for r in rec("TASKRSRC"):
            if r.get("proj_id") not in (None, pid):
                continue
            _fields(_sub(proj, "ResourceAssignment"), [("ActivityObjectId", r.get("task_id")), ("ActualOvertimeUnits", r.get("act_ot_qty")),
                                                       ("ActualRegularUnits", r.get("act_reg_qty")), ("RemainingUnits", r.get("remain_qty")),
                                                       ("ResourceObjectId", r.get("rsrc_id"))])
    ET.ElementTree(root).write(out, encoding="utf-8", xml_declaration=True)
    return out
