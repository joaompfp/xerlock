// Schedule health checks, as pure functions of the parsed schedule and the user's
// check configuration. Kept out of the Vue component so every rule can be read,
// unit-tested and audited in one place; docs/METHODOLOGY.md cites this file.

import { HARD_CONSTRAINT_TYPES } from './p6'

export const CFG_VERSION = 1

// One row per check: unit 'pct' evaluates the percentage against target, 'count' the raw
// count. cmp 'lte' = at most, 'gte' = at least. param is the check's own threshold (days).
// Defaults follow DCMA-14 conventions where one exists; targets/weights are user-editable
// because contracts specify their own.
export const CHECK_DEFS = [
  { key: 'openends', label: 'Open Ends', section: 'openEnds', unit: 'pct', cmp: 'lte', target: 5, weight: 2 },
  { key: 'leads', label: 'Leads', section: 'rel', unit: 'count', cmp: 'lte', target: 0, weight: 1 },
  { key: 'lags', label: 'Large Lags', section: 'rel', unit: 'pct', cmp: 'lte', target: 5, weight: 1, param: 10, paramLabel: 'Lag over (days)' },
  { key: 'fs', label: 'FS Relationships', section: 'rel', unit: 'pct', cmp: 'gte', target: 90, weight: 1 },
  { key: 'hardcstr', label: 'Hard Constraints', section: 'constraints', unit: 'pct', cmp: 'lte', target: 5, weight: 1 },
  { key: 'alap', label: 'ALAP Constraints', section: 'alap', unit: 'count', cmp: 'lte', target: 0, weight: 1 },
  { key: 'negfloat', label: 'Negative Float', section: 'negfloat', unit: 'count', cmp: 'lte', target: 0, weight: 2 },
  { key: 'highfloat', label: 'High Float', section: 'highfloat', unit: 'pct', cmp: 'lte', target: 5, weight: 1, param: 44, paramLabel: 'Float over (days)' },
  { key: 'invdates', label: 'Invalid Dates', section: 'invdates', unit: 'count', cmp: 'lte', target: 0, weight: 1 },
  { key: 'missed', label: 'Missed Tasks', section: 'missed', unit: 'pct', cmp: 'lte', target: 5, weight: 1 },
  { key: 'highdur', label: 'High Duration', section: 'highdur', unit: 'pct', cmp: 'lte', target: 5, weight: 1, param: 44, paramLabel: 'Duration over (days)' },
  { key: 'oos', label: 'Out-of-Sequence', section: 'oos', unit: 'count', cmp: 'lte', target: 0, weight: 1 },
  { key: 'loe', label: 'LOE on Critical', section: 'loe', unit: 'count', cmp: 'lte', target: 0, weight: 1 },
  { key: 'driving', label: 'Driving Mismatches', section: 'driving', unit: 'count', cmp: 'lte', target: 0, weight: 1 },
  { key: 'noresource', label: 'Missing Resources', section: 'resources', unit: 'pct', cmp: 'lte', target: 5, weight: 1 },
]

export function defaultConfig() {
  const cfg = {}
  for (const d of CHECK_DEFS) {
    cfg[d.key] = { enabled: true, target: d.target, weight: d.weight }
    if (d.param !== undefined) cfg[d.key].param = d.param
  }
  return cfg
}

