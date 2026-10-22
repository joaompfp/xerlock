// The Gantt's row model: which rows the chart shows (WBS headers and activities, in
// outline order, after expansion and filters), where each bar sits, how activities are
// classed, and the relationship lines between visible rows. Pure functions of the
// schedule and the view settings — no component state — so the chart's structure is
// unit-tested rather than only eyeballed, and the component only draws it.

import type { Activity, WbsNode } from '../types/schedule'
import { displayStart, displayEnd } from './p6'
import { isMilestone } from './format'

/** WBS ids, plus the synthetic group holding activities with no known WBS. */
export type WbsKey = number | '__unassigned'
export const UNASSIGNED: WbsKey = '__unassigned'

export type CriticalBasis = 'tf0' | 'longest'

export const NEAR_CRITICAL_HRS = 80 // 10 working days
const FLOAT_TAIL_MAX_DAYS = 26

// baseFinish: the latest compared finish of the activities under the node that the
// compared schedule also has (null without a compared schedule or with none in common).
export interface Rollup { start: Date | null; finish: Date | null; baseFinish: Date | null; count: number }

export interface WbsRow {
  type: 'wbs'
  key: string
  wbsId: WbsKey
  level: number
  name: string
  count: number
  start?: Date | null
  finish?: Date | null
  baseFinish?: Date | null
  index: number
}

export interface ActivityRow {
  type: 'activity'
  key: string
  level: number
  activity: Activity
  milestone: boolean
  x: number
  w: number
  tailW: number
  cls: string
  index: number
}

export type Row = WbsRow | ActivityRow
type UnindexedRow = Omit<WbsRow, 'index'> | Omit<ActivityRow, 'index'>

export type ToX = (date: string | null | undefined) => number | null

// ── WBS tree ────────────────────────────────────────────────────────────────

function walkTree(nodes: WbsNode[], visit: (n: WbsNode, level: number, parent: WbsNode | null) => void, level = 0, parent: WbsNode | null = null) {
  for (const n of nodes) {
    visit(n, level, parent)
    walkTree(n.children || [], visit, level + 1, n)
  }
}

export function wbsParentMap(tree: WbsNode[]): Map<number, number> {
  const m = new Map<number, number>()
  walkTree(tree, (n, _l, p) => { if (p) m.set(n.wbs_id, p.wbs_id) })
  return m
}

export function wbsIds(tree: WbsNode[]): Set<number> {
  const s = new Set<number>()
  walkTree(tree, n => s.add(n.wbs_id))
  return s
}

/** Every WBS key the chart can expand, the unassigned group included. */
export function allWbsKeys(tree: WbsNode[]): Set<WbsKey> {
  const s = new Set<WbsKey>(wbsIds(tree))
  s.add(UNASSIGNED)
  return s
}

export function wbsNodesByLevel(tree: WbsNode[]): { id: number; level: number }[] {
  const out: { id: number; level: number }[] = []
  walkTree(tree, (n, level) => out.push({ id: n.wbs_id, level }))
  return out
}

/** The first outline level open, as a file is first shown. */
export function initialExpanded(tree: WbsNode[]): Set<WbsKey> {
  return new Set<WbsKey>(tree.map(n => n.wbs_id))
}

/** Activities grouped by WBS, each group in start order (code breaking ties). */
export function activitiesByWbs(activities: Activity[]): Map<number, Activity[]> {
  const map = new Map<number, Activity[]>()
  for (const a of activities) {
    if (!map.has(a.wbs_id)) map.set(a.wbs_id, [])
    map.get(a.wbs_id)!.push(a)
  }
  for (const list of map.values()) {
    list.sort((a, b) => {
      const da = displayStart(a) || ''
      const db = displayStart(b) || ''
      if (da !== db) return da < db ? -1 : 1
      return a.task_code < b.task_code ? -1 : a.task_code > b.task_code ? 1 : 0
    })
  }
  return map
}

