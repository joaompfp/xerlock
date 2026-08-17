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

export function formatDateShort(d) {
  if (!d) return '—'
  const dt = new Date(d)
  return dt.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' })
}

export function formatDateRange(start, end) {
  if (!start) return '—'
  if (!end || start === end) return formatDateShort(start)
  return `${formatDateShort(start)}–${formatDateShort(end)}`
}

export function timeAgo(timestamp) {
  const diffMs = Date.now() - timestamp
  const min = Math.floor(diffMs / 60000)
  if (min < 1) return 'just now'
  if (min < 60) return `${min} min ago`
  const hr = Math.floor(min / 60)
  if (hr < 24) return `${hr}h ago`
  const day = Math.floor(hr / 24)
  if (day < 7) return `${day}d ago`
  return new Date(timestamp).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
}
