#!/usr/bin/env python3
"""
What a Microsoft Project oracle could prove: for every .mpp and MSPDI .xml under the
given paths, count the scheduling features each file uses, how much logic it carries,
and how many files, tasks and links a Project scheduling engine could be checked on
once the files it must refuse are set aside. Aggregates only.

    scripts/fetch_msp_corpus.sh                       # MPXJ test data -> .corpus/mpxj
    .venv/bin/python scripts/msp_oracle_coverage.py .corpus/mpxj
    .venv/bin/python scripts/msp_oracle_coverage.py .corpus/mpxj --confidential /path/to/file.mpp
    .venv/bin/python scripts/msp_oracle_coverage.py .corpus/mpxj --mpxj-scheduler

Not part of CI: it needs Java (MPXJ reads both formats here, so the counts come from
the same reader for .mpp and .xml) and takes about a minute. With --mpxj-scheduler it
also runs MPXJ's own MicrosoftScheduler on every file and reports how many files it
reproduces (MPXJ's MicrosoftSchedulerComparator: early/late dates, Start/Finish and
both slacks per task), which says how good MPXJ's rules are as a second reference.

Public corpus files are named in the per-file lists; a file given with --confidential
is reported as aggregates only, under the label "confidential": never a task name,
code, date or project name (the P6 oracle harness follows the same rule).
"""

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# The refusals phase 3 proposes (SPEC-MSPROJECT.md §7). A file is "in scope" when it
# triggers none of them and has at least one relationship between scheduled tasks.
REFUSALS = (
    "schedule from finish",
    "manual tasks (incomplete)",
    "levelling delay",
    "split tasks",
    "recurring tasks",
    "subprojects / external tasks",
    "cross-project links",
    "summary task constraints",
    "summary task logic",
    "multiple critical paths option",
    "resource-driven tasks (any work assignment)",
)
# Features with a documented rule (MPXJ's MicrosoftScheduler, Microsoft's pages) but
# no example in the corpus: not refused, since the per-file comparison validates them
# on the file itself, but reported so the spec can say what the oracle never saw.
UNCOVERED = (
    "deadlines",
    "constraint AS_LATE_AS_POSSIBLE",
    "constraint START_NO_LATER_THAN",
    "constraint FINISH_NO_LATER_THAN",
    "constraint FINISH_NO_EARLIER_THAN",
    "constraint MUST_START_ON",
    "elapsed durations",
    "elapsed or percentage lags",
    "links across two calendars",
    "lagged links across two calendars",
)
# The narrower resource rule the spec argues for: refuse only where an assignment
# would schedule the task on other working time or has moved it off its own dates.
NARROW_RESOURCE_REFUSAL = "resource-driven tasks (assignment calendar or dates differ)"

WEEKDAYS = ("MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY")


def jvm():
    import jpype
    import mpxj  # noqa: F401  (adds the MPXJ jars to the class path)
    if not jpype.isJVMStarted():
        jpype.startJVM(convertStrings=True)


def enum_name(v):
    return None if v is None else str(v.name())


def dur_hours(d):
    """An MPXJ Duration as hours (elapsed units are clock hours); only "is it zero"
    matters below."""
    if d is None:
        return 0.0
    units = enum_name(d.getUnits())
    n = float(d.getDuration())
    per = {"MINUTES": 1 / 60, "ELAPSED_MINUTES": 1 / 60, "HOURS": 1, "ELAPSED_HOURS": 1,
           "DAYS": 8, "ELAPSED_DAYS": 24, "WEEKS": 40, "ELAPSED_WEEKS": 168,
           "MONTHS": 160, "ELAPSED_MONTHS": 720, "YEARS": 2000, "ELAPSED_YEARS": 8760}
    return n * per.get(units, 1)


def is_elapsed(d):
    return d is not None and bool(d.getUnits().isElapsed())


