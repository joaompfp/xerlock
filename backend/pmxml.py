"""
Primavera P6 XML (PMXML, root element APIBusinessObjects): P6's other export format,
the only one some clients send.

The XML carries the same data as a .xer, element by element (Project, WBS, Activity,
Relationship, Calendar, activity codes, resources), with readable enumerations
("Finish to Start", "Task Dependent") and dates in ISO form. This module maps it onto
the tables a .xer has (TASK, TASKPRED, PROJWBS, PROJECT, SCHEDOPTIONS, CALENDAR, ...),
in .xer vocabulary, and hands them to xer.read_tables: one set of rules for both
formats, the recalculation and the Critical Path Test included. The raw-table
inspector shows the XML's own elements, field by field, not the mapped tables.

Embedded baselines (BaselineProject elements) are read as projects of the file, so
they can be opened or compared like any other project.

Standard library only, so it runs in the browser build too.
"""

import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Optional

from backend import analysis
from backend.worktime import WorkCalendar
from backend.xer import RAW_TABLE_ROW_CAP, read_tables

# P6's readable enumerations, to the codes a .xer stores.
STATUS = {"Not Started": "TK_NotStart", "In Progress": "TK_Active", "Completed": "TK_Complete"}
TASK_TYPE = {
    "Task Dependent": "TT_Task", "Resource Dependent": "TT_Rsrc", "Level of Effort": "TT_LOE",
    "Start Milestone": "TT_StartMile", "Finish Milestone": "TT_FinMile", "WBS Summary": "TT_WBS",
}
PCT_TYPE = {"Physical": "CP_Phys", "Duration": "CP_Drtn", "Units": "CP_Units"}
CONSTRAINT = {
    "Start On": "CS_MSO", "Start On or Before": "CS_MSOB", "Start On or After": "CS_MSOA",
    "Finish On": "CS_MEO", "Finish On or Before": "CS_MEOB", "Finish On or After": "CS_MEOA",
    "As Late As Possible": "CS_ALAP", "Mandatory Start": "CS_MANDSTART", "Mandatory Finish": "CS_MANDFIN",
}
REL_TYPE = {"Finish to Start": "PR_FS", "Start to Start": "PR_SS", "Finish to Finish": "PR_FF", "Start to Finish": "PR_SF"}
LAG_CALENDAR = {
    "Predecessor Activity Calendar": "rcal_Predecessor", "Successor Activity Calendar": "rcal_Successor",
    "24 Hour Calendar": "rcal_24Hour", "Project Default Calendar": "rcal_ProjDefault",
}
CRITICAL_PATH = {"Critical Float": "CT_TotFloat", "Longest Path": "CT_DrivPath"}
# P6 weekday numbers in calendar data: 1 = Sunday.
WEEKDAY = {"Sunday": "1", "Monday": "2", "Tuesday": "3", "Wednesday": "4", "Thursday": "5", "Friday": "6", "Saturday": "7"}


def is_pmxml(head: bytes) -> bool:
    return b"APIBusinessObjects" in head


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _fields(el) -> dict:
    """An element's simple children as {name: text} (complex children are left out)."""
    return {_local(c.tag): (c.text or "").strip() for c in el if len(c) == 0}


def _date(v: str) -> str:
    """ISO 'YYYY-MM-DDTHH:MM:SS' to the .xer's 'YYYY-MM-DD HH:MM'."""
    return v[:16].replace("T", " ") if v else ""


def _flag(v: str) -> str:
    """P6 XML booleans (1/0, true/false) as the .xer's Y/N; empty stays empty."""
    if v == "":
        return ""
    return "Y" if v.lower() in ("1", "true", "y", "yes") else "N"


def _pct(v: str) -> str:
    """Percentages are fractions (0.25) in the XML and 0-100 in a .xer."""
    try:
        return str(round(float(v) * 100, 4)) if v else ""
    except ValueError:
        return ""


def _float_type(v: str) -> str:
    if not v:
        return ""
    if "Smallest" in v:
        return "FT_SmallestFloat"
    return "FT_SF" if v.startswith("Start") else "FT_FF"


def _hhmm_end(t: str) -> str:
    """A work period's end: P6 writes the last minute (11:59, 23:59), meaning the hour."""
    hh, mm = int(t[0:2]), int(t[3:5])
    if mm % 30 == 29:
        mm += 1
        if mm == 60:
            hh, mm = hh + 1, 0
    return "00:00" if hh >= 24 else f"{hh:02d}:{mm:02d}"


