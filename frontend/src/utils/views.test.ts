import { describe, it, expect, beforeEach } from 'vitest'
import { loadViews, saveViews, completeState, stepView, type SavedView, type ViewState } from './views'

const state = (over: Partial<ViewState> = {}): ViewState => ({
  zoom: 'week', dayWidthOverride: null, criticalBasis: 'tf0', showLinks: true, linksScope: 'critical',
  showProgressLine: false, showBaseline: true, showMarkup: true, showSlipArrows: false, filterText: '', filterStatus: '',
  filterConstraint: '', filterNotes: '', filterCriticalOnly: false, filterFrom: '', filterTo: '',
  filterCodes: {}, isolatedCodes: null, expandedWbs: [], filterCollapsed: [], groupsOn: [],
  leftDate: null, topRowKey: null, ...over,
})
const view = (id: string): SavedView => ({ id, name: id, savedAt: 0, state: state() })

describe('saved views storage', () => {
  const mem = new Map<string, string>()
  beforeEach(() => {
    mem.clear()
    globalThis.localStorage = {
      getItem: (k: string) => mem.get(k) ?? null,
      setItem: (k: string, v: string) => { mem.set(k, v) },
    } as Storage
  })

  it('round-trips per project', () => {
    saveViews('P', [view('a'), view('b')])
    expect(loadViews('P').map(v => v.id)).toEqual(['a', 'b'])
    expect(loadViews('Q')).toEqual([])
  })

  it('drops malformed entries and survives junk', () => {
    mem.set('schedule-app:views:P', JSON.stringify([view('ok'), { id: 1 }, null, { id: 'x', name: 'no state' }]))
    expect(loadViews('P').map(v => v.id)).toEqual(['ok'])
    mem.set('schedule-app:views:P', '{oops')
    expect(loadViews('P')).toEqual([])
  })
})

describe('completeState', () => {
  it('keeps what was saved and fills the rest from the chart', () => {
    const out = completeState({ zoom: 'month', filterCriticalOnly: true }, state({ zoom: 'day', showLinks: false }))
    expect(out.zoom).toBe('month')
    expect(out.filterCriticalOnly).toBe(true)
    expect(out.showLinks).toBe(false)
  })
})

describe('stepView', () => {
  const vs = [view('a'), view('b'), view('c')]
  it('moves one step without wrapping', () => {
    expect(stepView(vs, 'b', 1)?.id).toBe('c')
    expect(stepView(vs, 'b', -1)?.id).toBe('a')
    expect(stepView(vs, 'c', 1)).toBeNull()
    expect(stepView(vs, 'a', -1)).toBeNull()
  })
  it('starts at the first view when none is current', () => {
    expect(stepView(vs, null, 1)?.id).toBe('a')
    expect(stepView([], null, 1)).toBeNull()
  })
})

describe('filter ⇄ view', () => {
  it('round-trips and keeps only the file\'s code categories', async () => {
    const { filterToView, filterFromView } = await import('./views')
    const f = { text: 'EW', status: 'TK_Active', constraint: 'hard', notes: 'any' as const, criticalOnly: true, from: '2026-01-01', to: '', codes: { Area: 'North' } }
    const s = state({ ...filterToView(f), filterCodes: { Area: 'North', Gone: 'x' } })
    expect(filterFromView(s, ['Area', 'Phase'])).toEqual({ ...f, codes: { Area: 'North', Phase: '' } })
  })
})

describe('project zoom', () => {
  it('is remembered per project and null for a new one', async () => {
    const mem = new Map<string, string>()
    globalThis.localStorage = { getItem: (k: string) => mem.get(k) ?? null, setItem: (k: string, v: string) => { mem.set(k, v) } } as Storage
    const { loadProjectZoom, saveProjectZoom } = await import('./views')
    expect(loadProjectZoom('A')).toBeNull()
    saveProjectZoom('A', { zoom: 'week', dayWidthOverride: 4.2 })
    expect(loadProjectZoom('A')).toEqual({ zoom: 'week', dayWidthOverride: 4.2 })
    expect(loadProjectZoom('B')).toBeNull()
    mem.set('schedule-app:gantt-zoom:C', '{"zoom":3}')
    expect(loadProjectZoom('C')).toBeNull()
  })
})
