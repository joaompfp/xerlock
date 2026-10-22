"""
What every schedule format shares once a reader has read the file: driving relationships
(working-time free float), the Longest Path, the CPLI, the critical flag, the WBS tree
with its roll-ups, the summary counts and the recalculation call.

A reader (backend/xer.py) turns its file into the neutral intermediate described under
`build`; this module turns the intermediate into the structure the API serves
(main.ScheduleData, frontend/src/types/schedule.ts). Pure Python with no web framework,
so it runs on the server and, under Pyodide, in the browser.
"""

from datetime import datetime

from backend.cpm import lag_calendar
from backend.worktime import ALL_HOURS, WorkCalendar

# Per-table row cap for the raw inspector. Far above any real single-project export
# (TASKPRED on a 10k-activity file is ~30k rows, which still fits) but bounds the JSON
# payload; the frontend surfaces `truncated` explicitly so nothing is silently dropped.
RAW_TABLE_ROW_CAP = 50_000

# A relationship drives its successor when its free float is zero. Dates in a .xer are
# minute-resolution, so anything within a minute either side is zero.
DRIVING_TOLERANCE_HRS = 1 / 60

# Contract fields a reader may add beyond the P6 set (frontend/src/types/schedule.ts
# marks them optional). They are emitted only when the reader supplies them, so a P6
# file's output does not change.
OPTIONAL_PROJECT_FIELDS = ("source_format", "inactive_activities", "summary_links", "msp_options", "proj_id", "projects_in_file")
OPTIONAL_ACTIVITY_FIELDS = ("manual", "deadline")
OPTIONAL_LINK_FIELDS = ("lag_elapsed", "lag_pct")


def parse_datetime(val):
    """Dates arrive as datetime objects or 'YYYY-MM-DD HH:MM[:SS]' strings."""
    if val is None or isinstance(val, datetime):
        return val
    try:
        return datetime.fromisoformat(str(val).strip())
    except ValueError:
        return None


def _date_str(v):
    return str(v) if v else None


def build_calendars(calendars: list, activities: list):
    """Calendar register: each calendar with how many activities use it."""
    assigned = {}
    for a in activities:
        assigned[a["clndr_id"]] = assigned.get(a["clndr_id"], 0) + 1
    out = [{**c, "assigned_count": assigned.get(c["clndr_id"], 0)} for c in calendars]
    # Most-used first; unused resource calendars sink to the bottom.
    out.sort(key=lambda c: -c["assigned_count"])
    return out


def build_wbs(nodes: list):
    """The WBS tree from flat nodes ({wbs_id, wbs_short_name, wbs_name, parent_wbs_id,
    seq_num}, in file order): each node gains level, children and activity_count.
    Returns (wbs_dict, root_ids, wbs_path_for)."""
    wbs_dict = {}
    for n in nodes:
        wbs_dict[n["wbs_id"]] = {
            "wbs_id": n["wbs_id"],
            "wbs_short_name": n["wbs_short_name"],
            "wbs_name": n["wbs_name"],
            "parent_wbs_id": n["parent_wbs_id"],
            "seq_num": n["seq_num"],
            "level": 0,
            "children": [],
            "activity_count": 0,
        }

    root_ids = []
    for wid, w in wbs_dict.items():
        parent = w["parent_wbs_id"]
        # None means a root; 0 is a real id in Project files (the project summary task).
        if parent is not None and int(parent) in wbs_dict:
            wbs_dict[int(parent)]["children"].append(wid)
        else:
            root_ids.append(wid)

    def assign_level(wid, level):
        wbs_dict[wid]["level"] = level
        for child in wbs_dict[wid]["children"]:
            assign_level(child, level + 1)

    for rid in root_ids:
        assign_level(rid, 0)

    # WBS breadcrumb per node (e.g. "MAIN WORKS / Level 01 / Electrical"), memoized
    # since many activities share the same WBS chain.
    wbs_path_cache = {}

    def wbs_path_for(wid):
        if wid is None or wid not in wbs_dict:
            return ""
        if wid in wbs_path_cache:
            return wbs_path_cache[wid]
        node = wbs_dict[wid]
        if node["level"] == 0:
            # The root WBS node is the project itself, already shown in the page header —
            # omit it so breadcrumbs start from the first real WBS level.
            path = ""
        else:
            parent_path = wbs_path_for(node["parent_wbs_id"])
            path = f"{parent_path} / {node['wbs_name']}" if parent_path else node["wbs_name"]
        wbs_path_cache[wid] = path
        return path

    return wbs_dict, root_ids, wbs_path_for


