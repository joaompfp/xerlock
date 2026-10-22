import { describe, it, expect } from 'vitest'
import type { Activity, WbsNode } from '../types/schedule'
import {
  activitiesByWbs, computeRollups, buildRows, buildActivityRow, buildLinks, rowIndexByTaskId,
  classifyActivity, floatClass, allWbsKeys, wbsNodesByLevel, wbsParentMap, initialExpanded, progressPoints,
  type WbsKey,
} from './ganttRows'
import { dateToX } from './ganttGeometry'

const act = (id: number, wbs: number, start: string, end: string, over: Partial<Activity> = {}): Activity => ({
  task_id: id, task_code: 'A' + id, task_name: 'Act ' + id, wbs_id: wbs, status: 'TK_NotStart', pct_complete: 0,
  early_start: start, early_end: end, act_start: null, act_end: null, total_float_hrs: 40, calendar_hrs_per_day: 8,
  duration_hrs: 40, task_type: 'TT_Task', predecessors: [], successors: [], is_critical: false, is_longest_path: false,
  is_negative_float: false, activity_codes: [], ...over,
} as unknown as Activity)

const node = (id: number, seq: number, children: WbsNode[] = []): WbsNode =>
  ({ wbs_id: id, wbs_name: 'W' + id, wbs_short_name: '', seq_num: seq, children } as unknown as WbsNode)

// 1 ─┬─ 2 (A1, A2)
//    └─ 3 (A3)
// plus A9 under an unknown WBS
const tree = [node(1, 0, [node(3, 2), node(2, 1)])]
const acts = [
  act(2, 2, '2026-03-10T08:00:00', '2026-03-12T17:00:00', { is_critical: true }),
  act(1, 2, '2026-03-02T08:00:00', '2026-03-06T17:00:00', { is_critical: true }),
  act(3, 3, '2026-03-05T08:00:00', '2026-03-20T17:00:00'),
  act(9, 99, '2026-04-01T08:00:00', '2026-04-02T17:00:00'),
]
acts[0].predecessors = [{ task_id: 1, type: 'PR_FS', lag_hrs: 0 }] as Activity['predecessors']
acts[2].predecessors = [{ task_id: 1, type: 'PR_FS', lag_hrs: 0 }] as Activity['predecessors']

const rangeStart = new Date('2026-03-01T00:00:00')
const toX = (d: string | null | undefined) => dateToX(d, rangeStart, 10)
const byWbs = activitiesByWbs(acts)
const rowsFor = (expanded: Set<WbsKey>, matched: Set<number> | null = null) => buildRows({
  tree, activities: acts, byWbs, matched,
  rollups: computeRollups(tree, byWbs, null, matched ? a => matched.has(a.task_id) : null),
  isExpanded: id => (matched ? true : expanded.has(id)),
  activityRow: (a, level) => buildActivityRow(a, level, toX, 10, 'tf0'),
})

describe('WBS tree helpers', () => {
  it('maps parents, levels and keys', () => {
    expect([...wbsParentMap(tree)]).toEqual([[3, 1], [2, 1]])
    expect(wbsNodesByLevel(tree)).toEqual([{ id: 1, level: 0 }, { id: 3, level: 1 }, { id: 2, level: 1 }])
    expect([...allWbsKeys(tree)]).toEqual([1, 3, 2, '__unassigned'])
    expect([...initialExpanded(tree)]).toEqual([1])
  })
  it('sorts each WBS by start, then code', () => {
    expect(byWbs.get(2)!.map(a => a.task_id)).toEqual([1, 2])
  })
})

describe('computeRollups', () => {
  it('rolls start, finish and count up the tree', () => {
    const r = computeRollups(tree, byWbs, null, null)
    expect(r.get(1)!.count).toBe(3)
    expect(r.get(1)!.start!.toISOString()).toBe(new Date('2026-03-02T08:00:00').toISOString())
    expect(r.get(1)!.finish!.toISOString()).toBe(new Date('2026-03-20T17:00:00').toISOString())
    expect(r.get(2)!.baseFinish).toBeNull()
  })
  it('takes the latest compared finish when a baseline is given', () => {
    const base = new Map([['A3', act(3, 3, '2026-03-05T08:00:00', '2026-03-25T17:00:00')]])
    expect(computeRollups(tree, byWbs, base, null).get(1)!.baseFinish!.getDate()).toBe(25)
  })
})

