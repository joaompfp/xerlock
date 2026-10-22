import { describe, it, expect } from 'vitest'
import type { Activity } from '../types/schedule'
import {
  emptyFilter, isFilterSet, matchesFilter, withoutChip, lookAheadWindow, toggleLookAhead, filterChips,
  emptyFilterHint, constraintOptions, noteOptions, codeValuesByType, type GanttFilter,
} from './ganttFilter'

const act = (over: Partial<Activity> = {}): Activity => ({
  task_id: 1, task_code: 'EW-010', task_name: 'Excavate', wbs_path: 'Site / Earthworks', status: 'TK_NotStart',
  early_start: '2026-03-02T08:00:00', early_end: '2026-03-06T17:00:00', act_start: null, act_end: null,
  is_critical: false, cstr_type: null, cstr_type2: null, activity_codes: [{ type: 'Area', code: 'North' }], ...over,
} as unknown as Activity)

const f = (over: Partial<GanttFilter> = {}): GanttFilter => ({ ...emptyFilter(['Area']), ...over })
const ctx = { annotations: {}, isCritical: (a: Activity) => a.is_critical }

describe('emptyFilter / isFilterSet', () => {
  it('seeds one empty entry per code type and is not set', () => {
    expect(emptyFilter(['Area', 'Phase']).codes).toEqual({ Area: '', Phase: '' })
    expect(isFilterSet(f())).toBe(false)
    expect(isFilterSet(f({ text: '  ' }))).toBe(false)
    expect(isFilterSet(f({ codes: { Area: 'North' } }))).toBe(true)
  })
})

describe('matchesFilter', () => {
  it('searches code, name and WBS path, case-insensitively', () => {
    expect(matchesFilter(act(), f({ text: 'ew-0' }), ctx)).toBe(true)
    expect(matchesFilter(act(), f({ text: 'earthworks' }), ctx)).toBe(true)
    expect(matchesFilter(act(), f({ text: 'roof' }), ctx)).toBe(false)
  })
  it('keeps activities touching the date window', () => {
    expect(matchesFilter(act(), f({ from: '2026-03-06' }), ctx)).toBe(true)
    expect(matchesFilter(act(), f({ from: '2026-03-07' }), ctx)).toBe(false)
    expect(matchesFilter(act(), f({ to: '2026-03-01' }), ctx)).toBe(false)
  })
  it('applies status, critical and codes', () => {
    expect(matchesFilter(act(), f({ status: 'TK_Active' }), ctx)).toBe(false)
    expect(matchesFilter(act(), f({ criticalOnly: true }), ctx)).toBe(false)
    expect(matchesFilter(act({ is_critical: true }), f({ criticalOnly: true }), ctx)).toBe(true)
    expect(matchesFilter(act(), f({ codes: { Area: 'North' } }), ctx)).toBe(true)
    expect(matchesFilter(act(), f({ codes: { Area: 'South' } }), ctx)).toBe(false)
  })
})

describe('look-ahead', () => {
  it('runs from the data date for N days, toggling off when set again', () => {
    expect(lookAheadWindow('2026-03-02T08:00:00', 28)).toEqual({ from: '2026-03-02', to: '2026-03-30' })
    const on = toggleLookAhead(f(), '2026-03-02', 28)
    expect([on.from, on.to]).toEqual(['2026-03-02', '2026-03-30'])
    expect(filterChips(on, '2026-03-02').map(c => c.label)).toEqual(['4-week look-ahead'])
    const off = toggleLookAhead(on, '2026-03-02', 28)
    expect([off.from, off.to]).toEqual(['', ''])
    expect(toggleLookAhead(f(), null, 28)).toEqual(f())
  })
})

describe('describing the filter', () => {
  it('labels each condition and removes one by chip id', () => {
    const set = f({ text: 'EW', criticalOnly: true, codes: { Area: 'North' } })
    expect(filterChips(set, null).map(c => c.id)).toEqual(['text', 'crit', 'code:Area'])
    expect(withoutChip(set, 'code:Area').codes).toEqual({ Area: '' })
    expect(withoutChip(set, 'crit').criticalOnly).toBe(false)
    expect(emptyFilterHint(set)).toBe('Filtering by text “EW”, critical only, an activity code.')
    expect(emptyFilterHint(f())).toBe('This schedule has no activities to show.')
  })
})

describe('counted options', () => {
  it('counts constraints, notes and code values on this file', () => {
    const acts = [act(), act({ task_id: 2, cstr_type: 'CS_ALAP', activity_codes: [{ type: 'Area', code: 'East' }] } as Partial<Activity>)]
    const c = constraintOptions(acts)
    expect(c.find(o => o.value === 'any')!.count).toBe(1)
    expect(c.find(o => o.value === 'CS_ALAP')!.count).toBe(1)
    expect(noteOptions(acts, { 2: { note: 'x', severity: 'risk' } } as never).find(o => o.value === 'any')!.count).toBe(1)
    expect(codeValuesByType(acts, ['Area']).get('Area')).toEqual(['East', 'North'])
  })
})
