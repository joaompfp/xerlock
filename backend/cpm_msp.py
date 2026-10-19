"""
CPM scheduling engine reproducing Microsoft Project's forward and backward passes.

Pure functions over plain data: no XML, no web framework. Input is the file's own
logic (summary-task logic already expanded to its leaves), durations, calendars,
constraints and actuals; output is early/late dates, total and free slack and which
predecessor links drive. Every rule names its source: "MS" is MPXJ 16.10.0's
org.mpxj.cpm.MicrosoftScheduler (LGPL; rules taken, no code), "SC" its
MicrosoftSlackCalculator, both read at tag v16.10.0, and Microsoft's own field pages;
SPEC-MSPROJECT.md §7.4 lists them and docs/METHODOLOGY.md is the prose version.

What Project does not have, this engine does not have either: no data date (a started
task is anchored at its actual start, the status date plays no part), no progress
modes, no float types, no open-ends or must-finish options.

Units: hours as floats, instants as datetimes. A duration, lag or slack is measured in
working time on a named calendar, or on the clock when the file says "elapsed".
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from backend import cpm_core
from backend.cpm_core import Dates, Link  # noqa: F401  (Link re-exported: the engine's link type)
from backend.cpm_core import round_hours as _clean
from backend.worktime import ALL_HOURS, WorkCalendar

# Project's ConstraintType codes (MSPDI Task/ConstraintType; MPXJ ConstraintType).
ASAP, ALAP, MSO, MFO, SNET, SNLT, FNET, FNLT = range(8)


@dataclass(frozen=True)
class Task:
    id: int
    clndr_id: str = ""
    # Task/Duration, RemainingDuration, ActualDuration in hours (on the clock when
    # `elapsed`: DurationFormat in elapsed units).
    duration_hrs: float = 0.0
    remaining_hrs: float = 0.0
    actual_hrs: float = 0.0
    elapsed: bool = False
    # Task/Milestone: the flag, not "zero duration" (a flagged task may have one).
    milestone: bool = False
    act_start: Optional[datetime] = None
    act_end: Optional[datetime] = None
    constraint: int = ASAP
    cstr_date: Optional[datetime] = None
    deadline: Optional[datetime] = None

    @property
    def started(self):
        return self.act_start is not None

    @property
    def finished(self):
        return self.act_end is not None


@dataclass(frozen=True)
class Options:
    # Project/StartDate: where tasks without predecessors start (MS L251).
    project_start: datetime


class _Engine:
    """One schedule run. Built once per call to schedule(); holds the indexes."""

    def __init__(self, tasks, links, calendars, default_cal, opts):
        self.opts = opts
        self.tasks = {t.id: t for t in tasks}
        self.cals = calendars
        self.default_cal = default_cal
        self.preds = {t.id: [] for t in tasks}
        self.succs = {t.id: [] for t in tasks}
        for l in links:
            if l.succ in self.tasks and l.pred in self.tasks:
                self.preds[l.succ].append(l)
                self.succs[l.pred].append(l)
        self.dates = {t.id: Dates() for t in tasks}
        # A started task shows its actual start as late start; what its FS
        # predecessors read is the late start the pass calculated (MS L487-491, L847).
        self.calc_ls = {}
        # Where logic puts a Must Start/Finish On task when that is later than its
        # constraint date: its slack is measured from there.
        self.logic_es = {}
        self.project_finish = None
        self.backward_done = False

    # ── Calendars and arithmetic ──────────────────────────────────────────────

    def cal(self, t: Task) -> WorkCalendar:
        """The task's effective calendar: its own, else the project's (MS: Task.getEffectiveCalendar)."""
        return self.cals.get(t.clndr_id) or self.default_cal or ALL_HOURS

    def dur_cal(self, t: Task) -> WorkCalendar:
        """Where the task's duration is counted: the clock for an elapsed duration
        (ProjectCalendar.getDate L643-651), else its calendar."""
        return ALL_HOURS if t.elapsed else self.cal(t)

    def add_dur(self, t: Task, date: datetime, hrs: float) -> datetime:
        return self.dur_cal(t).add_working_hours(date, hrs)

    def lag_cal(self, l) -> WorkCalendar:
        """A lag counts on the successor's calendar (Microsoft, Task Information dialog
        box, Predecessors tab: "If a successor uses a task calendar, lag time duration
        is based on that calendar; otherwise ... the project calendar"; MS L969), or on
        the clock when the lag is elapsed."""
        return ALL_HOURS if getattr(l, "lag_elapsed", False) else self.cal(self.tasks[l.succ])

    def add_lag(self, l, date: datetime) -> datetime:
        return self.lag_cal(l).add_working_hours(date, l.lag_hrs) if l.lag_hrs else date

    def remove_lag(self, l, date: datetime) -> datetime:
        return self.lag_cal(l).add_working_hours(date, -l.lag_hrs) if l.lag_hrs else date

    def next_work_start(self, t: Task, date: datetime) -> datetime:
        """The next working start on the task's calendar, except that a milestone may
        sit at the end of a working period (MS L1403-1412): an FS milestone after a
        Friday 17:00 finish is Friday 17:00, not Monday 08:00."""
        cal = self.cal(t)
        nws = cal.next_work_start(date)
        if nws > date and t.milestone and cal.prev_work_finish(date) == date:
            return date
        return nws

    # ── Forward pass (MS L203-357) ────────────────────────────────────────────

    def pred_date(self, l, finish_side: bool) -> datetime:
        """The predecessor date a link measures from. After the backward pass, an ALAP
        predecessor feeds a non-ALAP successor from its late dates (MS L1431-1434)."""
        p, s = self.tasks[l.pred], self.tasks[l.succ]
        pd = self.dates[p.id]
        alap = self.backward_done and p.constraint == ALAP and s.constraint != ALAP
        if finish_side:
            return pd.lf if alap else pd.ef
        return pd.ls if alap else pd.es

    def implied_by(self, l):
        """(start, finish) the link allows its successor (MS L538-667): the finish is
        None unless the link fixes it. An SF link fixes the successor's finish at the
        predecessor's start plus lag, exactly where that lands: Project stores a
        Monday 08:00 finish for a task that ends where its predecessor starts, with
        the start a full duration earlier (mpp9relations.mpp and its twins)."""
        p, s = self.tasks[l.pred], self.tasks[l.succ]
        if l.type == "PR_FS":
            return self.add_lag(l, self.pred_date(l, True)), None
        if l.type == "PR_SS":
            base = p.act_start if p.finished else self.pred_date(l, False)
            return self.add_lag(l, base), None
        if l.type == "PR_SF":
            finish = self.add_lag(l, self.pred_date(l, False))
            return self.add_dur(s, finish, -s.duration_hrs), finish
        # FF: the successor's remaining duration off the predecessor's finish, never
        # before the project start (MS L635-667).
        base = p.act_end if p.finished else self.pred_date(l, True)
        es = self.add_lag(l, self.add_dur(s, base, -s.remaining_hrs))
        return max(es, self.opts.project_start), None

    def forward(self, t: Task):
        d = self.dates[t.id]
        c, cd = t.constraint, t.cstr_date
        dated = cd is not None
        ef = None
        drivers = set()
        if not t.started:
            preds = self.preds[t.id]
            if not preds:
                if c == SNET and dated:
                    es = cd
                elif c == FNET and dated:
                    ef = cd
                    es = self.add_dur(t, cd, -t.duration_hrs)
                else:
                    es = self.next_work_start(t, self.opts.project_start)
            else:
                cands = [(self.implied_by(l), l) for l in preds]
                es = max(v[0] for v, _ in cands)
                drivers = {l.pred for v, l in cands if v[0] == es}
                fixed = [v[1] for v, _ in cands if v[0] == es and v[1] is not None]
                if fixed:
                    ef = max(fixed)
            if ef is None:
                es = self.next_work_start(t, es)
            logic_es = es
            # Constraints are honoured over logic, in both directions (Microsoft: the
            # "honor their constraint dates" setting "overrides the task relationship
            # links"; MS L262-321). The constraint date is taken as it is.
            if dated:
                if c == SNET:
                    es = max(es, cd)
                elif c == FNLT:
                    es = min(es, self.add_dur(t, cd, -t.duration_hrs))
                elif c == FNET:
                    es = max(es, self.add_dur(t, cd, -t.duration_hrs))
                elif c == SNLT:
                    es = min(es, cd)
                elif c == MSO:
                    es = cd
                elif c == MFO:
                    ef = cd
                    es = self.add_dur(t, cd, -t.duration_hrs)
                if es != logic_es and c != MFO:
                    ef = None
            # A Must Start/Finish On task shows its constraint date, but its slack is
            # measured from where its logic puts it when that is later (slack9.mpp:
            # a Must Finish On milestone shows all four dates on its constraint date
            # and a total slack of -1 day, its predecessor finishing a day later).
            if c in (MSO, MFO) and dated:
                self.logic_es[t.id] = max(logic_es, es)
        else:
            # A started task is anchored at its actual start and keeps its full
            # duration; no status date moves it (MS L323-353; Microsoft: a started
            # task's start "can't change ... automatically").
            es = t.act_start
            if not t.finished and c == FNET and dated:
                ef = max(self.add_dur(t, es, t.duration_hrs), cd)
        if ef is None:
            ef = t.act_end if t.finished else self.add_dur(t, es, t.duration_hrs)
        d.es, d.ef = es, ef
        d.driving_preds = drivers

    # ── Backward pass (MS L380-493) ───────────────────────────────────────────

    def implied_lf(self, l) -> datetime:
        """The late finish a successor allows its predecessor (MS L675-904), capped
        at the project finish."""
        p, s = self.tasks[l.pred], self.tasks[l.succ]
        sd = self.dates[s.id]
        if l.type == "PR_FS":
            lf = self.remove_lag(l, self.calc_ls[s.id])
        elif l.type == "PR_FF":
            lf = self.remove_lag(l, sd.lf)
        elif l.type == "PR_SF":
            lf = self.remove_lag(l, self.add_dur(p, sd.lf, p.duration_hrs))
        elif p.started:
            # SS from a started predecessor: no constraint on its late finish.
            lf = self.project_finish
        elif not s.started:
            ls = self.remove_lag(l, self.cal(p).next_work_start(sd.ls))
            lf = self.add_dur(p, ls, p.duration_hrs)
        elif not self.succs[s.id]:
            lf = self.project_finish
        else:
            ls = self.add_dur(s, s.act_start, s.actual_hrs)
            lf = self.add_dur(p, ls, p.duration_hrs)
        return min(lf, self.project_finish)

    def backward(self, t: Task):
        d = self.dates[t.id]
        c, cd = t.constraint, t.cstr_date
        if t.finished:
            lf = t.act_end
        else:
            # Finished successors are left out (MS L388); with none left, the late
            # finish is the project finish (Microsoft, Late Finish field; MS L400-403).
            succs = [l for l in self.succs[t.id] if not self.tasks[l.succ].finished]
            if not succs:
                lf = self.project_finish
            elif t.milestone and t.duration_hrs == 0 and t.started:
                lf = t.act_start
            else:
                lf = min(self.implied_lf(l) for l in succs)
            if cd is not None:
                if c == MSO:
                    lf = self.add_dur(t, cd, t.duration_hrs)
                elif c == MFO:
                    lf = cd
                elif c == SNLT:
                    lf = min(lf, self.add_dur(t, cd, t.duration_hrs))
                elif c == FNLT:
                    lf = min(lf, cd)
            # A deadline bounds the late finish (MS L456-459; Microsoft, Start Slack
            # field: "the finish slack is the difference between the task's finish
            # date and deadline date").
            if t.deadline is not None and lf > t.deadline:
                lf = t.deadline
            # A late finish at a period's start is the previous period's end (MS L462),
            # unless the task has no duration or an elapsed one: Project leaves a
            # milestone's late finish where its successor's late start is, period
            # start or not (the confidential oracle file, sf259.mpp, and every
            # zero-duration task at a project start in the MPXJ corpus), and an
            # elapsed task's at the clock time (the corpus duration fixtures).
            if t.duration_hrs > 0 and not t.elapsed:
                lf = self.cal(t).prev_work_finish(lf)
        calc_ls = self.add_dur(t, lf, -t.remaining_hrs)
        self.calc_ls[t.id] = calc_ls
        d.lf = lf
        d.ls = t.act_start if t.started else calc_ls

    # ── Slack (SC) ────────────────────────────────────────────────────────────

    def var_cal(self, t: Task) -> WorkCalendar:
        """Slack is measured in the task's duration units on its calendar: on the
        clock for an elapsed duration (SC L64, L88 via getVariance)."""
        return self.dur_cal(t)

    def shown(self, t: Task, finish: bool) -> datetime:
        """The date a task shows: its late date when ALAP (MS L118-119), else early."""
        d = self.dates[t.id]
        if t.constraint == ALAP:
            return d.lf if finish else d.ls
        return d.ef if finish else d.es

    def total_slack(self, t: Task) -> float:
        """The smaller of start and finish slack (Microsoft, Total Slack field; SC
        L189-196); the finish slack once the task has started (SC L154-157); zero for
        an ALAP task (SC L51-54)."""
        if t.constraint == ALAP:
            return 0.0
        d, cal = self.dates[t.id], self.var_cal(t)
        es = self.logic_es.get(t.id, d.es)
        ef = self.add_dur(t, es, t.duration_hrs) if t.id in self.logic_es else d.ef
        finish = cal.working_hours_between(ef, d.lf)
        if t.started:
            return finish
        return min(cal.working_hours_between(es, d.ls), finish)

    def free_slack(self, t: Task, total: float) -> float:
        """Working time on this task's calendar before the nearest unfinished
        successor would move, lag taken off (SC L92-133, L224-312); the total slack
        when no successor is left (Microsoft, Free Slack field); never negative, and
        never more than the total slack (Project caps it: slack9.mpp in the MPXJ
        corpus, where MPXJ's uncapped value differs from Project's)."""
        if t.finished:
            return 0.0
        cal = self.var_cal(t)
        best = None
        for l in self.succs[t.id]:
            s = self.tasks[l.succ]
            if s.finished:
                continue
            own = self.shown(t, l.type in ("PR_FS", "PR_FF"))
            target = self.shown(s, l.type in ("PR_FF", "PR_SF"))
            gap = cal.working_hours_between(own, target) - l.lag_hrs
            best = gap if best is None else min(best, gap)
        if best is None:
            best = total
        return max(0.0, min(best, total))

    # ── Run ───────────────────────────────────────────────────────────────────

    def run(self):
        ids = list(self.tasks)
        order = cpm_core.topological_order(ids, [(l.pred, l.succ) for tid in ids for l in self.succs[tid]])
        for tid in order:
            self.forward(self.tasks[tid])
        if not order:
            return self.dates
        # The project finish is the latest early finish (MS L101) and is not revised
        # by the ALAP pass.
        self.project_finish = max(self.dates[tid].ef for tid in order)
        for tid in reversed(order):
            self.backward(self.tasks[tid])
        self.backward_done = True
        if any(t.constraint == ALAP for t in self.tasks.values()):
            # ALAP: a second forward pass in which ALAP predecessors feed their
            # successors from their late dates (MS L106-109).
            for tid in order:
                self.forward(self.tasks[tid])
        for tid in order:
            t, d = self.tasks[tid], self.dates[tid]
            tf = self.total_slack(t)
            d.tf = _clean(tf)
            d.ff = _clean(self.free_slack(t, tf))
        for tid in order:
            t, d = self.tasks[tid], self.dates[tid]
            if t.constraint == ALAP:
                d.es, d.ef = d.ls, d.lf
        return self.dates


def schedule(tasks, links, calendars: dict, default_cal, opts: Options) -> dict:
    """Recompute the schedule. Returns {task id: Dates} with es/ef the dates Project
    shows as Start/Finish. Raises cpm_core.LogicLoop when the logic cannot be ordered."""
    return _Engine(tasks, links, calendars, default_cal, opts).run()


def _with_remaining(t: Task, hrs: float) -> Task:
    """The task with more remaining work: its duration grows by the same amount, since
    an unstarted task's finish is its start plus the full duration."""
    delta = hrs - t.remaining_hrs
    return Task(**{**t.__dict__, "remaining_hrs": hrs, "duration_hrs": t.duration_hrs + delta})


# The Project engine as the Critical Path Test sees it.
MSP = cpm_core.Engine(
    schedule=schedule,
    is_complete=lambda t: t.finished,
    remaining_of=lambda t: max(0.0, t.remaining_hrs),
    with_remaining=_with_remaining,
)


def critical_path_test(tasks, links, calendars, default_cal, opts: Options,
                       longest_path, delay_days: float, hrs_per_day: dict) -> Optional[dict]:
    """The Critical Path Test (cpm_core.critical_path_test) run with Project's rules."""
    return cpm_core.critical_path_test(MSP, tasks, links, calendars, default_cal, opts,
                                       longest_path, delay_days, hrs_per_day)
