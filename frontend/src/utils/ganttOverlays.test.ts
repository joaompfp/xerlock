import { describe, it, expect } from 'vitest'
import type { Activity } from '../types/schedule'
import { keyDateMarks, periodBands, placedTextBoxes, slipArrows, callouts, calloutAnchorX } from './ganttOverlays'
import { emptyMarkup } from './markup'
import type { ActivityRow } from './ganttRows'

// 10 px per day from 1 Mar 2026, local midnight.
const start = new Date('2026-03-01T00:00:00').getTime()
const toX = (d: string | null | undefined) => (d ? Math.round((new Date(d).getTime() - start) / 86400000 * 10) : null)

const row = (id: number, code: string, x: number, w: number, end: string, index: number, milestone = false): ActivityRow => ({
  type: 'activity', key: 'a' + id, level: 1, milestone, x, w, tailW: 0, cls: 'other', index,
  activity: { task_id: id, task_code: code, early_end: end, act_end: null } as unknown as Activity,
})

describe('markup geometry', () => {
  const m = { ...emptyMarkup(),
    keyDates: [{ id: 'k', date: '2026-03-04', label: 'Board', color: 'teal' as const }, { id: 'out', date: '2027-01-01', label: '', color: 'teal' as const }],
    periods: [{ id: 'p', from: '2026-03-06', to: '2026-03-03', label: '', color: 'amber' as const }] }
  it('places key dates at the start of their day and drops those off the chart', () => {
    expect(keyDateMarks(m, toX, 500).map(k => [k.id, k.x])).toEqual([['k', 30]])
  })
  it('runs a period to the end of its last day, read the right way round', () => {
    expect(periodBands(m, toX, 10, 500).map(p => [p.x, p.w])).toEqual([[20, 40]])
  })
  it('follows a dragged text box until it is dropped', () => {
    const texts = [{ id: 't', at: '2026-03-02T00:00:00', y: 5, text: 'x', color: 'slate' as const }]
    expect(placedTextBoxes(texts, toX, null)[0]).toMatchObject({ x: 10, y: 5 })
    expect(placedTextBoxes(texts, toX, { id: 't', x0: 10, y0: 5, x: 40, y: 9 })[0]).toMatchObject({ x: 40, y: 9 })
  })
})

describe('slip arrows and callouts', () => {
  const rows = [row(1, 'A', 0, 50, '2026-03-06T00:00:00', 0), row(2, 'B', 60, 0, '2026-03-08T00:00:00', 1, true)]
  it('draws an arrow only for a finish that moved', () => {
    const base = new Map([
      ['A', { task_code: 'A', early_end: '2026-03-04T00:00:00', act_end: null } as unknown as Activity],
      ['B', { task_code: 'B', early_end: '2026-03-08T00:00:00', act_end: null } as unknown as Activity],
    ])
    expect(slipArrows(rows, base, toX, 26)).toEqual([{ id: 1, x1: 30, x2: 50, y: 24, late: true }])
  })
  it('anchors a callout at the bar end or the milestone, with any live drag', () => {
    expect(calloutAnchorX(rows[0])).toBe(50)
    expect(calloutAnchorX(rows[1])).toBe(67)
    const notes = { 2: { note: 'n', severity: null, updatedAt: 1, callout: { dx: 18, dy: 10 } } } as never
    expect(callouts(rows, notes, null, 26)).toMatchObject([{ id: 2, ax: 74, ay: 39, dx: 18, dy: 10 }])
    expect(callouts(rows, notes, { id: 2, dx0: 18, dy0: 10, dx: 30, dy: 0 }, 26)[0]).toMatchObject({ dx: 30, dy: 0 })
  })
})
