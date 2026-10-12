// Duration-weighted progress S-curve: how much of the programme's work, measured in
// original duration, was planned, has been earned, and is forecast, over time.
//
// Weight: original duration in working days (duration_hrs / the activity's hours per
// day), for task and resource-dependent activities. Milestones carry no duration; level
// of effort spans other work and would count it twice. Days rather than hours, so an
// activity on a 24-hour calendar weighs the same per day as one on an 8-hour calendar.
//
// Each activity's weight is spread linearly in calendar time across its window. Spreading
// in working time would move a little weight off weekends and holidays; at the monthly
// resolution plotted here the difference is small, and it keeps the curve independent of
// calendar decoding. Documented in docs/METHODOLOGY.md.

const WEIGHTED = new Set(['TT_Task', 'TT_Rsrc'])

function elapsed(start, end, t) {
  if (t >= end) return 1
  if (t <= start) return 0
  return (t - start) / (end - start)
}

const ms = d => (d ? new Date(d).getTime() : null)

/**
 * @returns null when nothing carries duration, else
 *   { points: [{ t, planned, actual, forecast }], totalDays, skipped, dataDate }
 *   planned/actual/forecast are % of total original duration; actual is null after the
 *   data date and forecast null before it.
 */
export function durationSCurve(activities, dataDate) {
  const dd = ms(dataDate)
  const items = []
  let totalDays = 0
  let skipped = 0
  for (const a of activities) {
    if (!WEIGHTED.has(a.task_type) || !(a.duration_hrs > 0)) continue
    const perDay = a.calendar_hrs_per_day || 8
    const od = a.duration_hrs / perDay
    const rd = Math.max(0, (a.remain_duration_hrs || 0) / perDay)
    totalDays += od
    const done = a.status === 'TK_Complete'
    // Earned: P6's duration % complete basis, original less remaining, never negative.
    const earned = done ? od : a.act_start ? Math.max(0, Math.min(od, od - rd)) : 0
    const planStart = ms(a.target_start)
    const planEnd = ms(a.target_end)
    if (planStart == null || planEnd == null) skipped++
    items.push({
      od,
      plan: planStart != null && planEnd != null ? [planStart, planEnd] : null,
      earned,
      earnedWin: a.act_start ? [ms(a.act_start), ms(a.act_end) ?? dd] : null,
      remaining: done ? 0 : rd,
      remainWin: a.early_start && a.early_end ? [ms(a.early_start), ms(a.early_end)] : null,
    })
  }
  if (!totalDays) return null

  const dates = [dd]
  for (const it of items) {
    if (it.plan) dates.push(...it.plan)
    if (it.remainWin) dates.push(...it.remainWin)
    if (it.earnedWin) dates.push(...it.earnedWin)
  }
  const known = dates.filter(d => d != null)
  const lo = new Date(Math.min(...known))
  const hi = new Date(Math.max(...known))

  // Month starts spanning the programme, plus the data date itself so the actual and
  // forecast lines meet exactly where the status was taken.
  const times = []
  let m = new Date(lo.getFullYear(), lo.getMonth(), 1)
  const end = new Date(hi.getFullYear(), hi.getMonth() + 1, 1)
  for (let guard = 0; m <= end && guard < 600; guard++) {
    times.push(m.getTime())
    m = new Date(m.getFullYear(), m.getMonth() + 1, 1)
  }
  if (dd != null && !times.includes(dd)) times.push(dd)
  times.sort((x, y) => x - y)

  const pct = v => Math.round((1000 * v) / totalDays) / 10
  const earnedAt = t => items.reduce((s, it) => s + (it.earnedWin ? it.earned * elapsed(it.earnedWin[0], it.earnedWin[1], t) : 0), 0)
  const earnedAtDD = dd != null ? earnedAt(dd) : null

  const points = times.map(t => ({
    t,
    planned: pct(items.reduce((s, it) => s + (it.plan ? it.od * elapsed(it.plan[0], it.plan[1], t) : 0), 0)),
    actual: dd != null && t <= dd ? pct(earnedAt(t)) : null,
    forecast: dd != null && t >= dd
      ? pct(earnedAtDD + items.reduce((s, it) => s + (it.remainWin ? it.remaining * elapsed(it.remainWin[0], it.remainWin[1], t) : 0), 0))
      : null,
  }))
  return { points, totalDays: Math.round(totalDays), skipped, dataDate: dd }
}
