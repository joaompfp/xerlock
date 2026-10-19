"""The Microsoft Project engine, one rule per test on the smallest network that shows it.

Every expected value is a hand calculation on the calendar at the top: an 8-hour,
five-day week, 08:00-16:00. Monday 2026-03-02 08:00 is the project start unless a test
says otherwise. Project is the reference for every rule; SPEC-MSPROJECT.md §7.4 names
the source of each (MPXJ's MicrosoftScheduler at v16.10.0 and Microsoft's field pages).
"""

from datetime import datetime as dt

import pytest

from backend.cpm_core import LogicLoop
from backend.cpm_msp import (ALAP, FNET, FNLT, MFO, MSO, SNET, SNLT, Link, Options, Task,
                             critical_path_test, schedule)
from backend.worktime import ALL_HOURS, WorkCalendar

FIVE_DAY = {str(d): [] for d in range(1, 8)}
for d in "23456":
    FIVE_DAY[d] = [{"start": "08:00", "finish": "16:00"}]
CAL = WorkCalendar(FIVE_DAY, [])
SEVEN_DAY = WorkCalendar({str(d): [{"start": "08:00", "finish": "16:00"}] for d in range(1, 8)}, [])
CALS = {"5d": CAL, "7d": SEVEN_DAY, "24h": ALL_HOURS}

START = dt(2026, 3, 2, 8)  # Monday


def opts(start=START):
    return Options(project_start=start)


def task(id, hrs=8.0, cal="5d", **over):
    over.setdefault("remaining_hrs", hrs if over.get("act_end") is None else 0.0)
    return Task(id=id, duration_hrs=hrs, clndr_id=cal, **over)


def run(tasks, links=(), o=None):
    return schedule(tasks, list(links), CALS, CAL, o or opts())


# ── Forward pass ──────────────────────────────────────────────────────────────

def test_task_without_predecessors_starts_at_the_project_start():
    d = run([task(1, 16)])[1]
    assert (d.es, d.ef) == (dt(2026, 3, 2, 8), dt(2026, 3, 3, 16))


def test_project_start_in_non_working_time_moves_to_the_next_working_start():
    d = run([task(1, 8)], o=opts(dt(2026, 3, 1, 23, 59)))[1]
    assert d.es == dt(2026, 3, 2, 8)


def test_fs_successor_starts_the_next_working_period():
    d = run([task(1, 40), task(2, 8)], [Link(1, 2)])
    assert d[1].ef == dt(2026, 3, 6, 16)
    assert d[2].es == dt(2026, 3, 9, 8)
    assert d[2].driving_preds == {1}


@pytest.mark.parametrize("lag, es", [
    (0, dt(2026, 3, 9, 8)),
    (16, dt(2026, 3, 11, 8)),     # Fri 16:00 + 2 days = Tue 16:00 -> Wed 08:00
    (-8, dt(2026, 3, 6, 8)),      # a lead: Fri 16:00 - 8h = Fri 08:00
])
def test_fs_lag_and_lead(lag, es):
    assert run([task(1, 40), task(2, 8)], [Link(1, 2, lag_hrs=lag)])[2].es == es


def test_ss_lag_counts_from_the_predecessor_start():
    d = run([task(1, 16), task(2, 8)], [Link(1, 2, "PR_SS", 8)])
    assert d[2].es == dt(2026, 3, 3, 8)   # Mon 08:00 + 8h = Mon 16:00 -> Tue 08:00


def test_ff_takes_the_successor_remaining_duration_off_the_predecessor_finish():
    d = run([task(1, 16), task(2, 8)], [Link(1, 2, "PR_FF")])
    assert (d[2].es, d[2].ef) == (dt(2026, 3, 3, 8), dt(2026, 3, 3, 16))


def test_ff_never_starts_before_the_project_start():
    d = run([task(1, 8), task(2, 40)], [Link(1, 2, "PR_FF")])
    assert (d[2].es, d[2].ef) == (dt(2026, 3, 2, 8), dt(2026, 3, 6, 16))


def test_sf_fixes_the_successor_finish_at_the_predecessor_start():
    # The finish sits exactly where the predecessor starts, a period start included
    # (mpp9relations.mpp), with the start a full duration earlier; Project does not
    # floor it at the project start.
    d = run([task(1, 16), task(2, 8)], [Link(1, 2, "PR_SF")])
    assert (d[2].es, d[2].ef) == (dt(2026, 2, 27, 8), dt(2026, 3, 2, 8))