export function runChecks(data, cfg) {
  const acts = data.activities
  const byId = new Map(acts.map(a => [a.task_id, a]))
  const dd = data.project.data_date ? new Date(data.project.data_date) : null

  const openEnds = []
  for (const a of acts) {
    const noPred = a.predecessors.length === 0
    const noSucc = a.successors.length === 0
    const flagStart = noPred && a.task_type !== 'TT_StartMile'
    const flagFinish = noSucc && a.task_type !== 'TT_FinMile'
    if (flagStart || flagFinish) {
      openEnds.push({ ...a, openStart: flagStart, openFinish: flagFinish, bothOpen: flagStart && flagFinish })
    }
  }

  const relationshipStats = (() => {
    const counts = {}
    const leads = []
    const bigLags = []
    const largeLagHrs = (cfg.lags.param || 10) * 8
    let total = 0
    for (const a of acts) {
      for (const p of a.predecessors) {
        total++
        counts[p.type] = (counts[p.type] || 0) + 1
        if (p.lag_hrs < 0) leads.push({ succ: a, predId: p.task_id, type: p.type, lag: p.lag_hrs })
        else if (p.lag_hrs > largeLagHrs) bigLags.push({ succ: a, predId: p.task_id, type: p.type, lag: p.lag_hrs })
      }
    }
    leads.sort((x, y) => x.lag - y.lag)
    bigLags.sort((x, y) => y.lag - x.lag)
    const pctFs = total ? Math.round((100 * (counts.PR_FS || 0)) / total) : 100
    return { total, counts, leads, bigLags, pctFs }
  })()

  const constraintList = acts
    .filter(a => a.cstr_type)
    .map(a => ({
      ...a,
      hard: HARD_CONSTRAINT_TYPES.has(a.cstr_type),
      criticalOnlyByConstraint: a.is_critical && !a.is_longest_path,
    }))
    .sort((a, b) => (b.hard === a.hard ? 0 : b.hard ? 1 : -1))

  // As Late As Possible schedules an activity against its late dates, consuming the
  // float it would otherwise show. On the critical path that is worth challenging:
  // the activity may be critical because of the constraint, not because of logic.
  const alapList = acts
    .filter(a => a.cstr_type === 'CS_ALAP' || a.cstr_type2 === 'CS_ALAP')
    .map(a => ({ ...a, onCriticalPath: a.is_critical || a.is_longest_path }))
    .sort((a, b) => (b.onCriticalPath ? 1 : 0) - (a.onCriticalPath ? 1 : 0))
  const alapOnCriticalPath = alapList.filter(a => a.onCriticalPath)

  const negativeFloatList = acts
    .filter(a => a.is_negative_float)
    .sort((a, b) => a.total_float_hrs - b.total_float_hrs)

  const highFloatTh = cfg.highfloat.param ?? 44
  const highFloatList = acts
    .filter(a => a.status !== 'TK_Complete' && a.total_float_hrs !== null
      && a.total_float_hrs / (a.calendar_hrs_per_day || 8) > highFloatTh)
    .sort((a, b) => b.total_float_hrs - a.total_float_hrs)

  const invalidDatesList = []
  if (dd) {
    for (const a of acts) {
      const issues = []
      if (a.act_start && new Date(a.act_start) > dd) issues.push('Actual start after data date')
      if (a.act_end && new Date(a.act_end) > dd) issues.push('Actual finish after data date')
      if (!a.act_start && a.early_start && new Date(a.early_start) < dd) issues.push('Forecast start before data date')
      if (!a.act_end && a.early_end && new Date(a.early_end) < dd) issues.push('Forecast finish before data date')
      if (issues.length) invalidDatesList.push({ ...a, issues })
    }
  }

  // Denominator for the missed-tasks percentage: everything the schedule's own planned
  // dates said would be finished by now (BEI-style, but against the current plan — a
  // .xer carries no separate baseline).
  const plannedDoneCount = dd ? acts.filter(a => a.target_end && new Date(a.target_end) < dd).length : 0
  const missedTasksList = dd
    ? acts
      .filter(a => a.status !== 'TK_Complete' && a.target_end && new Date(a.target_end) < dd)
      .sort((a, b) => (a.target_end < b.target_end ? -1 : 1))
    : []

  const highDurTh = cfg.highdur.param ?? 44
  const highDurationList = acts
    .filter(a => a.task_type === 'TT_Task' && a.duration_hrs / (a.calendar_hrs_per_day || 8) > highDurTh)
    .sort((a, b) => b.duration_hrs - a.duration_hrs)

  const loeOnCriticalList = acts.filter(a => a.task_type === 'TT_LOE' && (a.is_critical || a.is_longest_path))

  const drivingPathAvailable = acts.some(a => a.driving_path_flag)
  const drivingMismatchList = drivingPathAvailable ? acts.filter(a => a.driving_path_flag !== a.is_longest_path) : []

  const outOfSequenceList = []
  for (const a of acts) {
    if (!a.act_start) continue
    for (const p of a.predecessors) {
      if (p.type !== 'PR_FS') continue
      const pred = byId.get(p.task_id)
      if (!pred) continue
      if (!pred.act_end || new Date(pred.act_end) > new Date(a.act_start)) {
        outOfSequenceList.push({ activity: a, predecessor: pred })
      }
    }
  }

  const noResourceList = data.project.has_resources
    ? acts.filter(a => a.task_type === 'TT_Task' && a.status !== 'TK_Complete' && a.resource_names.length === 0)
    : []

  const availability = {
    openends: true, leads: true, lags: true, fs: true, hardcstr: true, alap: true, negfloat: true,
    highfloat: true, highdur: true, oos: true, loe: true,
    invdates: !!dd,
    missed: !!dd,
    driving: drivingPathAvailable,
    noresource: data.project.has_resources,
  }

  // Per-check measurement: count of findings, the value the target is compared
  // against (a % of the check's own denominator, or the raw count), and pass/fail.
  const nAct = acts.length || 1
  const nRel = relationshipStats.total || 1
  const raw = {
    openends: { count: openEnds.length, denom: nAct },
    leads: { count: relationshipStats.leads.length, denom: nRel },
    lags: { count: relationshipStats.bigLags.length, denom: nRel },
    fs: { count: relationshipStats.pctFs, denom: 100, valueOverride: relationshipStats.pctFs, displayOverride: relationshipStats.pctFs + '%' },
    hardcstr: { count: constraintList.filter(c => c.hard).length, denom: nAct },
    alap: { count: alapList.length, denom: nAct },
    negfloat: { count: negativeFloatList.length, denom: nAct },
    highfloat: { count: highFloatList.length, denom: nAct },
    invdates: { count: invalidDatesList.length, denom: nAct },
    missed: { count: missedTasksList.length, denom: plannedDoneCount || 1 },
    highdur: { count: highDurationList.length, denom: nAct },
    oos: { count: outOfSequenceList.length, denom: nAct },
    loe: { count: loeOnCriticalList.length, denom: nAct },
    driving: { count: drivingMismatchList.length, denom: nAct },
    noresource: { count: noResourceList.length, denom: nAct },
  }
  const results = {}
  for (const def of CHECK_DEFS) {
    const r = raw[def.key]
    const c = cfg[def.key]
    const value = r.valueOverride !== undefined
      ? r.valueOverride
      : def.unit === 'pct' ? (100 * r.count) / r.denom : r.count
    const pass = def.cmp === 'gte' ? value >= c.target : value <= c.target
    results[def.key] = {
      count: r.count,
      value,
      pass,
      display: r.displayOverride !== undefined ? r.displayOverride : r.count,
      included: c.enabled && availability[def.key],
    }
  }

  return {
    openEnds, relationshipStats, constraintList, alapList, alapOnCriticalPath, negativeFloatList,
    highFloatList, invalidDatesList, plannedDoneCount, missedTasksList, highDurationList,
    loeOnCriticalList, drivingPathAvailable, drivingMismatchList, outOfSequenceList, noResourceList,
    availability, results,
  }
}

// Share of included checks' weight that passes, 0-100.
export function weightedScore(results, cfg) {
  let wTotal = 0
  let wPass = 0
  for (const d of CHECK_DEFS) {
    if (!results[d.key].included) continue
    const w = Math.max(0, cfg[d.key].weight || 0)
    wTotal += w
    if (results[d.key].pass) wPass += w
  }
  return wTotal ? Math.round((100 * wPass) / wTotal) : 100
}
