// Layered layout for the logic network: each activity's rank (its column along the
// logic) and its order within the rank, chosen to keep link crossings down. The
// classic Sugiyama steps, each in near-linear time, so a network of thousands of
// activities lays out in milliseconds:
//   1. break any logic loop (a corrupt file can carry one), keeping the rest a DAG;
//   2. rank by longest path from the starts, then pull each start up to just before its
//      first successor, so a side branch sits beside the chain it feeds, not at column 0;
//   3. order each rank by repeated barycentre sweeps (each node goes to the mean
//      position of its neighbours in the rank before/after), keeping the order with the
//      fewest crossings, counted with an accumulator tree (Barth, Jünger & Mutzel, 2002).

export interface Placed { rank: number; order: number }

/** Ranks and in-rank order for `nodes`, linked by `edges` [from, to]. Edges to nodes not
 *  in `nodes` are ignored. */
export function layerNetwork(nodes: number[], edges: [number, number][], sweeps = 24): Map<number, Placed> {
  const index = new Map<number, number>()
  nodes.forEach((id, i) => index.set(id, i))
  const n = nodes.length
  const succ: number[][] = Array.from({ length: n }, () => [])
  const pred: number[][] = Array.from({ length: n }, () => [])
  for (const [a, b] of edges) {
    const i = index.get(a), j = index.get(b)
    if (i === undefined || j === undefined || i === j) continue
    succ[i].push(j)
    pred[j].push(i)
  }

  // 1. Topological order (Kahn). When only loops remain, release the waiting node with
  //    the fewest unmet predecessors; the links that close its loop are then ignored.
  const indeg = pred.map(p => p.length)
  const topo: number[] = []
  const placed = new Uint8Array(n)
  const queue: number[] = []
  for (let i = 0; i < n; i++) if (indeg[i] === 0) queue.push(i)
  let head = 0
  while (topo.length < n) {
    if (head === queue.length) {
      let best = -1
      for (let i = 0; i < n; i++) if (!placed[i] && (best < 0 || indeg[i] < indeg[best])) best = i
      queue.push(best)
      indeg[best] = 0
    }
    const v = queue[head++]
    if (placed[v]) continue
    placed[v] = 1
    topo.push(v)
    for (const s of succ[v]) if (!placed[s] && --indeg[s] === 0) queue.push(s)
  }
  const pos = new Int32Array(n)
  topo.forEach((v, k) => { pos[v] = k })
  const forward = (a: number, b: number) => pos[a] < pos[b] // links that respect the order

  // 2. Ranks: longest path, then starts moved up beside their first successor.
  const rank = new Int32Array(n)
  for (const v of topo) for (const s of succ[v]) if (forward(v, s) && rank[s] < rank[v] + 1) rank[s] = rank[v] + 1
  for (let k = n - 1; k >= 0; k--) {
    const v = topo[k]
    if (pred[v].some(p => forward(p, v))) continue
    let first = Infinity
    for (const s of succ[v]) if (forward(v, s)) first = Math.min(first, rank[s])
    if (first !== Infinity) rank[v] = first - 1
  }
  let minRank = Infinity, maxRank = 0
  for (let i = 0; i < n; i++) minRank = Math.min(minRank, rank[i])
  for (let i = 0; i < n; i++) { rank[i] -= minRank; maxRank = Math.max(maxRank, rank[i]) }

  // 3. Order. Start from the topological order within each rank (a depth-first flavour:
  //    related activities start near each other), then sweep.
  const layers: number[][] = Array.from({ length: n ? maxRank + 1 : 0 }, () => [])
  for (const v of topo) layers[rank[v]].push(v)
  const at = new Float64Array(n) // position within its layer, normalised to 0..1
  const setPositions = (L: number[][]) => {
    for (const layer of L) layer.forEach((v, k) => { at[v] = layer.length > 1 ? k / (layer.length - 1) : 0.5 })
  }
  setPositions(layers)
  let best = layers.map(l => l.slice())
  let bestCross = crossings(layers, succ, rank)
  for (let it = 0; it < sweeps && bestCross > 0; it++) {
    const down = it % 2 === 0
    const order = down ? layers.keys() : [...layers.keys()].reverse()
    for (const r of order) {
      const layer = layers[r]
      const bary = new Map<number, number>()
      for (const v of layer) {
        const nbrs = down ? pred[v] : succ[v]
        let sum = 0, count = 0
        for (const u of nbrs) if (down ? rank[u] < r : rank[u] > r) { sum += at[u]; count++ }
        bary.set(v, count ? sum / count : at[v])
      }
      layer.sort((a, b) => bary.get(a)! - bary.get(b)!)
      layer.forEach((v, k) => { at[v] = layer.length > 1 ? k / (layer.length - 1) : 0.5 })
    }
    const c = crossings(layers, succ, rank)
    if (c < bestCross) { bestCross = c; best = layers.map(l => l.slice()) }
  }

  const out = new Map<number, Placed>()
  best.forEach(layer => layer.forEach((v, k) => out.set(nodes[v], { rank: rank[v], order: k })))
  return out
}

/** Link crossings between each pair of adjacent ranks (links spanning several ranks are
 *  left out of the count). Each pair is counted in O(E log V) with an accumulator tree. */
export function crossings(layers: number[][], succ: number[][], rank: Int32Array | number[]): number {
  let total = 0
  for (let r = 0; r + 1 < layers.length; r++) {
    const south = layers[r + 1]
    const southPos = new Map<number, number>()
    south.forEach((v, k) => southPos.set(v, k))
    const ends: number[] = []
    for (const v of layers[r]) {
      const targets: number[] = []
      for (const s of succ[v]) if (rank[s] === r + 1) targets.push(southPos.get(s)!)
      targets.sort((a, b) => a - b)
      ends.push(...targets)
    }
    let size = 1
    while (size < south.length) size *= 2
    const tree = new Int32Array(2 * size)
    for (const e of ends) {
      let i = e + size
      tree[i]++
      while (i > 1) {
        if (i % 2 === 0) total += tree[i + 1]
        i = Math.floor(i / 2)
        tree[i]++
      }
    }
  }
  return total
}
