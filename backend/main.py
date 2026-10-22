"""
XERlock web API: serves the parsing core (backend/xer.py) over HTTP, and the built frontend.
"""

import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel


logger = logging.getLogger("schedule-app")

# Generous for a text format (a ~20k-activity XER is well under this), but bounded so a
# single oversized upload can't exhaust the server's memory.
MAX_UPLOAD_BYTES = 50 * 1024 * 1024

app = FastAPI(
    title="XERlock",
    version="1.12.0",
    description="Parses Primavera P6 .xer exports and Microsoft Project files (XML, .mpp) in "
    "memory and returns the full schedule (activities, WBS tree, project stats, longest-path "
    "trace) as JSON. Nothing is persisted.",
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
    # Microsoft Project files only (backend/mspdi.py): manually scheduled task, deadline.
    manual: Optional[bool] = None
    deadline: Optional[str] = None

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
    # The CPM engine's reproduction of P6's dates and float (backend/recalc.py):
    # supported/reason, counts compared and differing, and the differences themselves.
    recalculation: Optional[dict] = None
    # DCMA check 12, only when the recalculation reproduces P6 exactly.
    critical_path_test: Optional[dict] = None
    # Which tool wrote the file: xer | mspdi | mpp. The UI names the tool from it.
    source_format: Optional[str] = None
    # .xer only: this project's id, and every project in the file with its activity count.
    proj_id: Optional[int] = None
    projects_in_file: Optional[list] = None
    # Microsoft Project files only (backend/mspdi.py): inactive tasks left out of every
    # population, relationships on summary tasks, Project's own scheduling settings.
    inactive_activities: Optional[int] = None
    summary_links: Optional[list] = None
    msp_options: Optional[dict] = None

class ScheduleData(BaseModel):
    project: ProjectSummary
    wbs_tree: list
    activities: list
    warnings: list = []
    calendars: list = []
    # {table_name: {"fields": [...], "rows": [[...]], "row_count": N, "truncated": bool}}
    raw_tables: dict = {}
    ermhdr: dict = {}


from backend.schedule import EXTENSIONS, parse_schedule as parse_schedule_dict
from backend.isolate import ParseFailed, parse_isolated


def parse_schedule(filepath: str) -> ScheduleData:
    """The parsing core's result, validated against the API models."""
    return ScheduleData(**parse_schedule_dict(filepath))


# The name the tests and scripts used when .xer was the only format.
parse_xer = parse_schedule


# ── API Routes ────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/upload", response_model=ScheduleData)
async def upload_schedule(file: UploadFile = File(...), project: Optional[int] = Form(None)):
    if not file.filename or not file.filename.lower().endswith(EXTENSIONS):
        if file.filename and file.filename.lower().endswith(".pp"):
            raise HTTPException(400, "Asta Powerproject (.pp) files can't be read. In Powerproject, export the "
                                     "project as Microsoft Project XML and open that file instead.")
        raise HTTPException(400, "Only .xer, .xml (Microsoft Project) and .mpp files are accepted")

    # Stream to a temp file in chunks, enforcing the size cap as bytes arrive rather than
    # slurping an unbounded body into memory first. The reader is chosen by content, not
    # by this suffix (backend/schedule.py).
    size = 0
    with tempfile.NamedTemporaryFile(delete=False, suffix=".upload") as tmp:
        tmp_path = tmp.name
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                os.unlink(tmp_path)
                raise HTTPException(413, f"File exceeds the {MAX_UPLOAD_BYTES // (1024*1024)} MB upload limit")
            tmp.write(chunk)

    try:
        # In a child process with a time limit (backend/isolate.py), waited for off the
        # event loop, so one upload can neither freeze nor take down the server.
        data = ScheduleData(**await run_in_threadpool(parse_isolated, tmp_path, project))
    except ValueError as e:
        # The readers' refusals (e.g. "no projects") are written for the user.
        raise HTTPException(422, str(e))
    except ParseFailed as e:
        logger.error("Failed to parse uploaded schedule %r\n%s", file.filename, e.detail)
        raise HTTPException(422, str(e))
    except Exception:
        logger.exception("Failed to parse uploaded schedule %r", file.filename)
        raise HTTPException(422, "Could not parse this file as a P6 .xer export or a Microsoft Project file")
    finally:
        os.unlink(tmp_path)

    return data


# ── Serve frontend ───────────────────────────────────────────────────────────

FRONTEND_DIR = Path(__file__).parent.parent / "frontend" / "dist"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
