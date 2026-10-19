"""
Recalculation of a Microsoft Project file: builds the Project engine's input from the
MSPDI elements, decides what the engine must refuse and which of its rules the oracle
corpus never saw, runs it, compares the result with the dates and slack Project stored,
and runs the DCMA 12 Critical Path Test when the two agree and no uncovered rule is in
play.

This is the only module that knows both the MSPDI element names and cpm_msp's data
types, as recalc.py is for the .xer tables. backend/mspdi.py hands it the parsed
elements; cpm_msp.py never sees XML. SPEC-MSPROJECT.md §7 is the design record.
"""

from datetime import datetime
from typing import Optional

from backend import cpm_core, cpm_msp, mspdi, recalc
from backend.cpm_msp import ALAP, ASAP, FNET, FNLT, MSO, SNLT
from backend.worktime import ALL_HOURS

LAG_CALENDAR = "rcal_Successor"

UNCOVERED_LABELS = {
    "deadline": "deadlines",
    "alap": "As Late As Possible constraints",
    "snlt": "Start No Later Than constraints",
    "fnlt": "Finish No Later Than constraints",
    "fnet": "Finish No Earlier Than constraints",
    "mso": "Must Start On constraints",
    "started_constraint": "constraints on started tasks",
    "elapsed_duration": "elapsed durations",
    "elapsed_lag": "elapsed lags",
    "pct_lag": "percentage lags",
    "two_calendars": "relationships across two calendars",
}


class _Reader:
    """Typed access to one task's elements."""

    def __init__(self, task):
        self.uid = task["uid"]
        self.t = task["t"]
        self.el = task["el"]

    def date(self, name):
        return mspdi.parse_date(self.t(name))

    def hours(self, name):
        return mspdi.iso_duration_hours(self.t(name)) or 0.0

    def flag(self, name):
        return mspdi._flag(self.t(name)) is True

    def int(self, name, default=0):
        return mspdi._int(self.t(name), default)


def _same_working_time(a: dict, b: dict) -> bool:
    """Two decoded calendars define the same working time: same weekday periods and
    the same dated exceptions (derived calendars arrive resolved, so an untouched
    resource calendar compares equal to the project calendar it is based on)."""
    return a["weekdays"] == b["weekdays"] and a["exceptions"] == b["exceptions"]