def test_sf_finish_follows_the_start_when_a_constraint_moves_it():
    d = run([task(1, 16), task(2, 8, constraint=SNET, cstr_date=dt(2026, 3, 3, 8))], [Link(1, 2, "PR_SF")])
    assert (d[2].es, d[2].ef) == (dt(2026, 3, 3, 8), dt(2026, 3, 3, 16))


def test_lag_counts_on_the_successor_calendar():
    # Fri 16:00 + 16h on the successor's 7-day calendar = Sun 16:00 -> Mon 08:00;
    # on the predecessor's 5-day calendar it would be Wed 08:00.
    d = run([task(1, 40, "5d"), task(2, 8, "7d")], [Link(1, 2, lag_hrs=16)])
    assert d[2].es == dt(2026, 3, 9, 8)


def test_elapsed_lag_counts_on_the_clock():
    d = run([task(1, 40), task(2, 8)], [Link(1, 2, lag_hrs=24, lag_elapsed=True)])
    assert d[2].es == dt(2026, 3, 9, 8)   # Fri 16:00 + 24 clock hours = Sat 16:00 -> Mon


def test_milestone_may_sit_at_the_end_of_a_period():
    d = run([task(1, 8), task(2, 0, milestone=True)], [Link(1, 2)])
    assert (d[2].es, d[2].ef) == (dt(2026, 3, 2, 16), dt(2026, 3, 2, 16))


def test_milestone_in_non_working_time_moves_to_the_next_start():
    d = run([task(1, 0, milestone=True)], o=opts(dt(2026, 3, 1, 23, 59)))[1]
    assert d.es == dt(2026, 3, 2, 8)


def test_elapsed_duration_runs_on_the_clock_in_both_passes():
    d = run([task(1, 24, elapsed=True), task(2, 40)])
    assert d[1].ef == dt(2026, 3, 3, 8)
    # Its late finish is the project finish on the clock, not the previous period's end.
    assert (d[1].ls, d[1].lf) == (dt(2026, 3, 5, 16), dt(2026, 3, 6, 16))
    assert d[1].tf == 80.0


# ── Constraints in the forward pass ───────────────────────────────────────────

def test_snet_without_predecessors_starts_at_its_date():
    d = run([task(1, 8, constraint=SNET, cstr_date=dt(2026, 3, 4, 8))])[1]
    assert d.es == dt(2026, 3, 4, 8)


def test_fnet_without_predecessors_finishes_at_its_date():
    d = run([task(1, 8, constraint=FNET, cstr_date=dt(2026, 3, 5, 16))])[1]
    assert (d.es, d.ef) == (dt(2026, 3, 5, 8), dt(2026, 3, 5, 16))


def test_snet_later_than_logic_holds_the_start():
    d = run([task(1, 8), task(2, 8, constraint=SNET, cstr_date=dt(2026, 3, 5, 8))], [Link(1, 2)])
    assert d[2].es == dt(2026, 3, 5, 8)


def test_snet_earlier_than_logic_has_no_effect():
    d = run([task(1, 8), task(2, 8, constraint=SNET, cstr_date=dt(2026, 3, 2, 8))], [Link(1, 2)])
    assert d[2].es == dt(2026, 3, 3, 8)


def test_snlt_pulls_a_task_earlier_than_its_logic_with_negative_slack():
    # Project honours the constraint over the link: the successor starts Wednesday
    # though its predecessor finishes Friday, and both show negative slack.
    d = run([task(1, 40), task(2, 8, constraint=SNLT, cstr_date=dt(2026, 3, 4, 8))], [Link(1, 2)])
    assert (d[2].es, d[2].ef) == (dt(2026, 3, 4, 8), dt(2026, 3, 4, 16))
    assert (d[2].ls, d[2].lf) == (dt(2026, 3, 4, 8), dt(2026, 3, 4, 16))
    assert d[2].tf == 0.0
    assert (d[1].ls, d[1].lf) == (dt(2026, 2, 25, 8), dt(2026, 3, 3, 16))
    assert d[1].tf == -24.0


def test_fnlt_pulls_the_finish_to_its_date():
    d = run([task(1, 40), task(2, 8, constraint=FNLT, cstr_date=dt(2026, 3, 4, 16))], [Link(1, 2)])
    assert (d[2].es, d[2].ef) == (dt(2026, 3, 4, 8), dt(2026, 3, 4, 16))
    assert d[2].lf == dt(2026, 3, 4, 16)


