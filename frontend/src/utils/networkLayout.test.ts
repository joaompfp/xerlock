import { describe, it, expect } from 'vitest'
import { layerNetwork, crossings } from './networkLayout'

const ranks = (m: Map<number, { rank: number }>) => Object.fromEntries([...m].map(([id, p]) => [id, p.rank]))

describe('layerNetwork', () => {
  it('ranks a chain left to right', () => {
    expect(ranks(layerNetwork([1, 2, 3], [[1, 2], [2, 3]]))).toEqual({ 1: 0, 2: 1, 3: 2 })
  })
  it('puts a successor after its longest predecessor path', () => {
    // 1→2→3→4 and 1→4: 4 sits after 3, not beside 2.
    expect(layerNetwork([1, 2, 3, 4], [[1, 2], [2, 3], [3, 4], [1, 4]]).get(4)!.rank).toBe(3)
  })
  it('pulls a side branch up beside the activity it feeds', () => {
    // 9 feeds only 3: it belongs in the column before 3, not at the start.
    expect(layerNetwork([1, 2, 3, 9], [[1, 2], [2, 3], [9, 3]]).get(9)!.rank).toBe(1)
  })
  it('survives a logic loop and still places every node', () => {
    const m = layerNetwork([1, 2, 3, 4], [[1, 2], [2, 3], [3, 2], [3, 4]])
    expect(m.size).toBe(4)
    expect(m.get(1)!.rank).toBeLessThan(m.get(4)!.rank)
  })
  it('orders a rank to undo crossings', () => {
    // a→d, b→c laid out naively crosses; the sweep uncrosses it.
    const m = layerNetwork([1, 2, 3, 4], [[1, 4], [2, 3]])
    expect(m.get(1)!.order < m.get(2)!.order).toBe(m.get(4)!.order < m.get(3)!.order)
  })
  it('handles nothing and lone activities', () => {
    expect(layerNetwork([], []).size).toBe(0)
    expect(ranks(layerNetwork([5, 6], []))).toEqual({ 5: 0, 6: 0 })
  })
})

describe('crossings', () => {
  it('counts crossings between adjacent ranks like a brute-force count', () => {
    // Random bipartite layers, compared with the O(E²) definition.
    let seed = 1
    const rnd = (n: number) => { seed = (seed * 16807) % 2147483647; return seed % n }
    for (let t = 0; t < 50; t++) {
      const north = Array.from({ length: 2 + rnd(6) }, (_, i) => i)
      const south = Array.from({ length: 2 + rnd(6) }, (_, i) => 100 + i)
      const succ: number[][] = []; const rank: number[] = []
      north.forEach(v => { rank[v] = 0; succ[v] = [] })
      south.forEach(v => { rank[v] = 1; succ[v] = [] })
      const edges: [number, number][] = []
      for (const v of north) for (const w of south) if (rnd(3) === 0) { succ[v].push(w); edges.push([v, w]) }
      let brute = 0
      for (const [a, b] of edges) for (const [c, d] of edges) {
        if (north.indexOf(a) < north.indexOf(c) && south.indexOf(b) > south.indexOf(d)) brute++
      }
      expect(crossings([north, south], succ, rank)).toBe(brute)
    }
  })
})
