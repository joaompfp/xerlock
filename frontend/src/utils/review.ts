// The review page's content: what the file is, the verdict, the findings that cost the
// most, the schedule's risks, the milestones and the reviewer's own notes, as plain
// data. One screen for someone who received a programme and must say what is wrong
// with it; built from the same checks and figures as the detailed views.

import type { Activity, Schedule } from '../types/schedule'
import type { Annotations, Severity } from './annotations'
import { CHECK_DEFS, runChecks, scoreBreakdown, weightedScore, type HealthConfig, type CheckKey } from './healthChecks'
import { milestoneTracker, type Milestone } from './milestones'
import { finishVerdict, longestPathStability, type FinishVerdict } from './compareChecks'
import { fileKind } from './source'

export interface Finding {
  key: CheckKey
  label: string
  /** What was measured against what: "8.3% of 21, target ≤ 5%". */
  measure: string
  pointsLost: number
}

export interface ReviewNote { code: string; name: string; severity: Severity | null; note: string }

export interface Review {
  kind: string
  activities: number
  dataDate: string | null
  finish: string | null
  longestPath: number
  complete: number
  score: number
  checksPassing: number
  checksIncluded: number
  pointsLost: number
  /** The failing checks, costliest first. */
  findings: Finding[]
  negativeFloat: number
  /** Incomplete activities with 0 < total float ≤ 10 days. */
  nearCritical: number
  cpli: { value: number; pathDays: number; finishFloatDays: number } | null
  /** Milestones not yet achieved, in forecast order. */
  milestonesAhead: Milestone[]
  milestonesAchieved: number
  notes: ReviewNote[]
  compare: { finishDeltaDays: number; earlierFinish: string | null; verdict: FinishVerdict; longestPathKept: string } | null
}

const DAY_MS = 86400000

function measure(key: CheckKey, r: { value: number; count: number; denom: number; display: number | string }, target: number): string {
  const d = CHECK_DEFS.find(c => c.key === key)!
  const t = `${d.cmp === 'gte' ? '≥' : '≤'} ${target}${d.unit === 'pct' ? '%' : ''}`
  if (d.unit === 'pct') return `${(Math.round(r.value * 10) / 10).toFixed(1)}% of ${r.denom}, target ${t}`
  if (d.unit === 'ratio') return `${r.display}, target ${t}`
  return `${r.count}, target ${t}`
}

export function buildReview(data: Schedule, cfg: HealthConfig, annotations: Annotations, compared: Schedule | null): Review {
  const { results } = runChecks(data, cfg)
  const shares = scoreBreakdown(results, cfg)
  const lostBy = new Map(shares.map(s => [s.key, s.lost]))
  const findings: Finding[] = CHECK_DEFS
    .filter(d => results[d.key].included && !results[d.key].pass)
    .map(d => ({ key: d.key, label: d.label, measure: measure(d.key, results[d.key], cfg[d.key].target), pointsLost: lostBy.get(d.key) ?? 0 }))
    .sort((a, b) => b.pointsLost - a.pointsLost)
  const acts = data.activities
  const hpd = (a: Activity) => a.calendar_hrs_per_day || 8
  const cpli = data.project.cpli
  const finAct = cpli ? acts.find(a => a.task_id === cpli.finish_task_id) : null
  const milestones = milestoneTracker(acts)
  let compare: Review['compare'] = null
  if (compared) {
    const cur = data.project.latest_end, base = compared.project.latest_end
    const delta = cur && base ? Math.round((new Date(cur).getTime() - new Date(base).getTime()) / DAY_MS) : 0
    const dd = data.project.data_date && compared.project.data_date
      ? Math.round((new Date(data.project.data_date).getTime() - new Date(compared.project.data_date).getTime()) / DAY_MS) : null
    const st = longestPathStability(compared, data)
    compare = { finishDeltaDays: delta, earlierFinish: base, verdict: finishVerdict(delta, st, dd), longestPathKept: `${st.retained}/${st.baseCount}` }
  }
  return {
    kind: fileKind(data.project),
    activities: acts.length,
    dataDate: data.project.data_date,
    finish: data.project.latest_end,
    longestPath: data.project.total_longest_path,
    complete: acts.filter(a => a.status === 'TK_Complete').length,
    score: weightedScore(results, cfg),
    checksPassing: CHECK_DEFS.filter(d => results[d.key].included && results[d.key].pass).length,
    checksIncluded: CHECK_DEFS.filter(d => results[d.key].included).length,
    pointsLost: shares.reduce((t, s) => t + s.lost, 0),
    findings,
    negativeFloat: data.project.total_negative_float,
    nearCritical: acts.filter(a => a.status !== 'TK_Complete' && a.total_float_hrs != null && a.total_float_hrs > 0 && a.total_float_hrs <= 10 * hpd(a)).length,
    cpli: cpli ? { value: cpli.value, pathDays: Math.round(cpli.cpl_hrs / (finAct ? hpd(finAct) : 8)), finishFloatDays: Math.round(cpli.tf_hrs / (finAct ? hpd(finAct) : 8)) } : null,
    milestonesAhead: milestones.filter(m => !m.achieved),
    milestonesAchieved: milestones.filter(m => m.achieved).length,
    notes: acts.filter(a => annotations[a.task_id]).map(a => ({
      code: a.task_code, name: a.task_name, severity: annotations[a.task_id].severity, note: annotations[a.task_id].note,
    })),
    compare,
  }
}