/** Start, finish and count under each WBS node, over the activities `matchFn` keeps. */
export function computeRollups(
  tree: WbsNode[],
  byWbs: Map<number, Activity[]>,
  baselineByCode: Map<string, Activity> | null,
  matchFn: ((a: Activity) => boolean) | null,
): Map<number, Rollup> {
  const map = new Map<number, Rollup>()
  const visit = (node: WbsNode): Rollup => {
    let start: Date | null = null, finish: Date | null = null, baseFinish: Date | null = null, count = 0
    for (const a of byWbs.get(node.wbs_id) || []) {
      if (matchFn && !matchFn(a)) continue
      count++
      const b = baselineByCode?.get(a.task_code)
      const be = b ? displayEnd(b) : null
      if (be) {
        const d = new Date(be)
        if (!baseFinish || d > baseFinish) baseFinish = d
      }
      const ds = displayStart(a)
      const de = displayEnd(a)
      if (ds) {
        const d = new Date(ds)
        if (!start || d < start) start = d
      }
      if (de) {
        const d = new Date(de)
        if (!finish || d > finish) finish = d
      }
    }
    for (const child of node.children || []) {
      const r = visit(child)
      count += r.count
      if (r.start && (!start || r.start < start)) start = r.start
      if (r.finish && (!finish || r.finish > finish)) finish = r.finish
      if (r.baseFinish && (!baseFinish || r.baseFinish > baseFinish)) baseFinish = r.baseFinish
    }
    const roll = { start, finish, baseFinish, count }
    map.set(node.wbs_id, roll)
    return roll
  }
  for (const root of tree) visit(root)
  return map
}

// ── Activities ──────────────────────────────────────────────────────────────

export function isBasisCritical(a: Activity, basis: CriticalBasis): boolean {
  return basis === 'longest' ? a.is_longest_path : a.is_critical
}

/** The bar's class: critical / near / other on the chosen basis, plus `negative`. */
export function classifyActivity(a: Activity, basis: CriticalBasis): string {
  const base = isBasisCritical(a, basis)
    ? 'critical'
    : (basis === 'tf0' && a.total_float_hrs != null && a.total_float_hrs > 0 && a.total_float_hrs <= NEAR_CRITICAL_HRS ? 'near' : 'other')
  // Negative float means the activity is already behind an imposed date — flag it
  // regardless of critical basis, since that's a property of the activity itself.
  return a.is_negative_float ? `${base} negative` : base
}

/** The float cell's severity band, the same bands as the bars. */
export function floatClass(a: Activity): string {
  if (a.total_float_hrs == null) return ''
  if (a.total_float_hrs < 0) return 'fl-neg'
  if (a.total_float_hrs === 0) return 'fl-crit'
  if (a.total_float_hrs <= NEAR_CRITICAL_HRS) return 'fl-near'
  return ''
}

export function buildActivityRow(a: Activity, level: number, toX: ToX, dayWidth: number, basis: CriticalBasis): Omit<ActivityRow, 'index'> {
  const milestone = isMilestone(a)
  const x = toX(displayStart(a))
  const xEnd = toX(displayEnd(a))
  const w = milestone ? 0 : Math.max((xEnd ?? x ?? 0) - (x ?? 0), 3)
  // Slack drawn as a dashed tail off the bar end: float becomes something you see
  // in the chart, not a number to look up. Capped so a 200-day tail can't dominate.
  const tfDays = a.total_float_hrs != null ? a.total_float_hrs / (a.calendar_hrs_per_day || 8) : 0
  const tailW = tfDays > 0 && tfDays <= FLOAT_TAIL_MAX_DAYS ? Math.round(tfDays * dayWidth) : 0
  return {
    type: 'activity' as const, key: 'a' + a.task_id, level, activity: a,
    milestone, x: x ?? 0, w, tailW, cls: classifyActivity(a, basis),
  }
}

// ── Rows ────────────────────────────────────────────────────────────────────

export interface RowInputs {
  tree: WbsNode[]
  activities: Activity[]
  byWbs: Map<number, Activity[]>
  rollups: Map<number, Rollup>
  /** The match set while a filter is on; null shows everything. */
  matched: Set<number> | null
  isExpanded: (id: WbsKey) => boolean
  activityRow: (a: Activity, level: number) => Omit<ActivityRow, 'index'>
}

/** The chart's rows in outline order. While filtering, WBS nodes with no match are
 *  dropped and only matching activities are listed. */
