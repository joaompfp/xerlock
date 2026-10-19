"""The Project recalculation layer (backend/recalc_msp.py): refusals with their reasons,
uncovered rules, summary-task logic, the resource rule and the comparison, one rule per
test on minimal MSPDI documents. The engine's own rules are in test_cpm_msp.py."""

from tests.test_mspdi import SAMPLE_XML, act, calendar, parse, task  # noqa: F401
from backend.schedule import parse_schedule

START = "<StartDate>2026-03-02T08:00:00</StartDate><ScheduleFromStart>1</ScheduleFromStart>"
LATE = {"LateStart": "2026-03-02T08:00:00", "LateFinish": "2026-03-02T16:00:00"}

WEEK_9_TO_17 = "".join(
    f"<WeekDay><DayType>{d}</DayType><DayWorking>{0 if d in (1, 7) else 1}</DayWorking>"
    + ("" if d in (1, 7) else "<WorkingTimes><WorkingTime><FromTime>09:00:00</FromTime><ToTime>17:00:00</ToTime></WorkingTime></WorkingTimes>")
    + "</WeekDay>" for d in range(1, 8))


def recalc(tasks, project=START, **kw):
    d = parse(tasks=tasks, project=project, **kw)
    return d["project"]["recalculation"], d["project"]["critical_path_test"]


def one(**fields):
    return task(1, **{**LATE, **fields})


# ── Comparison ───────────────────────────────────────────────────────────────

def test_a_reproduced_task_reports_no_difference_and_the_cpt_runs():
    r, cpt = recalc(one())
    assert r["supported"] and r["compared"] == 1 and r["differing"] == 0 and r["uncovered"] == []
    assert r["options"]["lag_calendar"] == "rcal_Successor" and r["options"]["schedule_from"] == "start"
    assert cpt["passed"] and cpt["delayed_task_id"] == 1


def test_a_stored_value_the_engine_does_not_reproduce_is_a_difference():
    r, cpt = recalc(one(LateFinish="2026-03-03T16:00:00", TotalSlack=4800))
    assert r["differing"] == 1 and r["by_field"]["lf"] == 1 and r["by_field"]["tf"] == 1 and r["by_field"]["ls"] == 0
    assert r["differences"][0]["task_id"] == 1 and cpt is None


def test_completed_tasks_are_compared_too():
    r, _ = recalc(one(ActualStart="2026-03-02T08:00:00", ActualFinish="2026-03-02T16:00:00"))
    assert r["compared"] == 1 and r["differing"] == 0 and r["excluded"]["complete"] == 0


def test_summary_tasks_are_excluded_and_counted():
    r, _ = recalc(task(1, "S", level=1, Summary=1) + task(2, level=2, **LATE))
    assert r["compared"] == 1 and r["excluded"]["wbs_summary"] == 1


# ── Refusals ─────────────────────────────────────────────────────────────────

def test_no_project_start_date_is_refused():
    r, _ = recalc(one(), project="")
    assert not r["supported"] and "no start date" in r["reason"]


def test_scheduled_from_finish_is_refused():
    r, _ = recalc(one(), project="<StartDate>2026-03-02T08:00:00</StartDate><ScheduleFromStart>0</ScheduleFromStart>")
    assert "scheduled from its finish date" in r["reason"]


def test_incomplete_manual_task_is_refused_but_a_complete_one_is_not():
    r, _ = recalc(one(Manual=1))
    assert r["reason"].startswith("1 manually scheduled task")
    r, _ = recalc(one(Manual=1, ActualStart="2026-03-02T08:00:00", ActualFinish="2026-03-02T16:00:00"))
    assert r["supported"]


def test_split_task_is_refused_when_its_dates_span_more_working_time_than_its_duration():
    r, _ = recalc(one(finish="2026-03-03T16:00:00", LateFinish="2026-03-03T16:00:00"))
    assert r["reason"].startswith("1 task is split or contoured")
    # Dates that merely bracket non-working time are no split: an SF successor
    # finishing Monday 08:00 after starting Friday 08:00.
    r, _ = recalc(one(start="2026-02-27T08:00:00", finish="2026-03-02T08:00:00", LateStart="2026-02-27T08:00:00", LateFinish="2026-03-02T08:00:00"))
    assert "split" not in (r["reason"] or "")


