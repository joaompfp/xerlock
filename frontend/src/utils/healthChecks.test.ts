import { describe, it, expect } from 'vitest'
import fixture from './fixtures/sample-schedule.json'
import xmlFixture from './fixtures/sample-schedule-xml.json'
import { runChecks, defaultConfig, weightedScore } from './healthChecks'
import type { CheckResult } from './healthChecks'
import type { Activity, CriticalPathTest, ProjectSummary, Recalculation, ScheduleCore } from '../types/schedule'
import { makeActivity, makeSchedule, link } from '../testing/factories'

// Typed as the API contract: if the backend's output and types/schedule.ts disagree, the
// type check fails here.
const sample: ScheduleCore = fixture

// Fixture: the backend's parse of examples/sample-schedule.xer (project + activities).
// tests/test_fixture.py fails when it drifts from the parser; it prints how to regenerate.
const counts = (r: Record<string, CheckResult>) => Object.fromEntries(Object.entries(r).map(([k, v]) => [k, v.count]))

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
        "inactive": 0,
        "invdates": 0,
        "lags": 4,
        "leads": 0,
        "loe": 0,
        "manual": 0,
        "missed": 4,
        "negfloat": 0,
        "noresource": 0,
        "oddlags": 0,
        "oos": 2,
        "openends": 2,
        "recalc": 0,
        "summarylogic": 0,
      }
    `)
  })

  it('scores', () => {
    expect(weightedScore(out.results, defaultConfig())).toMatchInlineSnapshot(`58`)
  })
})

// Fixture: the backend's parse of examples/sample-schedule.xml, the same demo project as
// Project would save it, plus one manual task, one inactive task, one summary
// relationship and one deadline. tests/test_mspdi.py keeps it current.
const sampleXml: ScheduleCore = xmlFixture

describe('runChecks on the Project XML sample', () => {
  const out = runChecks(sampleXml, defaultConfig())

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
        "inactive": 1,
        "invdates": 0,
        "lags": 4,
        "leads": 0,
        "loe": 0,
        "manual": 1,
        "missed": 4,
        "negfloat": 0,
        "noresource": 0,
        "oddlags": 0,
        "oos": 2,
        "openends": 2,
        "recalc": 0,
        "summarylogic": 1,
      }
    `)
  })

  it('names what cannot be checked on a Project file, and why', () => {
    expect(out.isProjectFile).toBe(true)
    expect(out.availability.driving).toBe(false)
    expect(out.naReasons.driving).toMatch(/stores no Longest Path flag/)
    expect(out.availability.loe).toBe(false)
    // The sample keeps a manually scheduled task to demonstrate the check, so the
    // engine refuses it; its deadline and Finish No Later Than constraint are listed.
    expect(out.availability.recalc).toBe(false)
    expect(out.naReasons.recalc).toMatch(/not checkable: 1 manually scheduled task is incomplete/)
    expect(out.naReasons.cpt).toMatch(/withheld: 1 manually scheduled task/)
    expect(out.recalculation?.uncovered).toEqual(['deadlines', 'Finish No Later Than constraints'])
    expect(out.availability.manual).toBe(true)
    expect(out.availability.missed).toBe(true)   // the sample has a Baseline 0
  })

  it('scores', () => {
    expect(weightedScore(out.results, defaultConfig())).toMatchInlineSnapshot(`42`)
  })
})

// Minimal synthetic schedules, one rule per test.
const act = makeActivity
const run = (activities: Activity[], project: Partial<ProjectSummary> = {}) =>
  runChecks(makeSchedule(activities, project), defaultConfig())

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
    expect(runChecks(makeSchedule([a, b]), cfg).relationshipStats.bigLags).toHaveLength(0)
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

  it('scores CPLI against 0.95', () => {
    const r = run([act()], { cpli: { value: 0.9, cpl_hrs: 1000, tf_hrs: -100, finish_task_id: 1 } })
    expect(r.results.cpli).toMatchObject({ value: 0.9, pass: false, included: true })
  })
})

const recalc = (over: Partial<Recalculation> = {}): Recalculation => ({
  supported: true, reason: null,
  options: { progress_mode: 'retained', float_type: 'FT_FF', lag_calendar: 'rcal_Predecessor', delay_days: 600 },
  compared: 1, excluded: { complete: 0, wbs_summary: 0 }, differing: 0,
  by_field: { es: 0, ef: 0, ls: 0, lf: 0, tf: 0, ff: 0 }, differences: [], truncated: false,
  ...over,
})
const cptResult = (over: Partial<CriticalPathTest> = {}): CriticalPathTest => ({
  passed: true, exact: true, delay_days: 600, delay_hrs: 4800, tolerance_hrs: 0.02, calendars_uniform: true,
  delayed_task_id: 1, finish_task_id: 1, finish_before: '2026-03-13 16:00', finish_after: '2028-07-07 16:00',
  expected_delta_hrs: 4800, finish_delta_hrs: 4800, absorbed_by_task_id: null,
  ...over,
})

