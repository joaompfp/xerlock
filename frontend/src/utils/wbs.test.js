import { describe, it, expect } from 'vitest'
import { buildWbsRollups } from './wbs'

const tree = [{
  wbs_id: 1, children: [
    { wbs_id: 2, children: [] },
    { wbs_id: 3, children: [{ wbs_id: 4, children: [] }] },
  ],
}]
const acts = [
  { wbs_id: 2, is_critical: true, pct_complete: 100, act_start: '2026-01-10', act_end: '2026-01-20', early_start: null, early_end: null },
  { wbs_id: 2, is_critical: false, pct_complete: 0, act_start: null, act_end: null, early_start: '2026-02-01', early_end: '2026-02-10' },
  { wbs_id: 4, is_critical: true, pct_complete: 50, act_start: null, act_end: null, early_start: '2026-03-01', early_end: '2026-04-30' },
]

describe('buildWbsRollups', () => {
  const r = buildWbsRollups(tree, acts)

  it('rolls descendants up into their ancestors', () => {
    expect(r.get(2).activities).toBe(2)
    expect(r.get(4).activities).toBe(1)
    expect(r.get(3).activities).toBe(1)   // via its child
    expect(r.get(1).activities).toBe(3)   // the whole branch
  })

  it('counts critical activities per branch', () => {
    expect(r.get(2).critical).toBe(1)
    expect(r.get(1).critical).toBe(2)
  })

  it('spans the branch using display dates, so completed work is not lost', () => {
    // act_start is preferred over the early date P6 reset to the data date.
    expect(r.get(1).start).toBe('2026-01-10')
    expect(r.get(1).finish).toBe('2026-04-30')
  })

  it('averages progress across the branch', () => {
    expect(r.get(2).pct).toBe(50)          // 100 and 0
    expect(r.get(1).pct).toBe(50)          // 100, 0, 50
  })

  it('reports an empty node without dates rather than throwing', () => {
    const empty = buildWbsRollups([{ wbs_id: 9, children: [] }], [])
    expect(empty.get(9)).toEqual({ activities: 0, critical: 0, start: null, finish: null, pct: 0 })
  })

  it('tolerates a missing tree', () => {
    expect(buildWbsRollups(null, acts).size).toBe(0)
  })
})
