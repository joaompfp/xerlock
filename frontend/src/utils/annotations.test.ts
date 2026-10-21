import { describe, it, expect } from 'vitest'
import { matchesNoteFilter, NOTE_FILTER_LABELS, type Annotation } from './annotations'

describe('notes filter', () => {
  const risk: Annotation = { severity: 'risk', note: 'check access date', updatedAt: 0 }
  const plain: Annotation = { severity: null, note: 'ask the planner', updatedAt: 0 }

  it('passes everything when unset', () => {
    expect([undefined, risk, plain].every(a => matchesNoteFilter(a, ''))).toBe(true)
  })

  it('keeps every noted activity for "any"', () => {
    expect([undefined, risk, plain].map(a => matchesNoteFilter(a, 'any'))).toEqual([false, true, true])
  })

  it('matches one severity, or notes saved without one', () => {
    expect([undefined, risk, plain].map(a => matchesNoteFilter(a, 'risk'))).toEqual([false, true, false])
    expect([undefined, risk, plain].map(a => matchesNoteFilter(a, 'unflagged'))).toEqual([false, false, true])
  })

  it('labels each choice', () => {
    expect(Object.keys(NOTE_FILTER_LABELS)).toEqual(['any', 'query', 'risk', 'logic', 'resolved', 'unflagged'])
  })
})
