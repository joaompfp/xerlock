// Forensic comparisons between two submissions of the same programme, over activities
// matched by code. Pure, so each rule is testable on its own.

import type { Activity } from '../types/schedule'

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