def build(ctx: dict):
    """(tasks, links, refusals, uncovered, stored, counts) from the reader's context:
    the engine's input, why the file is refused (a list of reasons, in order), which
    uncovered rules it rests on, Project's stored values per scheduled task, and the
    counts the report shows."""
    tasks_meta, is_summary, inactive = ctx["tasks"], ctx["is_summary"], ctx["inactive"]
    cal_names, default_cal = ctx["cal_names"], ctx["default_cal"]
    decoded = {c["clndr_id"]: c for c in ctx["calendars"]}
    source_format = ctx["source_format"]
    work_cals = ctx["work_cals"]
    absent_slack = 0.0 if source_format == "mpp" else None

    by_uid = {task["uid"]: task for task in tasks_meta}
    children = {}
    for task in tasks_meta:
        if task["parent"] is not None:
            children.setdefault(task["parent"]["uid"], []).append(task["uid"])

    def scheduled(uid):
        return uid in by_uid and not is_summary[uid] and uid not in inactive

    def leaves(uid):
        """The active, non-summary descendants of a summary task, in file order."""
        out = []
        for c in children.get(uid, []):
            if c in inactive:
                continue
            if is_summary[c]:
                out.extend(leaves(c))
            else:
                out.append(c)
        return out

    def cal_of(uid):
        cid = (by_uid[uid]["t"]("CalendarUID") or "").strip()
        return cid if cid in cal_names else default_cal

    refusals = []
    counts = {"manual": 0, "levelling": 0, "split": 0, "recurring": 0, "external": 0, "cross_project": 0,
              "summary_constraint": 0, "summary_logic": 0, "resource": 0}
    uncovered = set()
    tasks, stored = [], {}
    start_of = {}

    for task in tasks_meta:
        uid = task["uid"]
        if not scheduled(uid):
            if is_summary[uid] and uid not in inactive and (by_uid[uid]["t"]("ConstraintType") or "0").strip() not in ("0", ""):
                counts["summary_constraint"] += 1
            continue
        r = _Reader(task)
        act_start, act_end = r.date("ActualStart"), r.date("ActualFinish")
        started, finished = act_start is not None, act_end is not None
        constraint = r.int("ConstraintType", 0) or 0
        cstr_date = r.date("ConstraintDate") if constraint not in (ASAP, ALAP) else None
        duration = r.hours("Duration")
        deadline = r.date("Deadline")
        fmt = (r.t("DurationFormat") or "").strip()
        cid = cal_of(uid)
        if r.flag("Manual") and not finished:
            counts["manual"] += 1
        if r.flag("Recurring"):
            counts["recurring"] += 1
        if r.flag("IsSubproject") or r.flag("ExternalTask"):
            counts["external"] += 1
        # A task's levelling delay is honoured (cpm_msp.Task.leveling_delay_hrs); only an
        # assignment's, in regular duration units, is refused below.
        leveling_delay = mspdi.tenths_of_minutes_hours(r.t("LevelingDelay")) or 0.0
        # A split or contoured task: its stored dates span more working time than
        # its duration (an in-progress split shows it as Resume after Stop with
        # working time between; an unstarted split only as the longer span, since
        # the split lives in timephased data this reader does not keep).
        remaining = r.hours("RemainingDuration") if r.t("RemainingDuration") else (0.0 if finished else max(0.0, duration - r.hours("ActualDuration")))
        cal = ALL_HOURS if fmt in mspdi.ELAPSED_LAG_FORMATS else (work_cals.get(cid) or ctx["default_cal_obj"] or ALL_HOURS)
        start, finish = r.date("Start"), r.date("Finish")
        if start and finish and cal.working_hours_between(start, finish) > duration + cpm_core.MINUTE_HRS:
            counts["split"] += 1
        if deadline is not None:
            uncovered.add("deadline")
        if constraint == ALAP:
            uncovered.add("alap")
        elif constraint == SNLT:
            uncovered.add("snlt")
        elif constraint == FNLT:
            uncovered.add("fnlt")
        elif constraint == FNET:
            uncovered.add("fnet")
        elif constraint == MSO:
            uncovered.add("mso")
        if started and not finished and constraint not in (ASAP, ALAP, FNET):
            uncovered.add("started_constraint")
        if fmt in mspdi.ELAPSED_LAG_FORMATS:
            uncovered.add("elapsed_duration")
        start_of[uid] = r.date("Start")
        tasks.append(cpm_msp.Task(
            id=uid,
            clndr_id=cid,
            duration_hrs=duration,
            remaining_hrs=remaining,
            actual_hrs=r.hours("ActualDuration"),
            elapsed=fmt in mspdi.ELAPSED_LAG_FORMATS,
            milestone=r.flag("Milestone"),
            act_start=act_start,
            act_end=act_end,
            constraint=constraint,
            cstr_date=cstr_date,
            deadline=deadline,
            leveling_delay_hrs=max(0.0, leveling_delay),
        ))
        tf = mspdi.tenths_of_minutes_hours(r.t("TotalSlack"))
        ff = mspdi.tenths_of_minutes_hours(r.t("FreeSlack"))
        stored[uid] = cpm_core.Dates(
            es=r.date("Start"), ef=r.date("Finish"), ls=r.date("LateStart"), lf=r.date("LateFinish"),
            tf=absent_slack if tf is None else tf, ff=absent_slack if ff is None else ff,
        )

    # Relationships. Logic on a summary task is expanded to its leaves (MPXJ
    # MicrosoftScheduler L1001-1049): a summary predecessor of an SS or SF link stands
    # for its earliest-starting leaf, of an FS or FF link for every leaf; a summary
    # successor stands for every leaf.
    links = []
    summary_links = []
    for task in tasks_meta:
        uid = task["uid"]
        if uid in inactive:
            continue
        for link in task["el"].findall(mspdi._T + "PredecessorLink"):
            if mspdi._flag(link.findtext(mspdi._T + "CrossProject")):
                counts["cross_project"] += 1
                continue
            pred_uid = mspdi._int(link.findtext(mspdi._T + "PredecessorUID"))
            if pred_uid not in by_uid or pred_uid in inactive:
                continue
            ltype = mspdi.LINK_TYPES.get((link.findtext(mspdi._T + "Type") or "1").strip(), "PR_FS")
            fmt = (link.findtext(mspdi._T + "LagFormat") or "").strip()
            lag_raw = mspdi._int(link.findtext(mspdi._T + "LinkLag"), 0) or 0
            if fmt in mspdi.PERCENT_LAG_FORMATS:
                lag_hrs = lag_raw / 100 * (mspdi.iso_duration_hours(by_uid[pred_uid]["t"]("Duration")) or 0.0)
                if lag_raw:
                    uncovered.add("pct_lag")
            else:
                lag_hrs = lag_raw / 600
            elapsed = fmt in mspdi.ELAPSED_LAG_FORMATS
            if elapsed and lag_raw:
                uncovered.add("elapsed_lag")
            preds = [pred_uid] if scheduled(pred_uid) else (leaves(pred_uid) if is_summary[pred_uid] else [])
            succs = [uid] if scheduled(uid) else (leaves(uid) if is_summary[uid] else [])
            inherited = is_summary[pred_uid] or is_summary[uid]
            if inherited:
                counts["summary_logic"] += 1
                if is_summary[pred_uid] and ltype in ("PR_SS", "PR_SF") and preds:
                    preds = [min(preds, key=lambda u: (start_of.get(u) is None, start_of.get(u) or datetime.min))]
                if scheduled(pred_uid) and succs:
                    # The task's own link to a summary: its free slack is measured
                    # against the summary's rolled-up date (cpm_msp.Options.summary_links).
                    summary_links.append((pred_uid, ltype, round(lag_hrs, 4), elapsed, tuple(succs)))
            for p in preds:
                for s in succs:
                    if p == s:
                        continue
                    if not _same_working_time(decoded[cal_of(p)], decoded[cal_of(s)]):
                        uncovered.add("two_calendars")
                    links.append(cpm_core.Link(p, s, ltype, round(lag_hrs, 4), elapsed, inherited))

    # Resource-driven tasks (the narrow rule, SPEC-MSPROJECT §7.5): a work resource
    # assigned with units above zero drives the task when its calendar defines other
    # working time than the task's, when the assignment carries a levelling delay, or
    # when its dates have moved off the task's.
    resources = {}
    for res in ctx["root"].findall(f"{mspdi._T}Resources/{mspdi._T}Resource"):
        ruid = (res.findtext(mspdi._T + "UID") or "").strip()
        resources[ruid] = ((res.findtext(mspdi._T + "Type") or "").strip(), (res.findtext(mspdi._T + "CalendarUID") or "").strip())
    task_by_id = {t.id: t for t in tasks}
    driven = set()
    for asg in ctx["root"].findall(f"{mspdi._T}Assignments/{mspdi._T}Assignment"):
        g = lambda name: asg.findtext(mspdi._T + name)
        tuid = mspdi._int(g("TaskUID"))
        res = resources.get((g("ResourceUID") or "").strip())
        if tuid not in task_by_id or res is None or res[0] != "1":
            continue
        try:
            units = float(g("Units") or 0)
        except ValueError:
            units = 0.0
        if units <= 0:
            continue
        task = task_by_id[tuid]
        r = _Reader(by_uid[tuid])
        asg_cal = task.clndr_id if r.flag("IgnoreResourceCalendar") or res[1] not in decoded else res[1]
        if not _same_working_time(decoded[asg_cal], decoded[task.clndr_id]):
            driven.add(tuid)
        if (mspdi.tenths_of_minutes_hours(g("LevelingDelay")) or 0.0) > 0:
            driven.add(tuid)
            counts["levelling"] += 1
        a_start, a_finish = mspdi.parse_date(g("Start")), mspdi.parse_date(g("Finish"))
        if (a_start and stored[tuid].es and a_start != stored[tuid].es) or (a_finish and stored[tuid].ef and a_finish != stored[tuid].ef):
            driven.add(tuid)
    counts["resource"] = len(driven)

    if ctx["project_start"] is None:
        refusals.append("the project has no start date (Project/StartDate)")
    if ctx["schedule_from_start"] is False:
        refusals.append("the project is scheduled from its finish date; only start-date scheduling is modelled")
    if counts["manual"]:
        refusals.append(_n(counts["manual"], "manually scheduled task is", "manually scheduled tasks are") + " incomplete: their dates are typed, not computed, so the schedule cannot be recalculated")
    if counts["levelling"]:
        refusals.append(_n(counts["levelling"], "assignment carries", "assignments carry") + " a levelling delay in regular duration units, which the oracle has not validated")
    if counts["split"]:
        refusals.append(_n(counts["split"], "task is split or contoured", "tasks are split or contoured") + ": the stored dates span more working time than the duration")
    if counts["recurring"]:
        refusals.append(_n(counts["recurring"], "recurring task", "recurring tasks") + ": Project generates and constrains their occurrences itself")
    if counts["external"] or counts["cross_project"]:
        refusals.append(_n(counts["external"] + counts["cross_project"], "task or relationship belongs", "tasks or relationships belong") + " to inserted or external projects: their dates come from another file")
    if counts["summary_constraint"]:
        refusals.append(_n(counts["summary_constraint"], "summary task carries", "summary tasks carry") + " a constraint")
    if ctx["multiple_critical_paths"]:
        refusals.append("the project calculates multiple critical paths, a rule the oracle has not validated")
    if counts["resource"]:
        refusals.append(_n(counts["resource"], "task is", "tasks are") + " scheduled by resource assignments on other working time than the task's, or with delayed or contoured assignments")
    return tasks, links, refusals, sorted(uncovered), stored, counts, tuple(summary_links)