def build(parsed: dict) -> dict:
    """The schedule structure the API serves, from a reader's intermediate:

    project         proj_short_name, data_date (display string or None), schedule_options
    activities      one dict per activity, in file order: task_id, task_code, task_name,
                    wbs_id, status, pct_complete, pct_complete_type, early_start,
                    early_end, late_start, late_end (datetimes or None), total_float_hrs
                    (float or None), free_float_hrs, duration_hrs, remain_duration_hrs,
                    task_type, clndr_id (str), calendar, calendar_hrs_per_day,
                    driving_path_flag (bool), cstr_type, cstr_date, cstr_type2,
                    cstr_date2, act_start, act_end, target_start, target_end,
                    activity_codes, resource_names
    links           {pred_id, succ_id, type, lag_hrs} in file order, both ends activities
    wbs             flat nodes in file order (see build_wbs)
    calendars       decoded calendars (clndr_id, default_flag, day_hr_cnt, weekdays,
                    exceptions, ...)
    has_resources, activity_code_types, warnings, raw_tables, ermhdr
    recalculate     callable(work_cals, default_cal, longest_path_ids, hrs_per_day)
                    -> (recalculation report, critical path test or None)
    """
    project = parsed["project"]
    activities_in = parsed["activities"]
    calendars = parsed["calendars"]
    sched_options = project["schedule_options"]
    warnings = list(parsed["warnings"])

    wbs_dict, root_ids, wbs_path_for = build_wbs(parsed["wbs"])

    # Build predecessor/successor maps. succ_map is derived from pred_map in a
    # separate pass so the result is independent of iteration order.
    own_ids = {a["task_id"] for a in activities_in}
    pred_map = {tid: [] for tid in own_ids}
    succ_map = {tid: [] for tid in own_ids}
    for l in parsed["links"]:
        pred_map[l["succ_id"]].append({
            "task_id": l["pred_id"],
            "type": l["type"],
            "lag_hrs": l["lag_hrs"],
            **{k: l[k] for k in OPTIONAL_LINK_FIELDS if k in l},
        })
    for tid, preds in pred_map.items():
        for p in preds:
            succ_map.setdefault(p["task_id"], []).append({
                "task_id": tid,
                "type": p["type"],
                "lag_hrs": p["lag_hrs"],
                **{k: p[k] for k in OPTIONAL_LINK_FIELDS if k in p},
            })

    # Driving relationships, the way P6 defines them: a link drives its successor when
    # its *relationship free float* is zero — the successor's date sits exactly where
    # the link (plus its lag) puts it, measured in working time. Measured in clock time
    # instead, an ordinary Friday-to-Monday FS link shows a 64-hour "gap", nothing is
    # ever exactly driving, and picking the closest predecessor marks links driving
    # that P6 does not (an activity held by a constraint or by the data date has no
    # driving predecessor at all, and the trace must stop there).
    #   lag:  applied on the calendar the project's scheduling options name (an
    #         elapsed lag, a Project concept, counts on the 24-hour calendar);
    #   gap:  measured on the successor's calendar, since the successor is placed at
    #         the first working moment on its own calendar after the link allows.
    act_lookup = {a["task_id"]: a for a in activities_in}
    work_cals = {c["clndr_id"]: WorkCalendar(c["weekdays"], c["exceptions"]) for c in calendars}
    default_cal = next((work_cals[c["clndr_id"]] for c in calendars if c["default_flag"]), None)

    def cal_of(a):
        return work_cals.get(a["clndr_id"]) or default_cal or ALL_HOURS

    lag_basis = sched_options.get("lag_calendar", "rcal_Predecessor")

    def lag_cal(pred_a, succ_a, elapsed=False):
        if elapsed:
            return ALL_HOURS
        return lag_calendar(lag_basis, cal_of(pred_a), cal_of(succ_a), default_cal)

    def relationship_free_float_hrs(succ_a, pred_a, link):
        """Working hours between where the link puts the successor and where it is.
        None when either date is missing or the link type is unknown."""
        ends = {
            "PR_FS": (pred_a["early_end"], succ_a["early_start"]),
            "PR_SS": (pred_a["early_start"], succ_a["early_start"]),
            "PR_FF": (pred_a["early_end"], succ_a["early_end"]),
            "PR_SF": (pred_a["early_start"], succ_a["early_end"]),
        }.get(link["type"])
        if not ends or None in ends:
            return None
        implied = lag_cal(pred_a, succ_a, link.get("lag_elapsed", False)).add_working_hours(ends[0], link["lag_hrs"])
        return cal_of(succ_a).working_hours_between(implied, ends[1])

    for a in activities_in:
        for p in pred_map.get(a["task_id"], []):
            pred_a = act_lookup.get(p["task_id"])
            rff = relationship_free_float_hrs(a, pred_a, p) if pred_a else None
            p["free_float_hrs"] = None if rff is None else round(rff, 2)
            p["driving"] = rff is not None and abs(rff) <= DRIVING_TOLERANCE_HRS
    # Mirror onto the successor lists so both directions of the panel carry the flag.
    for tid, succs in succ_map.items():
        for s in succs:
            s["driving"] = False
            s["free_float_hrs"] = None
            for p in pred_map.get(s["task_id"], []):
                if p["task_id"] == tid and p["type"] == s["type"] and p["lag_hrs"] == s["lag_hrs"]:
                    s["driving"] = p["driving"]
                    s["free_float_hrs"] = p["free_float_hrs"]
                    break

    # Longest Path (P6's alternate critical definition, AACE 49R-06's preferred one):
    # from the activity finishing last, walk backward through driving links only. The
    # chain ends where no link drives — at the project start, or at an activity held
    # by a constraint or the data date. Computed independently of any stored flag
    # (driving_path_flag) so the two can be cross-checked: a disagreement means either
    # this trace is wrong or the schedule was not recalculated after its last edit.
    finish_activity = max(
        (a for a in activities_in if not succ_map.get(a["task_id"]) and a["early_end"]),
        key=lambda a: a["early_end"],
        default=None,
    )
    longest_path_ids = set()
    if finish_activity:
        finish_end = finish_activity["early_end"]
        stack = [a["task_id"] for a in activities_in
                 if not succ_map.get(a["task_id"]) and a["early_end"] == finish_end]
        while stack:
            tid = stack.pop()
            if tid in longest_path_ids:
                continue
            longest_path_ids.add(tid)
            stack.extend(p["task_id"] for p in pred_map.get(tid, []) if p["driving"])

    # Critical Path Length Index (DCMA check 13): (CPL + TF) / CPL, where CPL is the
    # working time from the data date to the project finish and TF the finish's total
    # float. Below 0.95 the remaining path must be compressed to make the date.
    cpli = None
    data_date = parse_datetime(project["data_date"])
    if finish_activity and data_date and finish_activity["total_float_hrs"] is not None:
        cpl_hrs = cal_of(finish_activity).working_hours_between(data_date, finish_activity["early_end"])
        if cpl_hrs > 0:
            tf_hrs = float(finish_activity["total_float_hrs"])
            cpli = {
                "value": round((cpl_hrs + tf_hrs) / cpl_hrs, 3),
                "cpl_hrs": round(cpl_hrs, 1),
                "tf_hrs": tf_hrs,
                "finish_task_id": finish_activity["task_id"],
            }

    # Critical, as this project defines it (critical_type): either total float at or
    # below the project's own threshold (critical_float_hrs — P6's default is 0, but
    # contracts often set it higher), or the stored Longest Path flag. A reader that
    # has the file's own stored critical flag (Project's Critical) supplies it as
    # `critical`, and that is used as it is.
    crit_threshold = sched_options["critical_float_hrs"]
    flags_present = any(a["driving_path_flag"] for a in activities_in)

    def critical(a, tf):
        if "critical" in a:
            return a["critical"]
        if sched_options["critical_type"] == "CT_DrivPath":
            return a["driving_path_flag"] if flags_present else a["task_id"] in longest_path_ids
        return tf is not None and tf <= crit_threshold

    # Recalculate the schedule from its own logic and compare with what the file
    # stored; the Critical Path Test runs only when the two agree (docs/METHODOLOGY.md).
    recalculation, critical_path_test = parsed["recalculate"](
        work_cals, default_cal, sorted(longest_path_ids),
        {c["clndr_id"]: c["day_hr_cnt"] for c in calendars},
    )

    activities = []
    wbs_act_count = {}
    for a in activities_in:
        wbs_act_count[a["wbs_id"]] = wbs_act_count.get(a["wbs_id"], 0) + 1
        tf = a["total_float_hrs"]
        activities.append({
            "task_id": a["task_id"],
            "task_code": a["task_code"],
            "task_name": a["task_name"],
            "wbs_id": a["wbs_id"],
            "wbs_path": wbs_path_for(a["wbs_id"]),
            "status": a["status"],
            "pct_complete": a["pct_complete"],
            "pct_complete_type": a["pct_complete_type"],
            "early_start": _date_str(a["early_start"]),
            "early_end": _date_str(a["early_end"]),
            "late_start": _date_str(a["late_start"]),
            "late_end": _date_str(a["late_end"]),
            "total_float_hrs": tf,
            "free_float_hrs": a["free_float_hrs"],
            "duration_hrs": a["duration_hrs"],
            "remain_duration_hrs": a["remain_duration_hrs"],
            "task_type": a["task_type"],
            "clndr_id": a["clndr_id"],
            "calendar": a["calendar"],
            "calendar_hrs_per_day": a["calendar_hrs_per_day"],
            "predecessors": pred_map.get(a["task_id"], []),
            "successors": succ_map.get(a["task_id"], []),
            # Negative float is critical too (it is below any threshold);
            # is_negative_float lets the frontend give it a visually distinct treatment.
            "is_critical": critical(a, tf),
            "is_longest_path": a["task_id"] in longest_path_ids,
            "is_negative_float": tf is not None and tf < 0,
            "driving_path_flag": a["driving_path_flag"],
            "cstr_type": a["cstr_type"],
            "cstr_date": _date_str(a["cstr_date"]),
            "cstr_type2": a["cstr_type2"],
            "cstr_date2": _date_str(a["cstr_date2"]),
            "act_start": _date_str(a["act_start"]),
            "act_end": _date_str(a["act_end"]),
            "target_start": _date_str(a["target_start"]),
            "target_end": _date_str(a["target_end"]),
            "activity_codes": a["activity_codes"],
            "resource_names": a["resource_names"],
            **{k: (_date_str(a[k]) if isinstance(a[k], datetime) else a[k])
               for k in OPTIONAL_ACTIVITY_FIELDS if k in a},
        })

    for wid in wbs_act_count:
        if wid in wbs_dict:
            wbs_dict[wid]["activity_count"] = wbs_act_count[wid]

    def build_tree(wid):
        node = wbs_dict[wid].copy()
        node["children"] = [build_tree(c) for c in wbs_dict[wid]["children"]]
        return node

    wbs_tree = [build_tree(rid) for rid in root_ids]

    # Stats
    total = len(activities)
    n_critical = sum(1 for a in activities if a["is_critical"])
    longest_path = sum(1 for a in activities if a["is_longest_path"])
    negative_float = sum(1 for a in activities if a["is_negative_float"])
    milestones = sum(1 for a in activities if a["task_type"] in ("TT_Mile", "TT_FinMile", "TT_StartMile"))
    complete = sum(1 for a in activities if a["status"] == "TK_Complete")
    active = sum(1 for a in activities if a["status"] == "TK_Active")
    not_started = sum(1 for a in activities if a["status"] == "TK_NotStart")
    pct = (complete / total * 100) if total > 0 else 0

    # Project range uses the display-date convention (actual once started/finished,
    # early otherwise): completed work's early dates are reset to the data date by P6,
    # so an early-dates-only range would exclude everything already built.
    starts = [(a["act_start"] or a["early_start"]) for a in activities]
    ends = [(a["act_end"] or a["early_end"]) for a in activities]
    earliest = min((d for d in starts if d), default=None)
    latest = max((d for d in ends if d), default=None)

    activity_code_types = parsed["activity_code_types"]

    return dict(
        project=dict(
            proj_short_name=project["proj_short_name"],
            total_activities=total,
            total_wbs=len(wbs_dict),
            total_critical=n_critical,
            total_longest_path=longest_path,
            total_negative_float=negative_float,
            total_milestones=milestones,
            total_complete=complete,
            total_active=active,
            total_not_started=not_started,
            pct_complete=round(pct, 1),
            earliest_start=earliest,
            latest_end=latest,
            data_date=project["data_date"],
            has_resources=parsed["has_resources"],
            has_activity_codes=len(activity_code_types) > 0,
            activity_code_types=activity_code_types,
            schedule_options=sched_options,
            cpli=cpli,
            recalculation=recalculation,
            critical_path_test=critical_path_test,
            **{k: project[k] for k in OPTIONAL_PROJECT_FIELDS if k in project},
        ),
        wbs_tree=wbs_tree,
        activities=activities,
        warnings=warnings,
        calendars=build_calendars(calendars, activities),
        raw_tables=parsed["raw_tables"],
        ermhdr=parsed["ermhdr"],
    )
