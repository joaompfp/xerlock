// Timeline geometry for the Gantt chart: the mapping from dates to pixels, and the
// tick rows drawn along the header. Pure functions of (range, dayWidth) — no
// component state — so the maths that positions every bar on screen is unit-tested
// rather than only eyeballed.

export type Zoom = 'day' | 'week' | 'month' | 'quarter'

export interface Tick {
  x: number
  label: string
  /** Day ticks only. */
  weekend?: boolean
}

type DateLike = string | number | Date

export const ZOOM_DAY_WIDTH: Record<Zoom, number> = { day: 32, week: 9, month: 3, quarter: 1.1 }
export const MIN_DAY_WIDTH = 0.4
export const MAX_DAY_WIDTH = 60

const MS_PER_DAY = 86400000

/** Visible range: the project's own span with a few days of air either side, so
 *  the first and last bars aren't flush against the chart edge. */
export function timelineRange(
  earliestStart: DateLike | null | undefined,
  latestEnd: DateLike | null | undefined,
  padDays = 5,
): { rangeStart: Date; rangeEnd: Date } {
  const start = earliestStart ? new Date(earliestStart) : new Date()
  const end = latestEnd ? new Date(latestEnd) : new Date()
  start.setDate(start.getDate() - padDays)
  end.setDate(end.getDate() + padDays)
  return { rangeStart: start, rangeEnd: end }
}

/** Widest span covering both schedules. When a baseline is loaded its activities are
 *  drawn as ghost bars, and a baseline that finishes later than the current programme
 *  would otherwise be positioned past the end of the grid — outside the drawn canvas,
 *  with no header, gridlines or background behind it. */
export function unionRange(
  aStart: string | null, aEnd: string | null, bStart: string | null, bEnd: string | null,
): { start: string | null; end: string | null } {
  const min = (x: string | null, y: string | null) => (!x ? y : !y ? x : (x < y ? x : y))
  const max = (x: string | null, y: string | null) => (!x ? y : !y ? x : (x > y ? x : y))
  return { start: min(aStart, bStart), end: max(aEnd, bEnd) }
}

export function dayWidthFor(zoom: Zoom, override: number | null = null): number {
  return override ?? ZOOM_DAY_WIDTH[zoom]
}

export function clampDayWidth(v: number): number {
  return Math.min(MAX_DAY_WIDTH, Math.max(MIN_DAY_WIDTH, v))
}

export function totalWidth(rangeStart: Date, rangeEnd: Date, dayWidth: number): number {
  const days = Math.max(1, (rangeEnd.getTime() - rangeStart.getTime()) / MS_PER_DAY)
  return Math.round(days * dayWidth)
}

/** Pixel offset of a date within the timeline. Returns null for missing or
 *  unparseable dates so callers can skip drawing rather than render at x=0. */
export function dateToX(dateStr: DateLike | null | undefined, rangeStart: Date, dayWidth: number): number | null {
  if (!dateStr) return null
  const d = new Date(dateStr)
  if (isNaN(d.getTime())) return null
  return Math.round(((d.getTime() - rangeStart.getTime()) / MS_PER_DAY) * dayWidth)
}

function xOf(date: Date, rangeStart: Date, dayWidth: number): number {
  return Math.round(((date.getTime() - rangeStart.getTime()) / MS_PER_DAY) * dayWidth)
}

export function yearTicks(rangeStart: Date, rangeEnd: Date, dayWidth: number): Tick[] {
  const ticks: Tick[] = []
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

export function monthTicks(rangeStart: Date, rangeEnd: Date, dayWidth: number): Tick[] {
  const ticks: Tick[] = []
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

/** Coarse header band above the tick row: 'MAR 26' per calendar month. Gives the
 *  eye a unit it can hold, which a bare year row does not. */
export function monthBandTicks(rangeStart: Date, rangeEnd: Date, dayWidth: number): Tick[] {
  const MON = ['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC']
  const ticks: Tick[] = []
  let cur = new Date(rangeStart.getFullYear(), rangeStart.getMonth(), 1)
  while (cur <= rangeEnd) {
    ticks.push({
      x: Math.round(((cur.getTime() - rangeStart.getTime()) / 86400000) * dayWidth),
      label: `${MON[cur.getMonth()]} ${String(cur.getFullYear()).slice(2)}`,
    })
    cur = new Date(cur.getFullYear(), cur.getMonth() + 1, 1)
  }
  return ticks
}

export function weekTicks(rangeStart: Date, rangeEnd: Date, dayWidth: number): Tick[] {
  const ticks: Tick[] = []
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

export function dayTicks(rangeStart: Date, rangeEnd: Date, dayWidth: number): Tick[] {
  const ticks: Tick[] = []
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
export function weekendRects(ticks: readonly { x: number; weekend?: boolean }[], dayWidth: number): { x: number; w: number }[] {
  return ticks.filter(t => t.weekend).map(t => ({ x: t.x, w: dayWidth }))
}
