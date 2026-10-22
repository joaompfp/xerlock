"""
XERlock's P6 reader: a .xer file in, the neutral intermediate out (see analysis.build),
and `parse_xer` for the full schedule structure the API serves.

Pure Python with no web framework, so it runs both behind the FastAPI app (backend/main.py)
and in the browser under Pyodide, where the file never leaves the user's machine.
"""

import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional


from backend import analysis, recalc

logger = logging.getLogger("schedule-app")


RAW_TABLE_ROW_CAP = analysis.RAW_TABLE_ROW_CAP

# P6 stores calendar exception dates as day serials with this epoch (Excel-compatible).
_CAL_EPOCH = date(1899, 12, 30)


def parse_raw_tables(text: str):
    """Parse the XER's own %T/%F/%R structure verbatim — audit-grade: no interpretation,
    every table and field in the file, exactly as the contractor exported it."""
    tables = {}
    ermhdr = {}
    current = None
    for line in text.split("\n"):
        line = line.rstrip("\r")
        if not line:
            continue
        if line.startswith("ERMHDR"):
            parts = line.split("\t")
            # ERMHDR: version, export date, then user/db context fields whose exact
            # layout varies by P6 version — expose the interesting leading ones.
            ermhdr = {
                "version": parts[1] if len(parts) > 1 else "",
                "export_date": parts[2] if len(parts) > 2 else "",
                "fields": parts[1:],
            }
        elif line.startswith("%T\t"):
            name = line.split("\t", 1)[1].strip()
            current = {"fields": [], "rows": [], "row_count": 0, "truncated": False}
            tables[name] = current
        elif line.startswith("%F\t") and current is not None:
            current["fields"] = line.split("\t")[1:]
        elif line.startswith("%R\t") and current is not None:
            current["row_count"] += 1
            if current["row_count"] <= RAW_TABLE_ROW_CAP:
                row = line.split("\t")[1:]
                # Pad/trim to the field count so the frontend can rely on alignment.
                nf = len(current["fields"])
                row = (row + [""] * nf)[:nf]
                current["rows"].append(row)
            else:
                current["truncated"] = True
    return tables, ermhdr


def _parse_cal_node(s: str, i: int):
    """Recursive-descent parser for one node of P6's CalendarData format:
    ``(0||name(params)(child child ...))`` — params contain no parentheses, and
    children (further nodes) are wrapped in their own paren *group* after the
    params, which may be empty: ``()``."""
    j = s.index("||", i)
    k = s.index("(", j + 2)
    name = s[j + 2 : k]
    p = s.index(")", k)
    params = s[k + 1 : p]
    i = p + 1
    children = []
    while i < len(s):
        c = s[i]
        if c in " \t\r\n":
            i += 1
        elif c == "(":
            # A child group: ( node* )
            i += 1
            while i < len(s):
                if s[i] in " \t\r\n":
                    i += 1
                elif s[i] == "(":
                    child, i = _parse_cal_node(s, i)
                    children.append(child)
                elif s[i] == ")":
                    i += 1
                    break
                else:
                    i += 1
        elif c == ")":
            return {"name": name, "params": params, "children": children}, i + 1
        else:
            i += 1
    return {"name": name, "params": params, "children": children}, i


def _periods_of(node):
    out = []
    for ch in node["children"]:
        parts = ch["params"].split("|")
        if len(parts) >= 4 and parts[0] == "s" and parts[2] == "f":
            out.append({"start": parts[1], "finish": parts[3]})
    return out


