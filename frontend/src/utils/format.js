export function formatDate(d) {
  if (!d) return '--'
  const dt = new Date(d)
  return dt.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
}

export function formatHours(h) {
  if (!h) return '0d'
  const days = Math.round(h / 8)
  return days + 'd'
}

export function statusLabel(s) {
  const map = { TK_Complete: 'Done', TK_Active: 'Active', TK_NotStart: 'Not started' }
  return map[s] || s
}

const MILESTONE_TYPES = new Set(['TT_Mile', 'TT_FinMile', 'TT_StartMile'])

export function isMilestone(activity) {
  return MILESTONE_TYPES.has(activity.task_type)
}

// total_float_hrs is null when P6 didn't compute a float (typically completed
// activities) — must not be displayed as "0h", which reads as zero float / critical.
export function formatFloat(hrs) {
  return hrs == null ? '—' : `${hrs}h`
}
