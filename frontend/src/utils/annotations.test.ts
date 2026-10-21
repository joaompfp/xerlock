import { describe, it, expect } from 'vitest'
import { matchesNoteFilter, NOTE_FILTER_LABELS, saveAnnotation, setCallout, DEFAULT_CALLOUT, type Annotation } from './annotations'

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

describe('callouts', () => {
  const mem = new Map<string, string>()
  globalThis.localStorage = {
    getItem: (k: string) => mem.get(k) ?? null,
    setItem: (k: string, v: string) => { mem.set(k, v) },
  } as Storage

  it('opens, keeps through a text edit, and closes', () => {
    saveAnnotation('P', 7, { severity: 'risk', note: 'first' })
    expect(setCallout('P', 7, { dx: 40.4, dy: -12.6 })[7].callout).toEqual({ dx: 40, dy: -13 })
    expect(saveAnnotation('P', 7, { severity: 'query', note: 'edited' })[7].callout).toEqual({ dx: 40, dy: -13 })
    expect(setCallout('P', 7, null)[7].callout).toBeUndefined()
  })

  it('ignores a task without a note', () => {
    expect(setCallout('P', 99, DEFAULT_CALLOUT)[99]).toBeUndefined()
  })
})
