// Schedule health checks, as pure functions of the parsed schedule and the user's
// check configuration. Kept out of the Vue component so every rule can be read,
// unit-tested and audited in one place; docs/METHODOLOGY.md cites this file.

import { HARD_CONSTRAINT_TYPES } from './p6'

// Bumped when a default changes meaning (v2: Lags became DCMA 03's "any positive
// lag"), so a saved configuration from the old definition is not silently reused.
export const CFG_VERSION = 2

// One row per check: unit 'pct' evaluates the percentage against target, 'count' the raw
// count, 'ratio' the value itself. cmp 'lte' = at most, 'gte' = at least. param is the
// check's own threshold (working days). source says where the rule comes from: the
// DCMA 14-Point Assessment metric it implements, or 'XERlock' for an addition. Targets
// and weights are user-editable because contracts specify their own; the defaults are
// DCMA's.
export const CHECK_DEFS = [
  { key: 'openends', source: 'DCMA 01', label: 'Logic (open ends)', section: 'openEnds', unit: 'pct', cmp: 'lte', target: 5, weight: 2 },
  { key: 'leads', source: 'DCMA 02', label: 'Leads', section: 'rel', unit: 'count', cmp: 'lte', target: 0, weight: 1 },
  { key: 'lags', source: 'DCMA 03', label: 'Lags', section: 'rel', unit: 'pct', cmp: 'lte', target: 5, weight: 1, param: 0, paramLabel: 'Lag over (days)' },
  { key: 'fs', source: 'DCMA 04', label: 'FS Relationships', section: 'rel', unit: 'pct', cmp: 'gte', target: 90, weight: 1 },
  { key: 'hardcstr', source: 'DCMA 05', label: 'Hard Constraints', section: 'constraints', unit: 'pct', cmp: 'lte', target: 5, weight: 1 },
  { key: 'highfloat', source: 'DCMA 06', label: 'High Float', section: 'highfloat', unit: 'pct', cmp: 'lte', target: 5, weight: 1, param: 44, paramLabel: 'Float over (days)' },
  { key: 'negfloat', source: 'DCMA 07', label: 'Negative Float', section: 'negfloat', unit: 'count', cmp: 'lte', target: 0, weight: 2 },
  { key: 'highdur', source: 'DCMA 08', label: 'High Duration', section: 'highdur', unit: 'pct', cmp: 'lte', target: 5, weight: 1, param: 44, paramLabel: 'Duration over (days)' },
  { key: 'invdates', source: 'DCMA 09', label: 'Invalid Dates', section: 'invdates', unit: 'count', cmp: 'lte', target: 0, weight: 1 },
  { key: 'noresource', source: 'DCMA 10', label: 'Missing Resources', section: 'resources', unit: 'pct', cmp: 'lte', target: 5, weight: 1 },
  { key: 'missed', source: 'DCMA 11', label: 'Missed Tasks', section: 'missed', unit: 'pct', cmp: 'lte', target: 5, weight: 1 },
  { key: 'cpt', source: 'DCMA 12', label: 'Critical Path Test', section: null, unit: 'count', cmp: 'lte', target: 0, weight: 1, naReason: 'not performed: it re-runs the schedule, and XERlock reads P6\'s dates without rescheduling' },
  { key: 'cpli', source: 'DCMA 13', label: 'CPLI', section: null, unit: 'ratio', cmp: 'gte', target: 0.95, weight: 1 },
  { key: 'oos', source: 'XERlock', label: 'Out-of-Sequence', section: 'oos', unit: 'count', cmp: 'lte', target: 0, weight: 1 },
  { key: 'alap', source: 'XERlock', label: 'ALAP Constraints', section: 'alap', unit: 'count', cmp: 'lte', target: 0, weight: 1 },
  { key: 'loe', source: 'XERlock', label: 'LOE on Critical', section: 'loe', unit: 'count', cmp: 'lte', target: 0, weight: 1 },
  { key: 'driving', source: 'XERlock', label: 'Driving Path Cross-Check', section: 'driving', unit: 'count', cmp: 'lte', target: 0, weight: 1 },
]