describe('recalculation and the Critical Path Test', () => {
  it('are not checkable on a schedule parsed before the engine existed', () => {
    const r = run([act()])
    expect(r.availability.recalc).toBe(false)
    expect(r.availability.cpt).toBe(false)
    expect(r.naReasons.cpt).toMatch(/not performed/)
  })

  it('counts the activities whose recalculation differs, and withholds the CPT', () => {
    const a = act()
    const diff = { task_id: a.task_id, field: 'ef', computed: '2026-03-16 16:00', stored: '2026-03-13 16:00', delta_hrs: 72 }
    const r = run([a], { recalculation: recalc({ differing: 1, by_field: { ef: 1 }, differences: [diff] }) })
    expect(r.results.recalc).toMatchObject({ count: 1, pass: false, included: true })
    expect(r.recalcDifferences).toEqual([{ ...diff, activity: a }])
    expect(r.availability.cpt).toBe(false)
    expect(r.naReasons.cpt).toMatch(/differs from P6 on 1 activity/)
  })

  it('reports the refusal reason when the engine declines the file', () => {
    const r = run([act()], { recalculation: recalc({ supported: false, reason: '2 resource-dependent activities (TT_Rsrc)' }) })
    expect(r.availability.recalc).toBe(false)
    expect(r.naReasons.recalc).toMatch(/resource-dependent/)
    expect(r.naReasons.cpt).toMatch(/withheld/)
  })

  it('withholds the CPT, naming the rules, when a Project file rests on uncovered rules', () => {
    const r = run([act()], { source_format: 'mpp', recalculation: recalc({
      options: { schedule_from: 'start', lag_calendar: 'rcal_Successor', critical_slack_limit_days: 0, multiple_critical_paths: false, delay_days: 600 },
      uncovered: ['deadlines', 'As Late As Possible constraints'],
    }) })
    expect(r.results.recalc).toMatchObject({ count: 0, pass: true, included: true })
    expect(r.availability.cpt).toBe(false)
    expect(r.naReasons.cpt).toMatch(/withheld: .*not validated \(deadlines, As Late As Possible constraints\)/)
  })

  it('scores a Project recalculation mismatch like a P6 one', () => {
    const a = act()
    const diff = { task_id: a.task_id, field: 'lf', computed: '2026-03-16 16:00', stored: '2026-03-13 16:00', delta_hrs: 72 }
    const r = run([a], { source_format: 'mspdi', recalculation: recalc({ differing: 1, by_field: { lf: 1 }, differences: [diff] }) })
    expect(r.results.recalc).toMatchObject({ count: 1, pass: false, included: true })
    expect(r.naReasons.cpt).toMatch(/differs from Microsoft Project on 1 activity/)
  })

  it('scores the CPT from the backend result: pass counts 0, fail counts 1', () => {
    const pass = run([act()], { recalculation: recalc(), critical_path_test: cptResult() })
    expect(pass.results.cpt).toMatchObject({ count: 0, pass: true, included: true, display: 'Pass' })
    const fail = run([act()], { recalculation: recalc(), critical_path_test: cptResult({ passed: false, finish_delta_hrs: 0, absorbed_by_task_id: 1 }) })
    expect(fail.results.cpt).toMatchObject({ count: 1, pass: false, included: true, display: 'Fail' })
    expect(fail.criticalPathTest?.absorbed_by_task_id).toBe(1)
  })
})

describe('Microsoft Project rules', () => {
  const msp = { source_format: 'mspdi' as const }

  it('are not applicable to a P6 file, and say so', () => {
    const out = run([act()])
    for (const k of ['manual', 'summarylogic', 'oddlags', 'inactive'] as const) {
      expect(out.availability[k]).toBe(false)
      expect(out.naReasons[k]).toMatch(/not applicable: a P6 file/)
    }
    expect(out.availability.loe).toBe(true)
  })

  it('counts manually scheduled tasks among incomplete work', () => {
    const out = run([act({ manual: true }), act({ manual: true, status: 'TK_Complete' }), act()], msp)
    expect(out.results.manual.count).toBe(1)
    expect(out.manualList.map(a => a.manual)).toEqual([true])
  })

  it('counts relationships on summary tasks from the backend list', () => {
    const summary_links = [{ pred_id: 1, pred_name: 'Phase', pred_is_summary: true, succ_id: 2, succ_name: 'Task', succ_is_summary: false, type: 'PR_FS', lag_hrs: 0 }]
    expect(run([act()], { ...msp, summary_links }).results.summarylogic.count).toBe(1)
  })

  it('lists elapsed and percentage lags, not ordinary ones', () => {
    const a = act(), b = act(), c = act(), d = act()
    link(a, b, 'PR_FS', 8); b.predecessors[0].lag_elapsed = true
    link(a, c, 'PR_FS', 8); c.predecessors[0].lag_pct = 50
    link(a, d, 'PR_FS', 8)
    const out = run([a, b, c, d], msp)
    expect(out.results.oddlags.count).toBe(2)
    expect(out.relationshipStats.oddLags.map(l => [l.elapsed, l.pct])).toEqual([[true, null], [false, 50]])
  })

  it('reports inactive tasks as a count, from the backend', () => {
    expect(run([act()], { ...msp, inactive_activities: 3 }).results.inactive.count).toBe(3)
  })

  it('withholds the date checks without a status date, and Missed Tasks without a baseline', () => {
    const noDate = run([act()], { ...msp, data_date: null })
    expect(noDate.availability.invdates).toBe(false)
    expect(noDate.naReasons.invdates).toMatch(/no status date/)
    const noBaseline = run([act({ target_end: null })], msp)
    expect(noBaseline.availability.missed).toBe(false)
    expect(noBaseline.naReasons.missed).toMatch(/no Baseline 0/)
    expect(run([act({ target_end: '2026-02-20 16:00:00' })], msp).availability.missed).toBe(true)
  })

  it('does not run the driving cross-check or LOE on a Project file', () => {
    const out = run([act({ task_type: 'TT_LOE', is_critical: true })], msp)
    expect(out.availability.driving).toBe(false)
    expect(out.availability.loe).toBe(false)
  })
})
