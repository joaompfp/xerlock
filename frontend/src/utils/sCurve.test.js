import { describe, it, expect } from 'vitest'
import { durationSCurve } from './sCurve'
import sample from './fixtures/sample-schedule.json'

const task = over => ({
  task_type: 'TT_Task', status: 'TK_NotStart', duration_hrs: 80, remain_duration_hrs: 80,
  calendar_hrs_per_day: 8, act_start: null, act_end: null, ...over,
})
const at = (curve, iso) => curve.points.find(p => p.t === new Date(iso).getTime())

describe('durationSCurve', () => {
  it('weights by original duration in days, not by activity count', () => {
    // One 30-day activity finished, one 10-day not started: 75% earned, not 50%.
    const c = durationSCurve([
      task({ duration_hrs: 240, remain_duration_hrs: 0, status: 'TK_Complete', act_start: '2026-01-05 08:00', act_end: '2026-02-13 16:00', target_start: '2026-01-05 08:00', target_end: '2026-02-13 16:00' }),
      task({ target_start: '2026-03-02 08:00', target_end: '2026-03-13 16:00', early_start: '2026-03-02 08:00', early_end: '2026-03-13 16:00' }),
    ], '2026-03-01 00:00')
    expect(c.totalDays).toBe(40)
    expect(at(c, '2026-03-01 00:00').actual).toBe(75)
    expect(c.points.at(-1).forecast).toBe(100)
  })

  it('earns an in-progress activity by original less remaining duration', () => {
    const c = durationSCurve([
      task({ status: 'TK_Active', remain_duration_hrs: 20, act_start: '2026-03-01 00:00', target_start: '2026-03-01 00:00', target_end: '2026-03-31 00:00', early_start: '2026-03-21 00:00', early_end: '2026-04-01 00:00' }),
    ], '2026-03-21 00:00')
    expect(at(c, '2026-03-21 00:00').actual).toBe(75)
    expect(at(c, '2026-03-21 00:00').forecast).toBe(75)
  })

  it('normalises calendars: a 24h-calendar day weighs the same as an 8h one', () => {
    const c = durationSCurve([task({ duration_hrs: 240, calendar_hrs_per_day: 24 }), task()], null)
    expect(c.totalDays).toBe(20)
  })

  it('ignores milestones and level of effort', () => {
    expect(durationSCurve([task({ task_type: 'TT_LOE' }), task({ task_type: 'TT_FinMile', duration_hrs: 0 })], null)).toBeNull()
  })

  it('a remaining estimate above the original shows as forecast growth past 100%', () => {
    const c = durationSCurve([
      task({ status: 'TK_Active', remain_duration_hrs: 120, act_start: '2026-03-01 00:00', target_start: '2026-03-01 00:00', target_end: '2026-03-14 00:00', early_start: '2026-03-10 00:00', early_end: '2026-04-01 00:00' }),
    ], '2026-03-10 00:00')
    expect(c.points.at(-1).forecast).toBe(150)
  })

  it('draws the sample from the data date with actual and forecast meeting there', () => {
    const c = durationSCurve(sample.activities, sample.project.data_date)
    const dd = c.points.find(p => p.t === c.dataDate)
    expect(dd.actual).toBe(dd.forecast)
    expect(c.points.at(-1).planned).toBe(100)
  })
})
