// WBS roll-ups: each node summarises its own activities plus everything beneath it,
// so a reviewer can read a branch's shape (span, criticality, progress) without
// expanding it. A node showing only its activity count says nothing about whether
// that branch is in trouble.

import { displayStart, displayEnd } from './p6'

/** @returns Map<wbs_id, {activities, critical, start, finish, pct}> */
export function buildWbsRollups(tree, activities) {
  const byWbs = new Map()
  for (const a of activities) {
    if (!byWbs.has(a.wbs_id)) byWbs.set(a.wbs_id, [])
    byWbs.get(a.wbs_id).push(a)
  }

  const out = new Map()
  const walk = (node) => {
    const own = byWbs.get(node.wbs_id) || []
    let acts = [...own]
    for (const child of node.children || []) acts = acts.concat(walk(child))

    const starts = acts.map(displayStart).filter(Boolean)
    const ends = acts.map(displayEnd).filter(Boolean)
    // Weighted by nothing but headcount: an activity-count average is what the rest
    // of the app reports, so the branch figure matches the project figure's basis.
    const pct = acts.length
      ? Math.round(acts.reduce((s, a) => s + (a.pct_complete || 0), 0) / acts.length)
      : 0

    out.set(node.wbs_id, {
      activities: acts.length,
      critical: acts.filter(a => a.is_critical).length,
      start: starts.length ? starts.reduce((m, d) => (d < m ? d : m)) : null,
      finish: ends.length ? ends.reduce((m, d) => (d > m ? d : m)) : null,
      pct,
    })
    return acts
  }

  for (const root of tree || []) walk(root)
  return out
}