def _periods(parent) -> list:
    out = []
    for wt in parent:
        if _local(wt.tag) != "WorkTime":
            continue
        f = _fields(wt)
        if f.get("Start") and f.get("Finish"):
            out.append({"start": f["Start"][:5], "finish": _hhmm_end(f["Finish"])})
    return out


def _calendar(el) -> tuple:
    """(CALENDAR row, calendar in parse_calendars' shape) for one Calendar element."""
    f = _fields(el)
    weekdays = {d: [] for d in WEEKDAY.values()}
    exceptions = []
    for part in el:
        name = _local(part.tag)
        if name == "StandardWorkWeek":
            for day in part:
                d = _fields(day).get("DayOfWeek", "")
                if d in WEEKDAY:
                    weekdays[WEEKDAY[d]] = _periods(day)
        elif name == "HolidayOrExceptions":
            for exc in part:
                d = _fields(exc).get("Date", "")
                if d:
                    exceptions.append({"date": d[:10], "periods": _periods(exc)})
    row = {
        "clndr_id": f.get("ObjectId", ""), "clndr_name": f.get("Name", ""),
        "clndr_type": f.get("Type", ""), "default_flag": _flag(f.get("IsDefault", "")),
        "day_hr_cnt": f.get("HoursPerDay", ""), "week_hr_cnt": f.get("HoursPerWeek", ""),
    }
    cal = {
        "clndr_id": row["clndr_id"], "clndr_name": row["clndr_name"], "clndr_type": row["clndr_type"],
        "default_flag": row["default_flag"] == "Y",
        "day_hr_cnt": float(row["day_hr_cnt"] or 8), "week_hr_cnt": float(row["week_hr_cnt"] or 40),
        "weekdays": weekdays, "exceptions": sorted(exceptions, key=lambda e: e["date"]),
    }
    return row, cal


def _table(rows: list) -> dict:
    """Records as a raw table: fields in order of first appearance, rows aligned, capped."""
    fields = []
    seen = set()
    for r in rows:
        for k in r:
            if k not in seen:
                seen.add(k)
                fields.append(k)
    shown = rows[:RAW_TABLE_ROW_CAP]
    return {
        "fields": fields,
        "rows": [[str(r.get(k, "")) for k in fields] for r in shown],
        "row_count": len(rows),
        "truncated": len(rows) > RAW_TABLE_ROW_CAP,
    }


def _shown_tables(root) -> dict:
    """The file's own elements as tables, one per element type, simple fields verbatim:
    what the inspector shows, so a reader can check the mapping against the file."""
    by_type: dict = {}

    def walk(el, depth):
        for c in el:
            name = _local(c.tag)
            if len(c) and any(len(g) == 0 for g in c):
                by_type.setdefault(name, []).append(_fields(c))
            if depth < 3:
                walk(c, depth + 1)

    walk(root, 0)
    return {name: _table(rows) for name, rows in by_type.items() if any(rows)}


def _derive_missing_float(tasks: list, calendars: list) -> list:
    """An export without TotalFloat (P6 lets the columns be chosen) gets it worked out as
    P6 defines finish float: late finish less early finish, in working hours on the
    activity's calendar. Returns the warning that says so, if any were derived."""
    # Only when the export left the field out altogether: P6 itself leaves float blank on
    # completed work, and a blank there is information, not a gap.
    if any(r["total_float_hr_cnt"] != "" for r in tasks):
        return []
    missing = [r for r in tasks if r["status_code"] != "TK_Complete" and r["early_end_date"] and r["late_end_date"]]
    if not missing:
        return []
    cals = {c["clndr_id"]: WorkCalendar(c["weekdays"], c["exceptions"]) for c in calendars}
    for r in missing:
        cal = cals.get(r["clndr_id"])
        if not cal:
            continue
        ef = datetime.fromisoformat(r["early_end_date"])
        lf = datetime.fromisoformat(r["late_end_date"])
        r["total_float_hr_cnt"] = str(round(cal.working_hours_between(ef, lf), 2))
    return [f"This export has no total float for {len(missing)} activities: it was worked out from their "
            "early and late finish dates on each activity's calendar, as P6 computes finish float."]