def work_assignments(task):
    """Assignments that MPXJ's scheduler lets drive a task: a time-based (work)
    resource with units above zero (MicrosoftScheduler.getResourceAssignmentStream)."""
    out = []
    for a in task.getResourceAssignments():
        r = a.getResource()
        if r is None or not r.getType().isTimeBased():
            continue
        u = a.getUnits()
        if u is None or float(u.doubleValue()) <= 0:
            continue
        out.append(a)
    return out


def same_working_time(cal, base) -> bool:
    """Does `cal` define the same working time as `base`? True when it is `base`, or
    a calendar derived from it (at any depth) that overrides nothing: no exceptions,
    no work weeks and every weekday left at the parent's default. A resource calendar
    is normally such an untouched copy of the project calendar."""
    from java.time import DayOfWeek
    seen = 0
    while cal is not None and seen < 20:
        if cal.getUniqueID() == base.getUniqueID():
            return True
        if not cal.isDerived():
            return False
        if cal.getCalendarExceptions().size() or cal.getWorkWeeks().size():
            return False
        if any(enum_name(cal.getCalendarDayType(DayOfWeek.valueOf(d))) != "DEFAULT" for d in WEEKDAYS):
            return False
        cal = cal.getParent()
        seen += 1
    return False


def analyse(path: str) -> dict:
    """Feature counts for one file, or {'skipped': reason}."""
    from java.io import File
    from org.mpxj.reader import UniversalProjectReader

    project = UniversalProjectReader().read(File(path))
    if project is None:
        return {"skipped": "not a project file MPXJ recognises"}
    props = project.getProjectProperties()
    file_type = str(props.getFileType() or "")
    if file_type not in ("MPP", "MSPDI"):
        return {"skipped": f"{file_type or 'unknown'} file, not Microsoft Project"}

    c = Counter()
    c["file"] = 1
    c[f"file type {file_type}"] = 1

    def scheduled(t):
        """A task the forward/backward passes place: MPXJ MicrosoftScheduler.isTask."""
        return not ((t.getSummary() and not t.getExternalProject()) or not t.getActive() or t.getNull())

    tasks = list(project.getTasks())
    sched = [t for t in tasks if scheduled(t)]
    by_uid = {int(t.getUniqueID()) for t in sched}
    c["tasks (scheduled, non-summary, active)"] = len(sched)
    c["summary tasks"] = sum(1 for t in tasks if t.getSummary())
    c["inactive tasks"] = sum(1 for t in tasks if not t.getActive())
    c["null tasks"] = sum(1 for t in tasks if t.getNull())

    project_start = props.getStartDate()
    status_date = props.getStatusDate()
    c["files with StatusDate"] = 1 if status_date is not None else 0
    if props.getScheduleFrom() is not None and enum_name(props.getScheduleFrom()) == "FINISH":
        c["refusal: schedule from finish"] = 1
    if props.getMultipleCriticalPaths():
        c["refusal: multiple critical paths option"] = 1
    # Information only: Project writes HonorConstraints 0 in every XML it saves and
    # MPXJ reads 1 from every .mpp, so the element says nothing about the file.
    c[f"HonorConstraints={props.getHonorConstraints()}"] = 1
    c[f"SplitInProgressTasks={props.getSplitInProgressTasks()}"] = 1

    links = 0
    for t in sched:
        uid = int(t.getUniqueID())
        started = t.getActualStart() is not None
        finished = t.getActualFinish() is not None
        if finished:
            c["tasks complete"] += 1
        elif started:
            c["tasks in progress"] += 1
        if project_start is not None and t.getStart() is not None and not t.getStart().isEqual(project_start):
            c["tasks whose Start differs from project start"] += 1
        if t.getPredecessors().size() > 0:
            c["tasks with predecessors"] += 1
        if enum_name(t.getTaskMode()) == "MANUALLY_SCHEDULED":
            c["manual tasks"] += 1
            if not finished:
                c["refusal: manual tasks (incomplete)"] += 1
            if t.getPredecessors().size() or t.getSuccessors().size():
                c["manual tasks with links"] += 1
        if t.getMilestone():
            c["milestones"] += 1
        if is_elapsed(t.getDuration()):
            c["elapsed durations"] += 1
        if t.getDeadline() is not None:
            c["deadlines"] += 1
        ct = enum_name(t.getConstraintType()) or "AS_SOON_AS_POSSIBLE"
        if ct != "AS_SOON_AS_POSSIBLE":
            c[f"constraint {ct}"] += 1
        if t.getRecurring():
            c["refusal: recurring tasks"] += 1
        if t.getExternalTask() or t.getExternalProject() or t.getSubprojectFile() is not None:
            c["refusal: subprojects / external tasks"] += 1
        if dur_hours(t.getLevelingDelay()) > 0:
            c["refusal: levelling delay"] += 1
        # A split: more than one work range (MPXJ derives them from the timephased
        # data), or an in-progress task whose remaining part resumes some working
        # time after the completed part stopped (Stop on a Friday evening and Resume
        # on the Monday morning is no split: no working time lies between them).
        splits = t.getWorkSplits()
        stop, resume = t.getStop(), t.getResume()
        gap = 0.0
        if stop is not None and resume is not None and resume.isAfter(stop) and not finished:
            from org.mpxj import TimeUnit
            gap = float(t.getEffectiveCalendar().getWork(stop, resume, TimeUnit.MINUTES).getDuration())
        if (splits is not None and splits.size() > 1) or gap > 0:
            c["refusal: split tasks"] += 1
        if t.getEffortDriven():
            c["effort-driven tasks"] += 1
        c[f"task type {enum_name(t.getType())}"] += 1
        if t.getCalendar() is not None:
            c["tasks with a task calendar"] += 1
        wa = work_assignments(t)
        if wa:
            c["refusal: resource-driven tasks (any work assignment)"] += 1
            task_cal = t.getEffectiveCalendar()
            differs = False
            for a in wa:
                acal = a.getEffectiveCalendar()
                if acal is not None and task_cal is not None and not same_working_time(acal, task_cal):
                    differs = True
                    c["assignments on other working time than the task"] += 1
                if dur_hours(a.getLevelingDelay()) > 0:
                    differs = True
                    c["assignments with levelling delay"] += 1
                a_start, a_finish = a.getStart(), a.getFinish()
                if (a_start is not None and t.getStart() is not None and not a_start.isEqual(t.getStart())) or \
                        (a_finish is not None and t.getFinish() is not None and not a_finish.isEqual(t.getFinish())):
                    differs = True
                    c["assignments whose dates differ from the task's"] += 1
            if differs:
                c[f"refusal: {NARROW_RESOURCE_REFUSAL}"] += 1

        for r in t.getPredecessors():
            p = r.getPredecessorTask()
            if p is None:
                continue
            if p.getExternalTask() or p.getExternalProject():
                c["refusal: cross-project links"] += 1
                continue
            puid = int(p.getUniqueID())
            if p.getSummary() or t.getSummary():
                c["refusal: summary task logic"] += 1
                continue
            if puid not in by_uid or uid not in by_uid:
                c["links to inactive or null tasks (ignored)"] += 1
                continue
            links += 1
            c[f"link {enum_name(r.getType())}"] += 1
            lag = r.getLag()
            if lag is not None and float(lag.getDuration()) != 0:
                units = enum_name(lag.getUnits())
                c["links with lag"] += 1
                c[f"lag unit {units}"] += 1
                if float(lag.getDuration()) < 0:
                    c["links with lead (negative lag)"] += 1
                if lag.getUnits().isElapsed() or units in ("PERCENT", "ELAPSED_PERCENT"):
                    c["elapsed or percentage lags"] += 1
            pc, sc = p.getEffectiveCalendar(), t.getEffectiveCalendar()
            if pc is not None and sc is not None and not same_working_time(pc, sc) and not same_working_time(sc, pc):
                c["links across two calendars"] += 1
                if lag is not None and float(lag.getDuration()) != 0:
                    c["lagged links across two calendars"] += 1
            if p.getActualFinish() is None and started and not finished:
                c["in-progress tasks with an unfinished predecessor"] += 1
            # Evidence of a constraint overriding logic: an FS predecessor that
            # finishes after this task's stored start.
            if enum_name(r.getType()) == "FINISH_START" and ct not in ("AS_SOON_AS_POSSIBLE", "AS_LATE_AS_POSSIBLE") \
                    and p.getFinish() is not None and t.getStart() is not None and p.getFinish().isAfter(t.getStart()) \
                    and not started:
                c["constrained tasks starting before an FS predecessor finishes"] += 1

    for t in tasks:
        if t.getSummary() and (enum_name(t.getConstraintType()) or "AS_SOON_AS_POSSIBLE") != "AS_SOON_AS_POSSIBLE":
            c["refusal: summary task constraints"] += 1

    c["links (between scheduled tasks)"] = links
    c["files with at least one link"] = 1 if links else 0
    c["files with progress"] = 1 if (c["tasks complete"] or c["tasks in progress"]) else 0
    return dict(c)


