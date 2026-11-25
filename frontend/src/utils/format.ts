import type { Activity } from '../types/schedule'

type DateInput = string | number | Date | null | undefined

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

// P6 prints dates DD-MMM-YY (02-Mar-26) and that is the format a planner reads most
// easily: day first, month by name, no ambiguity between 03/04 and 04/03. Built by hand
// rather than through Intl, because Intl inserts the locale's separator and has no
// hyphen-joined two-digit-year shape.
//
// Every formatter memoises: a programme repeats a few hundred dates thousands of times
// and this runs on every redraw of a large Gantt.
function twoDigit(n: number): string {
  return n < 10 ? `0${n}` : String(n)
}

function memoFormat(build: (dt: Date) => string): (d: string | number | Date) => string {
  const cache = new Map<string | number, string>()
  return d => {
    const key = d instanceof Date ? d.getTime() : d
    let s = cache.get(key)
    if (s === undefined) {
      const dt = d instanceof Date ? d : new Date(d)
      s = isNaN(dt.getTime()) ? 'Invalid Date' : build(dt)
      if (cache.size > 20000) cache.clear()
      cache.set(key, s)
    }
    return s
  }
}

const fmtDate = memoFormat(dt => `${twoDigit(dt.getDate())}-${MONTHS[dt.getMonth()]}-${twoDigit(dt.getFullYear() % 100)}`)
const fmtDateShort = memoFormat(dt => `${twoDigit(dt.getDate())}-${MONTHS[dt.getMonth()]}`)

/** Month labels for timeline ticks and axis bands, e.g. 'Mar' or 'Mar 26'. */
export function dateFormat(options: Intl.DateTimeFormatOptions): (d: string | number | Date) => string {
  const fmt = new Intl.DateTimeFormat('en-GB', options)
  const cache = new Map<string | number, string>()
  return d => {
    const key = d instanceof Date ? d.getTime() : d
    let s = cache.get(key)
    if (s === undefined) {
      const dt = new Date(d)
      // en-GB abbreviates September as "Sept"; every other month has three letters.
      s = isNaN(dt.getTime()) ? 'Invalid Date' : fmt.format(dt).replace('Sept', 'Sep')
      if (cache.size > 20000) cache.clear()
      cache.set(key, s)
    }
    return s
  }
}

export function formatDate(d: DateInput): string {
  if (!d) return '--'
  return fmtDate(d)
}

// hrsPerDay defaults to 8 but should be passed from the activity's own calendar
// (calendar_hrs_per_day) wherever available — a schedule mixing standard 8h calendars
// with night-shift/6-day/24-7 calendars would otherwise show silently wrong day counts
// for activities on the non-standard calendars.
export function formatHours(h: number | null | undefined, hrsPerDay = 8): string {
  if (!h) return '0d'
  const days = Math.round(h / (hrsPerDay || 8))
  return days + 'd'
}

export function statusLabel(s: string): string {
  const map: Record<string, string> = { TK_Complete: 'Done', TK_Active: 'Active', TK_NotStart: 'Not started' }
  return map[s] || s
}

const MILESTONE_TYPES = new Set(['TT_Mile', 'TT_FinMile', 'TT_StartMile'])

export function isMilestone(activity: Pick<Activity, 'task_type'>): boolean {
  return MILESTONE_TYPES.has(activity.task_type)
}

// total_float_hrs is null when P6 didn't compute a float (typically completed
// activities) — must not be displayed as "0d", which reads as zero float / critical.
// Displayed in DAYS (planners think in days), converted with the activity's own
// calendar; one decimal kept so small-but-nonzero floats don't masquerade as 0d.
export function formatFloat(hrs: number | null | undefined, hrsPerDay = 8): string {
  if (hrs == null) return '—'
  const days = Math.round((hrs / (hrsPerDay || 8)) * 10) / 10
  return `${days}d`
}

/** Day and month only, for columns with no room for the year (e.g. '02-Mar'). */
export function formatDateShort(d: DateInput): string {
  if (!d) return '—'
  return fmtDateShort(d)
}

export function formatDateRange(start: DateInput, end: DateInput): string {
  if (!start) return '—'
  if (!end || start === end) return formatDateShort(start)
  return `${formatDateShort(start)}–${formatDateShort(end)}`
}

export function timeAgo(timestamp: number): string {
  const diffMs = Date.now() - timestamp
  const min = Math.floor(diffMs / 60000)
  if (min < 1) return 'just now'
  if (min < 60) return `${min} min ago`
  const hr = Math.floor(min / 60)
  if (hr < 24) return `${hr}h ago`
  const day = Math.floor(hr / 24)
  if (day < 7) return `${day}d ago`
  return fmtDate(timestamp)
}

// Lags are stored in hours in the XER; planners think in working days. Uses the
// successor's calendar where the caller has it, else the standard 8h day.
export function formatLag(lagHrs: number | null | undefined, hrsPerDay = 8): string {
  if (!lagHrs) return ''
  const d = lagHrs / (hrsPerDay || 8)
  const v = Number.isInteger(d) ? d : Math.round(d * 10) / 10
  return (v > 0 ? '+' : '') + v + 'd'
}
