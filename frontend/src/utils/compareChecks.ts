// Forensic comparisons between two submissions of the same programme, over activities
// matched by code. Pure, so each rule is testable on its own.

import type { Activity, Schedule } from '../types/schedule'
import { displayEnd } from './p6'

const DAY_MS = 86400000

export interface MatchedPair {
  code: string
  cur: Activity
  base: Activity
}

export interface ActualChange {
  label: string
  was: string
  now: string | null
}

// Actual dates are history: once reported they should not move in a later update. A
// changed or withdrawn actual is either a correction that deserves a note or a
// rewrite of the record (AACE 29R-03 treats as-built data validation as a precondition
// of any delay analysis).
export function actualDateChanges(matched: MatchedPair[]): (MatchedPair & { changes: ActualChange[] })[] {
  const out: (MatchedPair & { changes: ActualChange[] })[] = []
  for (const d of matched) {
    const changes: ActualChange[] = []
    const fields = [['act_start', 'Actual start'], ['act_end', 'Actual finish']] as const
    for (const [field, label] of fields) {
      const was = d.base[field]
      const now = d.cur[field]
      if (was && was !== now) changes.push({ label, was, now: now || null })
    }
    if (changes.length) out.push({ ...d, changes })
  }
  return out
}

// A constraint added, removed, or moved between submissions changes what drives the
// dates without any change to the logic, so it does not show up as a logic change.
export function constraintChanges(matched: MatchedPair[]): MatchedPair[] {
  const key = (a: Activity) => [a.cstr_type || '', a.cstr_date || '', a.cstr_type2 || '', a.cstr_date2 || ''].join('|')
  return matched.filter(d => key(d.cur) !== key(d.base))
}

// Slippage: how far an activity's finish moved from one submission to the other, in
// calendar days, rounded (positive = later, a slip; negative = earlier, a gain). The
// finish is the displayed one, so a completed activity is measured on its actual finish.
// null when either side has no finish.
export function finishSlipDays(cur: Activity, base: Activity): number | null {
  const c = displayEnd(cur)
  const b = displayEnd(base)
  if (!c || !b) return null
  return dateSlipDays(c, b)
}

// The movement from one date to another in whole calendar days, rounded: the unit every
// slip in Compare and on the Gantt is given in.
export function dateSlipDays(cur: string | Date, base: string | Date): number {
  return Math.round((new Date(cur).getTime() - new Date(base).getTime()) / DAY_MS)
}


export interface FinishVerdict { cls: 'v-slip' | 'v-gain' | 'v-hold'; chips: string[] }

/** How the Compare banner reads a finish move. A later finish is a slip. An earlier one
 *  is shown as a gain only when the logic that drove the finish largely survived: with
 *  a new finish driver, or under half the earlier longest path kept, the programme was
 *  re-sequenced and the move is a re-plan, so the banner stays neutral and says why.
 *  Without a data-date advance, any move is re-planning rather than progress. */
export function finishVerdict(
  finishDelta: number,
  stability: { pct: number; baseCount: number; driverChanged: boolean | string | null },
  ddAdvance: number | null,
): FinishVerdict {
  const chips: string[] = []
  if (stability.driverChanged) chips.push('finish driver changed')
  const fewKept = stability.baseCount > 0 && stability.pct < 50
  if (fewKept) chips.push(`${stability.pct}% of the longest path kept`)
  if (ddAdvance === 0 && finishDelta) chips.push('data date unchanged: a re-plan, not progress')
  const resequenced = !!stability.driverChanged || fewKept
  const cls = finishDelta > 0 ? 'v-slip' : finishDelta < 0 && !resequenced ? 'v-gain' : 'v-hold'
  return { cls, chips }
}


export interface Stability {
  /** Share of the earlier longest path still on the current one, 0-100. */
  pct: number
  retained: number
  baseCount: number
  newlyCritical: number
  dropped: number
  /** The finish-driving activity's code when it changed, else false/null. */
  driverChanged: boolean | string | null
}

/** How much of the earlier file's longest path (by activity code) is still on the
 *  current one, and whether the activity driving the finish changed. */