def refused_by(counts: dict, narrow_resources: bool):
    out = []
    for r in REFUSALS:
        if narrow_resources and r.startswith("resource-driven"):
            continue
        if counts.get(f"refusal: {r}"):
            out.append(r)
    if narrow_resources and counts.get(f"refusal: {NARROW_RESOURCE_REFUSAL}"):
        out.append(NARROW_RESOURCE_REFUSAL)
    return out


def mpxj_scheduler_matches(path: str) -> bool:
    """Does MPXJ's MicrosoftScheduler reproduce the file's stored dates and slack?
    The comparator reads the file twice, schedules one copy from the project start
    date and compares early/late dates, Start/Finish and both slacks per task. Debug
    output stays off, so nothing from the file is printed."""
    from java.io import File
    from org.mpxj.cpm import MicrosoftSchedulerComparator
    cmp = MicrosoftSchedulerComparator()
    try:
        return bool(cmp.process(File(path)))
    except Exception:  # a Java exception (unreadable file, scheduler refusal) is a non-match
        return False


def report(label: str, files: list, run_scheduler: bool, name_files: bool):
    totals = Counter()
    skipped = Counter()
    per_file = {}
    matches = {}
    for p in files:
        try:
            counts = analyse(str(p))
        except Exception as e:  # a crash is a defect: name the type, never the content
            skipped[f"CRASH {type(e).__name__}"] += 1
            continue
        if "skipped" in counts:
            skipped[counts["skipped"]] += 1
            continue
        per_file[p] = counts
        totals.update(counts)
        if run_scheduler:
            matches[p] = mpxj_scheduler_matches(str(p))

    print(f"== {label}: {len(files)} files, {len(per_file)} Microsoft Project files read")
    for k, v in sorted(skipped.items()):
        print(f"   skipped ({k}): {v}")
    print("-- totals")
    for k, v in sorted(totals.items()):
        print(f"   {k:62} {v}")

    with_logic = [p for p, c in per_file.items() if c.get("links (between scheduled tasks)")]
    progressed = [p for p in with_logic if per_file[p].get("files with progress")]
    print(f"-- files with logic: {len(with_logic)}; of those progressed: {len(progressed)}, "
          f"with StatusDate: {sum(1 for p in with_logic if per_file[p].get('files with StatusDate'))}")
    for narrow in (False, True):
        rule = "narrow resource rule" if narrow else "strict resource rule"
        in_scope = [p for p in with_logic if not refused_by(per_file[p], narrow)]
        refused = Counter()
        sole = Counter()
        for p in with_logic:
            reasons = refused_by(per_file[p], narrow)
            for r in reasons:
                refused[r] += 1
            if len(reasons) == 1:
                sole[reasons[0]] += 1
        print(f"-- in scope ({rule}): {len(in_scope)} files with logic, "
              f"{sum(per_file[p]['tasks (scheduled, non-summary, active)'] for p in in_scope)} tasks, "
              f"{sum(per_file[p]['links (between scheduled tasks)'] for p in in_scope)} links")
        print(f"   in scope with progress: {sum(1 for p in in_scope if per_file[p].get('files with progress'))}, "
              f"with StatusDate: {sum(1 for p in in_scope if per_file[p].get('files with StatusDate'))}, "
              f"with lagged links: {sum(1 for p in in_scope if per_file[p].get('links with lag'))}, "
              f"with constraints: {sum(1 for p in in_scope if any(k.startswith('constraint ') for k in per_file[p]))}, "
              f"with deadlines: {sum(1 for p in in_scope if per_file[p].get('deadlines'))}, "
              f"with milestones: {sum(1 for p in in_scope if per_file[p].get('milestones'))}, "
              f"with two calendars on a link: {sum(1 for p in in_scope if per_file[p].get('links across two calendars'))}, "
              f"MSPDI: {sum(1 for p in in_scope if per_file[p].get('file type MSPDI'))}")
        for r, n in refused.most_common():
            print(f"   files with logic refused ({r}): {n}; the only reason on {sole[r]}")
        for f in UNCOVERED:
            n = sum(1 for p in in_scope if per_file[p].get(f))
            print(f"   in-scope files using '{f}': {n}" + ("" if n else " (rule not covered by this corpus)"))
        if name_files and in_scope:
            print("   in-scope files: " + ", ".join(sorted(p.name for p in in_scope)))

    if run_scheduler:
        print("-- MPXJ MicrosoftScheduler reproduction (MicrosoftSchedulerComparator per file)")
        print(f"   all files: {sum(matches.values())} of {len(matches)}")
        print(f"   files with logic: {sum(matches[p] for p in with_logic)} of {len(with_logic)}")
        print(f"   files with logic and progress: {sum(matches[p] for p in progressed)} of {len(progressed)}")
        for narrow in (False, True):
            rule = "narrow" if narrow else "strict"
            in_scope = [p for p in with_logic if not refused_by(per_file[p], narrow)]
            print(f"   in scope ({rule} resource rule): {sum(matches[p] for p in in_scope)} of {len(in_scope)}")
            if name_files:
                failed = sorted(p.name for p in in_scope if not matches[p])
                if failed:
                    print(f"   in-scope ({rule}) files MPXJ does not reproduce: " + ", ".join(failed))
        for r in REFUSALS + (NARROW_RESOURCE_REFUSAL,):
            group = [p for p in with_logic if refused_by(per_file[p], True) == [r] or refused_by(per_file[p], False) == [r]]
            if group:
                print(f"   files with logic refused only for '{r}': MPXJ reproduces {sum(matches[p] for p in group)} of {len(group)}")


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", help="directories (searched recursively) or files; public corpus")
    ap.add_argument("--confidential", action="append", default=[], metavar="PATH",
                    help="a file reported as aggregates only, never named")
    ap.add_argument("--mpxj-scheduler", action="store_true", help="also run MPXJ's MicrosoftScheduler per file")
    args = ap.parse_args(argv)
    if not args.paths and not args.confidential:
        ap.print_help()
        return 2
    jvm()
    for d in args.paths:
        root = Path(d)
        files = [root] if root.is_file() else sorted(p for p in root.rglob("*") if p.suffix.lower() in (".mpp", ".xml"))
        report(str(root), files, args.mpxj_scheduler, name_files=True)
    if args.confidential:
        report("confidential", [Path(p) for p in args.confidential], args.mpxj_scheduler, name_files=False)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
