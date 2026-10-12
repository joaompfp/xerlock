// The shape of POST /api/upload's response (backend/main.py: parse_xer), the one contract
// between parser and UI. Dates are P6 timestamps as strings ("YYYY-MM-DD HH:MM[:SS]");
// durations, float and lags are hours. tests/test_fixture.py keeps a parsed sample in
// utils/fixtures/, and healthChecks.test.ts types it as Schedule, so the backend and
// these declarations cannot drift apart unnoticed.
//
// Fields marked optional were added after the first release. Snapshots saved in users'
// browsers (utils/snapshots.ts) may predate them, so every reader must cope without them.

export type P6Date = string

export type RelType = 'PR_FS' | 'PR_SS' | 'PR_FF' | 'PR_SF'
export type TaskType = 'TT_Task' | 'TT_Rsrc' | 'TT_Mile' | 'TT_StartMile' | 'TT_FinMile' | 'TT_LOE' | 'TT_WBS'
export type TaskStatus = 'TK_NotStart' | 'TK_Active' | 'TK_Complete'
export type PctCompleteType = 'CP_Phys' | 'CP_Drtn' | 'CP_Units'

/** One end of a relationship, as seen from the activity holding the list. */
export interface Relationship {
  task_id: number
  /** Raw P6 code; normally a RelType, kept open for unknown values in odd exports. */
  type: RelType | string
  lag_hrs: number
  /** Relationship free float in working hours; driving when it is zero. */
  free_float_hrs?: number | null
  driving: boolean
}

export interface ActivityCode {
  type: string
  code: string
}

export interface Activity {
  task_id: number
  task_code: string
  task_name: string
  wbs_id: number
  wbs_path: string
  status: TaskStatus | string
  pct_complete: number
  pct_complete_type?: PctCompleteType | string
  early_start: P6Date | null
  early_end: P6Date | null
  late_start: P6Date | null
  late_end: P6Date | null
  /** null when P6 computed none (typically completed work) — never read as zero. */
  total_float_hrs: number | null
  free_float_hrs: number
  duration_hrs: number
  remain_duration_hrs: number
  task_type: TaskType | string
  clndr_id: string
  calendar: string | null
  calendar_hrs_per_day: number
  predecessors: Relationship[]
  successors: Relationship[]
  is_critical: boolean
  is_longest_path: boolean
  is_negative_float: boolean
  driving_path_flag: boolean
  cstr_type: string | null
  cstr_date: P6Date | null
  cstr_type2: string | null
  cstr_date2: P6Date | null
  act_start: P6Date | null
  act_end: P6Date | null
  target_start: P6Date | null
  target_end: P6Date | null
  activity_codes: ActivityCode[]
  resource_names: string[]
}

export interface ScheduleOptions {
  present: boolean
  retained_logic: boolean | null
  progress_override: boolean | null
  float_type: string
  lag_calendar: string
  open_ends_critical: boolean | null
  use_expected_finish: boolean | null
  float_to_project_finish: boolean | null
  external_relationships: string
  critical_type: string
  critical_float_hrs: number
}

export interface Cpli {
  value: number
  cpl_hrs: number
  tf_hrs: number
  finish_task_id: number
}

/** One field on one activity where the recalculation and P6's stored value differ. */
export interface RecalcDifference {
  task_id: number
  /** es, ef, ls, lf (dates) or tf, ff (hours). */
  field: string
  computed: string | number | null
  stored: string | number | null
  /** computed minus stored, in clock hours for dates and working hours for float. */
  delta_hrs: number | null
}

/** The CPM engine's reproduction of P6's dates and float (backend/recalc.py). */
export interface Recalculation {
  /** False when the engine refuses the file; `reason` says why. */
  supported: boolean
  reason: string | null
  options: { progress_mode: string; float_type: string; lag_calendar: string; delay_days: number }
  compared: number
  excluded: { complete: number; wbs_summary: number }
  differing: number
  by_field: Record<string, number>
  differences: RecalcDifference[]
  truncated: boolean
}

/** DCMA 12, reported only when the recalculation reproduces P6 exactly. */
export interface CriticalPathTest {
  passed: boolean
  /** The finish moved by the delay to the minute. */
  exact: boolean
  delay_days: number
  delay_hrs: number
  tolerance_hrs: number
  /** Every activity from the delayed one to the finish shares its calendar. */
  calendars_uniform: boolean
  delayed_task_id: number
  finish_task_id: number
  finish_before: P6Date
  finish_after: P6Date
  expected_delta_hrs: number
  /** Movement of the finish, in working hours on the delayed activity's calendar. */
  finish_delta_hrs: number
  absorbed_by_task_id: number | null
}

export interface ProjectSummary {
  proj_short_name: string
  total_activities: number
  total_wbs: number
  total_critical: number
  total_longest_path: number
  total_negative_float: number
  total_milestones: number
  total_complete: number
  total_active: number
  total_not_started: number
  /** Share of activities with status Complete — a count, not weighted progress. */
  pct_complete: number
  earliest_start: P6Date | null
  latest_end: P6Date | null
  data_date: P6Date | null
  has_resources: boolean
  has_activity_codes: boolean
  activity_code_types: string[]
  schedule_options?: ScheduleOptions | Record<string, never>
  cpli?: Cpli | null
  recalculation?: Recalculation | null
  critical_path_test?: CriticalPathTest | null
}

export interface WbsNode {
  wbs_id: number
  wbs_short_name: string
  wbs_name: string
  parent_wbs_id: number | null
  seq_num: number
  level: number
  children: WbsNode[]
  activity_count: number
}

export interface WorkPeriod {
  start: string
  finish: string
}

export interface CalendarInfo {
  clndr_id: string
  clndr_name: string
  clndr_type: string
  default_flag: boolean
  day_hr_cnt: number
  week_hr_cnt: number
  assigned_count: number
  /** P6 weekday "1".."7" = Sunday..Saturday. */
  weekdays: Record<string, WorkPeriod[]>
  exceptions: { date: string; periods: WorkPeriod[] }[]
}

export interface RawTable {
  fields: string[]
  rows: string[][]
  row_count: number
  truncated: boolean
}

export interface Schedule {
  project: ProjectSummary
  wbs_tree: WbsNode[]
  activities: Activity[]
  warnings: string[]
  calendars: CalendarInfo[]
  raw_tables: Record<string, RawTable>
  ermhdr: { version?: string; export_date?: string; fields?: string[] }
}

/** What the analysis utilities need: the activities and the project summary. */
export type ScheduleCore = Pick<Schedule, 'project' | 'activities'>