def parse_calendar_data(blob: str):
    """Decode clndr_data into weekday work patterns and dated exceptions.
    Weekday keys are P6's 1..7 = Sunday..Saturday; a day/exception with no work
    periods is non-working (a holiday, when it appears as an exception)."""
    weekdays = {str(d): [] for d in range(1, 8)}
    exceptions = []
    start = blob.find("(")
    if start == -1:
        return weekdays, exceptions
    try:
        root, _ = _parse_cal_node(blob, start)
    except (ValueError, IndexError):
        logger.warning("Unparseable clndr_data blob (len=%d)", len(blob))
        return weekdays, exceptions
    for section in root["children"]:
        if section["name"] == "DaysOfWeek":
            for day in section["children"]:
                if day["name"] in weekdays:
                    weekdays[day["name"]] = _periods_of(day)
        elif section["name"] == "Exceptions":
            for exc in section["children"]:
                parts = exc["params"].split("|")
                if len(parts) >= 2 and parts[0] == "d":
                    try:
                        d = _CAL_EPOCH + timedelta(days=int(parts[1]))
                    except (ValueError, OverflowError):
                        continue
                    exceptions.append({"date": d.isoformat(), "periods": _periods_of(exc)})
    exceptions.sort(key=lambda e: e["date"])
    return weekdays, exceptions


def table_records(raw_tables: dict, name: str):
    """Rows of one raw table as {field: value} dicts."""
    tbl = raw_tables.get(name)
    if not tbl:
        return []
    return [dict(zip(tbl["fields"], row)) for row in tbl["rows"]]


def parse_calendars(raw_tables: dict):
    """Calendars decoded from the raw CALENDAR table (so the
    inspector and viewer agree byte-for-byte with the file)."""
    out = []
    for row in table_records(raw_tables, "CALENDAR"):
        weekdays, exceptions = parse_calendar_data(row.get("clndr_data", ""))
        out.append({
            "clndr_id": row.get("clndr_id", ""),
            "clndr_name": row.get("clndr_name", ""),
            "clndr_type": row.get("clndr_type", ""),
            "default_flag": row.get("default_flag") == "Y",
            "day_hr_cnt": float(row.get("day_hr_cnt") or 8),
            "week_hr_cnt": float(row.get("week_hr_cnt") or 40),
            "weekdays": weekdays,
            "exceptions": exceptions,
        })
    return out


def schedule_options_for(raw_tables: dict, proj_id) -> dict:
    """The scheduling options P6 used for this project. Every computed date, float and
    critical flag in the file depends on them, so an auditor reads them first
    (AACE 78R-13, schedule design basis; GAO Schedule Assessment Guide, BP 9)."""
    pid = str(proj_id)
    opts = next((r for r in table_records(raw_tables, "SCHEDOPTIONS") if r.get("proj_id") == pid), {})
    proj = next((r for r in table_records(raw_tables, "PROJECT") if r.get("proj_id") == pid), {})
    def flag(row, field):
        v = row.get(field, "")
        return None if v == "" else v == "Y"
    try:
        crit_hrs = float(proj.get("critical_drtn_hr_cnt") or 0)
    except ValueError:
        crit_hrs = 0.0
    return {
        "present": bool(opts),
        "retained_logic": flag(opts, "sched_retained_logic"),
        "progress_override": flag(opts, "sched_progress_override"),
        "float_type": opts.get("sched_float_type", ""),
        "lag_calendar": opts.get("sched_calendar_on_relationship_lag", "") or "rcal_Predecessor",
        "open_ends_critical": flag(opts, "sched_open_critical_flag"),
        "use_expected_finish": flag(opts, "sched_use_expect_end_flag"),
        "float_to_project_finish": flag(opts, "sched_use_project_end_date_for_float"),
        "external_relationships": opts.get("sched_outer_depend_type", ""),
        "critical_type": proj.get("critical_path_type", "") or "CT_TotFloat",
        "critical_float_hrs": crit_hrs,
    }


def percent_complete(task: dict, units: Optional[tuple]) -> float:
    """Activity % complete on the basis the activity itself declares (complete_pct_type),
    as P6 computes it. Reading phys_complete_pct regardless reports 0% (or a stale
    figure) for every duration- and units-progressed activity."""
    kind = task.get("complete_pct_type", "")
    status = task.get("status_code", "")
    if kind == "CP_Drtn":
        if status == "TK_Complete":
            return 100.0
        od = safe_float(_num(task.get("target_drtn_hr_cnt")))
        rd = safe_float(_num(task.get("remain_drtn_hr_cnt")))
        return round(min(100.0, max(0.0, 100 * (od - rd) / od)), 1) if od > 0 else 0.0
    if kind == "CP_Units" and units and units[1] > 0:
        return round(min(100.0, 100 * units[0] / units[1]), 1)
    return safe_float(_num(task.get("phys_complete_pct")))