def test_recurring_task_is_refused():
    r, _ = recalc(one(Recurring=1))
    assert "recurring" in r["reason"]


def test_subproject_and_cross_project_links_are_refused():
    r, _ = recalc(one(IsSubproject=1))
    assert "inserted or external" in r["reason"]
    tasks = one() + task(2, **LATE).replace("</Task>", "<PredecessorLink><PredecessorUID>9</PredecessorUID><Type>1</Type>"
                                             "<CrossProject>1</CrossProject></PredecessorLink></Task>")
    r, _ = recalc(tasks)
    assert "inserted or external" in r["reason"]


def test_summary_task_constraint_is_refused():
    r, _ = recalc(task(1, "S", level=1, Summary=1, ConstraintType=4, ConstraintDate="2026-03-02T08:00:00") + task(2, level=2, **LATE))
    assert "summary task carries a constraint" in r["reason"]


def test_multiple_critical_paths_option_is_refused():
    r, _ = recalc(one(), project=START + "<MultipleCriticalPaths>1</MultipleCriticalPaths>")
    assert "multiple critical paths" in r["reason"]


def resource_doc(res_cal, units="1", rtype=1):
    return dict(
        tasks=one(),
        calendars=calendar() + calendar(uid=2, name="R", weekdays=res_cal, base=-1),
        resources=f"<Resource><UID>1</UID><Name>R</Name><Type>{rtype}</Type><CalendarUID>2</CalendarUID></Resource>",
        assignments=f"<Assignment><UID>1</UID><TaskUID>1</TaskUID><ResourceUID>1</ResourceUID><Units>{units}</Units>"
                    f"<Start>2026-03-02T08:00:00</Start><Finish>2026-03-02T16:00:00</Finish></Assignment>",
    )


def test_work_resource_on_other_working_time_is_refused():
    r, _ = recalc(**resource_doc(WEEK_9_TO_17))
    assert "resource assignments" in r["reason"]


def test_work_resource_on_the_same_working_time_is_not_refused():
    from tests.test_mspdi import WEEK_5DAY
    r, _ = recalc(**resource_doc(WEEK_5DAY))
    assert r["supported"]


def test_material_resource_or_zero_units_do_not_drive_the_task():
    r, _ = recalc(**resource_doc(WEEK_9_TO_17, rtype=0))
    assert r["supported"]
    r, _ = recalc(**resource_doc(WEEK_9_TO_17, units="0"))
    assert r["supported"]


def test_task_levelling_delay_is_honoured_as_elapsed_time():
    # 480 clock hours (288000 tenths of a minute) from Monday 2 March 08:00 is Sunday
    # 22 March 08:00, so the task starts Monday 23 March.
    r, cpt = recalc(one(LevelingDelay=288000, LevelingDelayFormat=8, start="2026-03-23T08:00:00", finish="2026-03-23T16:00:00",
                        LateStart="2026-03-23T08:00:00", LateFinish="2026-03-23T16:00:00"))
    assert r["supported"] and r["differing"] == 0, r["differences"]
    # Inside the validated case (unstarted, unconstrained, no non-FS or lagged
    # predecessor, delayed onto a working start): nothing uncovered, the CPT runs.
    assert r["uncovered"] == [] and cpt["passed"]


def test_levelling_delay_outside_the_validated_case_is_uncovered_and_withholds_the_cpt():
    # An SS predecessor is outside the evidence: compared, listed, test withheld.
    tasks = one() + task(2, start="2026-03-23T08:00:00", finish="2026-03-23T16:00:00", links=[(1, 3, 0, 7)],
                         LevelingDelay=288000, LevelingDelayFormat=8,
                         LateStart="2026-03-23T08:00:00", LateFinish="2026-03-23T16:00:00")
    r, cpt = recalc(tasks)
    assert r["supported"]
    assert r["uncovered"] == ["levelling delay outside the validated case (a started or constrained task, non-FS or lagged predecessors, or a delayed start off a working start)"]
    assert cpt is None


