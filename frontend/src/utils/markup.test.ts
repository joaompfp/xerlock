import { describe, it, expect, beforeEach } from 'vitest'
import { loadMarkup, saveMarkup, nextColor, periodSpan, highlightColors, toggleMember, MARK_COLORS, type HighlightGroup } from './markup'

describe('markup storage', () => {
  const mem = new Map<string, string>()
  beforeEach(() => {
    mem.clear()
    globalThis.localStorage = {
      getItem: (k: string) => mem.get(k) ?? null,
      setItem: (k: string, v: string) => { mem.set(k, v) },
    } as Storage
  })

  it('round-trips per project', () => {
    const m = {
      keyDates: [{ id: 'a', date: '2026-08-03', label: 'Client access', color: 'teal' as const }],
      periods: [{ id: 'b', from: '2026-08-10', to: '2026-08-21', label: 'Shutdown', color: 'amber' as const }],
      groups: [{ id: 'g', label: 'Delay path', color: 'rose' as const, on: true, codes: ['A1', 'A2'] }],
      texts: [{ id: 't', at: '2026-05-04T00:00:00.000Z', y: 120, text: 'Area A handed over late', color: 'slate' as const }],
    }
    saveMarkup('P1', m)
    expect(loadMarkup('P1')).toEqual(m)
    expect(loadMarkup('P2')).toEqual({ keyDates: [], periods: [], groups: [], texts: [] })
  })

  it('drops malformed entries instead of failing', () => {
    mem.set('schedule-app:markup:P', JSON.stringify({
      keyDates: [{ id: 'x', date: 'soon', label: 'bad', color: 'teal' }, { id: 'y', date: '2026-01-01', label: 'ok', color: 'slate' }],
      periods: [{ id: 'z', from: '2026-01-01', to: '2026-01-02', label: 'bad colour', color: 'neon' }],
    }))
    const m = loadMarkup('P')
    expect(m.keyDates.map(k => k.id)).toEqual(['y'])
    expect(m.texts).toEqual([])
    expect(m.periods).toEqual([])
  })

  it('survives unreadable storage', () => {
    mem.set('schedule-app:markup:P', '{not json')
    expect(loadMarkup('P')).toEqual({ keyDates: [], periods: [], groups: [], texts: [] })
  })
})

describe('markup helpers', () => {
  it('cycles the palette', () => {
    expect(MARK_COLORS.map(nextColor)).toEqual([...MARK_COLORS.slice(1), MARK_COLORS[0]])
  })

  it('reads a backwards period the right way round', () => {
    expect(periodSpan({ from: '2026-05-10', to: '2026-05-01' })).toEqual({ from: '2026-05-01', to: '2026-05-10' })
  })
})

describe('highlight groups', () => {
  const g = (id: string, color: HighlightGroup['color'], on: boolean, codes: string[]): HighlightGroup => ({ id, label: id, color, on, codes })

  it('colours members of switched-on groups only, first group winning', () => {
    const m = highlightColors([g('a', 'rose', true, ['X', 'Y']), g('b', 'teal', true, ['Y', 'Z']), g('c', 'amber', false, ['W'])])
    expect([...m.entries()]).toEqual([['X', 'rose'], ['Y', 'rose'], ['Z', 'teal']])
  })

  it('is empty when nothing is on', () => {
    expect(highlightColors([g('a', 'rose', false, ['X'])]).size).toBe(0)
  })

  it('toggles membership', () => {
    const a = g('a', 'rose', true, ['X'])
    expect(toggleMember(a, 'Y').codes).toEqual(['X', 'Y'])
    expect(toggleMember(a, 'X').codes).toEqual([])
  })

  it('reads markup saved before groups existed', () => {
    globalThis.localStorage = { getItem: () => JSON.stringify({ keyDates: [], periods: [] }), setItem: () => {} } as unknown as Storage
    expect(loadMarkup('old').groups).toEqual([])
    expect(loadMarkup('old').texts).toEqual([])
  })
})
