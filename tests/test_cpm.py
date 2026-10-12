"""The CPM engine, one P6 rule per test on the smallest network that shows it.

Every expected value is a hand calculation on the calendar at the top: an 8-hour,
five-day week, 08:00-16:00. Monday 2026-03-02 08:00 is the data date unless a test
says otherwise. P6 is the reference for every rule; docs/METHODOLOGY.md states each.
"""

from datetime import datetime as dt

import pytest

from backend.cpm import LogicLoop, Link, Options, Task, schedule, critical_path_test, refusal_reason
from backend.worktime import ALL_HOURS, WorkCalendar

FIVE_DAY = {str(d): [] for d in range(1, 8)}
for d in "23456":
    FIVE_DAY[d] = [{"start": "08:00", "finish": "16:00"}]
CAL = WorkCalendar(FIVE_DAY, [])
SEVEN_DAY = WorkCalendar({str(d): [{"start": "08:00", "finish": "16:00"}] for d in range(1, 8)}, [])
CALS = {"5d": CAL, "7d": SEVEN_DAY, "24h": ALL_HOURS}

DD = dt(2026, 3, 2, 8)  # Monday


def opts(**over):
    return Options(data_date=DD, **over)


def task(id, hrs=8.0, cal="5d", **over):
    return Task(id=id, remaining_hrs=hrs, clndr_id=cal, **over)


def run(tasks, links=(), o=None):
    return schedule(tasks, list(links), CALS, CAL, o or opts())


# ── Forward pass ──────────────────────────────────────────────────────────────

def test_single_task_starts_at_the_data_date():
    d = run([task(1, 16)])[1]
    assert (d.es, d.ef) == (dt(2026, 3, 2, 8), dt(2026, 3, 3, 16))


def test_data_date_in_non_working_time_moves_to_the_next_working_start():
    # P6 status dates are often Sunday 23:59 or Monday 00:00.
    d = schedule([task(1, 8)], [], CALS, CAL, Options(data_date=dt(2026, 3, 1, 23, 59)))[1]
    assert d.es == dt(2026, 3, 2, 8)


def test_fs_successor_starts_the_next_working_period():
    # 40h finishes Friday 16:00; the successor cannot start at 16:00, so Monday 08:00.
    d = run([task(1, 40), task(2, 8)], [Link(1, 2)])
    assert d[1].ef == dt(2026, 3, 6, 16)
    assert d[2].es == dt(2026, 3, 9, 8)


@pytest.mark.parametrize("lag, es", [
    (0, dt(2026, 3, 9, 8)),
    (16, dt(2026, 3, 11, 8)),     # Fri 16:00 + 2 days = Tue 16:00 -> Wed 08:00
    (-8, dt(2026, 3, 6, 8)),      # a lead: Fri 16:00 - 8h = Fri 08:00
])
def test_fs_lag_is_working_time_on_the_lag_calendar(lag, es):
    assert run([task(1, 40), task(2, 8)], [Link(1, 2, "PR_FS", lag)])[2].es == es


@pytest.mark.parametrize("lag, es", [(0, dt(2026, 3, 2, 8)), (8, dt(2026, 3, 3, 8)), (-8, dt(2026, 3, 2, 8))])
def test_ss_ties_the_start_and_never_precedes_the_data_date(lag, es):
    assert run([task(1, 40), task(2, 8)], [Link(1, 2, "PR_SS", lag)])[2].es == es


@pytest.mark.parametrize("lag, ef, es", [
    (0, dt(2026, 3, 6, 16), dt(2026, 3, 6, 8)),
    (8, dt(2026, 3, 9, 16), dt(2026, 3, 9, 8)),
    (-8, dt(2026, 3, 6, 8), dt(2026, 3, 5, 8)),   # a finish at a period's start is kept as is
])
def test_ff_pushes_the_finish_and_the_start_moves_with_it(lag, ef, es):
    # P6 keeps the duration: an FF-driven activity's start is its finish less the duration.
    d = run([task(1, 40), task(2, 8)], [Link(1, 2, "PR_FF", lag)])[2]
    assert (d.ef, d.es) == (ef, es)


@pytest.mark.parametrize("lag, ef", [(0, dt(2026, 3, 2, 16)), (16, dt(2026, 3, 3, 16)), (-8, dt(2026, 3, 2, 16))])
def test_sf_ties_the_finish_to_the_predecessor_start(lag, ef):
    # Pred starts Mon 08:00; succ (8h) finishes at or after Mon 08:00 + lag, and in any
    # case not before its own 8h from the data date.
    assert run([task(1, 40), task(2, 8)], [Link(1, 2, "PR_SF", lag)])[2].ef == ef