export function buildRows(p: RowInputs): Row[] {
  const rows: UnindexedRow[] = []
  const matched = p.matched
  const walk = (nodes: WbsNode[], level: number) => {
    const sorted = [...nodes].sort((a, b) => a.seq_num - b.seq_num)
    for (const node of sorted) {
      const roll = p.rollups.get(node.wbs_id) || { start: null, finish: null, baseFinish: null, count: 0 }
      if (matched && roll.count === 0) continue
      rows.push({
        type: 'wbs',
        key: 'w' + node.wbs_id,
        wbsId: node.wbs_id,
        level,
        name: node.wbs_short_name ? `${node.wbs_short_name} ${node.wbs_name}` : node.wbs_name,
        count: roll.count,
        start: roll.start,
        finish: roll.finish,
        baseFinish: roll.baseFinish,
      })
      if (p.isExpanded(node.wbs_id)) {
        walk(node.children || [], level + 1)
        for (const a of p.byWbs.get(node.wbs_id) || []) {
          if (matched && !matched.has(a.task_id)) continue
          rows.push(p.activityRow(a, level + 1))
        }
      }
    }
  }
  walk(p.tree, 0)

  const known = wbsIds(p.tree)
  const orphansAll = p.activities.filter(a => !known.has(a.wbs_id))
  const orphans = matched ? orphansAll.filter(a => matched.has(a.task_id)) : orphansAll
  if (orphans.length) {
    rows.push({ type: 'wbs', key: 'w-unassigned', wbsId: UNASSIGNED, level: 0, name: '(Unassigned)', count: orphans.length })
    if (p.isExpanded(UNASSIGNED)) {
      for (const a of orphans) rows.push(p.activityRow(a, 1))
    }
  }

  rows.forEach((r, i) => { (r as Row).index = i })
  return rows as Row[]
}

export function rowIndexByTaskId(rows: Row[]): Map<number, number> {
  const m = new Map<number, number>()
  for (const r of rows) if (r.type === 'activity') m.set(r.activity.task_id, r.index)
  return m
}

// ── Relationship lines and the progress line ────────────────────────────────

export interface Link {
  id: string
  d: string
  chain: boolean
  /** The rows' vertical span the link covers, so a drawn window can pick the ones crossing it. */
  yMin: number
  yMax: number
}

export interface LinkOptions {
  /** Draw only links between two critical activities (on `basis`). */
  criticalOnly: boolean
  basis: CriticalBasis
  toX: ToX
  rowHeight: number
}

/** Elbow paths from each visible predecessor's finish to its successor's start. A link
 *  between two critical activities is solid; any other is drawn as a `chain` link. */
export function buildLinks(rows: Row[], indexByTask: Map<number, number>, o: LinkOptions): Link[] {
  const out: Link[] = []
  for (const row of rows) {
    if (row.type !== 'activity') continue
    if (o.criticalOnly && !isBasisCritical(row.activity, o.basis)) continue
    for (const p of row.activity.predecessors || []) {
      const predIdx = indexByTask.get(p.task_id)
      if (predIdx === undefined) continue
      const predRow = rows[predIdx] as ActivityRow // indexByTask only indexes activity rows
      const bothCritical = isBasisCritical(row.activity, o.basis) && isBasisCritical(predRow.activity, o.basis)
      if (o.criticalOnly && !bothCritical) continue
      const predX = o.toX(displayEnd(predRow.activity))
      const predY = predIdx * o.rowHeight + o.rowHeight / 2
      const succX = row.x
      const succY = row.index * o.rowHeight + o.rowHeight / 2
      if (predX === null || succX === null) continue
      const midX = predX + 8
      out.push({
        id: `${p.task_id}-${row.activity.task_id}-${p.type}-${out.length}`,
        d: `M${predX},${predY} L${midX},${predY} L${midX},${succY} L${succX},${succY}`,
        chain: !bothCritical,
        yMin: Math.min(predY, succY),
        yMax: Math.max(predY, succY),
      })
    }
  }
  return out
}

/** One point per bar at its percent-complete position, for the progress line. */
export function progressPoints(rows: Row[], rowHeight: number): { x: number; y: number }[] {
  const pts: { x: number; y: number }[] = []
  for (const row of rows) {
    if (row.type !== 'activity' || row.milestone) continue
    pts.push({ x: row.x + row.w * (row.activity.pct_complete / 100), y: row.index * rowHeight + rowHeight / 2 })
  }
  return pts
}
