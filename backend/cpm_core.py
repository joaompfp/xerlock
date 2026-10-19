"""
What every CPM engine shares, whichever tool's rules it reproduces: the result and link
types, the loop error, the topological order, the comparison with a file's stored
values and the DCMA 12 Critical Path Test. backend/cpm.py (P6's rules) and
backend/cpm_msp.py (Microsoft Project's) both build on this; neither knows the other.

Units: hours as floats, instants as datetimes, every duration measured in working time
on a named calendar.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional

from backend.worktime import ALL_HOURS

# Dates in a schedule file are minute-resolution; anything within a minute is the same instant.
MINUTE_HRS = 1 / 60


@dataclass(frozen=True)
class Link:
    pred: int
    succ: int
    type: str = "PR_FS"
    lag_hrs: float = 0.0
    # A Project lag in elapsed units counts on the clock, not on a calendar.
    lag_elapsed: bool = False


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


def round_hours(hrs: float) -> float:
    """Hours to the 0.01 h the comparison uses, with -0.0 folded into 0.0."""
    return round(hrs, 2) + 0.0


def topological_order(ids, edges) -> list:
    """Kahn's algorithm over (pred, succ) pairs between the given ids. Whatever cannot
    be ordered sits on a loop, which no scheduler will schedule: LogicLoop names it."""
    indeg = {tid: 0 for tid in ids}
    succs = {tid: [] for tid in ids}
    for pred, succ in edges:
        indeg[succ] += 1
        succs[pred].append(succ)
    ready = sorted(tid for tid, n in indeg.items() if n == 0)
    order = []
    while ready:
        tid = ready.pop(0)
        order.append(tid)
        for s in succs[tid]:
            indeg[s] -= 1
            if indeg[s] == 0:
                ready.append(s)
    if len(order) != len(indeg):
        raise LogicLoop(tid for tid, n in indeg.items() if n > 0)
    return order


# ── Comparison with the file's stored values ──────────────────────────────────

DATE_FIELDS = ("es", "ef", "ls", "lf")
FLOAT_FIELDS = ("tf", "ff")
FLOAT_TOLERANCE_HRS = 0.01


def differences(computed: dict, stored: dict) -> list:
    """Per-activity, per-field differences between the engine's dates and the values
    the file stored. `stored` maps task id -> Dates read from the file; activities
    absent from it are not compared. Tolerance: one minute on dates, 0.01 h on float,
    the same as the driving rule."""
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

@dataclass(frozen=True)
class Engine:
    """What the Critical Path Test needs from a scheduler: how to run it, which tasks
    are complete, how much remaining work a task has, and how to give it more."""
    schedule: Callable
    is_complete: Callable
    remaining_of: Callable
    with_remaining: Callable


def critical_path_test(engine: Engine, tasks, links, calendars, default_cal, opts,
                       longest_path, delay_days: float, hrs_per_day: dict) -> Optional[dict]:
    """Add `delay_days` of working time to the remaining duration of the first
    incomplete activity on the Longest Path that has a duration to extend (a
    milestone has none) and whose finish drives the path onward, reschedule, and
    check that the project finish moved by the same amount, measured in working time
    on the delayed activity's calendar. On
    failure, name the first activity along the path whose own finish moved less than
    the delay: that is where the delay was absorbed (a constraint, or a parallel
    path taking over).

    "The same amount" is exact when every activity from the delayed one to the
    finish shares its calendar. Across unlike calendars the chain moves by the same
    span of clock time, and re-reading that span on another calendar, with its own
    holidays and work periods, shifts the figure by up to a few days either way
    without anything having absorbed the delay; the test then allows one working
    week and says so (`tolerance_hrs`, `calendars_uniform`)."""
    before = engine.schedule(tasks, links, calendars, default_cal, opts)
    by_id = {t.id: t for t in tasks}

    def cal_of(t):
        return calendars.get(t.clndr_id) or default_cal or ALL_HOURS

    on_path = [by_id[i] for i in longest_path if i in by_id and not engine.is_complete(by_id[i])
               and before[i].es is not None]
    on_path.sort(key=lambda t: (before[t.id].es, before[t.id].ef, t.id))
    has_succ = {l.pred for l in links}
    finish = max((t for t in tasks if t.id not in has_succ and before[t.id].ef is not None),
                 key=lambda t: (before[t.id].ef, -t.id), default=None)
    if finish is None:
        return None
    path_ids = {t.id for t in on_path}

    def finish_drives(t):
        """Its finish carries the path: a driving FS/FF link to a later Longest Path
        activity, or it is the finish itself. Where the path leaves an activity by its
        start (SS/SF), lengthening it is expected to move nothing, so it is no test."""
        return t.id == finish.id or any(
            l.type in ("PR_FS", "PR_FF") and l.succ in path_ids and t.id in before[l.succ].driving_preds
            for l in links if l.pred == t.id)

    delayed = next((t for t in on_path if engine.remaining_of(t) > 0 and finish_drives(t)), None)
    if delayed is None:
        return None
    per_day = hrs_per_day.get(delayed.clndr_id) or 8.0
    delay_hrs = delay_days * per_day
    cal = cal_of(delayed)
    trace = on_path[on_path.index(delayed):]
    uniform = all(t.clndr_id == delayed.clndr_id for t in trace) and finish.clndr_id == delayed.clndr_id
    tolerance = MINUTE_HRS if uniform else 5 * per_day

    delayed_tasks = [engine.with_remaining(t, engine.remaining_of(t) + delay_hrs) if t.id == delayed.id else t
                     for t in tasks]
    after = engine.schedule(delayed_tasks, links, calendars, default_cal, opts)
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
        "tolerance_hrs": round_hours(tolerance),
        "calendars_uniform": uniform,
        "delayed_task_id": delayed.id,
        "finish_task_id": finish.id,
        "finish_before": old_finish,
        "finish_after": new_finish,
        "expected_delta_hrs": round_hours(delay_hrs),
        "finish_delta_hrs": round_hours(delta),
        "absorbed_by_task_id": absorbed,
    }
