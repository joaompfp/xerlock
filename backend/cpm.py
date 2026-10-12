"""
CPM scheduling engine reproducing Primavera P6's forward and backward passes.

Everything here is a pure function over plain data: no FastAPI, no PyP6XER. Input is
the file's own logic, remaining durations, calendars, constraints, progress and
scheduling options; output is early/late dates, total and free float, and which
predecessor links drive. P6 is the reference for every rule, and each one says which
P6 setting or convention it follows. docs/METHODOLOGY.md ("Recalculation") is the
prose version of this module.

Units: hours as floats, instants as datetimes. Every duration, lag and float is
measured in working time on a named calendar, never in clock time.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from backend.worktime import ALL_HOURS, WorkCalendar

# Dates in a .xer are minute-resolution; anything within a minute is the same instant.
MINUTE_HRS = 1 / 60

COMPLETE = "TK_Complete"
ACTIVE = "TK_Active"
START_MILESTONES = ("TT_Mile", "TT_StartMile")
FINISH_MILESTONE = "TT_FinMile"
# Activities the engine does not place by logic: level of effort spans its links,
# a WBS summary spans its children (not modelled: it is excluded from comparison).
SPANNING = ("TT_LOE", "TT_WBS")

EARLY_START_CSTR = ("CS_MSOA", "CS_MSO", "CS_MANDSTART")
EARLY_FINISH_CSTR = ("CS_MEOA", "CS_MEO", "CS_MANDFIN")
LATE_START_CSTR = ("CS_MSOB", "CS_MSO", "CS_MANDSTART")
LATE_FINISH_CSTR = ("CS_MEOB", "CS_MEO", "CS_MANDFIN")


@dataclass(frozen=True)
class Task:
    id: int
    task_type: str = "TT_Task"
    status: str = "TK_NotStart"
    clndr_id: str = ""
    remaining_hrs: float = 0.0
    act_start: Optional[datetime] = None
    act_end: Optional[datetime] = None
    cstr_type: str = ""
    cstr_date: Optional[datetime] = None
    cstr_type2: str = ""
    cstr_date2: Optional[datetime] = None
    expect_end: Optional[datetime] = None
    # TASK.external_early_start_date / external_late_end_date: dates imposed by a
    # relationship to another project, which the engine cannot see.
    external_dates: bool = False

    @property
    def started(self):
        return self.status in (ACTIVE, COMPLETE)

    def constraints(self):
        for ctype, cdate in ((self.cstr_type, self.cstr_date), (self.cstr_type2, self.cstr_date2)):
            if ctype and cdate:
                yield ctype, cdate


@dataclass(frozen=True)
class Link:
    pred: int
    succ: int
    type: str = "PR_FS"
    lag_hrs: float = 0.0


@dataclass(frozen=True)
class Options:
    """The SCHEDOPTIONS and PROJECT settings the passes depend on."""
    data_date: datetime
    # P6's "when scheduling progressed activities use": retained | override | actual
    progress_mode: str = "retained"
    # sched_float_type: FT_FF finish float, FT_SF start float, anything else smallest.
    float_type: str = "FT_FF"
    lag_calendar: str = "rcal_Predecessor"
    open_ends_critical: bool = False
    use_expected_finish: bool = False
    # PROJECT.plan_end_date, the "must finish by" date, when set.
    must_finish: Optional[datetime] = None
    # sched_lag_early_start_flag = N: SS lag counted from the actual start.
    ss_lag_from_actual_start: bool = False
    multiple_float_paths: bool = False


@dataclass
class Dates:
    es: Optional[datetime] = None
    ef: Optional[datetime] = None
    ls: Optional[datetime] = None
    lf: Optional[datetime] = None
    tf: Optional[float] = None
    ff: Optional[float] = None
    driving_preds: set = field(default_factory=set)


class LogicLoop(ValueError):
    def __init__(self, task_ids):
        self.task_ids = sorted(task_ids)
        super().__init__(f"logic loop through {len(self.task_ids)} activities")


def lag_calendar(basis: str, pred_cal: WorkCalendar, succ_cal: WorkCalendar,
                 default_cal) -> WorkCalendar:
    """The calendar a relationship lag is measured on, per
    SCHEDOPTIONS.sched_calendar_on_relationship_lag. P6's default is the
    predecessor's calendar, which is also what an export without the table gets."""
    if basis == "rcal_Successor":
        return succ_cal
    if basis == "rcal_24Hour":
        return ALL_HOURS
    if basis == "rcal_ProjDefault":
        return default_cal or pred_cal
    return pred_cal


