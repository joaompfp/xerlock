// Complete, typed test records. Tests state only the fields their rule depends on; every
// other field takes a neutral default, so a schema change surfaces here once instead of
// as a partial object in every test.

import type { Activity, ProjectSummary, ScheduleCore, WbsNode } from '../types/schedule'

let nextId = 1

export function makeActivity(over: Partial<Activity> = {}): Activity {
  const id = nextId++
  return {
    task_id: id, task_code: 'A' + id, task_name: 'Activity ' + id, wbs_id: 1, wbs_path: '',
    status: 'TK_NotStart', pct_complete: 0, pct_complete_type: 'CP_Phys',
    early_start: '2026-03-02 08:00:00', early_end: '2026-03-13 16:00:00', late_start: null, late_end: null,
    total_float_hrs: 0, free_float_hrs: 0, duration_hrs: 80, remain_duration_hrs: 80,
    task_type: 'TT_Task', clndr_id: '1', calendar: 'Standard', calendar_hrs_per_day: 8,
    predecessors: [], successors: [],
    is_critical: false, is_longest_path: false, is_negative_float: false, driving_path_flag: false,
    cstr_type: null, cstr_date: null, cstr_type2: null, cstr_date2: null,
    act_start: null, act_end: null, target_start: null, target_end: null,
    activity_codes: [], resource_names: [],
    ...over,
  }
}

export function makeProject(over: Partial<ProjectSummary> = {}): ProjectSummary {
  return {
    proj_short_name: 'TEST', total_activities: 0, total_wbs: 0, total_critical: 0,
    total_longest_path: 0, total_negative_float: 0, total_milestones: 0, total_complete: 0,
    total_active: 0, total_not_started: 0, pct_complete: 0, earliest_start: null, latest_end: null,
    data_date: '2026-03-02 08:00', has_resources: false, has_activity_codes: false,
    activity_code_types: [], cpli: null, source_format: 'xer',
    ...over,
  }
}

/** Link pred -> succ in both directions, as the backend does. */
export function link(pred: Activity, succ: Activity, type = 'PR_FS', lag = 0): void {
  succ.predecessors.push({ task_id: pred.task_id, type, lag_hrs: lag, driving: false })
  pred.successors.push({ task_id: succ.task_id, type, lag_hrs: lag, driving: false })
}

export function makeSchedule(activities: Activity[], project: Partial<ProjectSummary> = {}): ScheduleCore {
  return { activities, project: makeProject(project) }
}

export function makeWbsNode(wbs_id: number, children: WbsNode[] = []): WbsNode {
  return {
    wbs_id, wbs_short_name: 'W' + wbs_id, wbs_name: 'WBS ' + wbs_id, parent_wbs_id: null,
    seq_num: 0, level: 0, children, activity_count: 0,
  }
}
