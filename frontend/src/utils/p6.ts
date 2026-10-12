// Shared P6 vocabulary: raw XER codes -> planner-readable labels.
// Single source of truth so the drawer, network diagram, health check, compare view,
// and exports all describe relationships and constraints identically.

import type { Activity } from '../types/schedule'

export const REL_TYPE_LABELS: Record<string, string> = { PR_FS: 'FS', PR_SS: 'SS', PR_FF: 'FF', PR_SF: 'SF' }

export function relTypeLabel(t: string | null | undefined): string {
  return (t && REL_TYPE_LABELS[t]) || t || ''
}

export const CSTR_LABELS: Record<string, string> = {
  CS_MSO: 'Start On',
  CS_MSOB: 'Start On or Before',
  CS_MSOA: 'Start On or After',
  CS_MANDSTART: 'Mandatory Start',
  CS_MEO: 'Finish On',
  CS_MEOB: 'Finish On or Before',
  CS_MEOA: 'Finish On or After',
  CS_MANDFIN: 'Mandatory Finish',
  CS_ALAP: 'As Late As Possible',
}

export function cstrLabel(t: string | null | undefined): string {
  return (t && CSTR_LABELS[t]) || t || ''
}

// "Hard" = can hold an activity against its logic and so produce negative float. DCMA 05
// names Must Start/Finish On and Start/Finish No Later Than; in P6 terms that is the two
// Mandatory constraints, Start/Finish On, and Start/Finish On or Before (P6's names for
// the "no later than" pair).
export const HARD_CONSTRAINT_TYPES: ReadonlySet<string> = new Set([
  'CS_MANDSTART', 'CS_MANDFIN', 'CS_MSO', 'CS_MEO', 'CS_MSOB', 'CS_MEOB',
])

// P6 display-date convention: once an activity has started, its actual start IS its start;
// once complete, its actual finish IS its finish. P6 resets the early dates of finished
// work to the data date on every reschedule, so rendering early dates alone collapses
// every completed activity to a zero-width bar sitting on the data date.
type DatedActivity = Pick<Activity, 'act_start' | 'act_end' | 'early_start' | 'early_end'>

export function displayStart(a: DatedActivity): string | null {
  return a.act_start || a.early_start
}

export function displayEnd(a: DatedActivity): string | null {
  return a.act_end || a.early_end
}
