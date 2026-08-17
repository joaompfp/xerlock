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

app = FastAPI(title="Schedule App", version="0.1.0")

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
    task_type: str
    calendar: Optional[str]
    predecessors: list
    successors: list
    is_critical: bool
    is_longest_path: bool

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
    total_milestones: int
    total_complete: int
    total_active: int
    total_not_started: int
    pct_complete: float
    earliest_start: Optional[str]
    latest_end: Optional[str]

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

    # Build activity lookup
    cal_dict = {}
    for c in reader.calendars:
        cal_dict[c.clndr_id] = c.clndr_name if hasattr(c, "clndr_name") else str(c.clndr_id)

    # Build predecessor/successor maps
    pred_map = {}
    succ_map = {}
    for a in project.activities:
        tid = a.task_id
        pred_map[tid] = []
        succ_map[tid] = []
        if hasattr(a, "predecessors") and a.predecessors:
            for p in a.predecessors:
                pred_map[tid].append({
                    "task_id": p.pred_task_id,
                    "type": p.pred_type,
                    "lag_hrs": float(p.lag_hr_cnt or 0),
                })
                if p.pred_task_id not in succ_map:
                    succ_map[p.pred_task_id] = []
                succ_map[p.pred_task_id].append({
                    "task_id": tid,
                    "type": p.pred_type,
                    "lag_hrs": float(p.lag_hr_cnt or 0),
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
    DRIVING_TOLERANCE_HRS = 1.0

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

    def is_driving(succ_a, pred_a, link_type, lag_hrs):
        base, which, lag = implied_date(pred_a, link_type, lag_hrs)
        if base is None:
            return False
        actual = succ_a.early_start_date if which == "start" else succ_a.early_end_date
        if actual is None:
            return False
        delta_hrs = abs(((actual - base) - lag).total_seconds()) / 3600
        return delta_hrs <= DRIVING_TOLERANCE_HRS

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
            for p in pred_map.get(tid, []):
                pred_a = act_lookup.get(p["task_id"])
                if pred_a and is_driving(succ_a, pred_a, p["type"], p["lag_hrs"]):
                    stack.append(p["task_id"])

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
            "wbs_path": "",
            "status": a.status_code or "",
            "pct_complete": safe_float(a.phys_complete_pct),
            "early_start": es,
            "early_end": ee,
            "late_start": ls,
            "late_end": le,
            "total_float_hrs": tf,
            "free_float_hrs": safe_float(a.free_float_hr_cnt),
            "duration_hrs": safe_float(a.target_drtn_hr_cnt),
            "task_type": a.task_type or "",
            "calendar": cal_name,
            "predecessors": pred_map.get(a.task_id, []),
            "successors": succ_map.get(a.task_id, []),
            "is_critical": tf == 0,
            "is_longest_path": a.task_id in longest_path_ids,
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
    milestones = sum(1 for a in activities if a["task_type"] in ("TT_Mile", "TT_FinMile", "TT_StartMile"))
    complete = sum(1 for a in activities if a["status"] == "TK_Complete")
    active = sum(1 for a in activities if a["status"] == "TK_Active")
    not_started = sum(1 for a in activities if a["status"] == "TK_NotStart")
    pct = (complete / total * 100) if total > 0 else 0

    dates = [a for a in activities if a["early_start"]]
    earliest = min((a["early_start"] for a in dates), default=None)
    latest = max((a["early_end"] for a in activities if a["early_end"]), default=None)

    return ScheduleData(
        project=ProjectSummary(
            proj_short_name=project.proj_short_name,
            total_activities=total,
            total_wbs=len(wbs_dict),
            total_critical=critical,
            total_longest_path=longest_path,
            total_milestones=milestones,
            total_complete=complete,
            total_active=active,
            total_not_started=not_started,
            pct_complete=round(pct, 1),
            earliest_start=earliest,
            latest_end=latest,
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