def test_assignment_levelling_delay_is_refused():
    from tests.test_mspdi import WEEK_5DAY
    kw = resource_doc(WEEK_5DAY)
    kw["assignments"] = kw["assignments"].replace("<Units>", "<LevelingDelay>4800</LevelingDelay><Units>")
    r, _ = recalc(**kw)
    assert r["reason"].startswith("1 assignment carries a levelling delay")



# ── Uncovered rules ──────────────────────────────────────────────────────────

def test_uncovered_rules_are_listed_and_withhold_the_cpt():
    r, cpt = recalc(one(Deadline="2026-03-02T16:00:00"))
    assert r["supported"] and r["differing"] == 0
    assert r["uncovered"] == ["deadlines"] and cpt is None


def test_each_uncovered_rule_is_named():
    r, _ = recalc(one(ConstraintType=5, ConstraintDate="2026-03-02T08:00:00", DurationFormat=8, duration="PT8H0M0S"))
    assert set(r["uncovered"]) == {"Start No Later Than constraints", "elapsed durations"}
    r, _ = recalc(one() + task(2, start="2026-03-03T08:00:00", finish="2026-03-03T16:00:00", links=[(1, 1, 100, 20)]))
    assert set(r["uncovered"]) == {"elapsed lags", "percentage lags"}


# ── Summary-task logic ───────────────────────────────────────────────────────

def test_logic_on_a_summary_task_is_expanded_to_its_leaves():
    # Phase A (tasks 2, 3) finish-to-start Phase B (task 5): task 5 starts after the
    # later of the two leaves.
    tasks = (task(1, "A", level=1, Summary=1)
             + task(2, level=2, LateStart="2026-03-03T08:00:00", LateFinish="2026-03-03T16:00:00", TotalSlack=4800, FreeSlack=4800)
             + task(3, level=2, start="2026-03-02T08:00:00", finish="2026-03-03T16:00:00", duration="PT16H0M0S",
                    LateStart="2026-03-02T08:00:00", LateFinish="2026-03-03T16:00:00")
             + task(4, "B", level=1, Summary=1, links=[(1, 1, 0, 7)])
             + task(5, level=2, start="2026-03-04T08:00:00", finish="2026-03-04T16:00:00",
                    LateStart="2026-03-04T08:00:00", LateFinish="2026-03-04T16:00:00"))
    r, _ = recalc(tasks)
    assert r["supported"] and r["differing"] == 0 and r["compared"] == 3, r["differences"]


def test_ss_from_a_summary_task_stands_for_its_earliest_leaf():
    tasks = (task(1, "A", level=1, Summary=1)
             + task(2, level=2, start="2026-03-03T08:00:00", finish="2026-03-03T16:00:00",
                    ConstraintType=4, ConstraintDate="2026-03-03T08:00:00",
                    LateStart="2026-03-03T08:00:00", LateFinish="2026-03-03T16:00:00")
             + task(3, level=2, LateStart="2026-03-03T08:00:00", LateFinish="2026-03-03T16:00:00", TotalSlack=4800, FreeSlack=4800)
             + task(4, start="2026-03-02T08:00:00", finish="2026-03-02T16:00:00", links=[(1, 3, 0, 7)],
                    LateStart="2026-03-03T08:00:00", LateFinish="2026-03-03T16:00:00", TotalSlack=4800, FreeSlack=4800))
    r, _ = recalc(tasks)
    assert r["supported"] and r["differing"] == 0, r["differences"]


# ── The sample ───────────────────────────────────────────────────────────────

def test_sample_xml_is_refused_for_its_manual_task_and_names_its_uncovered_rules():
    d = parse_schedule(str(SAMPLE_XML))
    r = d["project"]["recalculation"]
    assert not r["supported"] and r["reason"].startswith("1 manually scheduled task")
    assert r["uncovered"] == ["deadlines", "Finish No Later Than constraints"]
    assert d["project"]["critical_path_test"] is None