def test_mso_sets_the_start_regardless_of_logic():
    d = run([task(1, 40), task(2, 8, constraint=MSO, cstr_date=dt(2026, 3, 3, 8))], [Link(1, 2)])
    assert (d[2].es, d[2].ef) == (dt(2026, 3, 3, 8), dt(2026, 3, 3, 16))
    assert (d[2].ls, d[2].lf) == (dt(2026, 3, 3, 8), dt(2026, 3, 3, 16))


def test_mfo_sets_the_finish_and_holds_the_late_finish():
    d = run([task(1, 40), task(2, 0, milestone=True, constraint=MFO, cstr_date=dt(2026, 3, 4, 16))], [Link(1, 2)])
    assert (d[2].es, d[2].ef, d[2].lf) == (dt(2026, 3, 4, 16),) * 3
    assert d[1].tf == -16.0


def test_fnet_on_a_started_task_raises_its_finish():
    d = run([task(1, 8, act_start=dt(2026, 3, 2, 8), constraint=FNET, cstr_date=dt(2026, 3, 4, 16))])[1]
    assert d.ef == dt(2026, 3, 4, 16)


# ── Progress ──────────────────────────────────────────────────────────────────

def test_started_task_is_anchored_at_its_actual_start_with_its_full_duration():
    # Started before its predecessor finished: the logic does not move it, and its
    # total slack is the finish slack.
    d = run([task(1, 40), task(2, 8, act_start=dt(2026, 3, 2, 8))], [Link(1, 2)])
    assert (d[2].es, d[2].ef) == (dt(2026, 3, 2, 8), dt(2026, 3, 2, 16))
    assert (d[2].ls, d[2].lf) == (dt(2026, 3, 2, 8), dt(2026, 3, 6, 16))
    assert d[2].tf == 32.0


def test_completed_task_keeps_its_actual_dates_and_has_no_slack():
    d = run([task(1, 16, act_start=dt(2026, 3, 2, 8), act_end=dt(2026, 3, 3, 12)), task(2, 8)], [Link(1, 2)])
    assert (d[1].es, d[1].ef, d[1].ls, d[1].lf) == (dt(2026, 3, 2, 8), dt(2026, 3, 3, 12)) * 2
    assert (d[1].tf, d[1].ff) == (0.0, 0.0)
    assert d[2].es == dt(2026, 3, 3, 12)


def test_finished_successor_does_not_bound_the_late_finish():
    d = run([task(1, 8), task(2, 8, act_start=dt(2026, 3, 2, 8), act_end=dt(2026, 3, 2, 16)), task(3, 24)],
            [Link(1, 2)])
    assert d[1].lf == dt(2026, 3, 4, 16)   # the project finish, not the finished successor


def test_fs_predecessor_reads_the_calculated_late_start_of_a_started_successor():
    # The successor shows its actual start as late start; its predecessor's late finish
    # comes from late finish minus remaining duration instead.
    d = run([task(1, 8), task(2, 16, act_start=dt(2026, 3, 2, 8))], [Link(1, 2)])
    assert d[2].ls == dt(2026, 3, 2, 8)
    assert d[1].lf == dt(2026, 2, 27, 16)
    assert d[1].tf == -8.0


# ── Backward pass ─────────────────────────────────────────────────────────────

def test_late_dates_without_successors_come_from_the_project_finish():
    d = run([task(1, 16), task(2, 8)])
    assert (d[2].ls, d[2].lf) == (dt(2026, 3, 3, 8), dt(2026, 3, 3, 16))
    assert (d[2].tf, d[2].ff) == (8.0, 8.0)   # no successor: free slack is the total slack


def test_late_finish_at_a_period_start_moves_back_to_the_previous_period_end():
    d = run([task(1, 8), task(2, 8)], [Link(1, 2)])
    assert (d[1].ls, d[1].lf) == (dt(2026, 3, 2, 8), dt(2026, 3, 2, 16))
    assert d[1].tf == 0.0


def test_zero_duration_task_keeps_its_late_finish_at_the_successor_late_start():
    # A milestone's late finish is not moved back to the previous period's end.
    d = run([task(1, 0, milestone=True), task(2, 8)], [Link(1, 2)])
    assert (d[1].ls, d[1].lf) == (dt(2026, 3, 2, 8), dt(2026, 3, 2, 8))
    assert (d[1].tf, d[1].ff) == (0.0, 0.0)


def test_must_finish_on_measures_slack_from_where_logic_puts_the_task():
    # slack9.mpp: the milestone shows its constraint date on all four dates and a
    # total slack of -1 day, its predecessor finishing a day after the date.
    d = run([task(1, 16), task(2, 0, milestone=True, constraint=MFO, cstr_date=dt(2026, 3, 2, 16))], [Link(1, 2)])
    assert (d[2].es, d[2].ef, d[2].ls, d[2].lf) == (dt(2026, 3, 2, 16),) * 4
    assert d[2].tf == -8.0
    assert d[1].tf == -8.0


