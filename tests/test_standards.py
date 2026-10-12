"""Standards-facing figures: critical definition, % complete basis, scheduling
options, CPLI. Each is something an auditor would recompute by hand, so each test
states the hand calculation."""

from backend.main import percent_complete, schedule_options_for


def test_cpli_hand_calculation(schedule):
    """DCMA 13: CPLI = (CPL + TF) / CPL. CPL runs from the data date (Mon 2 Mar 2026
    08:00) to MS-030's early finish (Wed 9 Sep 08:00) on Standard 5-Day: 137 working
    days less Good Friday (3 Apr) and 1 May = 135 days x 8h = 1080h. TF is 0."""
    cpli = schedule.project.cpli
    assert cpli["cpl_hrs"] == 1080
    assert cpli["tf_hrs"] == 0
    assert cpli["value"] == 1.0


def test_percent_complete_follows_the_activity_type():
    base = {"status_code": "TK_Active", "target_drtn_hr_cnt": "80", "remain_drtn_hr_cnt": "20",
            "phys_complete_pct": "10"}
    assert percent_complete({**base, "complete_pct_type": "CP_Phys"}, None) == 10
    assert percent_complete({**base, "complete_pct_type": "CP_Drtn"}, None) == 75
    assert percent_complete({**base, "complete_pct_type": "CP_Units"}, (30.0, 120.0)) == 25
    # Units with no resource quantities falls back to the physical figure.
    assert percent_complete({**base, "complete_pct_type": "CP_Units"}, None) == 10
    assert percent_complete({**base, "complete_pct_type": "CP_Drtn", "status_code": "TK_Complete"}, None) == 100
    # Remaining above original (a re-estimate) is 0%, not negative.
    assert percent_complete({**base, "complete_pct_type": "CP_Drtn", "remain_drtn_hr_cnt": "100"}, None) == 0


def _tables(opts=None, proj=None):
    t = {"PROJECT": {"fields": ["proj_id", "critical_drtn_hr_cnt", "critical_path_type"],
                     "rows": [["7", *(proj or ["40", "CT_TotFloat"])]]}}
    if opts:
        t["SCHEDOPTIONS"] = {"fields": ["proj_id", *opts.keys()], "rows": [["7", *opts.values()]]}
    return t


def test_schedule_options_decoded():
    o = schedule_options_for(_tables({"sched_retained_logic": "N", "sched_progress_override": "Y",
                                      "sched_calendar_on_relationship_lag": "rcal_24Hour"}), 7)
    assert o["present"] and o["retained_logic"] is False and o["progress_override"] is True
    assert o["lag_calendar"] == "rcal_24Hour"
    assert o["critical_float_hrs"] == 40 and o["critical_type"] == "CT_TotFloat"


def test_schedule_options_absent_are_unknown_not_false():
    o = schedule_options_for(_tables(), 7)
    assert o["present"] is False and o["retained_logic"] is None
    assert o["lag_calendar"] == "rcal_Predecessor"  # P6's default


def test_critical_uses_the_file_threshold(schedule):
    """The sample defines no threshold, so P6's default (TF <= 0) applies."""
    for a in schedule.activities:
        tf = a["total_float_hrs"]
        assert a["is_critical"] == (tf is not None and tf <= 0)