def _num(v):
    try:
        return float(v) if v not in (None, "") else None
    except ValueError:
        return None


# Field readers matching the types the rest of the reader expects: ids as integers,
# text stripped, numbers as floats, P6's "YYYY-MM-DD HH:MM" stamps as datetimes; an
# empty field is None.

def _int(v):
    v = (v or "").strip()
    try:
        return int(v) if v else None
    except ValueError:
        return None


def _str(v):
    return v.strip() if v else None


def _float(v):
    return float(v) if v and v.strip() else None


def _date(v):
    # fromisoformat reads P6's stamp natively, many times faster than strptime.
    return datetime.fromisoformat(v) if v and v.strip() else None


def safe_float(val, default=0.0):
    """Convert to float, handling None and falsy 0.0 correctly."""
    if val is None:
        return default
    return float(val)

def safe_float_or(val, default=999.0):
    """Convert to float, returning default only for None (not 0.0)."""
    if val is None:
        return default
    return float(val)



def read_xer(filepath: str) -> dict:
    """Read a .xer into the neutral intermediate (analysis.build documents its keys):
    the file's own activities, links, WBS, calendars and options, with nothing derived."""
    # One pass over the file: decode as UTF-8 with a Windows-1252 fallback (P6's usual
    # export encoding), split it into its tables, and read everything from those.
    raw_bytes = Path(filepath).read_bytes()
    encoding_ok = True
    try:
        raw_text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        encoding_ok = False
        raw_text = raw_bytes.decode("cp1252", errors="replace")
    raw_tables, ermhdr = parse_raw_tables(raw_text)
    calendars = parse_calendars(raw_tables)

    # Every table is read from the raw pass above: one parse of the file, and no
    # third-party object model (which re-read the file, built an object per row with a
    # strptime per date, and failed outright on exports missing optional columns).
    projects = [r for r in table_records(raw_tables, "PROJECT") if _int(r.get("proj_id")) is not None]
    if not projects:
        raise ValueError("No projects found in XER file")
    tasks_by_proj: dict = {}
    for r in table_records(raw_tables, "TASK"):
        tasks_by_proj.setdefault(_int(r.get("proj_id")), []).append(r)

    # Pick the project owning the most activities, not the first one in the file.
    # Exports routinely lead with near-empty shells (a baseline stub, a template, a
    # closed phase); taking projects[0] on such a file showed an empty schedule while
    # the real programme sat further down the list.
    counts = [(p, len(tasks_by_proj.get(_int(p.get("proj_id")), []))) for p in projects]
    project, chosen_count = max(counts, key=lambda pc: pc[1])
    proj_id = _int(project.get("proj_id"))
    proj_short_name = _str(project.get("proj_short_name"))
    warnings = []
    if len(projects) > 1:
        others = ", ".join(
            f"{_str(p.get('proj_short_name')) or '?'} ({n})" for p, n in counts if p is not project
        )
        warnings.append(
            f"This file contains {len(projects)} projects — showing "
            f"'{proj_short_name}', the largest with {chosen_count} activities "
            f"(also present: {others})."
        )

    wbs = [{
        "wbs_id": _int(w.get("wbs_id")),
        "wbs_short_name": (w.get("wbs_short_name") or "").strip(),
        "wbs_name": (w.get("wbs_name") or "").strip(),
        "parent_wbs_id": _int(w.get("parent_wbs_id")) or None,
        "seq_num": int((w.get("seq_num") or "").strip() or 0),
    } for w in table_records(raw_tables, "PROJWBS") if _int(w.get("proj_id")) == proj_id]

    cal_dict = {}
    cal_hrs_dict = {}
    for c in table_records(raw_tables, "CALENDAR"):
        cid = _int(c.get("clndr_id"))
        cal_dict[cid] = _str(c.get("clndr_name"))
        cal_hrs_dict[cid] = _float(c.get("day_hr_cnt")) or 8.0

    # Activity codes: ACTVTYPE holds the code categories (e.g. "Phase"/"Area"), ACTVCODE
    # the code values (e.g. "Main Contract"), TASKACTV the per-task assignments.
    actv_type_names = {_int(t.get("actv_code_type_id")): _str(t.get("actv_code_type"))
                       for t in table_records(raw_tables, "ACTVTYPE")}
    actv_code_lookup = {_int(c.get("actv_code_id")): (_int(c.get("actv_code_type_id")), _str(c.get("actv_code_name")))
                        for c in table_records(raw_tables, "ACTVCODE")}
    task_codes_map = {}
    for assignment in table_records(raw_tables, "TASKACTV"):
        entry = actv_code_lookup.get(_int(assignment.get("actv_code_id")))
        if not entry:
            continue
        type_id, code_name = entry
        type_name = actv_type_names.get(type_id, "")
        if not type_name or not code_name:
            continue
        task_codes_map.setdefault(_int(assignment.get("task_id")), []).append({"type": type_name, "code": code_name})

    # Resources: TASKRSRC rows per activity, each resolved to its RSRC name. Many
    # contractor XER exports carry no resource data at all — degrade to empty
    # lists/flags rather than erroring.
    rsrc_names = {_int(r.get("rsrc_id")): _str(r.get("rsrc_name")) for r in table_records(raw_tables, "RSRC") if _int(r.get("rsrc_id"))}
    task_rsrc = {}
    rsrc_tbl = raw_tables.get("TASKRSRC")
    if rsrc_tbl:
        ri = {f: n for n, f in enumerate(rsrc_tbl["fields"])}
        if "task_id" in ri and "rsrc_id" in ri:
            for row in rsrc_tbl["rows"]:
                try:
                    tid = int(row[ri["task_id"]])
                except (ValueError, IndexError):
                    continue
                name = rsrc_names.get(row[ri["rsrc_id"]])
                if name:
                    task_rsrc.setdefault(tid, set()).add(name)

    own_tasks = tasks_by_proj.get(proj_id, [])

    # Relationships from the raw TASKPRED table in one pass (PyP6XER's
    # task.predecessors is O(activities x relationships): 96 million comparisons on a
    # 4,217-activity export). Cross-project relationships point outside this schedule;
    # the graph would dangle, so they are left out.
    own_ids = {_int(a.get("task_id")) for a in own_tasks}
    links = []
    pred_tbl = raw_tables.get("TASKPRED")
    if pred_tbl:
        idx = {f: n for n, f in enumerate(pred_tbl["fields"])}
        for row in pred_tbl["rows"]:
            try:
                succ_id = int(row[idx["task_id"]])
                pred_id = int(row[idx["pred_task_id"]])
            except (ValueError, KeyError, IndexError):
                continue
            if succ_id not in own_ids or pred_id not in own_ids:
                continue
            lag_raw = row[idx["lag_hr_cnt"]] if "lag_hr_cnt" in idx else ""
            try:
                lag = float(lag_raw or 0)
            except ValueError:
                lag = 0.0
            links.append({
                "pred_id": pred_id,
                "succ_id": succ_id,
                "type": row[idx["pred_type"]] if "pred_type" in idx else "",
                "lag_hrs": lag,
            })

    sched_options = schedule_options_for(raw_tables, proj_id)
    task_rows = {r.get("task_id"): r for r in table_records(raw_tables, "TASK")}
    units_done = {}
    for r in table_records(raw_tables, "TASKRSRC"):
        act = sum(safe_float(_num(r.get(f))) for f in ("act_reg_qty", "act_ot_qty"))
        rem = safe_float(_num(r.get("remain_qty")))
        d, t = units_done.get(r.get("task_id"), (0.0, 0.0))
        units_done[r.get("task_id")] = (d + act, t + act + rem)

    activities = []
    for row in own_tasks:
        task_id = _int(row.get("task_id"))
        clndr_id = _int(row.get("clndr_id"))
        activities.append({
            "task_id": task_id,
            "task_code": _str(row.get("task_code")),
            "task_name": _str(row.get("task_name")),
            "wbs_id": _int(row.get("wbs_id")),
            "status": _str(row.get("status_code")) or "",
            "pct_complete": percent_complete(row, units_done.get(str(task_id))),
            "pct_complete_type": row.get("complete_pct_type", ""),
            "early_start": _date(row.get("early_start_date")),
            "early_end": _date(row.get("early_end_date")),
            "late_start": _date(row.get("late_start_date")),
            "late_end": _date(row.get("late_end_date")),
            "total_float_hrs": _float(row.get("total_float_hr_cnt")),
            "free_float_hrs": safe_float(_float(row.get("free_float_hr_cnt"))),
            "duration_hrs": safe_float(_float(row.get("target_drtn_hr_cnt"))),
            "remain_duration_hrs": safe_float(_float(row.get("remain_drtn_hr_cnt")) or 0),
            "task_type": _str(row.get("task_type")) or "",
            "clndr_id": str(clndr_id) if clndr_id is not None else "",
            "calendar": cal_dict.get(clndr_id, ""),
            "calendar_hrs_per_day": cal_hrs_dict.get(clndr_id, 8.0),
            "driving_path_flag": row.get("driving_path_flag") == "Y",
            "cstr_type": _str(row.get("cstr_type")),
            "cstr_date": _date(row.get("cstr_date")),
            "cstr_type2": _str(row.get("cstr_type2")),
            "cstr_date2": _date(row.get("cstr_date2")),
            "act_start": _date(row.get("act_start_date")),
            "act_end": _date(row.get("act_end_date")),
            "target_start": _date(row.get("target_start_date")),
            "target_end": _date(row.get("target_end_date")),
            "activity_codes": task_codes_map.get(task_id, []),
            "resource_names": sorted(task_rsrc.get(task_id, ())),
        })

    # P6 commonly exports Windows-1252 rather than UTF-8. The file was decoded as such
    # above, which is right for P6's own exports; say so, since a file from elsewhere
    # in another single-byte encoding would show some characters wrongly.
    if not encoding_ok:
        warnings.append(
            "This file is not valid UTF-8, so it was read as Windows-1252, the encoding "
            "P6 usually exports in. If accented characters look wrong, the file was saved "
            "in another encoding."
        )

    pid = str(proj_id)
    project_row = next((r for r in table_records(raw_tables, "PROJECT") if r.get("proj_id") == pid), {})
    sched_row = next((r for r in table_records(raw_tables, "SCHEDOPTIONS") if r.get("proj_id") == pid), {})

    def recalculate(work_cals, default_cal, longest_path_ids, hrs_per_day):
        return recalc.run(list(task_rows.values()), table_records(raw_tables, "TASKPRED"),
                          project_row, sched_row, work_cals, default_cal, longest_path_ids,
                          hrs_per_day=hrs_per_day)

    return {
        "project": {
            "proj_short_name": proj_short_name,
            "data_date": (project.get("last_recalc_date") or "").strip() or None,
            "schedule_options": sched_options,
            "source_format": "xer",
        },
        "activities": activities,
        "links": links,
        "wbs": wbs,
        "calendars": calendars,
        "has_resources": len(rsrc_names) > 0,
        "activity_code_types": sorted(set(actv_type_names.values())),
        "warnings": warnings,
        "raw_tables": raw_tables,
        "ermhdr": ermhdr,
        "recalculate": recalculate,
    }


def parse_xer(filepath: str) -> dict:
    """Parse a .xer into the schedule structure the API serves (see main.ScheduleData and
    frontend/src/types/schedule.ts)."""
    return analysis.build(read_xer(filepath))