def refusal_reason(tasks, links, opts: Options) -> Optional[str]:
    """Why the engine will not model this file, or None. These are the cases the
    engine cannot reproduce; they are refused rather than approximated."""
    ids = {t.id for t in tasks}
    n = sum(1 for t in tasks if t.task_type == "TT_Rsrc")
    if n:
        return (f"{n} resource-dependent activities (TT_Rsrc): they schedule on resource "
                "calendars, which the engine does not model")
    n = sum(1 for t in tasks if t.external_dates)
    if n:
        return f"{n} activities carry external relationship dates from another project"
    n = sum(1 for l in links if l.pred not in ids or l.succ not in ids)
    if n:
        return f"{n} relationships point outside this project"
    if opts.multiple_float_paths:
        return "the schedule was run with multiple float path calculation"
    return None


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
        self.dd = opts.data_date

    def cal(self, t: Task) -> WorkCalendar:
        return self.cals.get(t.clndr_id) or self.default_cal or ALL_HOURS

    def lag_cal(self, link: Link) -> WorkCalendar:
        pred, succ = self.tasks[link.pred], self.tasks[link.succ]
        return lag_calendar(self.opts.lag_calendar, self.cal(pred), self.cal(succ), self.default_cal)

    @staticmethod
    def spanning(t: Task) -> bool:
        return t.task_type in SPANNING

    def logic_links(self, links):
        """Links that carry logic: neither end is a spanning (LOE/WBS) activity."""
        return [l for l in links if not self.spanning(self.tasks[l.pred]) and not self.spanning(self.tasks[l.succ])]

    # ── Ordering ──────────────────────────────────────────────────────────────

    def topological_order(self):
        """Kahn's algorithm over the logic links. Whatever cannot be ordered sits on a
        loop, which P6 refuses to schedule and so does the engine."""
        indeg = {tid: 0 for tid in self.tasks if not self.spanning(self.tasks[tid])}
        for tid in indeg:
            indeg[tid] = len(self.logic_links(self.preds[tid]))
        ready = sorted(tid for tid, n in indeg.items() if n == 0)
        order = []
        while ready:
            tid = ready.pop(0)
            order.append(tid)
            for l in self.logic_links(self.succs[tid]):
                indeg[l.succ] -= 1
                if indeg[l.succ] == 0:
                    ready.append(l.succ)
        if len(order) != len(indeg):
            raise LogicLoop(tid for tid, n in indeg.items() if n > 0)
        return order

    # ── Forward pass ──────────────────────────────────────────────────────────

    @staticmethod
    def remaining_of(t: Task) -> float:
        """Remaining working hours to schedule; a milestone has none."""
        return 0.0 if t.task_type in START_MILESTONES + (FINISH_MILESTONE,) else max(0.0, t.remaining_hrs)

    def remaining(self, t: Task) -> float:
        return self.remaining_of(t)

    def pred_start(self, p: Task) -> datetime:
        """The predecessor date an SS/SF link measures from: its early start, which for
        started work P6 holds at the data date, unless the option says to count the
        lag from the actual start."""
        if p.started and self.opts.ss_lag_from_actual_start and p.act_start:
            return p.act_start
        return self.dates[p.id].es

    def pred_finish(self, p: Task) -> datetime:
        return self.dates[p.id].ef

    def implied_by(self, l: Link, p: Task) -> Optional[datetime]:
        """The instant link `l` from predecessor `p` allows its successor. A completed
        predecessor's lag counts from its actual finish (or start); and when Retained
        Logic holds the completed activity behind an unfinished predecessor, its held
        early date applies too, so out-of-sequence completion does not release the
        successors early."""
        finish_side = l.type in ("PR_FS", "PR_FF")
        base = self.pred_finish(p) if finish_side else self.pred_start(p)
        if base is None:
            return None
        if p.status == COMPLETE:
            actual = p.act_end if finish_side else p.act_start
            if actual:
                return max(self.lag_cal(l).add_working_hours(actual, l.lag_hrs), base)
        return self.lag_cal(l).add_working_hours(base, l.lag_hrs)

    def forward_candidates(self, t: Task):
        """(start candidates, finish candidates) from the predecessor links, each the
        instant the link allows, lag added on the lag calendar."""
        starts, finishes = [], []
        for l in self.preds[t.id]:
            p = self.tasks[l.pred]
            if self.spanning(p):
                continue
            implied = self.implied_by(l, p)
            if implied is None:
                continue
            # A finish milestone has only a finish: every link constrains that.
            if l.type in ("PR_FS", "PR_SS") and t.task_type != FINISH_MILESTONE:
                starts.append((implied, l))
            else:
                finishes.append((implied, l))
        return starts, finishes

    def forward(self, t: Task):
        d = self.dates[t.id]
        if t.status == COMPLETE:
            # Nothing is left to schedule, but P6 still gives completed work an early
            # date: the data date itself (not moved into working time), or under
            # Retained Logic the date an unfinished predecessor allows, which then
            # holds the successors of out-of-sequence work.
            starts, finishes = ([], []) if self.opts.progress_mode == "override" else self.forward_candidates(t)
            d.es = d.ef = max([self.dd] + [v for v, _ in starts + finishes])
            return
        cal = self.cal(t)
        dur = self.remaining(t)
        # Remaining work starts no earlier than the data date. Under "Actual Dates" an
        # actual start after the data date is honoured instead.
        floor = self.dd
        if t.status == ACTIVE and self.opts.progress_mode == "actual" and t.act_start and t.act_start > self.dd:
            floor = t.act_start
        starts, finishes = ([], []) if (t.status == ACTIVE and self.opts.progress_mode == "override") \
            else self.forward_candidates(t)
        if not t.started:
            starts += [(cd, None) for ct, cd in t.constraints() if ct in EARLY_START_CSTR]
        finishes += [(cd, None) for ct, cd in t.constraints() if ct in EARLY_FINISH_CSTR]

        if t.task_type == FINISH_MILESTONE:
            cands = [(floor, None)] + starts + finishes
            best = max(cands, key=lambda c: c[0])
            d.ef = d.es = cal.next_work_finish(best[0])
            drivers = [l for v, l in cands if l and v == best[0]]
        else:
            best = max([(floor, None)] + starts, key=lambda c: c[0])
            d.es = cal.next_work_start(best[0])
            d.ef = cal.add_working_hours(d.es, dur)
            drivers = [l for v, l in starts if l and v == best[0]]
            if finishes:
                bestf = max(finishes, key=lambda c: c[0])
                f = cal.next_work_finish(bestf[0])
                if f > d.ef:
                    # P6 keeps the duration: a finish pushed by an FF/SF link or a finish
                    # constraint pulls the start with it.
                    d.ef, d.es = f, cal.add_working_hours(f, -dur)
                    drivers = [l for v, l in finishes if l and v == bestf[0]]
        if self.opts.use_expected_finish and t.expect_end and t.expect_end > d.es:
            d.ef = cal.next_work_finish(t.expect_end)
        for ct, cd in t.constraints():
            # Mandatory dates override logic in both directions.
            if ct == "CS_MANDSTART" and not t.started:
                d.es, d.ef = cd, cal.add_working_hours(cd, dur)
            elif ct == "CS_MANDFIN":
                d.ef, d.es = cd, cal.add_working_hours(cd, -dur)
        d.driving_preds = {l.pred for l in drivers}

    # ── Backward pass ─────────────────────────────────────────────────────────

    def backward_candidates(self, t: Task):
        """(finish candidates, start candidates) from the successor links: the latest
        instant each one allows, lag taken off on the lag calendar. Completed
        successors count: P6 carries late dates through them."""
        finishes, starts = [], []
        for l in self.succs[t.id]:
            s = self.tasks[l.succ]
            if self.spanning(s) or self.dates[s.id].lf is None:
                continue
            sd = self.dates[s.id]
            start_side = l.type in ("PR_FS", "PR_SS")
            implied = sd.ls if start_side else sd.lf
            # A lag into completed work was spent with the work; P6 no longer takes it off.
            if l.lag_hrs and s.status != COMPLETE:
                # Lag arithmetic lands where the calendar puts it; P6 then reads the
                # result as a date of the successor's kind on the successor's own
                # calendar, so a start that lands on a period's end is the next
                # period's start. A lag-free link passes the date through as it is.
                implied = self.lag_cal(l).add_working_hours(implied, -l.lag_hrs)
                implied = self.cal(s).next_work_start(implied) if start_side else self.cal(s).prev_work_finish(implied)
            # A milestone has one date, which every link constrains: the start of a
            # start milestone, the finish of a finish milestone. A task with no
            # remaining duration has one date too, and P6 reads it as a finish here.
            if t.task_type in START_MILESTONES:
                starts.append(implied)
            elif self.remaining(t) == 0 or l.type in ("PR_FS", "PR_FF"):
                finishes.append(implied)
            else:
                starts.append(implied)
        return finishes, starts

    def backward(self, t: Task, project_finish: datetime):
        d = self.dates[t.id]
        cal = self.cal(t)
        dur = self.remaining(t)
        finishes, starts = self.backward_candidates(t)
        if not finishes and not (starts and t.task_type in START_MILESTONES):
            # An open finish (no successor, or only SS/SF ones) floats to the project
            # finish, or to the activity's own finish when open ends are made critical.
            # For a start milestone that date is, like everything else, its start.
            end = d.ef if self.opts.open_ends_critical else project_finish
            (starts if t.task_type in START_MILESTONES else finishes).append(end)
        if t.status == COMPLETE:
            # Completed work carries late dates for its predecessors' sake: the
            # earliest its successors allow, taken as it is.
            d.ls = d.lf = min(finishes + starts)
            return
        finishes += [cal.prev_work_finish(cd) for ct, cd in t.constraints() if ct in LATE_FINISH_CSTR]
        # A constraint date is read as a start, as the forward pass reads it.
        starts += [cal.next_work_start(cd) for ct, cd in t.constraints() if ct in LATE_START_CSTR]
        if finishes:
            d.lf = cal.prev_work_finish(min(finishes))
            d.ls = cal.add_working_hours(d.lf, -dur)
        if starts:
            # A late start may sit anywhere within a period, its end included (P6
            # keeps a 16:00 start imposed by a successor on another calendar).
            s = cal.prev_work_start(min(starts))
            if d.ls is None or s < d.ls:
                d.ls, d.lf = s, cal.add_working_hours(s, dur)
        for ct, cd in t.constraints():
            if ct == "CS_MANDSTART" and not t.started:
                d.ls, d.lf = d.es, d.ef
            elif ct == "CS_MANDFIN":
                d.ls, d.lf = d.es, d.ef

    # ── Float ─────────────────────────────────────────────────────────────────

    def free_float(self, t: Task, project_finish: datetime) -> float:
        """Working time, on the activity's own calendar, before the nearest successor
        would move. Without successors, the time to the project finish."""
        d, cal = self.dates[t.id], self.cal(t)
        best = None
        for l in self.succs[t.id]:
            s = self.tasks[l.succ]
            if self.spanning(s) or self.dates[s.id].es is None:
                continue
            sd = self.dates[s.id]
            own = d.ef if l.type in ("PR_FS", "PR_FF") else d.es
            implied = self.lag_cal(l).add_working_hours(own, l.lag_hrs)
            target = sd.es if l.type in ("PR_FS", "PR_SS") else sd.ef
            # Never negative: a started successor scheduled regardless of this link
            # (Progress Override) has no float to give or take through it.
            gap = max(0.0, cal.working_hours_between(implied, target))
            best = gap if best is None else min(best, gap)
        if best is None:
            best = cal.working_hours_between(d.ef, project_finish)
        return best

    def total_float(self, t: Task) -> float:
        d, cal = self.dates[t.id], self.cal(t)
        finish = cal.working_hours_between(d.ef, d.lf)
        start = cal.working_hours_between(d.es, d.ls)
        if self.opts.float_type == "FT_FF":
            return finish
        if self.opts.float_type == "FT_SF":
            return start
        return min(start, finish)

    def alap(self, t: Task, project_finish: datetime):
        """As Late As Possible: P6 delays the early dates by the free float, so the
        activity ends exactly where its nearest successor needs it."""
        d, cal = self.dates[t.id], self.cal(t)
        ff = self.free_float(t, project_finish)
        if ff > MINUTE_HRS:
            d.ef = cal.add_working_hours(d.ef, ff)
            d.es = cal.add_working_hours(d.ef, -self.remaining(t))

    # ── Spanning activities ───────────────────────────────────────────────────

    def span(self, t: Task):
        """Level of effort: starts with the earliest link from its predecessors and
        finishes with the latest link to its predecessors' finishes or successors'
        dates. It never drives anything."""
        if t.status == COMPLETE or t.task_type != "TT_LOE":
            return
        d, cal = self.dates[t.id], self.cal(t)
        starts, finishes = self.forward_candidates(t)
        for l in self.succs[t.id]:
            s = self.tasks[l.succ]
            if self.spanning(s) or s.status == COMPLETE:
                continue
            sd = self.dates[s.id]
            base = sd.es if l.type in ("PR_FS", "PR_SS") else sd.ef
            finishes.append((self.lag_cal(l).add_working_hours(base, -l.lag_hrs), l))
        d.es = cal.next_work_start(max([self.dd] + [v for v, _ in starts]))
        d.ef = max([d.es] + [cal.next_work_finish(v) for v, _ in finishes])
        d.ls, d.lf, d.tf, d.ff = d.es, d.ef, 0.0, 0.0

    # ── Run ───────────────────────────────────────────────────────────────────

    def run(self):
        order = self.topological_order()
        for tid in order:
            self.forward(self.tasks[tid])
        ends = [self.dates[tid].ef for tid in order if self.dates[tid].ef is not None]
        if not ends:
            return self.dates
        project_finish = max(ends)
        late_base = self.opts.must_finish or project_finish
        for tid in reversed(order):
            self.backward(self.tasks[tid], late_base)
        # ALAP in reverse order, so a chain of ALAP activities slides from the end.
        for tid in reversed(order):
            t = self.tasks[tid]
            if t.status != COMPLETE and "CS_ALAP" in (t.cstr_type, t.cstr_type2):
                self.alap(t, project_finish)
        for tid in order:
            t, d = self.tasks[tid], self.dates[tid]
            if t.status == COMPLETE:
                continue
            d.tf = _clean(self.total_float(t))
            d.ff = _clean(self.free_float(t, project_finish))
        for t in self.tasks.values():
            if self.spanning(t):
                self.span(t)
        return self.dates