describe('buildRows', () => {
  it('lists WBS in seq order and activities under expanded nodes only', () => {
    expect(rowsFor(new Set([1])).map(r => r.key)).toEqual(['w1', 'w2', 'w3', 'w-unassigned'])
    expect(rowsFor(new Set([1, 2, '__unassigned'])).map(r => r.key)).toEqual(['w1', 'w2', 'a1', 'a2', 'w3', 'w-unassigned', 'a9'])
  })
  it('numbers the rows in order', () => {
    expect(rowsFor(new Set([1, 2])).map(r => r.index)).toEqual([0, 1, 2, 3, 4, 5])
  })
  it('drops WBS without matches while filtering', () => {
    const rows = rowsFor(new Set(), new Set([3]))
    expect(rows.map(r => r.key)).toEqual(['w1', 'w3', 'a3'])
    expect(rows[0].type === 'wbs' && rows[0].count).toBe(1)
  })
})

describe('activities', () => {
  it('classes bars on the chosen basis', () => {
    expect(classifyActivity(act(1, 1, '', '', { is_critical: true }), 'tf0')).toBe('critical')
    expect(classifyActivity(act(1, 1, '', '', { total_float_hrs: 40 }), 'tf0')).toBe('near')
    expect(classifyActivity(act(1, 1, '', '', { total_float_hrs: 40 }), 'longest')).toBe('other')
    expect(classifyActivity(act(1, 1, '', '', { is_negative_float: true, total_float_hrs: -8 }), 'tf0')).toBe('other negative')
  })
  it('bands the float cell', () => {
    expect(floatClass(act(1, 1, '', '', { total_float_hrs: -1 }))).toBe('fl-neg')
    expect(floatClass(act(1, 1, '', '', { total_float_hrs: 0 }))).toBe('fl-crit')
    expect(floatClass(act(1, 1, '', '', { total_float_hrs: 80 }))).toBe('fl-near')
    expect(floatClass(act(1, 1, '', '', { total_float_hrs: 81 }))).toBe('')
  })
  it('places the bar and a float tail', () => {
    const r = buildActivityRow(acts[1], 2, toX, 10, 'tf0')
    expect(r.x).toBe(toX('2026-03-02T08:00:00'))
    expect(r.w).toBe(toX('2026-03-06T17:00:00')! - r.x)
    expect(r.tailW).toBe(50) // 40h / 8h-day = 5 days × 10px
  })
})

describe('buildLinks', () => {
  const rows = rowsFor(new Set([1, 2, 3]))
  const idx = rowIndexByTaskId(rows)
  it('draws every visible relationship, critical pairs solid', () => {
    const links = buildLinks(rows, idx, { criticalOnly: false, basis: 'tf0', toX, rowHeight: 26 })
    expect(links.map(l => l.chain)).toEqual([false, true])
  })
  it('keeps only critical-to-critical links in critical scope', () => {
    expect(buildLinks(rows, idx, { criticalOnly: true, basis: 'tf0', toX, rowHeight: 26 })).toHaveLength(1)
  })
  it('skips predecessors that are not on screen', () => {
    const hidden = rowsFor(new Set([1, 3]))
    expect(buildLinks(hidden, rowIndexByTaskId(hidden), { criticalOnly: false, basis: 'tf0', toX, rowHeight: 26 })).toEqual([])
  })
})

describe('progressPoints', () => {
  it('puts one point per bar at its percent complete', () => {
    const rows = rowsFor(new Set([1, 2]))
    const pts = progressPoints(rows, 26)
    expect(pts).toHaveLength(2)
    expect(pts[0].y).toBe(2 * 26 + 13)
  })
})
