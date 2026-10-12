"""
XERlock — FastAPI backend with PyP6XER
Parses Primavera P6 XER files and serves structured schedule data.
"""

import codecs
import logging
import os
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from xerparser.reader import Reader

from backend.cpm import lag_calendar
from backend.worktime import ALL_HOURS, WorkCalendar

logger = logging.getLogger("schedule-app")

# Generous for a text format (a ~20k-activity XER is well under this), but bounded so a
# single oversized upload can't exhaust the server's memory.
MAX_UPLOAD_BYTES = 50 * 1024 * 1024

app = FastAPI(
    title="XERlock",
    version="1.0.0",
    description="Parses Primavera P6 .xer exports in memory and returns the full schedule "
    "(activities, WBS tree, project stats, longest-path trace) as JSON. Nothing is persisted.",
)

# No CORS middleware: the frontend is served same-origin by this app in production, and the
# Vite dev server proxies /api. Cross-origin API consumers should host their own instance.

# The raw-table payload roughly doubles the response size of large schedules; tab-separated
# text compresses extremely well, so gzip keeps the wire size close to what it was before.
app.add_middleware(GZipMiddleware, minimum_size=1024)


@app.middleware("http")
async def cache_headers(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/assets/"):
        # Vite content-hashes these filenames, so they never change under the same URL.
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    else:
        # index.html (and any other top-level file) must always be revalidated,
        # otherwise browsers can keep serving a stale build after a deploy.
        response.headers["Cache-Control"] = "no-cache"
    return response

# ── Data models ──────────────────────────────────────────────────────────────

class ActivitySummary(BaseModel):
    task_id: int
    task_code: str
    task_name: str
    wbs_id: int
    wbs_path: str
    status: str
    pct_complete: float
    pct_complete_type: str
    early_start: Optional[str]
    early_end: Optional[str]
    late_start: Optional[str]
    late_end: Optional[str]
    total_float_hrs: Optional[float]
    free_float_hrs: float
    duration_hrs: float
    remain_duration_hrs: float
    task_type: str
    clndr_id: str
    calendar: Optional[str]
    calendar_hrs_per_day: float
    predecessors: list
    successors: list
    is_critical: bool
    is_longest_path: bool
    is_negative_float: bool
    driving_path_flag: bool
    cstr_type: Optional[str]
    cstr_date: Optional[str]
    cstr_type2: Optional[str]
    cstr_date2: Optional[str]
    act_start: Optional[str]
    act_end: Optional[str]
    target_start: Optional[str]
    target_end: Optional[str]
    activity_codes: list
    resource_names: list

class WBSNode(BaseModel):
    wbs_id: int
    wbs_short_name: str
    wbs_name: str
    parent_wbs_id: Optional[int]
    seq_num: int
    level: int
    children: list
    activity_count: int

class ProjectSummary(BaseModel):
    proj_short_name: str
    total_activities: int
    total_wbs: int
    total_critical: int
    total_longest_path: int
    total_negative_float: int
    total_milestones: int
    total_complete: int
    total_active: int
    total_not_started: int
    pct_complete: float
    earliest_start: Optional[str]
    latest_end: Optional[str]
    data_date: Optional[str]
    has_resources: bool
    has_activity_codes: bool
    activity_code_types: list
    # P6 scheduling options the computed dates depend on (see schedule_options_for).
    schedule_options: dict = {}
    # DCMA check 13; None when it cannot be computed (no data date, finish complete).
    cpli: Optional[dict] = None

class ScheduleData(BaseModel):
    project: ProjectSummary
    wbs_tree: list
    activities: list
    warnings: list = []
    calendars: list = []
    # {table_name: {"fields": [...], "rows": [[...]], "row_count": N, "truncated": bool}}
    raw_tables: dict = {}
    ermhdr: dict = {}


# Per-table row cap for the raw inspector. Far above any real single-project export
# (TASKPRED on a 10k-activity file is ~30k rows, which still fits) but bounds the JSON
# payload; the frontend surfaces `truncated` explicitly so nothing is silently dropped.
RAW_TABLE_ROW_CAP = 50_000

# A relationship drives its successor when its free float is zero. Dates in a .xer are
# minute-resolution, so anything within a minute either side is zero.
DRIVING_TOLERANCE_HRS = 1 / 60

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


def build_calendars(calendars: list, activities: list):
    """Calendar register: each calendar with how many activities use it."""
    assigned = {}
    for a in activities:
        assigned[a["clndr_id"]] = assigned.get(a["clndr_id"], 0) + 1
    out = [{**c, "assigned_count": assigned.get(c["clndr_id"], 0)} for c in calendars]
    # Most-used first; unused resource calendars sink to the bottom.
    out.sort(key=lambda c: -c["assigned_count"])
    return out

def parse_p6_datetime(val):
    """P6 dates arrive as datetime objects from PyP6XER or 'YYYY-MM-DD HH:MM' strings
    from the raw tables."""
    if val is None or isinstance(val, datetime):
        return val
    try:
        return datetime.fromisoformat(str(val).strip())
    except ValueError:
        return None


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

def parse_xer(filepath: str) -> ScheduleData:
    # Raw pass first, independent of PyP6XER: decode as UTF-8 with cp1252 fallback
    # (P6's usual export encoding), so the table inspector shows accented characters
    # correctly even where the object parser drops them.
    raw_bytes = Path(filepath).read_bytes()
    try:
        raw_text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
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

    # Build WBS tree
    wbs_dict = {}
    for w in project.wbss:
        wbs_dict[w.wbs_id] = {
            "wbs_id": w.wbs_id,
            "wbs_short_name": w.wbs_short_name,
            "wbs_name": w.wbs_name,
            "parent_wbs_id": w.parent_wbs_id if w.parent_wbs_id and w.parent_wbs_id != "0" else None,
            "seq_num": int(getattr(w, "seq_num", 0) or 0),
            "level": 0,
            "children": [],
            "activity_count": 0,
        }

    # Build parent-child relationships
    root_ids = []
    for wid, w in wbs_dict.items():
        parent = w["parent_wbs_id"]
        if parent and int(parent) in wbs_dict:
            wbs_dict[int(parent)]["children"].append(wid)
        else:
            root_ids.append(wid)

    # Assign levels
    def assign_level(wid, level):
        wbs_dict[wid]["level"] = level
        for child in wbs_dict[wid]["children"]:
            assign_level(child, level + 1)

    for rid in root_ids:
        assign_level(rid, 0)

    # WBS breadcrumb per node (e.g. "MAIN WORKS / Level 01 / Electrical"), memoized
    # since many activities share the same WBS chain.
    wbs_path_cache = {}
    def wbs_path_for(wid):
        if wid is None or wid not in wbs_dict:
            return ""
        if wid in wbs_path_cache:
            return wbs_path_cache[wid]
        node = wbs_dict[wid]
        if node["level"] == 0:
            # The root WBS node is the project itself, already shown in the page header —
            # omit it so breadcrumbs start from the first real WBS level.
            path = ""
        else:
            parent_path = wbs_path_for(node["parent_wbs_id"])
            path = f"{parent_path} / {node['wbs_name']}" if parent_path else node["wbs_name"]
        wbs_path_cache[wid] = path
        return path

    # Build activity lookup
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

    # Resources: task.resources looks up TASKRSRC rows for the activity; resolve each to
    # its RSRC name. Many contractor XER exports carry no resource data at all — degrade
    # to empty lists/flags rather than erroring.
    rsrc_names = {res.rsrc_id: res.rsrc_name for res in reader.resources if res.rsrc_id}
    # Indexed once from raw TASKRSRC for the same reason as TASKPRED above.
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

    def resource_names_for(a):
        return sorted(task_rsrc.get(a.task_id, ()))

    # Build predecessor/successor maps. succ_map is derived from pred_map in a
    # separate pass (rather than populated inline while building pred_map) because
    # every activity unconditionally resets its own succ_map[tid] = [] when its turn
    # in the project.activities loop comes up — if that reset ran after an earlier
    # activity had already recorded itself as tid's successor, the earlier entry
    # would be silently wiped. Deriving succ_map by inverting the completed pred_map
    # afterward makes the result independent of iteration order.
    # Built from the raw TASKPRED table in one pass rather than from PyP6XER's
    # task.predecessors, which rescans every relationship row for every activity —
    # O(activities x relationships). On a 4,217-activity export that was 96 million
    # comparisons and about 25 of the 31 seconds spent parsing.
    own_ids = {a.task_id for a in project.activities}
    pred_map = {tid: [] for tid in own_ids}
    succ_map = {tid: [] for tid in own_ids}
    pred_tbl = raw_tables.get("TASKPRED")
    if pred_tbl:
        idx = {f: n for n, f in enumerate(pred_tbl["fields"])}
        for row in pred_tbl["rows"]:
            try:
                succ_id = int(row[idx["task_id"]])
                pred_id = int(row[idx["pred_task_id"]])
            except (ValueError, KeyError, IndexError):
                continue
            # Cross-project relationships point outside this schedule; the graph
            # would dangle, so they are left out (as they were before).
            if succ_id not in own_ids or pred_id not in own_ids:
                continue
            lag_raw = row[idx["lag_hr_cnt"]] if "lag_hr_cnt" in idx else ""
            try:
                lag = float(lag_raw or 0)
            except ValueError:
                lag = 0.0
            pred_map[succ_id].append({
                "task_id": pred_id,
                "type": row[idx["pred_type"]] if "pred_type" in idx else "",
                "lag_hrs": lag,
            })
    for tid, preds in pred_map.items():
        for p in preds:
            succ_map.setdefault(p["task_id"], []).append({
                "task_id": tid,
                "type": p["type"],
                "lag_hrs": p["lag_hrs"],
            })

    # Driving relationships, the way P6 defines them: a link drives its successor when
    # its *relationship free float* is zero — the successor's date sits exactly where
    # the link (plus its lag) puts it, measured in working time. Measured in clock time
    # instead, an ordinary Friday-to-Monday FS link shows a 64-hour "gap", nothing is
    # ever exactly driving, and picking the closest predecessor marks links driving
    # that P6 does not (an activity held by a constraint or by the data date has no
    # driving predecessor at all, and the trace must stop there).
    #   lag:  applied on the calendar the project's scheduling options name
    #         (SCHEDOPTIONS.sched_calendar_on_relationship_lag);
    #   gap:  measured on the successor's calendar, since P6 places the successor at
    #         the first working moment on its own calendar after the link allows.
    act_lookup = {a.task_id: a for a in project.activities}
    sched_options = schedule_options_for(raw_tables, project.proj_id)
    work_cals = {c["clndr_id"]: WorkCalendar(c["weekdays"], c["exceptions"]) for c in calendars}
    default_cal = next((work_cals[c["clndr_id"]] for c in calendars if c["default_flag"]), None)

    def cal_of(a):
        return work_cals.get(str(a.clndr_id)) or default_cal or ALL_HOURS

    lag_basis = sched_options.get("lag_calendar", "rcal_Predecessor")

    def lag_cal(pred_a, succ_a):
        return lag_calendar(lag_basis, cal_of(pred_a), cal_of(succ_a), default_cal)

    def relationship_free_float_hrs(succ_a, pred_a, link_type, lag_hrs):
        """Working hours between where the link puts the successor and where it is.
        None when either date is missing or the link type is unknown."""
        ends = {
            "PR_FS": (pred_a.early_end_date, succ_a.early_start_date),
            "PR_SS": (pred_a.early_start_date, succ_a.early_start_date),
            "PR_FF": (pred_a.early_end_date, succ_a.early_end_date),
            "PR_SF": (pred_a.early_start_date, succ_a.early_end_date),
        }.get(link_type)
        if not ends or None in ends:
            return None
        implied = lag_cal(pred_a, succ_a).add_working_hours(ends[0], lag_hrs)
        return cal_of(succ_a).working_hours_between(implied, ends[1])

    for a in project.activities:
        for p in pred_map.get(a.task_id, []):
            pred_a = act_lookup.get(p["task_id"])
            rff = relationship_free_float_hrs(a, pred_a, p["type"], p["lag_hrs"]) if pred_a else None
            p["free_float_hrs"] = None if rff is None else round(rff, 2)
            p["driving"] = rff is not None and abs(rff) <= DRIVING_TOLERANCE_HRS
    # Mirror onto the successor lists so both directions of the panel carry the flag.
    for tid, succs in succ_map.items():
        for s in succs:
            s["driving"] = False
            s["free_float_hrs"] = None
            for p in pred_map.get(s["task_id"], []):
                if p["task_id"] == tid and p["type"] == s["type"] and p["lag_hrs"] == s["lag_hrs"]:
                    s["driving"] = p["driving"]
                    s["free_float_hrs"] = p["free_float_hrs"]
                    break

    # Longest Path (P6's alternate critical definition, AACE 49R-06's preferred one):
    # from the activity finishing last, walk backward through driving links only. The
    # chain ends where no link drives — at the project start, or at an activity held
    # by a constraint or the data date. Computed independently of P6's own stored flag
    # (driving_path_flag) so the two can be cross-checked: a disagreement means either
    # this trace is wrong or the schedule was not recalculated after its last edit.
    finish_activity = max(
        (a for a in project.activities if not succ_map.get(a.task_id) and a.early_end_date),
        key=lambda a: a.early_end_date,
        default=None,
    )
    longest_path_ids = set()
    if finish_activity:
        finish_end = finish_activity.early_end_date
        stack = [a.task_id for a in project.activities
                 if not succ_map.get(a.task_id) and a.early_end_date == finish_end]
        while stack:
            tid = stack.pop()
            if tid in longest_path_ids:
                continue
            longest_path_ids.add(tid)
            stack.extend(p["task_id"] for p in pred_map.get(tid, []) if p["driving"])

    # Critical Path Length Index (DCMA check 13): (CPL + TF) / CPL, where CPL is the
    # working time from the data date to the project finish and TF the finish's total
    # float. Below 0.95 the remaining path must be compressed to make the date.
    cpli = None
    data_date = parse_p6_datetime(project.last_recalc_date)
    if finish_activity and data_date and finish_activity.total_float_hr_cnt is not None:
        cpl_hrs = cal_of(finish_activity).working_hours_between(data_date, finish_activity.early_end_date)
        if cpl_hrs > 0:
            tf_hrs = float(finish_activity.total_float_hr_cnt)
            cpli = {
                "value": round((cpl_hrs + tf_hrs) / cpl_hrs, 3),
                "cpl_hrs": round(cpl_hrs, 1),
                "tf_hrs": tf_hrs,
                "finish_task_id": finish_activity.task_id,
            }

    # Critical, as this project defines it (PROJECT.critical_path_type): either total
    # float at or below the project's own threshold (critical_drtn_hr_cnt — P6's
    # default is 0, but contracts often set it higher), or P6's Longest Path.
    crit_threshold = sched_options["critical_float_hrs"]
    p6_flags_present = any(a.driving_path_flag == "Y" for a in project.activities)

    def critical(a, tf):
        if sched_options["critical_type"] == "CT_DrivPath":
            return (a.driving_path_flag == "Y") if p6_flags_present else a.task_id in longest_path_ids
        return tf is not None and tf <= crit_threshold

    task_rows = {r.get("task_id"): r for r in table_records(raw_tables, "TASK")}
    units_done = {}
    for r in table_records(raw_tables, "TASKRSRC"):
        act = sum(safe_float(_num(r.get(f))) for f in ("act_reg_qty", "act_ot_qty"))
        rem = safe_float(_num(r.get("remain_qty")))
        d, t = units_done.get(r.get("task_id"), (0.0, 0.0))
        units_done[r.get("task_id")] = (d + act, t + act + rem)

    activities = []
    wbs_act_count = {}
    for a in project.activities:
        wbs_act_count[a.wbs_id] = wbs_act_count.get(a.wbs_id, 0) + 1
        es = str(a.early_start_date) if a.early_start_date else None
        ee = str(a.early_end_date) if a.early_end_date else None
        ls = str(a.late_start_date) if a.late_start_date else None
        le = str(a.late_end_date) if a.late_end_date else None
        cal_name = cal_dict.get(a.clndr_id, "")
        tf = float(a.total_float_hr_cnt) if a.total_float_hr_cnt is not None else None
        activities.append({
            "task_id": a.task_id,
            "task_code": a.task_code,
            "task_name": a.task_name,
            "wbs_id": a.wbs_id,
            "wbs_path": wbs_path_for(a.wbs_id),
            "status": a.status_code or "",
            "pct_complete": percent_complete(task_rows.get(str(a.task_id), {}), units_done.get(str(a.task_id))),
            "pct_complete_type": task_rows.get(str(a.task_id), {}).get("complete_pct_type", ""),
            "early_start": es,
            "early_end": ee,
            "late_start": ls,
            "late_end": le,
            "total_float_hrs": tf,
            "free_float_hrs": safe_float(a.free_float_hr_cnt),
            "duration_hrs": safe_float(a.target_drtn_hr_cnt),
            "remain_duration_hrs": safe_float(a.remain_drtn_hr_cnt),
            "task_type": a.task_type or "",
            "clndr_id": str(a.clndr_id) if a.clndr_id is not None else "",
            "calendar": cal_name,
            "calendar_hrs_per_day": cal_hrs_dict.get(a.clndr_id, 8.0),
            "predecessors": pred_map.get(a.task_id, []),
            "successors": succ_map.get(a.task_id, []),
            # Negative float is critical too (it is below any threshold);
            # is_negative_float lets the frontend give it a visually distinct treatment.
            "is_critical": critical(a, tf),
            "is_longest_path": a.task_id in longest_path_ids,
            "is_negative_float": tf is not None and tf < 0,
            "driving_path_flag": a.driving_path_flag == "Y",
            "cstr_type": a.cstr_type,
            "cstr_date": str(a.cstr_date) if a.cstr_date else None,
            "cstr_type2": a.cstr_type2,
            "cstr_date2": str(a.cstr_date2) if a.cstr_date2 else None,
            "act_start": str(a.act_start_date) if a.act_start_date else None,
            "act_end": str(a.act_end_date) if a.act_end_date else None,
            "target_start": str(a.target_start_date) if a.target_start_date else None,
            "target_end": str(a.target_end_date) if a.target_end_date else None,
            "activity_codes": task_codes_map.get(a.task_id, []),
            "resource_names": resource_names_for(a),
        })

    # Update WBS activity counts
    for wid in wbs_act_count:
        if wid in wbs_dict:
            wbs_dict[wid]["activity_count"] = wbs_act_count[wid]

    # Build WBS tree as nested list
    def build_tree(wid):
        node = wbs_dict[wid].copy()
        node["children"] = [build_tree(c) for c in wbs_dict[wid]["children"]]
        return node

    wbs_tree = [build_tree(rid) for rid in root_ids]

    # Stats
    total = len(activities)
    critical = sum(1 for a in activities if a["is_critical"])
    longest_path = sum(1 for a in activities if a["is_longest_path"])
    negative_float = sum(1 for a in activities if a["is_negative_float"])
    milestones = sum(1 for a in activities if a["task_type"] in ("TT_Mile", "TT_FinMile", "TT_StartMile"))
    complete = sum(1 for a in activities if a["status"] == "TK_Complete")
    active = sum(1 for a in activities if a["status"] == "TK_Active")
    not_started = sum(1 for a in activities if a["status"] == "TK_NotStart")
    pct = (complete / total * 100) if total > 0 else 0

    # Project range uses the display-date convention (actual once started/finished,
    # early otherwise): completed work's early dates are reset to the data date by P6,
    # so an early-dates-only range would exclude everything already built.
    starts = [(a["act_start"] or a["early_start"]) for a in activities]
    ends = [(a["act_end"] or a["early_end"]) for a in activities]
    earliest = min((d for d in starts if d), default=None)
    latest = max((d for d in ends if d), default=None)

    has_resources = len(rsrc_names) > 0
    activity_code_types = sorted(set(actv_type_names.values()))

    return ScheduleData(
        project=ProjectSummary(
            proj_short_name=project.proj_short_name,
            total_activities=total,
            total_wbs=len(wbs_dict),
            total_critical=critical,
            total_longest_path=longest_path,
            total_negative_float=negative_float,
            total_milestones=milestones,
            total_complete=complete,
            total_active=active,
            total_not_started=not_started,
            pct_complete=round(pct, 1),
            earliest_start=earliest,
            latest_end=latest,
            data_date=str(project.last_recalc_date) if project.last_recalc_date else None,
            has_resources=has_resources,
            has_activity_codes=len(activity_code_types) > 0,
            activity_code_types=activity_code_types,
            schedule_options=sched_options,
            cpli=cpli,
        ),
        wbs_tree=wbs_tree,
        activities=activities,
        warnings=warnings,
        calendars=build_calendars(calendars, activities),
        raw_tables=raw_tables,
        ermhdr=ermhdr,
    )


# ── API Routes ────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/upload", response_model=ScheduleData)
async def upload_xer(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".xer"):
        raise HTTPException(400, "Only .xer files are accepted")

    # Stream to a temp file in chunks, enforcing the size cap as bytes arrive rather than
    # slurping an unbounded body into memory first. Along the way, incrementally validate
    # UTF-8: PyP6XER opens files with errors='ignore', which silently DROPS any bytes that
    # aren't valid UTF-8 — and P6 commonly exports cp1252/latin-1, so accented characters
    # in activity names would vanish without a trace. We can't fix the upstream decode,
    # but we can tell the user their names may be mangled.
    utf8_checker = codecs.getincrementaldecoder("utf-8")()
    encoding_ok = True
    size = 0
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xer") as tmp:
        tmp_path = tmp.name
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                os.unlink(tmp_path)
                raise HTTPException(413, f"File exceeds the {MAX_UPLOAD_BYTES // (1024*1024)} MB upload limit")
            if encoding_ok:
                try:
                    utf8_checker.decode(chunk)
                except UnicodeDecodeError:
                    encoding_ok = False
            tmp.write(chunk)

    try:
        # The parse is CPU-bound and can take seconds-to-minutes on large schedules;
        # run it off the event loop so one upload doesn't freeze the server for everyone.
        data = await run_in_threadpool(parse_xer, tmp_path)
    except ValueError as e:
        # Deliberate validation errors (e.g. "no projects") are safe to show verbatim.
        raise HTTPException(422, str(e))
    except Exception:
        logger.exception("Failed to parse uploaded XER %r", file.filename)
        raise HTTPException(422, "Could not parse this file as a valid P6 .xer export")
    finally:
        os.unlink(tmp_path)

    if not encoding_ok:
        data.warnings.append(
            "This file is not valid UTF-8 (P6 often exports cp1252/latin-1). Accented or "
            "special characters in activity names may be missing."
        )
    return data


# ── Serve frontend ───────────────────────────────────────────────────────────

FRONTEND_DIR = Path(__file__).parent.parent / "frontend" / "dist"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
