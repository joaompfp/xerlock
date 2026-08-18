export function formatDate(d) {
  if (!d) return '--'
  const dt = new Date(d)
  return dt.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
}

// hrsPerDay defaults to 8 but should be passed from the activity's own calendar
// (calendar_hrs_per_day) wherever available — a schedule mixing standard 8h calendars
// with night-shift/6-day/24-7 calendars would otherwise show silently wrong day counts
// for activities on the non-standard calendars.
export function formatHours(h, hrsPerDay = 8) {
  if (!h) return '0d'
  const days = Math.round(h / (hrsPerDay || 8))
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
// activities) — must not be displayed as "0d", which reads as zero float / critical.
// Displayed in DAYS (planners think in days), converted with the activity's own
// calendar; one decimal kept so small-but-nonzero floats don't masquerade as 0d.
export function formatFloat(hrs, hrsPerDay = 8) {
  if (hrs == null) return '—'
  const days = Math.round((hrs / (hrsPerDay || 8)) * 10) / 10
  return `${days}d`
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

// Lags are stored in hours in the XER; planners think in working days. Uses the
// successor's calendar where the caller has it, else the standard 8h day.
export function formatLag(lagHrs, hrsPerDay = 8) {
  if (!lagHrs) return ''
  const d = lagHrs / (hrsPerDay || 8)
  const v = Number.isInteger(d) ? d : Math.round(d * 10) / 10
  return (v > 0 ? '+' : '') + v + 'd'
}
