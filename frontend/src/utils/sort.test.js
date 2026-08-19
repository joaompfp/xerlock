import { describe, it, expect } from 'vitest'
import { compareBy, sortRows } from './sort'

const byFloat = (dir) => compareBy(a => a.total_float_hrs, dir)

describe('unknown values sort last, not as zero', () => {
  // Regression: P6 leaves total float blank on completed activities. The old
  // comparator coerced null to '' — which JS compares as 0 — so on a real
  // 487-activity schedule 65 completed activities landed between the negative
  // and zero float bands, scattered through the critical work a reviewer scans.
  const rows = [
    { code: 'done-a', total_float_hrs: null },
    { code: 'neg', total_float_hrs: -8 },
    { code: 'zero', total_float_hrs: 0 },
    { code: 'done-b', total_float_hrs: null },
    { code: 'pos', total_float_hrs: 80 },
  ]

  it('puts unknown float after every real value ascending', () => {
    const order = sortRows(rows, r => r.total_float_hrs, 'asc').map(r => r.code)
    expect(order).toEqual(['neg', 'zero', 'pos', 'done-a', 'done-b'])
  })

  it('keeps unknown float last when the direction flips', () => {
    // Flipping direction should reorder the data, not parade the blanks.
    const order = sortRows(rows, r => r.total_float_hrs, 'desc').map(r => r.code)
    expect(order).toEqual(['pos', 'zero', 'neg', 'done-a', 'done-b'])
  })

  it('never places an unknown value between two known ones', () => {
    for (const dir of ['asc', 'desc']) {
      const vals = sortRows(rows, r => r.total_float_hrs, dir).map(r => r.total_float_hrs)
      const firstUnknown = vals.findIndex(v => v == null)
      expect(vals.slice(firstUnknown).every(v => v == null)).toBe(true)
    }
  })

  it('does not confuse zero float with missing float', () => {
    // Zero means critical; blank means P6 gave us nothing.
    expect(byFloat('asc')({ total_float_hrs: 0 }, { total_float_hrs: null })).toBeLessThan(0)
    expect(byFloat('desc')({ total_float_hrs: 0 }, { total_float_hrs: null })).toBeLessThan(0)
  })

  it('treats empty strings as missing too', () => {
    const order = sortRows(
      [{ c: 'b', v: 'beta' }, { c: 'blank', v: '' }, { c: 'a', v: 'alpha' }],
      r => r.v, 'asc',
    ).map(r => r.c)
    expect(order).toEqual(['a', 'b', 'blank'])
  })
})

describe('ordinary comparisons', () => {
  it('sorts numbers by value, not lexically', () => {
    const order = sortRows([{ n: 100 }, { n: 9 }, { n: 80 }], r => r.n, 'asc').map(r => r.n)
    expect(order).toEqual([9, 80, 100])
  })

  it('sorts strings case-insensitively', () => {
    const order = sortRows([{ s: 'beta' }, { s: 'Alpha' }], r => r.s, 'asc').map(r => r.s)
    expect(order).toEqual(['Alpha', 'beta'])
  })

  it('sorts ISO date strings chronologically', () => {
    const order = sortRows(
      [{ d: '2026-03-01' }, { d: '2026-01-15' }, { d: '2026-02-20' }], r => r.d, 'asc',
    ).map(r => r.d)
    expect(order).toEqual(['2026-01-15', '2026-02-20', '2026-03-01'])
  })

  it('is stable for equal values', () => {
    const rows = [{ id: 1, v: 5 }, { id: 2, v: 5 }, { id: 3, v: 5 }]
    expect(sortRows(rows, r => r.v, 'asc').map(r => r.id)).toEqual([1, 2, 3])
  })

  it('does not mutate the input array', () => {
    const rows = [{ v: 3 }, { v: 1 }]
    sortRows(rows, r => r.v, 'asc')
    expect(rows.map(r => r.v)).toEqual([3, 1])
  })
})
