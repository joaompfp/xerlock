"""
Recalculation of a parsed .xer: builds the CPM engine's input from the raw tables,
runs it, compares the result with the dates and float P6 stored, and runs the DCMA 12
Critical Path Test when the two agree.

This is the only module that knows both the .xer field names and the engine's data
types. main.py calls `run` once per parse; cpm.py never sees a table.
"""

from datetime import datetime
from typing import Optional

from backend import cpm

# DCMA 12 test delay: 600 working days is the common practice value used with the
# DCMA 14-Point Assessment. It is deliberately far longer than any real float.
CPT_DELAY_DAYS = 600

# Differences listed in the response; the count is always complete.
MAX_DIFFERENCES_LISTED = 500


def _dt(s) -> Optional[datetime]:
    """Raw-table dates are 'YYYY-MM-DD HH:MM' strings, empty when unset."""
    try:
        return datetime.fromisoformat(s.strip()) if s and s.strip() else None
    except ValueError:
        return None


def _hrs(s) -> Optional[float]:
    try:
        return float(s) if s not in (None, "") else None
    except ValueError:
        return None


def engine_input(task_rows: list, pred_rows: list, project: dict, sched: dict):
    """(tasks, links, options) for cpm.schedule from the raw TASK, TASKPRED, PROJECT
    rows of one project and its SCHEDOPTIONS row."""
    pid = str(project.get("proj_id"))
    tasks = [cpm.Task(
        id=int(r["task_id"]),
        task_type=r.get("task_type", ""),
        status=r.get("status_code", ""),
        clndr_id=r.get("clndr_id", ""),
        remaining_hrs=_hrs(r.get("remain_drtn_hr_cnt")) or 0.0,
        act_start=_dt(r.get("act_start_date")),
        act_end=_dt(r.get("act_end_date")),
        cstr_type=r.get("cstr_type", ""),
        cstr_date=_dt(r.get("cstr_date")),
        cstr_type2=r.get("cstr_type2", ""),
        cstr_date2=_dt(r.get("cstr_date2")),
        expect_end=_dt(r.get("expect_end_date")),
        external_dates=bool(_dt(r.get("external_early_start_date")) or _dt(r.get("external_late_end_date"))),
    ) for r in task_rows if r.get("proj_id") == pid]
    # Every relationship touching this project, cross-project ones included: the
    # engine refuses those explicitly rather than dropping them.
    links = []
    for r in pred_rows:
        if r.get("proj_id") != pid and r.get("pred_proj_id") != pid:
            continue
        try:
            links.append(cpm.Link(int(r["pred_task_id"]), int(r["task_id"]), r.get("pred_type", ""),
                                  _hrs(r.get("lag_hr_cnt")) or 0.0))
        except (KeyError, ValueError):
            continue
    # P6 stores its three progress modes as two flags; neither set means Actual Dates.
    if sched.get("sched_progress_override") == "Y":
        mode = "override"
    elif sched.get("sched_retained_logic") == "Y" or not sched:
        mode = "retained"
    else:
        mode = "actual"
    opts = cpm.Options(
        data_date=_dt(project.get("last_recalc_date")),
        progress_mode=mode,
        float_type=sched.get("sched_float_type") or "FT_FF",
        lag_calendar=sched.get("sched_calendar_on_relationship_lag") or "rcal_Predecessor",
        open_ends_critical=sched.get("sched_open_critical_flag") == "Y",
        use_expected_finish=sched.get("sched_use_expect_end_flag") == "Y",
        must_finish=_dt(project.get("plan_end_date")),
        ss_lag_from_actual_start=sched.get("sched_lag_early_start_flag") == "N",
        multiple_float_paths=sched.get("enable_multiple_longest_path_calc") == "Y"
        or any(r.get("float_path") for r in task_rows if r.get("proj_id") == pid),
    )
    return tasks, links, opts