export function longestPathStability(baseline: Schedule, current: Schedule): Stability {
  const baseLongest = new Set(baseline.activities.filter(a => a.is_longest_path).map(a => a.task_code))
  const curLongest = new Set(current.activities.filter(a => a.is_longest_path).map(a => a.task_code))
  const retained = [...baseLongest].filter(c => curLongest.has(c)).length
  const pct = baseLongest.size ? Math.round((100 * retained) / baseLongest.size) : 100
  const newlyCritical = [...curLongest].filter(c => !baseLongest.has(c)).length
  const dropped = [...baseLongest].filter(c => !curLongest.has(c)).length
  const driverOf = (data: Schedule, codeSet: Set<string>) => {
    let best: Activity | null = null
    for (const a of data.activities) {
      if (!codeSet.has(a.task_code) || !a.early_end) continue
      if (!best || new Date(a.early_end) > new Date(best.early_end!)) best = a
    }
    return best ? best.task_code : null
  }
  const baseDriver = driverOf(baseline, baseLongest)
  const curDriver = driverOf(current, curLongest)
  return { pct, retained, baseCount: baseLongest.size, newlyCritical, dropped, driverChanged: baseDriver && curDriver && baseDriver !== curDriver }
}

// ── What drives the finish ───────────────────────────────────────────────────

export interface PathChange {
  code: string
  name: string
  /** Not in the earlier file at all. */
  added: boolean
  /** Was not on the earlier longest path. */
  joined: boolean
  /** Original duration edited, in working days (current − earlier). */
  durationDays: number
  /** Start moved, in calendar days. */
  startDays: number | null
  logicEdited: boolean
  constraintChanged: boolean
}

export interface FinishDrivers {
  /** The current longest path in start order, each activity with what changed on it. */
  path: PathChange[]
  /** Activities on the earlier longest path that are no longer on it. */
  left: { code: string; name: string; removed: boolean }[]
  /** Duration edits on the current path, summed (working days): a first-order part of
   *  the finish move, not a forensic decomposition. */
  durationEditDays: number
  /** Durations of activities new to the file on the current path (working days). */
  addedDays: number
}

const workDays = (hrs: number | null | undefined, a: Activity) => (hrs || 0) / (a.calendar_hrs_per_day || 8)

function predKeys(a: Activity, codeOf: Map<number, string>): string {
  return a.predecessors.map(p => `${codeOf.get(p.task_id) ?? p.task_id}|${p.type}|${p.lag_hrs || 0}`).sort().join(',')
}

/** The current longest path against the earlier file's, activity by activity. */
export function finishDrivers(baseline: Schedule, current: Schedule): FinishDrivers {
  const baseByCode = new Map(baseline.activities.map(a => [a.task_code, a]))
  const curCodes = new Set(current.activities.map(a => a.task_code))
  const baseCode = new Map(baseline.activities.map(a => [a.task_id, a.task_code]))
  const curCode = new Map(current.activities.map(a => [a.task_id, a.task_code]))
  const cstr = (a: Activity) => [a.cstr_type || '', a.cstr_date || '', a.cstr_type2 || '', a.cstr_date2 || ''].join('|')
  const day = (d: string | null | undefined) => (d ? new Date(d).getTime() : NaN)
  const path: PathChange[] = current.activities
    .filter(a => a.is_longest_path)
    .sort((x, y) => day(displayStartOf(x)) - day(displayStartOf(y)))
    .map(a => {
      const b = baseByCode.get(a.task_code)
      const sa = day(displayStartOf(a)), sb = b ? day(displayStartOf(b)) : NaN
      return {
        code: a.task_code, name: a.task_name, added: !b, joined: !!b && !b.is_longest_path,
        durationDays: b ? Math.round((workDays(a.duration_hrs, a) - workDays(b.duration_hrs, b)) * 10) / 10 : 0,
        startDays: b && !isNaN(sa) && !isNaN(sb) ? Math.round((sa - sb) / 86400000) : null,
        logicEdited: !!b && predKeys(a, curCode) !== predKeys(b, baseCode),
        constraintChanged: !!b && cstr(a) !== cstr(b),
      }
    })
  const curOnPath = new Set(path.map(p => p.code))
  const left = baseline.activities
    .filter(b => b.is_longest_path && !curOnPath.has(b.task_code))
    .map(b => ({ code: b.task_code, name: b.task_name, removed: !curCodes.has(b.task_code) }))
  const curByCode = new Map(current.activities.map(a => [a.task_code, a]))
  return {
    path, left,
    durationEditDays: Math.round(path.reduce((t, p) => t + p.durationDays, 0) * 10) / 10,
    addedDays: Math.round(path.filter(p => p.added).reduce((t, p) => t + workDays(curByCode.get(p.code)!.duration_hrs, curByCode.get(p.code)!), 0) * 10) / 10,
  }
}

function displayStartOf(a: Activity): string | null {
  return a.act_start || a.early_start
}
