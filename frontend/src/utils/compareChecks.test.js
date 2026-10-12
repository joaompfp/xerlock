import { describe, it, expect } from 'vitest'
import { actualDateChanges, constraintChanges } from './compareChecks'

const pair = (base, cur) => ({ code: 'A1', base: { ...base }, cur: { ...cur } })

describe('actualDateChanges', () => {
  it('flags a moved actual and a withdrawn actual', () => {
    const r = actualDateChanges([
      pair({ act_start: '2026-02-01 08:00' }, { act_start: '2026-02-03 08:00' }),
      pair({ act_start: '2026-02-01 08:00', act_end: '2026-02-10 16:00' }, { act_start: '2026-02-01 08:00', act_end: null }),
    ])
    expect(r.map(x => x.changes.map(c => [c.label, c.now]))).toEqual([
      [['Actual start', '2026-02-03 08:00']],
      [['Actual finish', null]],
    ])
  })

  it('does not flag new progress', () => {
    expect(actualDateChanges([pair({ act_start: null }, { act_start: '2026-02-03 08:00' })])).toEqual([])
  })
})

describe('constraintChanges', () => {
  it('flags added, removed and re-dated constraints only', () => {
    const r = constraintChanges([
      pair({}, { cstr_type: 'CS_MEOB', cstr_date: '2026-09-01' }),
      pair({ cstr_type: 'CS_MEOB', cstr_date: '2026-09-01' }, {}),
      pair({ cstr_type: 'CS_MEOB', cstr_date: '2026-09-01' }, { cstr_type: 'CS_MEOB', cstr_date: '2026-10-01' }),
      pair({ cstr_type: 'CS_MEOB', cstr_date: '2026-09-01' }, { cstr_type: 'CS_MEOB', cstr_date: '2026-09-01' }),
    ])
    expect(r).toHaveLength(3)
  })
})