def read_pmxml(source, project_id: Optional[int] = None) -> dict:
    """A P6 XML file (path or bytes) into the neutral intermediate (see xer.read_tables)."""
    try:
        root = ET.fromstring(source) if isinstance(source, (bytes, bytearray)) else ET.parse(source).getroot()
    except ET.ParseError as e:
        raise ValueError(f"This P6 XML file is not well-formed XML ({e}).")
    if _local(root.tag) != "APIBusinessObjects":
        raise ValueError("This is not a Primavera P6 XML export (no APIBusinessObjects root).")

    t = {name: [] for name in ("PROJECT", "PROJWBS", "TASK", "TASKPRED", "SCHEDOPTIONS", "CALENDAR",
                               "ACTVTYPE", "ACTVCODE", "TASKACTV", "RSRC", "TASKRSRC")}
    calendars = []

    def add_calendar(el):
        row, cal = _calendar(el)
        if row["clndr_id"] and not any(r["clndr_id"] == row["clndr_id"] for r in t["CALENDAR"]):
            t["CALENDAR"].append(row)
            calendars.append(cal)

    def add_codes(el):
        for c in el:
            name, f = _local(c.tag), _fields(c)
            if name == "ActivityCodeType":
                t["ACTVTYPE"].append({"actv_code_type_id": f.get("ObjectId", ""), "actv_code_type": f.get("Name", "")})
            elif name == "ActivityCode":
                t["ACTVCODE"].append({"actv_code_id": f.get("ObjectId", ""), "actv_code_type_id": f.get("CodeTypeObjectId", ""),
                                      "actv_code_name": f.get("CodeValue", ""), "short_name": f.get("CodeValue", "")})
            elif name == "Resource":
                t["RSRC"].append({"rsrc_id": f.get("ObjectId", ""), "rsrc_name": f.get("Name", ""), "rsrc_short_name": f.get("Id", "")})

    for el in root:
        if _local(el.tag) == "Calendar":
            add_calendar(el)
    add_codes(root)

    for proj in root:
        if _local(proj.tag) not in ("Project", "BaselineProject"):
            continue
        pf = _fields(proj)
        pid = pf.get("ObjectId", "")
        so = next((_fields(c) for c in proj if _local(c.tag) == "ScheduleOptions"), {})
        opt = {**pf, **so}  # options appear on the project, or in its ScheduleOptions
        oos = opt.get("OutOfSequenceScheduleType", "")
        t["PROJECT"].append({
            "proj_id": pid, "proj_short_name": pf.get("Id", "") or pf.get("Name", ""),
            "last_recalc_date": _date(pf.get("DataDate", "")),
            "plan_start_date": _date(pf.get("PlannedStartDate", "")),
            "plan_end_date": _date(pf.get("MustFinishByDate", "")),
            "critical_drtn_hr_cnt": opt.get("CriticalActivityFloatLimit", "") or opt.get("CriticalActivityFloatThreshold", ""),
            "critical_path_type": CRITICAL_PATH.get(opt.get("CriticalActivityPathType", ""), ""),
            "clndr_id": pf.get("ActivityDefaultCalendarObjectId", ""),
        })
        if opt:
            ss_lag = opt.get("StartToStartLagCalculationType", "")
            t["SCHEDOPTIONS"].append({
                "proj_id": pid,
                "sched_retained_logic": "Y" if oos == "Retained Logic" else ("N" if oos else ""),
                "sched_progress_override": "Y" if oos == "Progress Override" else ("N" if oos else ""),
                "sched_float_type": _float_type(opt.get("ComputeTotalFloatType", "")),
                "sched_calendar_on_relationship_lag": LAG_CALENDAR.get(opt.get("RelationshipLagCalendar", ""), ""),
                "sched_open_critical_flag": _flag(opt.get("MakeOpenEndedActivitiesCritical", "")),
                "sched_use_expect_end_flag": _flag(opt.get("UseExpectedFinishDates", "")),
                "sched_use_project_end_date_for_float": _flag(opt.get("CalculateFloatBasedOnFinishDate", "")),
                "sched_lag_early_start_flag": "Y" if ss_lag == "Early Start" else ("N" if ss_lag else ""),
                "enable_multiple_longest_path_calc": _flag(opt.get("MultipleFloatPathsEnabled", "")),
            })

        # The project itself is the WBS root, as in a .xer (its proj_node_flag row).
        root_wbs = f"-{pid}"
        t["PROJWBS"].append({"wbs_id": root_wbs, "proj_id": pid, "parent_wbs_id": "", "seq_num": "0",
                             "wbs_short_name": pf.get("Id", ""), "wbs_name": pf.get("Name", ""), "proj_node_flag": "Y"})
        for c in proj:
            name, f = _local(c.tag), _fields(c)
            if name == "Calendar":
                add_calendar(c)
            elif name == "WBS":
                parent = f.get("ParentObjectId", "")
                t["PROJWBS"].append({
                    "wbs_id": f.get("ObjectId", ""), "proj_id": pid,
                    "parent_wbs_id": parent if parent and parent != pid else root_wbs,
                    "seq_num": f.get("SequenceNumber", "0"), "wbs_short_name": f.get("Code", ""),
                    "wbs_name": f.get("Name", ""), "proj_node_flag": "N",
                })
            elif name == "Activity":
                aid = f.get("ObjectId", "")
                t["TASK"].append({
                    "task_id": aid, "proj_id": pid, "wbs_id": f.get("WBSObjectId", "") or root_wbs,
                    "clndr_id": f.get("CalendarObjectId", ""), "task_code": f.get("Id", ""), "task_name": f.get("Name", ""),
                    "status_code": STATUS.get(f.get("Status", ""), ""), "task_type": TASK_TYPE.get(f.get("Type", ""), ""),
                    "complete_pct_type": PCT_TYPE.get(f.get("PercentCompleteType", ""), ""),
                    "phys_complete_pct": _pct(f.get("PhysicalPercentComplete", "")),
                    "target_drtn_hr_cnt": f.get("PlannedDuration", ""), "remain_drtn_hr_cnt": f.get("RemainingDuration", ""),
                    "total_float_hr_cnt": f.get("TotalFloat", ""), "free_float_hr_cnt": f.get("FreeFloat", ""),
                    "early_start_date": _date(f.get("EarlyStartDate", "")), "early_end_date": _date(f.get("EarlyFinishDate", "")),
                    "late_start_date": _date(f.get("LateStartDate", "")), "late_end_date": _date(f.get("LateFinishDate", "")),
                    "act_start_date": _date(f.get("ActualStartDate", "")), "act_end_date": _date(f.get("ActualFinishDate", "")),
                    "target_start_date": _date(f.get("PlannedStartDate", "")), "target_end_date": _date(f.get("PlannedFinishDate", "")),
                    "restart_date": _date(f.get("RemainingEarlyStartDate", "")), "reend_date": _date(f.get("RemainingEarlyFinishDate", "")),
                    "expect_end_date": _date(f.get("ExpectedFinishDate", "")),
                    "external_early_start_date": _date(f.get("ExternalEarlyStartDate", "")),
                    "external_late_end_date": _date(f.get("ExternalLateFinishDate", "")),
                    "cstr_type": CONSTRAINT.get(f.get("PrimaryConstraintType", ""), ""), "cstr_date": _date(f.get("PrimaryConstraintDate", "")),
                    "cstr_type2": CONSTRAINT.get(f.get("SecondaryConstraintType", ""), ""), "cstr_date2": _date(f.get("SecondaryConstraintDate", "")),
                    "driving_path_flag": _flag(f.get("DrivingPathFlag", "")), "float_path": f.get("FloatPath", ""),
                })
                for code in c:
                    if _local(code.tag) == "Code":
                        cf = _fields(code)
                        t["TASKACTV"].append({"task_id": aid, "actv_code_type_id": cf.get("TypeObjectId", ""),
                                              "actv_code_id": cf.get("ValueObjectId", ""), "proj_id": pid})
            elif name == "Relationship":
                t["TASKPRED"].append({
                    "task_pred_id": f.get("ObjectId", ""), "task_id": f.get("SuccessorActivityObjectId", ""),
                    "pred_task_id": f.get("PredecessorActivityObjectId", ""),
                    "proj_id": f.get("SuccessorProjectObjectId", "") or pid, "pred_proj_id": f.get("PredecessorProjectObjectId", "") or pid,
                    "pred_type": REL_TYPE.get(f.get("Type", ""), ""), "lag_hr_cnt": f.get("Lag", ""),
                })
            elif name == "ResourceAssignment":
                t["TASKRSRC"].append({
                    "task_id": f.get("ActivityObjectId", ""), "rsrc_id": f.get("ResourceObjectId", ""), "proj_id": pid,
                    "act_reg_qty": f.get("ActualRegularUnits", ""), "act_ot_qty": f.get("ActualOvertimeUnits", ""),
                    "remain_qty": f.get("RemainingUnits", ""),
                })
        add_codes(proj)

    if not t["PROJECT"]:
        raise ValueError("No projects found in this P6 XML file")
    warnings = _derive_missing_float(t["TASK"], calendars)
    tables = {name: _table(rows) for name, rows in t.items() if rows}
    # Read in full, not capped: the cap only bounds what the inspector is sent.
    for name, rows in t.items():
        if rows:
            tables[name]["rows"] = [[str(r.get(k, "")) for k in tables[name]["fields"]] for r in rows]
    return read_tables(tables, calendars, project_id, shown_tables=_shown_tables(root),
                       ermhdr={}, source_format="pmxml", trailing_warnings=warnings)


def parse_pmxml(source, project_id: Optional[int] = None) -> dict:
    """A P6 XML file into the schedule structure the API serves."""
    return analysis.build(read_pmxml(source, project_id))
