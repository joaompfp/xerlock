import { describe, it, expect } from 'vitest'
import {
  ZOOM_DAY_WIDTH, MIN_DAY_WIDTH, MAX_DAY_WIDTH,
  timelineRange, dayWidthFor, clampDayWidth, totalWidth,
  dateToX, yearTicks, monthTicks, weekTicks, dayTicks, weekendRects,
} from './ganttGeometry'

// A fixed two-month window so every expectation is an exact pixel, not a range.
const START = '2026-03-01 00:00:00'
const END = '2026-04-30 00:00:00'
const { rangeStart, rangeEnd } = timelineRange(START, END)
const DW = 10 // 10px per day keeps the arithmetic readable

describe('timelineRange', () => {
  it('pads the project span so end bars are not flush with the chart edge', () => {
    expect(rangeStart.getDate()).toBe(24)      // 1 Mar - 5d
    expect(rangeStart.getMonth()).toBe(1)      // February
    expect(rangeEnd.getDate()).toBe(5)         // 30 Apr + 5d
    expect(rangeEnd.getMonth()).toBe(4)        // May
  })

  it('falls back to today when the project has no dates', () => {
    const { rangeStart: s, rangeEnd: e } = timelineRange(null, null)
    expect(e - s).toBe(10 * 86400000)
  })

  it('does not mutate its inputs', () => {
    const d = new Date('2026-03-01T00:00:00')
    const before = d.getTime()
    timelineRange(d, d)
    expect(d.getTime()).toBe(before)
  })
})

describe('dateToX', () => {
  it('places the range start at x=0 and scales by day width', () => {
    expect(dateToX(rangeStart, rangeStart, DW)).toBe(0)
    const tenDaysOn = new Date(rangeStart.getTime() + 10 * 86400000)
    expect(dateToX(tenDaysOn, rangeStart, DW)).toBe(100)
  })

  it('scales linearly with day width', () => {
    const d = new Date(rangeStart.getTime() + 7 * 86400000)
    expect(dateToX(d, rangeStart, 1)).toBe(7)
    expect(dateToX(d, rangeStart, 32)).toBe(224)
  })

  it('returns null rather than 0 for missing or unparseable dates', () => {
    // Returning 0 would silently draw the bar at the start of the project.
    expect(dateToX(null, rangeStart, DW)).toBeNull()
    expect(dateToX('', rangeStart, DW)).toBeNull()
    expect(dateToX('not a date', rangeStart, DW)).toBeNull()
  })

  it('handles dates before the range start as negative offsets', () => {
    const before = new Date(rangeStart.getTime() - 2 * 86400000)
    expect(dateToX(before, rangeStart, DW)).toBe(-20)
  })
})

describe('dayWidthFor / clampDayWidth', () => {
  it('uses the zoom preset unless overridden', () => {
    expect(dayWidthFor('day')).toBe(ZOOM_DAY_WIDTH.day)
    expect(dayWidthFor('quarter')).toBe(ZOOM_DAY_WIDTH.quarter)
    expect(dayWidthFor('day', 17)).toBe(17)
  })

  it('treats an override of 0 as a real value, not a missing one', () => {
    // ?? not || — a 0 override must not silently fall back to the preset.
    expect(dayWidthFor('day', 0)).toBe(0)
  })

  it('clamps to the zoom limits', () => {
    expect(clampDayWidth(1000)).toBe(MAX_DAY_WIDTH)
    expect(clampDayWidth(0.0001)).toBe(MIN_DAY_WIDTH)
    expect(clampDayWidth(12)).toBe(12)
  })
})

describe('totalWidth', () => {
  it('spans the full padded range', () => {
    const days = (rangeEnd - rangeStart) / 86400000
    expect(totalWidth(rangeStart, rangeEnd, DW)).toBe(Math.round(days * DW))
  })

  it('never collapses to zero for a single-day project', () => {
    const d = new Date('2026-03-01T00:00:00')
    expect(totalWidth(d, d, 32)).toBe(32)
  })
})

describe('tick rows', () => {
  it('emits one month tick per calendar month, in order', () => {
    const ticks = monthTicks(rangeStart, rangeEnd, DW)
    expect(ticks.map(t => t.label)).toEqual(['Feb', 'Mar', 'Apr', 'May'])
    expect(ticks.map(t => t.x)).toEqual([...ticks.map(t => t.x)].sort((a, b) => a - b))
  })

  it('clamps the first year tick into view instead of off-screen', () => {
    const ticks = yearTicks(rangeStart, rangeEnd, DW)
    expect(ticks).toHaveLength(1)
    expect(ticks[0]).toEqual({ x: 0, label: '2026' })
  })

  it('spans a year boundary with a tick for each year', () => {
    const { rangeStart: s, rangeEnd: e } = timelineRange('2025-12-01', '2026-02-01')
    const ticks = yearTicks(s, e, DW)
    expect(ticks.map(t => t.label)).toEqual(['2025', '2026'])
    expect(ticks[0].x).toBe(0)
    expect(ticks[1].x).toBeGreaterThan(0)
  })

  it('steps week ticks exactly seven days apart', () => {
    const ticks = weekTicks(rangeStart, rangeEnd, DW)
    for (let i = 1; i < ticks.length; i++) {
      expect(ticks[i].x - ticks[i - 1].x).toBe(7 * DW)
    }
  })

  it('emits one day tick per day and flags weekends', () => {
    const ticks = dayTicks(rangeStart, rangeEnd, DW)
    const days = Math.round((rangeEnd - rangeStart) / 86400000)
    expect(ticks.length).toBeGreaterThanOrEqual(days)
    // 24 Feb 2026 is a Tuesday; the first Saturday follows four days later.
    const weekends = ticks.filter(t => t.weekend)
    expect(weekends.length).toBeGreaterThan(0)
    for (const w of weekends) expect(['6', '7', '13', '14', '20', '21', '27', '28',
      '1', '8', '15', '22', '29', '2', '9', '16', '23', '30', '3', '4', '5', '11',
      '12', '18', '19', '25', '26', '10', '17', '24', '31']).toContain(w.label)
  })

  it('marks exactly two weekend days per seven consecutive day ticks', () => {
    const ticks = dayTicks(rangeStart, rangeEnd, DW)
    const firstWeek = ticks.slice(0, 7)
    expect(firstWeek.filter(t => t.weekend)).toHaveLength(2)
  })
})

describe('weekendRects', () => {
  it('produces one band per weekend day, one day wide', () => {
    const ticks = dayTicks(rangeStart, rangeEnd, DW)
    const rects = weekendRects(ticks, DW)
    expect(rects).toHaveLength(ticks.filter(t => t.weekend).length)
    for (const r of rects) expect(r.w).toBe(DW)
  })

  it('is empty when no ticks are weekends', () => {
    expect(weekendRects([{ x: 0, weekend: false }], 10)).toEqual([])
  })
})
