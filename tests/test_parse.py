"""Numerically load-bearing parse behaviour.

These are the values a reviewer would put in a report — float, critical basis,
driving logic, and the dates shown on screen. If one of these changes silently,
the tool is lying to its user, so each is pinned explicitly.
"""

from backend.main import safe_float, safe_float_or


# ── Project-level stats ──────────────────────────────────────────────────────

def test_project_stats(schedule):
    p = schedule.project
    assert p.proj_short_name == "DEMO-DC-01"
    assert p.total_activities == 24
    assert len(schedule.activities) == 24
    assert p.total_wbs == 7
    assert p.data_date is not None


def test_no_warnings_on_clean_single_project_file(schedule):
    """The sample is single-project and valid UTF-8; any warning here means a
    regression in the multi-project or encoding detection."""
    assert schedule.warnings == []


# ── Critical basis: TF<=0 vs longest path ────────────────────────────────────

def test_critical_is_tf_le_zero_not_just_zero(schedule):
    """is_critical must follow the planning convention TF <= 0, so that activities
    already behind an imposed date count as critical rather than dropping out."""
    for a in schedule.activities:
        tf = a["total_float_hrs"]
        assert a["is_critical"] == (tf is not None and tf <= 0), a["task_code"]
        assert a["is_negative_float"] == (tf is not None and tf < 0), a["task_code"]


def test_longest_path_and_critical_sets(schedule):
    """Longest path is the driving-chain trace; TF<=0 is the float test. They are
    different definitions and the sample exercises the difference: MS-010 is a
    completed milestone on the driving chain but carries float."""
    lp = {a["task_code"] for a in schedule.activities if a["is_longest_path"]}
    crit = {a["task_code"] for a in schedule.activities if a["is_critical"]}

    assert lp == {"MS-010", "MS-020", "MS-030", "MEP-020", "MEP-060",
                  "MEP-080", "CX-010", "CX-020", "CX-030", "CX-040"}
    assert crit == lp - {"MS-010"}
    assert schedule.project.total_longest_path == len(lp)
    assert schedule.project.total_critical == len(crit)


def test_longest_path_is_a_connected_chain(schedule, by_code):
    """Every longest-path activity except the start must have at least one
    predecessor that is also on the longest path — otherwise the trace is broken."""
    lp_ids = {a["task_id"] for a in schedule.activities if a["is_longest_path"]}
    roots = []
    for a in schedule.activities:
        if not a["is_longest_path"]:
            continue
        if not any(p["task_id"] in lp_ids for p in a["predecessors"]):
            roots.append(a["task_code"])
    assert roots == ["MS-010"], f"chain should have exactly one root, got {roots}"


# ── Driving relationships ────────────────────────────────────────────────────

def test_driving_flags_pick_the_closest_predecessor(by_code):
    """Among several predecessors, only the one(s) actually explaining the
    successor's computed date are driving."""
    mep050 = by_code["MEP-050"]
    driving = [p for p in mep050["predecessors"] if p["driving"]]
    assert len(mep050["predecessors"]) == 2
    assert len(driving) == 1, "exactly one of MEP-050's two predecessors drives it"

    cx040 = by_code["CX-040"]
    assert sum(1 for p in cx040["predecessors"] if p["driving"]) == 1


def test_single_predecessor_drives_unless_progress_is_out_of_sequence(schedule, by_code):
    """A lone predecessor drives its successor — except where the successor was
    progressed before that predecessor finished. Then the successor's early start
    precedes the date the link implies, no relationship explains its dates, and
    nothing is marked driving.

    ST-010 is the sample's deliberate out-of-sequence case (started 23 Feb while
    its FS predecessor EW-030 is still in progress). Pinned here because it is a
    real limitation, not an accident: the chain trace dead-ends on such an
    activity, and any change to that behaviour is a scheduling-semantics
    decision that should be made deliberately.
    """
    out_of_sequence = {"ST-010"}
    for a in schedule.activities:
        if len(a["predecessors"]) != 1:
            continue
        p = a["predecessors"][0]
        if a["task_code"] in out_of_sequence:
            assert p["driving"] is False
        else:
            assert p["driving"] is True, f"{a['task_code']} sole predecessor not driving"

    st010 = by_code["ST-010"]
    assert st010["status"] == "TK_Active"
    assert st010["act_start"] is not None
    assert not any(p["driving"] for p in st010["predecessors"])


def test_out_of_sequence_is_the_only_case_without_a_driving_predecessor(schedule):
    """Every activity with predecessors should have at least one driving link;
    a growing list here means the driving rule is losing chains."""
    dead_ends = sorted(a["task_code"] for a in schedule.activities
                       if a["predecessors"] and not any(p["driving"] for p in a["predecessors"]))
    assert dead_ends == ["ST-010"]


