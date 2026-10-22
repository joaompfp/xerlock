// The shape of POST /api/upload's response (backend/main.py: parse_schedule), the one
// contract between parser and UI. The vocabulary is P6's: a Microsoft Project file is
// mapped into it by backend/mspdi.py (docs/METHODOLOGY.md, "Microsoft Project files").
// Dates are timestamps as strings ("YYYY-MM-DD HH:MM[:SS]"); durations, float and lags
// are hours. tests/test_fixture.py and tests/test_mspdi.py keep parsed samples in
// utils/fixtures/, and healthChecks.test.ts types them as Schedule, so the backend and
// these declarations cannot drift apart unnoticed.
//
// Fields marked optional were added after the first release. Snapshots saved in users'
// browsers (utils/snapshots.ts) may predate them, so every reader must cope without them.

export type P6Date = string

/** Which tool wrote the file. Absent on snapshots saved before 1.2.0, which are all .xer. */
export type SourceFormat = 'xer' | 'mspdi' | 'mpp'

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
  /** Microsoft Project only: the lag counts on the 24-hour clock (e.g. "2ed"). */
  lag_elapsed?: boolean
  /** Microsoft Project only: a percentage lag; lag_hrs is that share of the predecessor's duration. */
  lag_pct?: number | null
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
  /** Microsoft Project only: manually scheduled (Task Mode), so logic does not place it. */
  manual?: boolean
  /** Microsoft Project only: a deadline, which bounds the late finish without being a constraint. */
  deadline?: P6Date | null
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

/** One field on one activity where the recalculation and the file's stored value differ. */
export interface RecalcDifference {
  task_id: number
  /** es, ef, ls, lf (dates) or tf, ff (hours). */
  field: string
  computed: string | number | null
  stored: string | number | null
  /** computed minus stored, in clock hours for dates and working hours for float. */
  delta_hrs: number | null
}

/**
 * The CPM engine's reproduction of the file's dates and float: P6's rules
 * (backend/recalc.py) or Microsoft Project's (backend/recalc_msp.py).
 */
export interface Recalculation {
  /** False when the engine refuses the file; `reason` says why. */
  supported: boolean
  reason: string | null
  /** P6: progress_mode, float_type, lag_calendar. Project: schedule_from, lag_calendar,
   *  critical_slack_limit_days, multiple_critical_paths. Both: delay_days. */
  options: {
    progress_mode?: string; float_type?: string; lag_calendar: string; delay_days: number
    schedule_from?: string; critical_slack_limit_days?: number; multiple_critical_paths?: boolean
  }
  compared: number
  excluded: { complete: number; wbs_summary: number }
  differing: number
  by_field: Record<string, number>
  differences: RecalcDifference[]
  truncated: boolean
  /** Project files only: rules the file rests on that the oracle corpus has not
   *  validated (named for the reviewer). The CPT is withheld while any is present. */
  uncovered?: string[]
}

/** DCMA 12, reported only when the recalculation reproduces the file exactly. */
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

/** Microsoft Project only: a relationship with a summary task at one or both ends. */
export interface SummaryLink {
  pred_id: number
  pred_name: string
  pred_is_summary: boolean
  succ_id: number
  succ_name: string
  succ_is_summary: boolean
  type: RelType | string
  lag_hrs: number
  lag_elapsed?: boolean
  lag_pct?: number | null
}

/** Microsoft Project only: the file's own scheduling settings, as stored. */
export interface MspOptions {
  schedule_from_start: boolean | null
  honor_constraints: boolean | null
  minutes_per_day: number
  critical_slack_limit_days: number
  multiple_critical_paths: boolean | null
  new_tasks_manual: boolean | null
  splits_in_progress_tasks: boolean | null
  status_date: P6Date | null
  current_date: P6Date | null
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
  /** Normally a SourceFormat; kept open as JSON fixtures and snapshots widen it to string. */
  source_format?: SourceFormat | string
  /** .xer only: this project's id, and every project in the file (an embedded baseline
   *  is often one), so another can be opened from the same file. */
  proj_id?: number | null
  projects_in_file?: ProjectInFile[] | null
  /** Microsoft Project only: inactive tasks, left out of every population. */
  inactive_activities?: number | null
  summary_links?: SummaryLink[] | null
  msp_options?: MspOptions | null
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

/** One project of a multi-project .xer. */
export interface ProjectInFile {
  proj_id: number
  proj_short_name: string
  activities: number
}