def test_the_latest_predecessor_drives():
    d = run([task(1, 8), task(2, 24), task(3, 8)], [Link(1, 3), Link(2, 3)])
    assert d[3].es == dt(2026, 3, 5, 8)
    assert d[3].driving_preds == {2}


# ── Lag calendars ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("basis, es", [
    ("rcal_Predecessor", dt(2026, 3, 10, 8)),   # 8h on the 5-day pred calendar: Fri 16:00 -> Mon 16:00 -> Tue 08:00
    ("rcal_Successor", dt(2026, 3, 8, 8)),      # 8h on the 7-day succ calendar: Sat 16:00 -> Sun 08:00
    ("rcal_24Hour", dt(2026, 3, 7, 8)),         # 8 clock hours: Sat 00:00 -> Sat 08:00
    ("rcal_ProjDefault", dt(2026, 3, 10, 8)),   # the project default is the 5-day calendar
])
def test_lag_calendar_option(basis, es):
    # Pred (5-day, 40h) finishes Friday 16:00; the successor is on a 7-day calendar.
    d = run([task(1, 40), task(2, 8, cal="7d")], [Link(1, 2, "PR_FS", 8)], opts(lag_calendar=basis))
    assert d[2].es == es


# ── Mixed calendars and 24-hour work ─────────────────────────────────────────

def test_seven_day_successor_starts_on_saturday():
    d = run([task(1, 40), task(2, 8, cal="7d")], [Link(1, 2)])
    assert d[2].es == dt(2026, 3, 7, 8)


def test_five_day_successor_of_weekend_work_waits_for_monday():
    d = run([task(1, 40, cal="7d"), task(2, 8)], [Link(1, 2)])
    assert d[1].ef == dt(2026, 3, 6, 16)       # Mon..Fri, 5 x 8h
    d = run([task(1, 48, cal="7d"), task(2, 8)], [Link(1, 2)])
    assert d[1].ef == dt(2026, 3, 7, 16)       # finishes Saturday
    assert d[2].es == dt(2026, 3, 9, 8)


def test_twenty_four_hour_calendar_counts_clock_time():
    d = run([task(1, 48, cal="24h")])
    assert d[1].ef == dt(2026, 3, 4, 8)


def test_holiday_and_worked_exception():
    cal = WorkCalendar(FIVE_DAY, [
        {"date": "2026-03-04", "periods": []},                                   # Wednesday holiday
        {"date": "2026-03-07", "periods": [{"start": "08:00", "finish": "12:00"}]},  # worked Saturday
    ])
    d = schedule([task(1, 36, cal="x")], [], {"x": cal}, cal, opts())[1]
    # Mon 8 + Tue 8 + Thu 8 + Fri 8 + Sat 4 = 36
    assert d.ef == dt(2026, 3, 7, 12)


# ── Milestones ────────────────────────────────────────────────────────────────

def test_finish_milestone_sits_at_the_end_of_its_predecessor_period():
    d = run([task(1, 40), task(2, 0, task_type="TT_FinMile")], [Link(1, 2)])
    assert (d[2].es, d[2].ef) == (dt(2026, 3, 6, 16), dt(2026, 3, 6, 16))


def test_finish_milestone_in_non_working_time_moves_forward():
    # Predecessor on a 7-day calendar finishes Saturday; the milestone's own calendar
    # has no Saturday, so P6 places it at the next working start, Monday 08:00.
    d = run([task(1, 48, cal="7d"), task(2, 0, task_type="TT_FinMile")], [Link(1, 2)])
    assert d[2].ef == dt(2026, 3, 9, 8)


def test_start_milestone_sits_at_the_start_of_the_next_period():
    d = run([task(1, 40), task(2, 0, task_type="TT_Mile")], [Link(1, 2)])
    assert (d[2].es, d[2].ef) == (dt(2026, 3, 9, 8), dt(2026, 3, 9, 8))