def test_ss_backward_caps_the_predecessor_at_the_project_finish():
    d = run([task(1, 16), task(2, 8)], [Link(1, 2, "PR_SS")])
    assert (d[1].ls, d[1].lf) == (dt(2026, 3, 2, 8), dt(2026, 3, 3, 16))
    assert d[1].tf == 0.0


def test_ff_backward():
    d = run([task(1, 8), task(2, 16)], [Link(1, 2, "PR_FF")])
    assert (d[1].ls, d[1].lf) == (dt(2026, 3, 3, 8), dt(2026, 3, 3, 16))
    assert (d[1].tf, d[1].ff) == (8.0, 8.0)


def test_sf_backward():
    d = run([task(1, 16), task(2, 8)], [Link(1, 2, "PR_SF")])
    assert (d[1].ls, d[1].lf) == (dt(2026, 3, 2, 8), dt(2026, 3, 3, 16))
    assert d[1].tf == 0.0


def test_mso_bounds_the_late_finish():
    d = run([task(1, 40), task(2, 8, constraint=MSO, cstr_date=dt(2026, 3, 4, 8))])
    assert d[2].lf == dt(2026, 3, 4, 16)
    assert (d[2].tf, d[2].ff) == (0.0, 0.0)


def test_deadline_bounds_the_late_finish():
    d = run([task(1, 40), task(2, 8, deadline=dt(2026, 3, 2, 16))])
    assert d[2].lf == dt(2026, 3, 2, 16)
    assert d[2].tf == 0.0


def test_deadline_before_the_finish_gives_negative_total_and_zero_free_slack():
    d = run([task(1, 8, deadline=dt(2026, 3, 2, 12))])[1]
    assert (d.tf, d.ff) == (-4.0, 0.0)


# ── ALAP ──────────────────────────────────────────────────────────────────────

def test_alap_task_takes_its_late_dates_and_feeds_its_successor_from_them():
    d = run([task(1, 8, constraint=ALAP), task(2, 8), task(3, 40)], [Link(1, 2)])
    assert (d[1].es, d[1].ef) == (dt(2026, 3, 5, 8), dt(2026, 3, 5, 16))
    assert (d[2].es, d[2].ef) == (dt(2026, 3, 6, 8), dt(2026, 3, 6, 16))
    assert (d[1].tf, d[1].ff, d[2].tf) == (0.0, 0.0, 0.0)


# ── Slack ─────────────────────────────────────────────────────────────────────

def test_free_slack_is_the_gap_to_the_successor_less_the_lag():
    d = run([task(1, 8), task(2, 8)], [Link(1, 2, lag_hrs=16)])
    assert d[2].es == dt(2026, 3, 5, 8)
    assert (d[1].tf, d[1].ff) == (0.0, 0.0)


def test_free_slack_never_exceeds_total_slack():
    # A deadline leaves the task no total slack though its successor could wait a day.
    d = run([task(1, 8, deadline=dt(2026, 3, 2, 16)),
             task(2, 8, constraint=SNET, cstr_date=dt(2026, 3, 4, 8)), task(3, 40)], [Link(1, 2)])
    assert d[1].tf == 0.0
    assert d[1].ff == 0.0


def test_loop_is_refused():
    with pytest.raises(LogicLoop):
        run([task(1), task(2)], [Link(1, 2), Link(2, 1)])


# ── Critical Path Test ────────────────────────────────────────────────────────

def cpt(tasks, links, path, days=5):
    return critical_path_test(tasks, list(links), CALS, CAL, opts(), path, delay_days=days,
                              hrs_per_day={"5d": 8.0, "7d": 8.0})


def test_cpt_passes_on_a_clean_chain():
    r = cpt([task(1, 8), task(2, 8), task(3, 8)], [Link(1, 2), Link(2, 3)], [1, 2, 3])
    assert r["passed"] and r["exact"]
    assert r["delayed_task_id"] == 1 and r["finish_task_id"] == 3
    assert r["finish_delta_hrs"] == 40.0


def test_cpt_fails_where_a_constraint_absorbs_the_delay():
    r = cpt([task(1, 8), task(2, 8, constraint=SNLT, cstr_date=dt(2026, 3, 4, 8)), task(3, 8)],
            [Link(1, 2), Link(2, 3)], [1, 2, 3])
    assert not r["passed"]
    assert r["absorbed_by_task_id"] == 2
