import { describe, it, expect } from 'vitest'
import sample from './fixtures/sample-schedule.json'
import { runChecks, defaultConfig, weightedScore } from './healthChecks'

// Fixture: the backend's parse of examples/sample-schedule.xer (project + activities).
// tests/test_fixture.py fails when it drifts from the parser; it prints how to regenerate.
const counts = r => Object.fromEntries(Object.entries(r).map(([k, v]) => [k, v.count]))

describe('runChecks on the sample schedule', () => {
  const out = runChecks(sample, defaultConfig())

  it('produces the pinned finding counts', () => {
    expect(counts(out.results)).toMatchInlineSnapshot(`
      {
        "alap": 0,
        "cpli": 1,
        "cpt": 0,
        "driving": 0,
        "fs": 93,
        "hardcstr": 2,
        "highdur": 2,
        "highfloat": 5,
        "invdates": 0,
        "lags": 4,
        "leads": 0,
        "loe": 0,
        "missed": 4,
        "negfloat": 0,
        "noresource": 0,
        "oos": 2,
        "openends": 2,
      }
    `)
  })

  it('scores', () => {
    expect(weightedScore(out.results, defaultConfig())).toMatchInlineSnapshot(`53`)
  })
})

// Minimal synthetic schedules, one rule per test.
let nextId = 1
function act(over = {}) {
  return {
    task_id: nextId++, task_code: 'A' + nextId, task_type: 'TT_Task', status: 'TK_NotStart',
    predecessors: [], successors: [], total_float_hrs: 0, duration_hrs: 80, calendar_hrs_per_day: 8,
    cstr_type: null, cstr_type2: null, act_start: null, act_end: null, early_start: '2026-03-02 08:00:00',
    early_end: '2026-03-13 16:00:00', target_end: null, resource_names: [], is_critical: false,
    is_longest_path: false, is_negative_float: false, driving_path_flag: false, ...over,
  }
}
function link(pred, succ, type = 'PR_FS', lag = 0) {
  succ.predecessors.push({ task_id: pred.task_id, type, lag_hrs: lag })
  pred.successors.push({ task_id: succ.task_id, type, lag_hrs: lag })
}
const run = (activities, project = {}) =>
  runChecks({ activities, project: { data_date: '2026-03-02 08:00', has_resources: false, cpli: null, ...project } }, defaultConfig())

describe('DCMA rules', () => {
  it('exempts only the one project start and one project finish milestone', () => {
    const start = act({ task_type: 'TT_StartMile', early_start: '2026-03-02 08:00:00' })
    const stray = act({ task_type: 'TT_StartMile', early_start: '2026-04-01 08:00:00' })
    const work = act()
    const finish = act({ task_type: 'TT_FinMile' })
    link(start, work); link(stray, work); link(work, finish)
    expect(run([start, stray, work, finish]).openEnds.map(a => a.task_id)).toEqual([stray.task_id])
  })

  it('counts a finish tied only by SS as dangling', () => {
    const a = act(), b = act()
    const s = act({ task_type: 'TT_StartMile' }), f = act({ task_type: 'TT_FinMile' })
    link(s, a); link(a, b, 'PR_SS'); link(s, b); link(b, f)
    const open = run([s, a, b, f]).openEnds
    expect(open.map(x => [x.task_id, x.openFinish, x.dangling])).toEqual([[a.task_id, true, true]])
  })

  it('leaves completed work and LOE out of the population', () => {
    const done = act({ status: 'TK_Complete' })
    const loe = act({ task_type: 'TT_LOE' })
    const r = run([done, loe])
    expect(r.openEnds).toEqual([])
    expect(r.results.highdur.count).toBe(0)
  })

  it('counts every positive lag by default (DCMA 03), in the successor\'s calendar days', () => {
    const a = act(), b = act({ calendar_hrs_per_day: 10 })
    link(a, b, 'PR_FS', 10)
    expect(run([a, b]).relationshipStats.bigLags).toHaveLength(1)
    const cfg = defaultConfig(); cfg.lags.param = 1
    expect(runChecks({ activities: [a, b], project: { has_resources: false } }, cfg).relationshipStats.bigLags).toHaveLength(0)
  })

  it('treats Finish On or Before as hard, including as the secondary constraint', () => {
    const r = run([act({ cstr_type: 'CS_MSOA', cstr_type2: 'CS_MEOB' }), act({ cstr_type: 'CS_MSOA' })])
    expect(r.results.hardcstr.count).toBe(1)
  })

  it('counts late finishes as missed, not only open work (DCMA 11)', () => {
    const late = act({ status: 'TK_Complete', target_end: '2026-02-01 16:00:00', act_end: '2026-02-10 16:00:00' })
    const onTime = act({ status: 'TK_Complete', target_end: '2026-02-01 16:00:00', act_end: '2026-01-30 16:00:00' })
    const open = act({ status: 'TK_Active', target_end: '2026-02-20 16:00:00', act_start: '2026-02-01 08:00:00' })
    const r = run([late, onTime, open])
    expect(r.missedTasksList.map(a => a.task_id).sort()).toEqual([late.task_id, open.task_id].sort())
    expect(r.results.missed.value).toBeCloseTo(66.67, 1)
  })

  it('flags out-of-sequence progress on SS and FF links, not only FS', () => {
    const p = act({ act_start: '2026-02-10 08:00:00' })
    const ss = act({ act_start: '2026-02-05 08:00:00' })
    const ff = act({ act_start: '2026-02-01 08:00:00', act_end: '2026-02-20 16:00:00', status: 'TK_Complete' })
    link(p, ss, 'PR_SS'); link(p, ff, 'PR_FF')
    expect(run([p, ss, ff]).outOfSequenceList.map(r => r.type)).toEqual(['PR_SS', 'PR_FF'])
  })

  it('scores CPLI against 0.95 and marks the Critical Path Test as not performed', () => {
    const r = run([act()], { cpli: { value: 0.9 } })
    expect(r.results.cpli).toMatchObject({ value: 0.9, pass: false, included: true })
    expect(r.availability.cpt).toBe(false)
    expect(r.results.cpt.included).toBe(false)
  })
})
