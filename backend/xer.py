"""
XERlock's P6 reader: a .xer file in, the neutral intermediate out (see analysis.build),
and `parse_xer` for the full schedule structure the API serves.

Pure Python with no web framework, so it runs both behind the FastAPI app (backend/main.py)
and in the browser under Pyodide, where the file never leaves the user's machine.
"""

import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from xerparser.reader import Reader

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
    """Calendars decoded from the raw CALENDAR table (not PyP6XER's objects, so the
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
    # Raw pass first, independent of PyP6XER: decode as UTF-8 with cp1252 fallback
    # (P6's usual export encoding), so the table inspector shows accented characters
    # correctly even where the object parser drops them.
    raw_bytes = Path(filepath).read_bytes()
    encoding_ok = True
    try:
        raw_text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        encoding_ok = False
        raw_text = raw_bytes.decode("cp1252", errors="replace")
    raw_tables, ermhdr = parse_raw_tables(raw_text)
    calendars = parse_calendars(raw_tables)

    reader = Reader(filepath)
    # Deliberately single-project: this is a one-file, one-programme review tool. When an
    # export carries several projects (common with embedded baselines), take the first and
    # say so rather than silently showing partial data.
    projects = list(reader.projects)
    if not projects:
        raise ValueError("No projects found in XER file")

    # Pick the project owning the most activities, not the first one in the file.
    # Exports routinely lead with near-empty shells (a baseline stub, a template, a
    # closed phase); taking projects[0] on such a file showed an empty schedule while
    # the real programme sat further down the list.
    counts = [(p, len(list(p.activities))) for p in projects]
    project, chosen_count = max(counts, key=lambda pc: pc[1])
    warnings = []
    if len(projects) > 1:
        others = ", ".join(
            f"{p.proj_short_name or '?'} ({n})" for p, n in counts if p is not project
        )
        warnings.append(
            f"This file contains {len(projects)} projects — showing "
            f"'{project.proj_short_name}', the largest with {chosen_count} activities "
            f"(also present: {others})."
        )

    wbs = [{
        "wbs_id": w.wbs_id,
        "wbs_short_name": w.wbs_short_name,
        "wbs_name": w.wbs_name,
        "parent_wbs_id": w.parent_wbs_id if w.parent_wbs_id and w.parent_wbs_id != "0" else None,
        "seq_num": int(getattr(w, "seq_num", 0) or 0),
    } for w in project.wbss]

    cal_dict = {}
    cal_hrs_dict = {}
    for c in reader.calendars:
        cal_dict[c.clndr_id] = c.clndr_name if hasattr(c, "clndr_name") else str(c.clndr_id)
        cal_hrs_dict[c.clndr_id] = float(c.day_hr_cnt) if getattr(c, "day_hr_cnt", None) else 8.0

    # Activity codes: xerparser's property names are swapped relative to what the XER
    # table names suggest — reader.acttypes holds the code CATEGORIES (ACTVTYPE, e.g.
    # "Phase"/"Area"), reader.actvcodes holds the code VALUES (ACTVCODE, e.g. "Main
    # Contract"), and reader.activitycodes holds the per-task code ASSIGNMENTS (TASKACTV).
    actv_type_names = {t.actv_code_type_id: t.actv_code_type for t in reader.acttypes}
    actv_code_lookup = {c.actv_code_id: (c.actv_code_type_id, c.actv_code_name) for c in reader.actvcodes}
    task_codes_map = {}
    for assignment in reader.activitycodes:
        entry = actv_code_lookup.get(assignment.actv_code_id)
        if not entry:
            continue
        type_id, code_name = entry
        type_name = actv_type_names.get(type_id, "")
        if not type_name or not code_name:
            continue
        task_codes_map.setdefault(assignment.task_id, []).append({"type": type_name, "code": code_name})

    # Resources: TASKRSRC rows per activity, each resolved to its RSRC name. Many
    # contractor XER exports carry no resource data at all — degrade to empty
    # lists/flags rather than erroring. Indexed once from the raw table rather than
    # through PyP6XER's per-task lookups, which rescan every row for every activity.
    rsrc_names = {res.rsrc_id: res.rsrc_name for res in reader.resources if res.rsrc_id}
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

    # Relationships from the raw TASKPRED table in one pass (PyP6XER's
    # task.predecessors is O(activities x relationships): 96 million comparisons on a
    # 4,217-activity export). Cross-project relationships point outside this schedule;
    # the graph would dangle, so they are left out.
    own_ids = {a.task_id for a in project.activities}
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

    sched_options = schedule_options_for(raw_tables, project.proj_id)
    task_rows = {r.get("task_id"): r for r in table_records(raw_tables, "TASK")}
    units_done = {}
    for r in table_records(raw_tables, "TASKRSRC"):
        act = sum(safe_float(_num(r.get(f))) for f in ("act_reg_qty", "act_ot_qty"))
        rem = safe_float(_num(r.get("remain_qty")))
        d, t = units_done.get(r.get("task_id"), (0.0, 0.0))
        units_done[r.get("task_id")] = (d + act, t + act + rem)

    activities = []
    for a in project.activities:
        row = task_rows.get(str(a.task_id), {})
        activities.append({
            "task_id": a.task_id,
            "task_code": a.task_code,
            "task_name": a.task_name,
            "wbs_id": a.wbs_id,
            "status": a.status_code or "",
            "pct_complete": percent_complete(row, units_done.get(str(a.task_id))),
            "pct_complete_type": row.get("complete_pct_type", ""),
            "early_start": a.early_start_date,
            "early_end": a.early_end_date,
            "late_start": a.late_start_date,
            "late_end": a.late_end_date,
            "total_float_hrs": float(a.total_float_hr_cnt) if a.total_float_hr_cnt is not None else None,
            "free_float_hrs": safe_float(a.free_float_hr_cnt),
            "duration_hrs": safe_float(a.target_drtn_hr_cnt),
            "remain_duration_hrs": safe_float(a.remain_drtn_hr_cnt),
            "task_type": a.task_type or "",
            "clndr_id": str(a.clndr_id) if a.clndr_id is not None else "",
            "calendar": cal_dict.get(a.clndr_id, ""),
            "calendar_hrs_per_day": cal_hrs_dict.get(a.clndr_id, 8.0),
            "driving_path_flag": a.driving_path_flag == "Y",
            "cstr_type": a.cstr_type,
            "cstr_date": a.cstr_date,
            "cstr_type2": a.cstr_type2,
            "cstr_date2": a.cstr_date2,
            "act_start": a.act_start_date,
            "act_end": a.act_end_date,
            "target_start": a.target_start_date,
            "target_end": a.target_end_date,
            "activity_codes": task_codes_map.get(a.task_id, []),
            "resource_names": sorted(task_rsrc.get(a.task_id, ())),
        })

    # PyP6XER opens files with errors='ignore', which silently DROPS bytes that aren't valid
    # UTF-8, and P6 commonly exports cp1252, so accented characters in activity names can
    # vanish. The raw tables above decode correctly; the object-parsed names may not.
    if not encoding_ok:
        warnings.append(
            "This file is not valid UTF-8 (P6 often exports cp1252/latin-1). Accented or "
            "special characters in activity names may be missing."
        )

    pid = str(project.proj_id)
    project_row = next((r for r in table_records(raw_tables, "PROJECT") if r.get("proj_id") == pid), {})
    sched_row = next((r for r in table_records(raw_tables, "SCHEDOPTIONS") if r.get("proj_id") == pid), {})

    def recalculate(work_cals, default_cal, longest_path_ids, hrs_per_day):
        return recalc.run(list(task_rows.values()), table_records(raw_tables, "TASKPRED"),
                          project_row, sched_row, work_cals, default_cal, longest_path_ids,
                          hrs_per_day=hrs_per_day)

    return {
        "project": {
            "proj_short_name": project.proj_short_name,
            "data_date": str(project.last_recalc_date) if project.last_recalc_date else None,
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
