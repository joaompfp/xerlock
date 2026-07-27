"""
Schedule App — FastAPI backend with PyP6XER
Parses Primavera P6 XER files and serves structured schedule data.
"""

import os
import tempfile
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
    total_float_hrs: float
    free_float_hrs: float
    duration_hrs: float
    task_type: str
    calendar: Optional[str]
    predecessors: list
    successors: list
    is_critical: bool

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
    critical_path: list

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

    # Build activity lookup by task_id
    act_lookup = {}
    for a in project.activities:
        act_lookup[a.task_id] = a

    # Compute critical path: longest path through TF=0 activities
    # Step 1: compute path lengths (memoized)
    memo = {}

    def compute_path_length(task_id):
        if task_id in memo:
            return memo[task_id]
        a = act_lookup.get(task_id)
        if not a:
            memo[task_id] = 0
            return 0
        dur = safe_float(a.target_drtn_hr_cnt)
        preds = pred_map.get(task_id, [])
        if not preds:
            memo[task_id] = dur
            return dur
        max_len = 0
        for p in preds:
            plen = compute_path_length(p["task_id"])
            if plen > max_len:
                max_len = plen
        memo[task_id] = dur + max_len
        return dur + max_len

    # Step 2: find end milestone (activity with no successors)
    end_ids = [a.task_id for a in project.activities if not succ_map.get(a.task_id)]
    if not end_ids:
        end_ids = [a.task_id for a in project.activities]

    # Compute path lengths for all activities
    for a in project.activities:
        compute_path_length(a.task_id)

    # Step 3: trace critical path from TF=0 activity with longest path
    def find_critical_chain(start_id):
        chain = []
        current = start_id
        visited = set()
        while current and current not in visited:
            visited.add(current)
            chain.append(current)
            a = act_lookup.get(current)
            if not a:
                break
            preds = pred_map.get(current, [])
            if not preds:
                break
            # Among TF=0 predecessors, pick the one with the longest path
            best_pid = None
            best_len = -1
            for p in preds:
                pa = act_lookup.get(p["task_id"])
                if pa and safe_float_or(pa.total_float_hr_cnt) == 0:
                    plen = memo.get(p["task_id"], 0)
                    if plen > best_len:
                        best_len = plen
                        best_pid = p["task_id"]
            if best_pid is None:
                break
            current = best_pid
        return chain

    # Find the TF=0 activity with the longest path
    tf0_activities = [a for a in project.activities if safe_float_or(a.total_float_hr_cnt) == 0]
    if tf0_activities:
        best_start = max(tf0_activities, key=lambda a: memo.get(a.task_id, 0))
        critical_chain = find_critical_chain(best_start.task_id)
    else:
        critical_chain = []
    critical_set = set(critical_chain)

    # Build activities list
    activities = []
    wbs_act_count = {}
    for a in project.activities:
        wbs_act_count[a.wbs_id] = wbs_act_count.get(a.wbs_id, 0) + 1
        es = str(a.early_start_date) if a.early_start_date else None
        ee = str(a.early_end_date) if a.early_end_date else None
        ls = str(a.late_start_date) if a.late_start_date else None
        le = str(a.late_end_date) if a.late_end_date else None
        cal_name = cal_dict.get(a.clndr_id, "")
        tf = safe_float(a.total_float_hr_cnt)
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
            "is_critical": a.task_id in critical_set,
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
    milestones = sum(1 for a in activities if a["task_type"] == "TT_Mile")
    complete = sum(1 for a in activities if a["status"] == "TK_Complete")
    active = sum(1 for a in activities if a["status"] == "TK_Active")
    not_started = sum(1 for a in activities if a["status"] == "TK_NotStart")
    pct = (complete / total * 100) if total > 0 else 0

    dates = [a for a in activities if a["early_start"]]
    earliest = min((a["early_start"] for a in dates), default=None)
    latest = max((a["early_end"] for a in activities if a["early_end"]), default=None)

    # Critical path chain with details
    cp_chain = []
    for tid in critical_chain:
        a = act_lookup.get(tid)
        if a:
            cp_chain.append({
                "task_id": tid,
                "task_code": a.task_code,
                "task_name": a.task_name,
                "duration_hrs": safe_float(a.target_drtn_hr_cnt),
                "early_start": str(a.early_start_date) if a.early_start_date else None,
                "early_end": str(a.early_end_date) if a.early_end_date else None,
                "total_float_hrs": safe_float(a.total_float_hr_cnt),
            })

    return ScheduleData(
        project=ProjectSummary(
            proj_short_name=project.proj_short_name,
            total_activities=total,
            total_wbs=len(wbs_dict),
            total_critical=critical,
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
        critical_path=cp_chain,
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
