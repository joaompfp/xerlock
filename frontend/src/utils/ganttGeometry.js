// Timeline geometry for the Gantt chart: the mapping from dates to pixels, and the
// tick rows drawn along the header. Pure functions of (range, dayWidth) — no
// component state — so the maths that positions every bar on screen is unit-tested
// rather than only eyeballed.

export const ZOOM_DAY_WIDTH = { day: 32, week: 9, month: 3, quarter: 1.1 }
export const MIN_DAY_WIDTH = 0.4
export const MAX_DAY_WIDTH = 60

const MS_PER_DAY = 86400000

/** Visible range: the project's own span with a few days of air either side, so
 *  the first and last bars aren't flush against the chart edge. */
export function timelineRange(earliestStart, latestEnd, padDays = 5) {
  const start = earliestStart ? new Date(earliestStart) : new Date()
  const end = latestEnd ? new Date(latestEnd) : new Date()
  start.setDate(start.getDate() - padDays)
  end.setDate(end.getDate() + padDays)
  return { rangeStart: start, rangeEnd: end }
}

export function dayWidthFor(zoom, override = null) {
  return override ?? ZOOM_DAY_WIDTH[zoom]
}

export function clampDayWidth(v) {
  return Math.min(MAX_DAY_WIDTH, Math.max(MIN_DAY_WIDTH, v))
}

export function totalWidth(rangeStart, rangeEnd, dayWidth) {
  const days = Math.max(1, (rangeEnd - rangeStart) / MS_PER_DAY)
  return Math.round(days * dayWidth)
}

/** Pixel offset of a date within the timeline. Returns null for missing or
 *  unparseable dates so callers can skip drawing rather than render at x=0. */
export function dateToX(dateStr, rangeStart, dayWidth) {
  if (!dateStr) return null
  const d = new Date(dateStr)
  if (isNaN(d)) return null
  return Math.round(((d - rangeStart) / MS_PER_DAY) * dayWidth)
}

function xOf(date, rangeStart, dayWidth) {
  return Math.round(((date - rangeStart) / MS_PER_DAY) * dayWidth)
}

export function yearTicks(rangeStart, rangeEnd, dayWidth) {
  const ticks = []
  for (let y = rangeStart.getFullYear(); y <= rangeEnd.getFullYear(); y++) {
    const boundary = new Date(y, 0, 1)
    // The first year's boundary sits before the padded range start; clamp it so
    // the label stays on-screen instead of scrolling off to negative x.
    const clamped = boundary < rangeStart ? rangeStart : boundary
    if (clamped > rangeEnd) break
    ticks.push({ x: xOf(clamped, rangeStart, dayWidth), label: String(y) })
  }
  return ticks
}

export function monthTicks(rangeStart, rangeEnd, dayWidth) {
  const ticks = []
  let cur = new Date(rangeStart.getFullYear(), rangeStart.getMonth(), 1)
  while (cur <= rangeEnd) {
    ticks.push({
      x: xOf(cur, rangeStart, dayWidth),
      label: cur.toLocaleDateString('en-GB', { month: 'short' }),
    })
    cur = new Date(cur.getFullYear(), cur.getMonth() + 1, 1)
  }
  return ticks
}

export function weekTicks(rangeStart, rangeEnd, dayWidth) {
  const ticks = []
  let cur = new Date(rangeStart)
  while (cur <= rangeEnd) {
    ticks.push({
      x: xOf(cur, rangeStart, dayWidth),
      label: cur.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' }),
    })
    cur = new Date(cur.getTime() + 7 * MS_PER_DAY)
  }
  return ticks
}

export function dayTicks(rangeStart, rangeEnd, dayWidth) {
  const ticks = []
  const cur = new Date(rangeStart)
  cur.setHours(0, 0, 0, 0)
  while (cur <= rangeEnd) {
    const dow = cur.getDay()
    ticks.push({
      x: xOf(cur, rangeStart, dayWidth),
      label: String(cur.getDate()),
      weekend: dow === 0 || dow === 6,
    })
    cur.setDate(cur.getDate() + 1)
  }
  return ticks
}

/** Shaded bands behind Saturdays and Sundays — only legible at day zoom. */
export function weekendRects(ticks, dayWidth) {
  return ticks.filter(t => t.weekend).map(t => ({ x: t.x, w: dayWidth }))
}