// DCMA's population for its percentage metrics: incomplete activities, less
// level-of-effort and WBS-summary activities (which carry no logic of their own).
// Milestones stay in: they carry logic and constraints like any task.
export function inScope(a) {
  return a.status !== 'TK_Complete' && a.task_type !== 'TT_LOE' && a.task_type !== 'TT_WBS'
}

const TASK_TYPES = new Set(['TT_Task', 'TT_Rsrc'])
const hrsPerDay = a => a.calendar_hrs_per_day || 8

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

  const scope = acts.filter(inScope)

  // DCMA 01: an activity needs a predecessor and a successor. Dangling logic (GAO
  // Schedule Assessment Guide, BP 2) counts too: a start tied only by FF/SF links, or a
  // finish tied only by SS/SF links, is as free to move as one with no link at all.
  // Exempt: the one project start milestone and the one project finish milestone.
  const firstStart = scope
    .filter(a => a.task_type === 'TT_StartMile' && !a.predecessors.length)
    .sort((x, y) => (x.early_start < y.early_start ? -1 : 1))[0]
  const lastFinish = scope
    .filter(a => a.task_type === 'TT_FinMile' && !a.successors.length)
    .sort((x, y) => (x.early_end > y.early_end ? -1 : 1))[0]
  const openEnds = []
  for (const a of scope) {
    const startTied = a.predecessors.some(p => p.type === 'PR_FS' || p.type === 'PR_SS')
    const finishTied = a.successors.some(s => s.type === 'PR_FS' || s.type === 'PR_FF')
    // A start milestone has no finish to tie, a finish milestone no start.
    const flagStart = !startTied && a !== firstStart && a.task_type !== 'TT_FinMile'
    const flagFinish = !finishTied && a !== lastFinish && a.task_type !== 'TT_StartMile'
    if (flagStart || flagFinish) {
      openEnds.push({
        ...a,
        openStart: flagStart,
        openFinish: flagFinish,
        bothOpen: flagStart && flagFinish,
        dangling: (flagStart && a.predecessors.length > 0) || (flagFinish && a.successors.length > 0),
      })
    }
  }

  const relationshipStats = (() => {
    const counts = {}
    const leads = []
    const bigLags = []
    // DCMA 02-04 count the relationships of incomplete work: a lag on a link
    // between two finished activities can no longer move anything.
    const lagOverDays = cfg.lags.param ?? 0
    let total = 0
    for (const a of scope) {
      for (const p of a.predecessors) {
        total++
        counts[p.type] = (counts[p.type] || 0) + 1
        if (p.lag_hrs < 0) leads.push({ succ: a, predId: p.task_id, type: p.type, lag: p.lag_hrs })
        else if (p.lag_hrs > 0 && p.lag_hrs / hrsPerDay(a) > lagOverDays) bigLags.push({ succ: a, predId: p.task_id, type: p.type, lag: p.lag_hrs })
      }
    }
    leads.sort((x, y) => x.lag - y.lag)
    bigLags.sort((x, y) => y.lag - x.lag)
    const pctFs = total ? Math.round((100 * (counts.PR_FS || 0)) / total) : 100
    return { total, counts, leads, bigLags, pctFs }
  })()

  // Primary and secondary constraint both count: P6 applies both.
  const constraintList = acts
    .filter(a => a.cstr_type || a.cstr_type2)
    .map(a => ({
      ...a,
      hard: HARD_CONSTRAINT_TYPES.has(a.cstr_type) || HARD_CONSTRAINT_TYPES.has(a.cstr_type2),
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

  const negativeFloatList = scope
    .filter(a => a.is_negative_float)
    .sort((a, b) => a.total_float_hrs - b.total_float_hrs)

  const highFloatTh = cfg.highfloat.param ?? 44
  const highFloatList = scope
    .filter(a => a.total_float_hrs !== null && a.total_float_hrs / hrsPerDay(a) > highFloatTh)
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

  // DCMA 11: of the activities planned to finish by the data date, the share that did
  // not finish on time — still open, or finished after the planned date. DCMA plans
  // against the baseline; a single .xer has none, so "planned" is P6's Planned Finish
  // (target_end), which P6 moves with the forecast on unstarted work. Read it as a
  // check against the current plan, not a baseline BEI.
  const plannedDone = dd ? acts.filter(a => a.target_end && new Date(a.target_end) <= dd) : []
  const plannedDoneCount = plannedDone.length
  const missedTasksList = plannedDone
    .filter(a => a.status !== 'TK_Complete' || (a.act_end && new Date(a.act_end) > new Date(a.target_end)))
    .sort((a, b) => (a.target_end < b.target_end ? -1 : 1))

  const highDurTh = cfg.highdur.param ?? 44
  const highDurationList = scope
    .filter(a => TASK_TYPES.has(a.task_type) && a.duration_hrs / hrsPerDay(a) > highDurTh)
    .sort((a, b) => b.duration_hrs - a.duration_hrs)

  const loeOnCriticalList = acts.filter(a => a.task_type === 'TT_LOE' && (a.is_critical || a.is_longest_path))

  const drivingPathAvailable = acts.some(a => a.driving_path_flag)
  const drivingMismatchList = drivingPathAvailable ? acts.filter(a => a.driving_path_flag !== a.is_longest_path) : []

  // Progress that contradicts the logic: the successor did, by its actual dates, what the
  // relationship says it could not do yet. FS: started before the predecessor finished.
  // SS: started before the predecessor started. FF: finished before it finished.
  const before = (x, y) => !y || new Date(x) < new Date(y)
  const OOS_RULES = {
    PR_FS: (a, p) => a.act_start && before(a.act_start, p.act_end) && { what: 'Started before predecessor finished', predDate: p.act_end },
    PR_SS: (a, p) => a.act_start && before(a.act_start, p.act_start) && { what: 'Started before predecessor started', predDate: p.act_start },
    PR_FF: (a, p) => a.act_end && before(a.act_end, p.act_end) && { what: 'Finished before predecessor finished', predDate: p.act_end },
  }
  const outOfSequenceList = []
  for (const a of acts) {
    for (const link of a.predecessors) {
      const pred = byId.get(link.task_id)
      const hit = pred && OOS_RULES[link.type]?.(a, pred)
      if (hit) outOfSequenceList.push({ activity: a, predecessor: pred, type: link.type, ...hit })
    }
  }

  const noResourceList = data.project.has_resources
    ? scope.filter(a => TASK_TYPES.has(a.task_type) && a.resource_names.length === 0)
    : []

  const availability = {
    openends: true, leads: true, lags: true, fs: true, hardcstr: true, alap: true, negfloat: true,
    highfloat: true, highdur: true, oos: true, loe: true,
    invdates: !!dd,
    missed: !!dd,
    driving: drivingPathAvailable,
    noresource: data.project.has_resources,
    // DCMA 12 extends the critical path by a test delay and re-runs the schedule. That
    // needs a CPM engine; XERlock reads P6's computed dates and does not reschedule.
    cpt: false,
    cpli: !!data.project.cpli,
  }

  // Per-check measurement: count of findings, the value the target is compared
  // against (a % of the check's own denominator, or the raw count), and pass/fail.
  const nAct = scope.length || 1
  const nRel = relationshipStats.total || 1
  const cpli = data.project.cpli?.value
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
    cpt: { count: 0, denom: 1 },
    cpli: { count: cpli ?? 0, denom: 1, valueOverride: cpli ?? 0, displayOverride: cpli != null ? cpli.toFixed(2) : '—' },
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