def _clean(hrs: float) -> float:
    """Float to the 0.01 h the comparison uses, with -0.0 folded into 0.0."""
    return round(hrs, 2) + 0.0


def schedule(tasks, links, calendars: dict, default_cal, opts: Options) -> dict:
    """Recompute the schedule. Returns {task id: Dates}. Raises LogicLoop when the
    logic cannot be ordered. Completed activities keep None dates: P6 computes no
    early/late dates or float for them."""
    return _Engine(tasks, links, calendars, default_cal, opts).run()


# ── Comparison with P6's stored values ────────────────────────────────────────

DATE_FIELDS = ("es", "ef", "ls", "lf")
FLOAT_FIELDS = ("tf", "ff")
FLOAT_TOLERANCE_HRS = 0.01


def differences(computed: dict, stored: dict) -> list:
    """Per-activity, per-field differences between the engine's dates and the values
    P6 stored. `stored` maps task id -> Dates read from the file; activities absent
    from it (completed work) are not compared. Tolerance: one minute on dates,
    0.01 h on float, the same as the driving rule."""
    out = []
    for tid, s in stored.items():
        c = computed.get(tid)
        if c is None:
            continue
        for f in DATE_FIELDS:
            a, b = getattr(c, f), getattr(s, f)
            if a is None or b is None:
                if a is not b:
                    out.append({"task_id": tid, "field": f, "computed": a, "stored": b, "delta_hrs": None})
                continue
            if abs((a - b).total_seconds()) > 60:
                out.append({"task_id": tid, "field": f, "computed": a, "stored": b,
                            "delta_hrs": round((a - b).total_seconds() / 3600, 2)})
        for f in FLOAT_FIELDS:
            a, b = getattr(c, f), getattr(s, f)
            if a is None or b is None:
                if a is not b:
                    out.append({"task_id": tid, "field": f, "computed": a, "stored": b, "delta_hrs": None})
                continue
            if abs(a - b) > FLOAT_TOLERANCE_HRS:
                out.append({"task_id": tid, "field": f, "computed": a, "stored": b, "delta_hrs": round(a - b, 2)})
    return out


