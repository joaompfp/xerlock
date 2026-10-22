import { describe, it, expect, vi, beforeEach } from 'vitest'
import { trackDrag } from './drag'

// A minimal window: just the listener registry trackDrag uses.
const handlers = new Map<string, Set<(e: MouseEvent) => void>>()
beforeEach(() => {
  handlers.clear()
  globalThis.window = {
    addEventListener: (t: string, h: (e: MouseEvent) => void) => { if (!handlers.has(t)) handlers.set(t, new Set()); handlers.get(t)!.add(h) },
    removeEventListener: (t: string, h: (e: MouseEvent) => void) => { handlers.get(t)?.delete(h) },
  } as unknown as Window & typeof globalThis
})
const fire = (t: string, x = 0, y = 0) => { for (const h of [...(handlers.get(t) || [])]) h({ clientX: x, clientY: y } as MouseEvent) }

describe('trackDrag', () => {
  it('reports offsets from the start and ends once on release', () => {
    const moves: [number, number][] = []
    const end = vi.fn()
    trackDrag({ clientX: 10, clientY: 20 } as MouseEvent, (dx, dy) => moves.push([dx, dy]), end)
    fire('mousemove', 15, 18)
    fire('mouseup')
    fire('mousemove', 99, 99)
    expect(moves).toEqual([[5, -2]])
    expect(end).toHaveBeenCalledTimes(1)
    expect(handlers.get('mousemove')!.size + handlers.get('mouseup')!.size).toBe(0)
  })
  it('stops early without ending', () => {
    const end = vi.fn()
    const stop = trackDrag({ clientX: 0, clientY: 0 } as MouseEvent, () => {}, end)
    stop()
    fire('mouseup')
    expect(end).not.toHaveBeenCalled()
  })
})