def stored_dates(task_rows: list, pid: str) -> dict:
    """P6's own result per incomplete activity: the remaining early/late dates where
    P6 writes them (restart_date etc.), else the early/late dates, plus float.
    Completed work has no remaining dates or float and is not compared; neither are
    WBS summaries, which the engine does not place."""
    out = {}
    for r in task_rows:
        if r.get("proj_id") != pid or r.get("status_code") == cpm.COMPLETE or r.get("task_type") == "TT_WBS":
            continue
        out[int(r["task_id"])] = cpm.Dates(
            es=_dt(r.get("restart_date")) or _dt(r.get("early_start_date")),
            ef=_dt(r.get("reend_date")) or _dt(r.get("early_end_date")),
            ls=_dt(r.get("rem_late_start_date")) or _dt(r.get("late_start_date")),
            lf=_dt(r.get("rem_late_end_date")) or _dt(r.get("late_end_date")),
            tf=_hrs(r.get("total_float_hr_cnt")),
            ff=_hrs(r.get("free_float_hr_cnt")),
        )
    return out


def _iso(v):
    return v.isoformat(sep=" ", timespec="minutes") if isinstance(v, datetime) else v


def unsupported(reason: str, delay_days: int = CPT_DELAY_DAYS) -> dict:
    """The report for a file the engine does not model at all (a format it has no
    rules for yet): the same shape as `run` returns, with nothing compared."""
    return {
        "supported": False,
        "reason": reason,
        "options": {"progress_mode": "", "float_type": "", "lag_calendar": "", "delay_days": delay_days},
        "compared": 0,
        "excluded": {"complete": 0, "wbs_summary": 0},
        "differing": 0,
        "by_field": {f: 0 for f in cpm.DATE_FIELDS + cpm.FLOAT_FIELDS},
        "differences": [],
        "truncated": False,
    }


def run(task_rows: list, pred_rows: list, project: dict, sched: dict, calendars: dict,
        default_cal, longest_path_ids, delay_days: int = CPT_DELAY_DAYS, hrs_per_day=None):
    """The recalculation report and, when it reproduces P6, the Critical Path Test.
    Returns (recalculation: dict, critical_path_test: dict | None)."""
    pid = str(project.get("proj_id"))
    tasks, links, opts = engine_input(task_rows, pred_rows, project, sched)
    n_complete = sum(1 for t in tasks if t.status == cpm.COMPLETE)
    n_wbs = sum(1 for t in tasks if t.task_type == "TT_WBS")
    report = {
        "supported": False,
        "reason": None,
        "options": {"progress_mode": opts.progress_mode, "float_type": opts.float_type,
                    "lag_calendar": opts.lag_calendar, "delay_days": delay_days},
        "compared": 0,
        "excluded": {"complete": n_complete, "wbs_summary": n_wbs},
        "differing": 0,
        "by_field": {f: 0 for f in cpm.DATE_FIELDS + cpm.FLOAT_FIELDS},
        "differences": [],
        "truncated": False,
    }
    if opts.data_date is None:
        report["reason"] = "the project has no data date (PROJECT.last_recalc_date)"
        return report, None
    reason = cpm.refusal_reason(tasks, links, opts)
    if reason:
        report["reason"] = reason
        return report, None
    try:
        computed = cpm.schedule(tasks, links, calendars, default_cal, opts)
    except cpm.LogicLoop as e:
        report["reason"] = str(e)
        return report, None
    stored = stored_dates(task_rows, pid)
    diffs = cpm.differences(computed, stored)
    report["supported"] = True
    report["compared"] = len(stored)
    report["differing"] = len({d["task_id"] for d in diffs})
    for d in diffs:
        report["by_field"][d["field"]] += 1
    report["differences"] = [{**d, "computed": _iso(d["computed"]), "stored": _iso(d["stored"])}
                             for d in diffs[:MAX_DIFFERENCES_LISTED]]
    report["truncated"] = len(diffs) > MAX_DIFFERENCES_LISTED
    if diffs:
        return report, None

    cpt = cpm.critical_path_test(tasks, links, calendars, default_cal, opts, longest_path_ids,
                                 delay_days=delay_days, hrs_per_day=hrs_per_day or {})
    if cpt:
        cpt = {k: _iso(v) for k, v in cpt.items()}
    return report, cpt