def test_successor_driving_flags_mirror_predecessor_flags(schedule, by_code):
    """The same relationship must report the same driving flag from both ends,
    or the two detail drawers contradict each other."""
    by_id = {a["task_id"]: a for a in schedule.activities}
    checked = 0
    for a in schedule.activities:
        for s in a["successors"]:
            succ = by_id[s["task_id"]]
            match = [p for p in succ["predecessors"]
                     if p["task_id"] == a["task_id"]
                     and p["type"] == s["type"]
                     and p["lag_hrs"] == s["lag_hrs"]]
            assert match, f"successor {s} of {a['task_code']} has no mirror"
            assert match[0]["driving"] == s["driving"]
            checked += 1
    assert checked > 0


def test_relationships_are_symmetric(schedule):
    """Every predecessor entry has a matching successor entry and vice versa."""
    preds = {(a["task_id"], p["task_id"], p["type"]) for a in schedule.activities
             for p in a["predecessors"]}
    succs = {(s["task_id"], a["task_id"], s["type"]) for a in schedule.activities
             for s in a["successors"]}
    assert preds == succs


# ── Display-date convention ──────────────────────────────────────────────────

def test_completed_activity_keeps_actual_dates(by_code):
    """P6 resets the early dates of completed work to the data date. MS-010 is
    complete, so its actual dates must survive parsing — the frontend's
    displayStart/displayEnd prefer them, and without this a finished activity
    renders as a zero-width bar sitting on the data date."""
    ms010 = by_code["MS-010"]
    assert ms010["status"] == "TK_Complete"
    assert ms010["act_start"] is not None and ms010["act_end"] is not None
    assert ms010["act_start"].startswith("2026-01-21")
    # the early dates really have been collapsed onto the data date
    assert ms010["early_start"][:10] == "2026-03-02"


def test_project_range_uses_display_dates(schedule, by_code):
    """Project start must come from actual dates where present, otherwise the
    Gantt range would begin at the data date and hide all completed work."""
    ms010 = by_code["MS-010"]
    assert schedule.project.earliest_start[:10] <= ms010["act_start"][:10]
    assert schedule.project.earliest_start[:10] == "2026-01-21"


# ── Units and per-activity fields ────────────────────────────────────────────

def test_calendar_hours_per_day_present_for_float_conversion(schedule):
    """Float is displayed in days; without hrs/day the frontend would silently
    fall back to 8 and misreport any non-standard calendar."""
    for a in schedule.activities:
        assert a["calendar_hrs_per_day"] > 0, a["task_code"]
    assert {a["calendar_hrs_per_day"] for a in schedule.activities} == {8.0}


def test_every_activity_carries_the_fields_the_ui_requires(schedule):
    required = {"task_id", "task_code", "task_name", "wbs_path", "status",
                "total_float_hrs", "duration_hrs", "remain_duration_hrs",
                "predecessors", "successors", "is_critical", "is_longest_path",
                "clndr_id", "calendar", "calendar_hrs_per_day", "activity_codes",
                "resource_names", "task_type", "pct_complete"}
    for a in schedule.activities:
        assert required <= set(a), f"{a['task_code']} missing {required - set(a)}"


def test_milestones_have_zero_duration(schedule):
    for a in schedule.activities:
        if "Mile" in a["task_type"]:
            assert a["duration_hrs"] == 0, a["task_code"]


# ── WBS tree ─────────────────────────────────────────────────────────────────

def test_wbs_tree_is_well_formed(schedule):
    seen = []

    def walk(nodes, level):
        for n in nodes:
            assert n["level"] == level, f"{n['wbs_name']} level {n['level']} != {level}"
            seen.append(n["wbs_id"])
            walk(n["children"], level + 1)

    walk(schedule.wbs_tree, 0)
    assert len(seen) == len(set(seen)), "a WBS node appears twice in the tree"
    assert len(seen) == schedule.project.total_wbs


def test_every_activity_maps_into_the_wbs_tree(schedule):
    ids = set()

    def walk(nodes):
        for n in nodes:
            ids.add(n["wbs_id"])
            walk(n["children"])

    walk(schedule.wbs_tree)
    for a in schedule.activities:
        assert a["wbs_id"] in ids, f"{a['task_code']} is orphaned from the WBS tree"


# ── Numeric helpers ──────────────────────────────────────────────────────────

def test_safe_float_treats_zero_as_a_value_not_a_default():
    assert safe_float(0.0) == 0.0
    assert safe_float(None) == 0.0
    assert safe_float(None, 7.5) == 7.5
    assert safe_float("3.5") == 3.5


def test_safe_float_or_preserves_zero_float():
    """A zero total float means critical; collapsing it to the 999 default would
    silently drop activities off the critical path."""
    assert safe_float_or(0.0) == 0.0
    assert safe_float_or(None) == 999.0
    assert safe_float_or(-8.0) == -8.0