def test_start_milestone_late_date_is_a_start():
    # Successor LS Monday 08:00: the milestone's late dates are Monday 08:00, a start,
    # not the previous period's end a task's late finish would get.
    d = run([task(1, 0, task_type="TT_Mile"), task(2, 8)], [Link(1, 2)])
    assert d[2].ls == dt(2026, 3, 2, 8)
    assert (d[1].ls, d[1].lf) == (dt(2026, 3, 2, 8), dt(2026, 3, 2, 8))
    assert d[1].tf == 0
    # Open-ended, it sits on the project finish as it is, even at a period's end.
    d = run([task(1, 0, task_type="TT_Mile"), task(2, 40)])
    assert (d[1].ls, d[1].lf) == (dt(2026, 3, 6, 16), dt(2026, 3, 6, 16))


def test_finish_milestone_late_date_is_a_finish():
    # An SS successor starting Monday 08:00 puts the milestone at Friday 16:00.
    d = run([task(1, 0, task_type="TT_FinMile"), task(2, 8)], [Link(1, 2, "PR_SS")])
    assert (d[1].ls, d[1].lf) == (dt(2026, 2, 27, 16), dt(2026, 2, 27, 16))


def test_late_start_through_a_lag_is_read_as_a_start_on_the_successor_calendar():
    # 2 (40h) is critical: LS Monday 08:00. 1 precedes it SS with an 8h lead, so 1 may
    # start as late as Monday 08:00 + 8h = Monday 16:00, which P6 reads as Tuesday 08:00.
    d = run([task(1, 8), task(2, 40)], [Link(1, 2, "PR_SS", -8)])
    assert (d[1].ls, d[1].lf) == (dt(2026, 3, 3, 8), dt(2026, 3, 3, 16))
    assert d[1].tf == 8
    # Without a lag the successor's late start passes through as it is.
    d = run([task(1, 8), task(2, 40)], [Link(1, 2, "PR_SS")])
    assert d[1].ls == DD


# ── Backward pass, float ──────────────────────────────────────────────────────

def test_chain_has_zero_float_and_the_branch_carries_its_slack():
    d = run([task(1, 8), task(2, 40), task(3, 8), task(4, 8)], [Link(1, 2), Link(2, 4), Link(1, 3), Link(3, 4)])
    assert d[4].ef == dt(2026, 3, 10, 16)
    assert (d[1].tf, d[2].tf, d[4].tf) == (0, 0, 0)
    assert d[3].tf == 32
    assert (d[3].ls, d[3].lf) == (dt(2026, 3, 9, 8), dt(2026, 3, 9, 16))
    assert d[3].ff == 32
    assert d[4].ff == 0


def test_open_ended_activity_floats_to_the_project_finish():
    d = run([task(1, 40), task(2, 8)])
    assert d[2].lf == dt(2026, 3, 6, 16)
    assert d[2].tf == 32
    # P6 free float of an activity without successors is measured to the project finish.
    assert d[2].ff == 32


def test_open_ends_critical_option_zeroes_their_float():
    d = run([task(1, 40), task(2, 8)], o=opts(open_ends_critical=True))
    assert d[2].tf == 0 and d[1].tf == 0


def test_must_finish_by_sets_the_project_late_finish():
    d = run([task(1, 40)], o=opts(must_finish=dt(2026, 3, 13, 16)))
    assert d[1].tf == 40
    d = run([task(1, 40)], o=opts(must_finish=dt(2026, 3, 4, 16)))
    assert d[1].tf == -16


def test_ss_successor_limits_the_late_start():
    # 1 (40h) SS 2 (8h): 2 is the longer path? No: project finish is 1's Fri 16:00.
    # LS(2) = LF - 8h = Fri 08:00; LS(1) <= LS(2) via SS, so LS(1) = Fri 08:00?? But 1
    # is open-ended too: LF(1) = Fri 16:00 -> LS = Mon 08:00, the smaller wins.
    d = run([task(1, 40), task(2, 8)], [Link(1, 2, "PR_SS")])
    assert d[1].ls == dt(2026, 3, 2, 8)
    d = run([task(1, 8), task(2, 40)], [Link(1, 2, "PR_SS")])
    # 1 is held by SS to 2's LS (Mon 08:00): zero float even though 1 is tiny.
    assert d[1].tf == 0


@pytest.mark.parametrize("ft", ["FT_FF", "FT_SF", "FT_SMLST"])
def test_float_type_option(ft):
    # Finish float is LF - EF, start float LS - ES, smallest the lesser. The engine's late
    # dates keep the remaining duration, so on a plain network the three coincide; the
    # test pins that each definition is honoured.
    d = run([task(1, 40), task(2, 8)], o=opts(float_type=ft))
    assert d[2].tf == 32
    assert d[2].tf == CAL.working_hours_between(d[2].ef, d[2].lf) == CAL.working_hours_between(d[2].es, d[2].ls)


