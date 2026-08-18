// Shared P6 vocabulary: raw XER codes -> planner-readable labels.
// Single source of truth so the drawer, network diagram, health check, compare view,
// and exports all describe relationships and constraints identically.

export const REL_TYPE_LABELS = { PR_FS: 'FS', PR_SS: 'SS', PR_FF: 'FF', PR_SF: 'SF' }

export function relTypeLabel(t) {
  return REL_TYPE_LABELS[t] || t || ''
}

export const CSTR_LABELS = {
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

export function cstrLabel(t) {
  return CSTR_LABELS[t] || t || ''
}

// "Hard" = can override network logic in a way that produces negative float.
export const HARD_CONSTRAINT_TYPES = new Set(['CS_MANDSTART', 'CS_MANDFIN', 'CS_MSO', 'CS_MEO'])

// P6 display-date convention: once an activity has started, its actual start IS its start;
// once complete, its actual finish IS its finish. P6 resets the early dates of finished
// work to the data date on every reschedule, so rendering early dates alone collapses
// every completed activity to a zero-width bar sitting on the data date.
export function displayStart(a) {
  return a.act_start || a.early_start
}

export function displayEnd(a) {
  return a.act_end || a.early_end
}
