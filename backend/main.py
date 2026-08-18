"""
Schedule App — FastAPI backend with PyP6XER
Parses Primavera P6 XER files and serves structured schedule data.
"""

import os
import tempfile
from datetime import timedelta
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from xerparser.reader import Reader

app = FastAPI(
    title="Schedule App",
    version="1.0.0",
    description="Parses Primavera P6 .xer exports in memory and returns the full schedule "
    "(activities, WBS tree, project stats, longest-path trace) as JSON. Nothing is persisted.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    early_start: Optional[str]
    early_end: Optional[str]
    late_start: Optional[str]
    late_end: Optional[str]
    total_float_hrs: Optional[float]
    free_float_hrs: float
    duration_hrs: float
    remain_duration_hrs: float
    task_type: str
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

class ScheduleData(BaseModel):
    project: ProjectSummary
    wbs_tree: list
    activities: list

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
    reader = Reader(filepath)
    project = None
    for p in reader.projects:
        project = p
        break
    if not project:
        raise ValueError("No projects found in XER file")

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
    def resource_names_for(a):
        try:
            names = {rsrc_names.get(tr.rsrc_id) for tr in a.resources if tr.rsrc_id}
        except Exception:
            return []
        return sorted(n for n in names if n)

    # Build predecessor/successor maps. succ_map is derived from pred_map in a
    # separate pass (rather than populated inline while building pred_map) because
    # every activity unconditionally resets its own succ_map[tid] = [] when its turn
    # in the project.activities loop comes up — if that reset ran after an earlier
    # activity had already recorded itself as tid's successor, the earlier entry
    # would be silently wiped. Deriving succ_map by inverting the completed pred_map
    # afterward makes the result independent of iteration order.
    pred_map = {}
    succ_map = {tid: [] for tid in (a.task_id for a in project.activities)}
    for a in project.activities:
        tid = a.task_id
        pred_map[tid] = []
        if hasattr(a, "predecessors") and a.predecessors:
            for p in a.predecessors:
                pred_map[tid].append({
                    "task_id": p.pred_task_id,
                    "type": p.pred_type,
                    "lag_hrs": float(p.lag_hr_cnt or 0),
                })
    for tid, preds in pred_map.items():
        for p in preds:
            succ_map.setdefault(p["task_id"], []).append({
                "task_id": tid,
                "type": p["type"],
                "lag_hrs": p["lag_hrs"],
            })

    # "Longest Path" (P6's alternate critical-activity definition): trace backward
    # from the true finish driver(s) through only the *driving* predecessor
    # relationship(s) at each step — the link(s) whose implied date actually equals
    # the successor's computed early date. This is different from (and usually a
    # strict subset of) plain TF=0: a schedule can have many zero-float activities
    # that aren't actually connected to what's driving the finish date (e.g. they
    # carry their own explicit constraint), while Longest Path only follows the
    # unbroken logic chain. Handles multiple parallel/converging critical chains
    # correctly, unlike a single backward trace from one arbitrary start point.
    act_lookup = {a.task_id: a for a in project.activities}
    # A small epsilon on top of the closest gap, not a fixed absolute tolerance:
    # predecessor/successor calendars routinely differ (a 7-day milestone calendar
    # reacting to a 5-day construction calendar, working-hour offsets, etc.), which
    # can put even the true driving link a full calendar day or more away from an
    # exact date match. Picking whichever predecessor(s) come closest to explaining
    # the successor's computed date is robust to that; a fixed ~1hr tolerance is not
    # — it silently produces zero driving predecessors on any link crossing a
    # calendar boundary, truncating the backward trace after a single step.
    DRIVING_EPSILON_HRS = 1.0

    def implied_date(pred_a, link_type, lag_hrs):
        lag = timedelta(hours=lag_hrs)
        if link_type == "PR_FS":
            return pred_a.early_end_date, "start", lag
        if link_type == "PR_SS":
            return pred_a.early_start_date, "start", lag
        if link_type == "PR_FF":
            return pred_a.early_end_date, "finish", lag
        if link_type == "PR_SF":
            return pred_a.early_start_date, "finish", lag
        return None, None, lag

    def driving_gap_hrs(succ_a, pred_a, link_type, lag_hrs):
        base, which, lag = implied_date(pred_a, link_type, lag_hrs)
        if base is None:
            return None
        actual = succ_a.early_start_date if which == "start" else succ_a.early_end_date
        if actual is None:
            return None
        # Only a predecessor whose implied date is at or before the successor's
        # actual date can be driving it forward; one implying a later date than
        # what's observed isn't consistent with driving this particular link.
        gap = ((actual - base) - lag).total_seconds() / 3600
        return gap if gap >= -DRIVING_EPSILON_HRS else None

    end_activities = [
        a for a in project.activities
        if not succ_map.get(a.task_id) and a.early_end_date
    ]
    longest_path_ids = set()
    if end_activities:
        min_tf = min(safe_float_or(a.total_float_hr_cnt) for a in end_activities)
        stack = [a.task_id for a in end_activities if safe_float_or(a.total_float_hr_cnt) == min_tf]
        while stack:
            tid = stack.pop()
            if tid in longest_path_ids:
                continue
            longest_path_ids.add(tid)
            succ_a = act_lookup.get(tid)
            if not succ_a:
                continue
            gaps = []
            for p in pred_map.get(tid, []):
                pred_a = act_lookup.get(p["task_id"])
                if not pred_a:
                    continue
                gap = driving_gap_hrs(succ_a, pred_a, p["type"], p["lag_hrs"])
                if gap is not None:
                    gaps.append((gap, p["task_id"]))
            if gaps:
                min_gap = min(g for g, _ in gaps)
                for gap, ptid in gaps:
                    if gap <= min_gap + DRIVING_EPSILON_HRS:
                        stack.append(ptid)

    # Build activities list. is_critical uses the standard TF=0 definition (every
    # zero-float activity); is_longest_path uses the driving-chain trace above.
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
            "pct_complete": safe_float(a.phys_complete_pct),
            "early_start": es,
            "early_end": ee,
            "late_start": ls,
            "late_end": le,
            "total_float_hrs": tf,
            "free_float_hrs": safe_float(a.free_float_hr_cnt),
            "duration_hrs": safe_float(a.target_drtn_hr_cnt),
            "remain_duration_hrs": safe_float(a.remain_drtn_hr_cnt),
            "task_type": a.task_type or "",
            "calendar": cal_name,
            "calendar_hrs_per_day": cal_hrs_dict.get(a.clndr_id, 8.0),
            "predecessors": pred_map.get(a.task_id, []),
            "successors": succ_map.get(a.task_id, []),
            # Standard planning convention: the critical path is float <= 0, not just == 0.
            # Activities already behind an imposed date (negative float) are critical too —
            # is_negative_float lets the frontend give them a visually distinct treatment.
            "is_critical": tf is not None and tf <= 0,
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

    dates = [a for a in activities if a["early_start"]]
    earliest = min((a["early_start"] for a in dates), default=None)
    latest = max((a["early_end"] for a in activities if a["early_end"]), default=None)

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
        ),
        wbs_tree=wbs_tree,
        activities=activities,
    )


# ── API Routes ────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/upload", response_model=ScheduleData)
async def upload_xer(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".xer"):
        raise HTTPException(400, "Only .xer files are accepted")

    # Save to temp file
    suffix = ".xer"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        data = parse_xer(tmp_path)
    except Exception as e:
        os.unlink(tmp_path)
        raise HTTPException(422, f"Failed to parse XER: {str(e)}")

    os.unlink(tmp_path)
    return data


# ── Serve frontend ───────────────────────────────────────────────────────────

FRONTEND_DIR = Path(__file__).parent.parent / "frontend" / "dist"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