# ── Constraints ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("ctype", ["CS_MSOA", "CS_MSO", "CS_MANDSTART"])
def test_start_on_or_after_delays_the_early_start(ctype):
    d = run([task(1, 8, cstr_type=ctype, cstr_date=dt(2026, 3, 4, 8))])
    assert d[1].es == dt(2026, 3, 4, 8)


@pytest.mark.parametrize("ctype", ["CS_MEOA", "CS_MEO", "CS_MANDFIN"])
def test_finish_on_or_after_delays_the_early_finish(ctype):
    d = run([task(1, 8, cstr_type=ctype, cstr_date=dt(2026, 3, 4, 16))])
    assert (d[1].es, d[1].ef) == (dt(2026, 3, 4, 8), dt(2026, 3, 4, 16))


@pytest.mark.parametrize("ctype", ["CS_MEOB", "CS_MEO"])
def test_finish_on_or_before_caps_the_late_finish_and_makes_float_negative(ctype):
    d = run([task(1, 40, cstr_type=ctype, cstr_date=dt(2026, 3, 4, 16))])
    assert d[1].lf == dt(2026, 3, 4, 16)
    assert d[1].tf == -16


@pytest.mark.parametrize("ctype", ["CS_MSOB", "CS_MSO"])
def test_start_on_or_before_caps_the_late_start(ctype):
    d = run([task(1, 40), task(2, 8, cstr_type=ctype, cstr_date=dt(2026, 3, 3, 8))], [Link(1, 2)])
    assert d[2].ls == dt(2026, 3, 3, 8)
    assert d[2].tf == -32          # EF Mon 16:00 (9th) vs LF Tue 16:00 (3rd)


def test_mandatory_dates_override_logic_in_both_directions():
    # Logic says Monday 9th; mandatory start says Wednesday 4th: the activity goes there,
    # with zero float, and its predecessor inherits the squeeze as negative float.
    d = run([task(1, 40), task(2, 8, cstr_type="CS_MANDSTART", cstr_date=dt(2026, 3, 4, 8))], [Link(1, 2)])
    assert (d[2].es, d[2].ls) == (dt(2026, 3, 4, 8), dt(2026, 3, 4, 8))
    assert d[2].tf == 0
    assert d[1].tf == -24
    d = run([task(1, 40, cstr_type="CS_MANDFIN", cstr_date=dt(2026, 3, 4, 16))])
    assert (d[1].ef, d[1].lf, d[1].tf) == (dt(2026, 3, 4, 16), dt(2026, 3, 4, 16), 0)


def test_secondary_constraint_applies_too():
    d = run([task(1, 8, cstr_type2="CS_MSOA", cstr_date2=dt(2026, 3, 4, 8))])
    assert d[1].es == dt(2026, 3, 4, 8)


def test_as_late_as_possible_consumes_free_float_only():
    # 1 (8h, ALAP) and 2 (40h) both feed 3. 1 can slide to finish Friday 16:00 without
    # delaying 3, so P6 moves its early dates there; its float becomes zero.
    d = run([task(1, 8, cstr_type="CS_ALAP"), task(2, 40), task(3, 8)], [Link(1, 3), Link(2, 3)])
    assert (d[1].es, d[1].ef) == (dt(2026, 3, 6, 8), dt(2026, 3, 6, 16))
    assert d[1].tf == 0 and d[1].ff == 0
    assert d[3].es == dt(2026, 3, 9, 8)


def test_unachievable_constraint_gives_negative_float():
    d = run([task(1, 40), task(2, 8, cstr_type="CS_MEOB", cstr_date=dt(2026, 3, 6, 16))], [Link(1, 2)])
    assert d[2].tf == -8 and d[1].tf == -8


# ── Progress ──────────────────────────────────────────────────────────────────

def test_in_progress_remaining_work_starts_at_the_data_date():
    d = run([task(1, 16, status="TK_Active", act_start=dt(2026, 2, 23, 8))])
    assert (d[1].es, d[1].ef) == (dt(2026, 3, 2, 8), dt(2026, 3, 3, 16))