def _n(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def _iso(v):
    return v.isoformat(sep=" ", timespec="minutes") if isinstance(v, datetime) else v


def run(ctx: dict, longest_path_ids, hrs_per_day: dict, delay_days: int = recalc.CPT_DELAY_DAYS):
    """The recalculation report and, when it reproduces Project and rests on validated
    rules only, the Critical Path Test. Returns (recalculation, critical_path_test | None)."""
    tasks, links, refusals, uncovered, stored, counts, summary_links = build(ctx)
    options = {
        "schedule_from": "finish" if ctx["schedule_from_start"] is False else "start",
        "lag_calendar": LAG_CALENDAR,
        "critical_slack_limit_days": ctx["critical_slack_limit_days"],
        "multiple_critical_paths": bool(ctx["multiple_critical_paths"]),
        "delay_days": delay_days,
    }
    report = {
        **recalc.unsupported("", delay_days),
        "options": options,
        "excluded": {"complete": 0, "wbs_summary": sum(1 for u, s in ctx["is_summary"].items() if s and u not in ctx["inactive"])},
        "uncovered": [UNCOVERED_LABELS[u] for u in uncovered],
    }
    if refusals:
        report["reason"] = refusals[0]
        return report, None
    opts = cpm_msp.Options(project_start=ctx["project_start"], summary_links=summary_links)
    work_cals, default_cal = ctx["work_cals"], ctx["default_cal_obj"]
    try:
        computed = cpm_msp.schedule(tasks, links, work_cals, default_cal, opts)
    except cpm_core.LogicLoop as e:
        report["reason"] = str(e)
        return report, None
    diffs = cpm_core.differences(computed, stored)
    report["supported"] = True
    report["reason"] = None
    report["compared"] = len(stored)
    report["differing"] = len({d["task_id"] for d in diffs})
    for d in diffs:
        report["by_field"][d["field"]] += 1
    report["differences"] = [{**d, "computed": _iso(d["computed"]), "stored": _iso(d["stored"])}
                             for d in diffs[:recalc.MAX_DIFFERENCES_LISTED]]
    report["truncated"] = len(diffs) > recalc.MAX_DIFFERENCES_LISTED
    if diffs or uncovered:
        return report, None
    cpt = cpm_msp.critical_path_test(tasks, links, work_cals, default_cal, opts, longest_path_ids,
                                     delay_days=delay_days, hrs_per_day=hrs_per_day)
    if cpt:
        cpt = {k: _iso(v) for k, v in cpt.items()}
    return report, cpt
