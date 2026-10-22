import { describe, it, expect } from 'vitest'
import { actualDateChanges, constraintChanges, finishSlipDays } from './compareChecks'

import type { Activity } from '../types/schedule'
import { makeActivity } from '../testing/factories'

const pair = (base: Partial<Activity>, cur: Partial<Activity>) =>
  ({ code: 'A1', base: makeActivity(base), cur: makeActivity(cur) })

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

describe('finishSlipDays', () => {
  it('measures the displayed finish in calendar days: later is positive, earlier negative', () => {
    const a = (f: Partial<Activity>) => makeActivity({ act_end: null, early_end: null, ...f })
    expect(finishSlipDays(a({ early_end: '2026-03-13 17:00' }), a({ early_end: '2026-03-10 17:00' }))).toBe(3)
    expect(finishSlipDays(a({ early_end: '2026-03-09 17:00' }), a({ early_end: '2026-03-10 17:00' }))).toBe(-1)
    // a completed activity is measured on its actual finish
    expect(finishSlipDays(a({ act_end: '2026-03-12 12:00', early_end: '2026-03-20 17:00' }), a({ early_end: '2026-03-10 12:00' }))).toBe(2)
    expect(finishSlipDays(a({}), a({ early_end: '2026-03-10 17:00' }))).toBeNull()
  })
})

describe('finishVerdict', () => {
  const kept = { pct: 90, baseCount: 20, driverChanged: false }
  it('reads a later finish as a slip, whatever else changed', async () => {
    const { finishVerdict } = await import('./compareChecks')
    expect(finishVerdict(5, kept, 30).cls).toBe('v-slip')
  })
  it('credits an earlier finish only when the driving logic survived', async () => {
    const { finishVerdict } = await import('./compareChecks')
    expect(finishVerdict(-8, kept, 30)).toEqual({ cls: 'v-gain', chips: [] })
    const replanned = finishVerdict(-8, { pct: 14, baseCount: 96, driverChanged: 'A100' }, 0)
    expect(replanned.cls).toBe('v-hold')
    expect(replanned.chips).toEqual(['finish driver changed', '14% of the longest path kept', 'data date unchanged: a re-plan, not progress'])
  })
  it('says nothing about the data date when the finish did not move', async () => {
    const { finishVerdict } = await import('./compareChecks')
    expect(finishVerdict(0, kept, 0)).toEqual({ cls: 'v-hold', chips: [] })
  })
})