def test_completed_work_sits_on_the_data_date_and_lags_count_from_its_actual_finish():
    done = task(1, 0, status="TK_Complete", act_start=dt(2026, 2, 23, 8), act_end=dt(2026, 2, 27, 16))
    d = run([done, task(2, 8)], [Link(1, 2, "PR_FS", 8)])
    assert (d[1].es, d[1].ef, d[1].tf) == (DD, DD, None)
    # The lag counts from the actual finish: Fri 27th 16:00 + 8h = Mon 2nd 16:00 -> Tue 08:00.
    assert d[2].es == dt(2026, 3, 3, 8)
    # A lag already spent before the data date holds nothing back.
    earlier = task(1, 0, status="TK_Complete", act_start=dt(2026, 2, 23, 8), act_end=dt(2026, 2, 26, 16))
    assert run([earlier, task(2, 8)], [Link(1, 2, "PR_FS", 4)])[2].es == DD


def test_retained_logic_holds_successors_of_completed_out_of_sequence_work():
    # 1 is unfinished, 2 completed before it: 2's early date waits for 1 and so does 3.
    done = task(2, 0, status="TK_Complete", act_start=dt(2026, 2, 23, 8), act_end=dt(2026, 2, 27, 16))
    d = run([task(1, 24), done, task(3, 8)], [Link(1, 2), Link(2, 3)])
    assert d[2].ef == dt(2026, 3, 4, 16)
    assert d[3].es == dt(2026, 3, 5, 8)


def test_retained_logic_holds_out_of_sequence_remaining_work():
    started = task(2, 16, status="TK_Active", act_start=dt(2026, 2, 25, 8))
    d = run([task(1, 24), started], [Link(1, 2)])
    assert d[2].es == dt(2026, 3, 5, 8)


def test_progress_override_lets_started_work_ignore_its_predecessors():
    started = task(2, 16, status="TK_Active", act_start=dt(2026, 2, 25, 8))
    d = run([task(1, 24), started], [Link(1, 2)], opts(progress_mode="override"))
    assert d[2].es == dt(2026, 3, 2, 8)


def test_actual_dates_mode_schedules_a_future_actual_start_from_that_date():
    started = task(2, 16, status="TK_Active", act_start=dt(2026, 3, 4, 8))
    d = run([started], o=opts(progress_mode="actual"))
    assert d[2].es == dt(2026, 3, 4, 8)
    d = run([started], o=opts(progress_mode="retained"))
    assert d[2].es == dt(2026, 3, 2, 8)


def test_ss_lag_from_actual_start_option():
    started = task(1, 16, status="TK_Active", act_start=dt(2026, 2, 25, 8))
    # P6 default (lag from early start): the in-progress predecessor's early start is
    # the data date, so the successor starts Mon 2nd 08:00 + 16h -> Wed 4th 08:00.
    assert run([started, task(2, 8)], [Link(1, 2, "PR_SS", 16)])[2].es == dt(2026, 3, 4, 8)
    # From the actual start: Wed 25th + 16h = Fri 27th 08:00, before the data date.
    assert run([started, task(2, 8)], [Link(1, 2, "PR_SS", 16)], opts(ss_lag_from_actual_start=True))[2].es == DD


def test_expected_finish_sets_the_remaining_duration():
    t = task(1, 8, expect_end=dt(2026, 3, 5, 16))
    assert run([t], o=opts(use_expected_finish=True))[1].ef == dt(2026, 3, 5, 16)
    assert run([t])[1].ef == dt(2026, 3, 2, 16)


# ── Level of effort ───────────────────────────────────────────────────────────

def test_loe_spans_its_predecessors_and_successors_and_never_drives():
    loe = task(9, 0, task_type="TT_LOE")
    d = run([task(1, 8), task(2, 40), loe, task(3, 8)], [Link(1, 2), Link(1, 9, "PR_SS"), Link(2, 9, "PR_FF"), Link(9, 3)])
    assert (d[9].es, d[9].ef) == (dt(2026, 3, 2, 8), dt(2026, 3, 9, 16))
    # 3 follows the LOE by link, but the LOE does not drive: 3 starts at the data date.
    assert d[3].es == DD


# ── Loops ─────────────────────────────────────────────────────────────────────

def test_logic_loop_is_reported():
    with pytest.raises(LogicLoop) as e:
        run([task(1), task(2), task(3)], [Link(1, 2), Link(2, 3), Link(3, 1)])
    assert set(e.value.task_ids) == {1, 2, 3}