# ── DCMA 12 Critical Path Test ────────────────────────────────────────────────

def critical_path_test(tasks, links, calendars, default_cal, opts: Options,
                       longest_path, delay_days: float, hrs_per_day: dict) -> Optional[dict]:
    """Add `delay_days` of working time to the remaining duration of the first
    incomplete activity on the Longest Path that has a duration to extend (a
    milestone has none), reschedule, and check that the project finish moved by the
    same amount, measured in working time on the delayed activity's calendar. On
    failure, name the first activity along the path whose own finish moved less than
    the delay: that is where the delay was absorbed (a constraint, or a parallel
    path taking over).

    "The same amount" is exact when every activity from the delayed one to the
    finish shares its calendar. Across unlike calendars the chain moves by the same
    span of clock time, and re-reading that span on another calendar, with its own
    holidays and work periods, shifts the figure by up to a few days either way
    without anything having absorbed the delay; the test then allows one working
    week and says so (`tolerance_hrs`, `calendars_uniform`)."""
    before = schedule(tasks, links, calendars, default_cal, opts)
    by_id = {t.id: t for t in tasks}

    def cal_of(t):
        return calendars.get(t.clndr_id) or default_cal or ALL_HOURS

    on_path = [by_id[i] for i in longest_path if i in by_id and by_id[i].status != COMPLETE
               and before[i].es is not None]
    on_path.sort(key=lambda t: (before[t.id].es, before[t.id].ef, t.id))
    delayed = next((t for t in on_path if _Engine.remaining_of(t) > 0), None)
    has_succ = {l.pred for l in links}
    finish = max((t for t in tasks if t.id not in has_succ and before[t.id].ef is not None),
                 key=lambda t: (before[t.id].ef, -t.id), default=None)
    if delayed is None or finish is None:
        return None
    per_day = hrs_per_day.get(delayed.clndr_id) or 8.0
    delay_hrs = delay_days * per_day
    cal = cal_of(delayed)
    trace = on_path[on_path.index(delayed):]
    uniform = all(t.clndr_id == delayed.clndr_id for t in trace) and finish.clndr_id == delayed.clndr_id
    tolerance = MINUTE_HRS if uniform else 5 * per_day

    delayed_tasks = [Task(**{**t.__dict__, "remaining_hrs": t.remaining_hrs + delay_hrs}) if t.id == delayed.id else t
                     for t in tasks]
    after = schedule(delayed_tasks, links, calendars, default_cal, opts)
    old_finish, new_finish = before[finish.id].ef, after[finish.id].ef
    delta = cal.working_hours_between(old_finish, new_finish)
    passed = delta >= delay_hrs - tolerance
    absorbed = None
    if not passed:
        for t in trace:
            if cal.working_hours_between(before[t.id].ef, after[t.id].ef) < delay_hrs - tolerance:
                absorbed = t.id
                break
        if absorbed is None:
            absorbed = finish.id
    return {
        "passed": passed,
        "exact": abs(delta - delay_hrs) <= MINUTE_HRS,
        "delay_days": delay_days,
        "delay_hrs": delay_hrs,
        "tolerance_hrs": _clean(tolerance),
        "calendars_uniform": uniform,
        "delayed_task_id": delayed.id,
        "finish_task_id": finish.id,
        "finish_before": old_finish,
        "finish_after": new_finish,
        "expected_delta_hrs": _clean(delay_hrs),
        "finish_delta_hrs": _clean(delta),
        "absorbed_by_task_id": absorbed,
    }
