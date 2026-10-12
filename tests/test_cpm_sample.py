"""The engine reproduces examples/sample-schedule.xer exactly, and the Critical Path
Test runs on it.

The sample is the one schedule that may appear in the repository. Its dates follow
P6's placement rules as verified on real exports (docs/METHODOLOGY.md,
"Recalculation"), so a mismatch here is an engine regression, not a data quirk.
"""

from backend.recalc import CPT_DELAY_DAYS


def test_recalculation_reproduces_every_stored_date_and_float(schedule):
    r = schedule.project.recalculation
    assert r["supported"] is True and r["reason"] is None
    # 24 activities less the 3 completed ones, which P6 computes no float for.
    assert r["compared"] == 21
    assert r["excluded"] == {"complete": 3, "wbs_summary": 0}
    assert r["differing"] == 0
    assert r["differences"] == []
    assert all(n == 0 for n in r["by_field"].values())


def test_sample_options_are_decoded_for_the_engine(schedule):
    o = schedule.project.recalculation["options"]
    assert o["progress_mode"] == "override"
    assert o["float_type"] == "FT_FF"
    assert o["lag_calendar"] == "rcal_Predecessor"
    assert o["delay_days"] == CPT_DELAY_DAYS == 600


def test_critical_path_test_passes_on_the_sample(schedule, by_code):
    c = schedule.project.critical_path_test
    assert c["passed"] is True and c["exact"] is True
    # MS-010 is complete; MEP-020 is the first Longest Path activity with work left.
    assert c["delayed_task_id"] == by_code["MEP-020"]["task_id"]
    assert c["finish_task_id"] == by_code["MS-030"]["task_id"]
    assert c["delay_days"] == 600 and c["delay_hrs"] == 4800
    assert c["finish_before"] == "2026-09-08 16:00"
    assert c["finish_delta_hrs"] == c["expected_delta_hrs"] == 4800
    assert c["calendars_uniform"] is True
    assert c["absorbed_by_task_id"] is None


def test_critical_path_test_moves_the_finish_by_600_working_days(schedule, by_code):
    """Hand check of the delta: 600 working days on the sample's 5-day calendar
    (three holidays and one worked Saturday in between) from 2026-09-08."""
    c = schedule.project.critical_path_test
    assert c["finish_after"] == "2028-12-27 16:00"