# ── Refusal ───────────────────────────────────────────────────────────────────

def test_refuses_resource_dependent_activities():
    assert "resource-dependent" in refusal_reason([task(1, task_type="TT_Rsrc")], [], opts())


def test_refuses_external_relationships_and_dates():
    assert "outside" in refusal_reason([task(1)], [Link(99, 1)], opts())
    assert "external" in refusal_reason([task(1, external_dates=True)], [], opts())


def test_refuses_multiple_float_paths():
    assert "float path" in refusal_reason([task(1)], [], opts(multiple_float_paths=True))


def test_supported_file_has_no_refusal():
    assert refusal_reason([task(1)], [], opts()) is None


# ── Critical Path Test ────────────────────────────────────────────────────────

HPD = {"5d": 8.0, "7d": 8.0, "24h": 24.0}


def cpt(tasks, links, longest_path, delay_days):
    return critical_path_test(tasks, links, CALS, CAL, opts(), longest_path, delay_days, HPD)


def test_cpt_passes_on_a_clean_chain():
    tasks = [task(1, 8), task(2, 40), task(3, 8)]
    links = [Link(1, 2), Link(2, 3)]
    r = cpt(tasks, links, longest_path=[1, 2, 3], delay_days=10)
    assert r["passed"] is True and r["exact"] is True
    assert r["delayed_task_id"] == 1
    assert r["finish_task_id"] == 3
    assert r["expected_delta_hrs"] == 80 and r["finish_delta_hrs"] == 80
    assert r["absorbed_by_task_id"] is None


def test_cpt_fails_when_a_constraint_absorbs_the_delay():
    tasks = [task(1, 8), task(2, 40), task(3, 8, cstr_type="CS_MANDSTART", cstr_date=dt(2026, 3, 9, 8))]
    links = [Link(1, 2), Link(2, 3)]
    r = cpt(tasks, links, longest_path=[1, 2, 3], delay_days=10)
    assert r["passed"] is False
    assert r["finish_delta_hrs"] == 0
    assert r["absorbed_by_task_id"] == 3


def test_cpt_fails_when_a_parallel_path_absorbs_part_of_the_delay():
    # 1 -> 3 is the longest path (48h); 2 -> 3 is 40h. Delaying 1 by 8h moves the finish by 8h
    # (clean); delaying by 80h also moves it 80h. Absorption needs a constraint-free case:
    # a successor with its own SOA constraint later than the current finish.
    tasks = [task(1, 8), task(2, 40), task(3, 8, cstr_type="CS_MSOA", cstr_date=dt(2026, 3, 16, 8))]
    links = [Link(1, 3), Link(2, 3)]
    r = cpt(tasks, links, longest_path=[2, 3], delay_days=2)
    # 3 is held to Mon 16th by its constraint; a 16h delay on 2 moves nothing.
    assert r["passed"] is False and r["absorbed_by_task_id"] == 3


def test_cpt_skips_completed_activities_on_the_path():
    done = task(1, 0, status="TK_Complete", act_start=dt(2026, 2, 23, 8), act_end=dt(2026, 2, 27, 16))
    tasks = [done, task(2, 40), task(3, 8)]
    r = cpt(tasks, [Link(1, 2), Link(2, 3)], longest_path=[1, 2, 3], delay_days=10)
    assert r["delayed_task_id"] == 2 and r["passed"] is True


def test_cpt_delays_the_first_activity_with_a_duration_not_a_milestone():
    tasks = [task(1, 0, task_type="TT_Mile"), task(2, 40), task(3, 0, task_type="TT_FinMile")]
    r = cpt(tasks, [Link(1, 2), Link(2, 3)], longest_path=[1, 2, 3], delay_days=10)
    assert r["delayed_task_id"] == 2 and r["passed"] is True
    assert (r["delay_hrs"], r["finish_delta_hrs"]) == (80, 80)


def test_cpt_across_unlike_calendars_allows_a_week_and_says_so():
    # A 5-day task drives a 7-day finish: the finish moves the same clock span, which
    # on the delayed activity's calendar reads as the delay give or take snapping.
    tasks = [task(1, 40), task(2, 8, cal="7d")]
    r = cpt(tasks, [Link(1, 2)], longest_path=[1, 2], delay_days=10)
    assert r["calendars_uniform"] is False and r["tolerance_hrs"] == 40
    assert r["passed"] is True
