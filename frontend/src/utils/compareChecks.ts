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
