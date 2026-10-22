<template>
  <div class="progress-wrap">
    <div class="view-bar">
      <div class="strip-title">
        <span class="strip-sub">Milestones, look-ahead window &amp; progress trend &middot; data date {{ dataDateObj ? formatDate(data.project.data_date) : 'unknown' }}</span>
      </div>
    </div>

    <!-- Milestone tracker -->
    <section class="progress-section">
      <div class="section-head-static">
        <span class="section-title">Milestone Tracker <em>({{ milestoneList.length }})</em></span>
        <span class="section-hint">Forecast vs target date for every milestone</span>
      </div>
      <div class="section-body">
        <div v-if="milestoneList.length === 0" class="empty-state">No milestones found.</div>
        <table v-else class="progress-table">
          <thead><tr><th>Code</th><th>Milestone</th><th class="num">Target</th><th class="num">Forecast</th><th class="num">Variance</th><th>Status</th></tr></thead>
          <tbody>
            <tr v-for="m in milestoneList" :key="m.task_id" class="jump-row" title="Show in Gantt" @click="$emit('jump', m.task_id)">
              <td class="code">{{ m.task_code }}</td>
              <td class="name-cell">{{ m.task_name }}</td>
              <td class="num-cell">{{ m.target ? formatDate(m.target) : '—' }}</td>
              <td class="num-cell">{{ m.forecast ? formatDate(m.forecast) : '—' }}</td>
              <td class="num-cell" :class="varianceClass(m)">{{ m.varianceDays == null ? '—' : (m.varianceDays > 0 ? '+' : '') + m.varianceDays + 'd' }}</td>
              <td><span class="status-chip" :class="'status-' + m.status">{{ statusLabels[m.status] }}</span></td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- Look-ahead window -->
    <section class="progress-section">
      <div class="section-head-static">
        <span class="section-title">Look-ahead Window <em>({{ lookaheadList.length }})</em></span>
        <span class="section-hint">Incomplete activities overlapping the next {{ lookaheadWeeks }} weeks from the data date</span>
        <div class="week-toggle">
          <button :class="{ active: lookaheadWeeks === 4 }" @click="lookaheadWeeks = 4">4 weeks</button>
          <button :class="{ active: lookaheadWeeks === 8 }" @click="lookaheadWeeks = 8">8 weeks</button>
        </div>
      </div>
      <div class="section-body">
        <div v-if="!dataDateObj" class="empty-state warn">No data date available in this file — look-ahead window can't be anchored.</div>
        <div v-else-if="lookaheadList.length === 0" class="empty-state">No incomplete activities fall within this window.</div>
        <table v-else class="progress-table">
          <thead><tr><th>Code</th><th>Activity</th><th class="num">Start</th><th class="num">Finish</th><th class="num">Float</th><th class="num">% Complete</th><th class="num">Remaining / Original</th></tr></thead>
          <tbody>
            <tr v-for="a in lookaheadList" :key="a.task_id" class="jump-row" title="Show in Gantt" @click="$emit('jump', a.task_id)" :class="{ critical: a.is_critical }">
              <td class="code">{{ a.task_code }}</td>
              <td class="name-cell">{{ a.task_name }}</td>
              <td class="num-cell">{{ formatDate(a.early_start) }}</td>
              <td class="num-cell">{{ formatDate(a.early_end) }}</td>
              <td class="num-cell" :class="a.is_negative_float ? 'lag-neg' : ''">{{ formatFloat(a.total_float_hrs, a.calendar_hrs_per_day) }}</td>
              <td class="num-cell">{{ a.pct_complete }}%</td>
              <td class="num-cell">{{ formatHours(a.remain_duration_hrs, a.calendar_hrs_per_day) }} / {{ formatHours(a.duration_hrs, a.calendar_hrs_per_day) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- Progress S-curve -->
    <section class="progress-section">
      <div class="section-head-static">
        <span class="section-title">Progress S-Curve</span>
        <span class="section-hint">Cumulative % of the programme's original duration (working days): planned, earned (original less remaining) and forecast (remaining work on its early dates)</span>
      </div>
      <div class="section-body">
        <p class="section-note">
          Weighted by duration across {{ curve ? curve.totalDays : 0 }} working days of task work; milestones and level of effort excluded.
          "Planned" uses {{ isProject ? "the file's Baseline 0 dates" : "this file's P6 planned dates, not a locked baseline" }}.
          <template v-if="curve && curve.skipped">{{ curve.skipped }} activities without planned dates are left out of the planned line.</template>
        </p>
        <div v-if="!curve || curve.points.length < 2" class="empty-state warn">Not enough date data to draw a trend.</div>
        <svg v-else :viewBox="`0 0 ${chartW} ${chartH}`" class="scurve-svg">
          <!-- Two gridlines, not six: 0% and 100% are the only ones that carry meaning.
               Everything else was chart furniture competing with the data. -->
          <line v-for="g in [0, 100]" :key="'g'+g" :x1="padL" :x2="chartW - padR" :y1="yFor(g)" :y2="yFor(g)" class="grid-line" />
          <text v-for="g in [0, 100]" :key="'gl'+g" :x="padL - 6" :y="yFor(g) + 3" class="axis-label" text-anchor="end">{{ g }}%</text>
          <text v-for="m in monthTicks" :key="'ml'+m.t" :x="xFor(m.t)" :y="chartH - 6" class="axis-label" text-anchor="middle">{{ monthLabel(m.t) }}</text>
          <!-- The shortfall is the shape between the lines, so it reads without
               subtracting two numbers. -->
          <path v-if="gapPath" :d="gapPath" class="curve-gap" />
          <path :d="pathOf('planned')" class="curve-planned" />
          <path :d="pathOf('forecast')" class="curve-forecast" />
          <path :d="pathOf('actual')" class="curve-actual" />
          <line v-if="ddPoint" :x1="xFor(ddPoint.t)" :x2="xFor(ddPoint.t)" :y1="padT" :y2="chartH - padB" class="data-date-line" />
          <text v-if="ddPoint" :x="xFor(ddPoint.t)" :y="padT - 4" class="axis-label data-date-label" text-anchor="middle">data date · {{ Math.round(ddPoint.actual ?? 0) }}% earned vs {{ Math.round(ddPoint.planned) }}% planned</text>
          <!-- Series named at the end of their own line, in their own colour: no legend
               to look away to and match up. -->
          <template v-if="endLabels">
            <text :x="endLabels.x" :y="endLabels.plannedY" class="series-label series-planned">Planned</text>
            <text :x="endLabels.x" :y="endLabels.forecastY" class="series-label series-forecast">Forecast {{ endLabels.forecastPct }}%</text>
          </template>
        </svg>
      </div>
    </section>
  </div>
</template>

<script lang="ts">
import { defineComponent, type PropType } from 'vue'
import { formatDate, formatHours, formatFloat, isMilestone, dateFormat } from '../utils/format'
import { displayEnd } from '../utils/p6'
import { durationSCurve, type SCurve, type SCurvePoint } from '../utils/sCurve'
import type { Activity, Schedule } from '../types/schedule'
import { isProjectFile } from '../utils/source'

const fmtMonthYear = dateFormat({ month: 'short', year: '2-digit' })

type MilestoneStatus = 'achieved' | 'on-track' | 'watch' | 'at-risk' | 'unknown'
type CurveSeries = 'planned' | 'actual' | 'forecast'

interface Milestone extends Activity {
  forecast: string | null
  target: string | null
  varianceDays: number | null
  achieved: boolean
  status: MilestoneStatus
}

const STATUS_LABELS: Record<MilestoneStatus, string> = { achieved: 'Achieved', 'on-track': 'On track', watch: 'Watch', 'at-risk': 'At risk', unknown: 'Unknown' }

export default defineComponent({
  name: 'ProgressView',
  props: {
    data: { type: Object as PropType<Schedule>, required: true },
  },
  emits: ['jump'],
  data() {
    return {
      lookaheadWeeks: 4,
      statusLabels: STATUS_LABELS,
      chartW: 900,
      chartH: 280,
      padL: 44,
      padR: 96,
      padT: 24,
      padB: 26,
    }
  },
  computed: {
    isProject(): boolean { return isProjectFile(this.data.project) },
    dataDateObj(): Date | null {
      return this.data.project.data_date ? new Date(this.data.project.data_date) : null
    },
    milestoneList(): Milestone[] {
      return this.data.activities
        .filter(isMilestone)
        .map(a => {
          const forecast = displayEnd(a) || a.act_start || a.early_start
          const target = a.target_end || a.target_start
          const achieved = a.status === 'TK_Complete' || !!a.act_end || !!a.act_start
          let varianceDays: number | null = null
          if (forecast && target) {
            varianceDays = Math.round((new Date(forecast).getTime() - new Date(target).getTime()) / 86400000)
          }
          let status: MilestoneStatus
          if (achieved) status = 'achieved'
          else if (varianceDays == null) status = 'unknown'
          else if (varianceDays <= 0) status = 'on-track'
          else if (varianceDays <= 10) status = 'watch'
          else status = 'at-risk'
          return { ...a, forecast, target, varianceDays, achieved, status }
        })
        .sort((x, y) => new Date(x.forecast || 0).getTime() - new Date(y.forecast || 0).getTime())
    },
    lookaheadList(): Activity[] {
      const start = this.dataDateObj
      if (!start) return []
      const end = new Date(start.getTime() + this.lookaheadWeeks * 7 * 86400000)
      return this.data.activities
        .filter(a => {
          if (a.status === 'TK_Complete') return false
          if (!a.early_start || !a.early_end) return false
          const es = new Date(a.early_start)
          const ee = new Date(a.early_end)
          return es <= end && ee >= start
        })
        // early_start is non-null here: the filter above drops activities without one.
        .sort((a, b) => new Date(a.early_start!).getTime() - new Date(b.early_start!).getTime())
    },
    curve(): SCurve | null {
      return durationSCurve(this.data.activities, this.data.project.data_date)
    },
    // Forecast growth (remaining above original) can run past 100%; keep it on the chart.
    yMax(): number {
      if (!this.curve) return 100
      return Math.max(100, ...this.curve.points.map(p => p.forecast ?? 0))
    },
    tRange(): [number, number] {
      const pts = this.curve?.points || []
      return pts.length ? [pts[0].t, pts[pts.length - 1].t] : [0, 1]
    },
    monthTicks(): SCurvePoint[] {
      const months = (this.curve?.points || []).filter(p => { const d = new Date(p.t); return d.getDate() === 1 && d.getHours() === 0 })
      const step = months.length > 18 ? 3 : months.length > 9 ? 2 : 1
      return months.filter((_, i) => i % step === 0)
    },
    ddPoint(): SCurvePoint | null | undefined {
      const c = this.curve
      return c && c.dataDate != null ? c.points.find(p => p.t === c.dataDate) : null
    },
    // Shortfall band: between planned and earned, up to the data date.
    gapPath(): string | null {
      const pts = (this.curve?.points || []).filter(p => p.actual != null)
      if (pts.length < 2) return null
      const up = pts.map(p => `${this.xFor(p.t)},${this.yFor(p.planned)}`)
      const down = pts.map(p => `${this.xFor(p.t)},${this.yFor(p.actual!)}`).reverse()
      return `M ${up.join(' L ')} L ${down.join(' L ')} Z`
    },
    endLabels(): { x: number; plannedY: number; forecastY: number; forecastPct: number } | null {
      const pts = this.curve?.points
      if (!pts || pts.length < 2) return null
      const last = pts[pts.length - 1]
      const plannedY = this.yFor(last.planned)
      const forecastY = this.yFor(last.forecast ?? last.planned)
      const close = Math.abs(plannedY - forecastY) < 12
      return {
        x: this.xFor(last.t) + 6,
        plannedY: close ? Math.min(plannedY, forecastY) - 3 : plannedY + 3,
        forecastY: close ? Math.max(plannedY, forecastY) + 11 : forecastY + 3,
        forecastPct: Math.round(last.forecast ?? last.planned),
      }
    },
  },
  methods: {
    formatDate,
    formatHours,
    formatFloat,
    varianceClass(m: Milestone): string {
      if (m.status === 'at-risk') return 'lag-neg'
      if (m.status === 'watch') return 'lag-warn'
      return ''
    },
    xFor(t: number): number {
      const [t0, t1] = this.tRange
      return this.padL + ((t - t0) / Math.max(1, t1 - t0)) * (this.chartW - this.padL - this.padR)
    },
    yFor(pct: number): number {
      return this.padT + (this.chartH - this.padT - this.padB) * (1 - pct / this.yMax)
    },
    pathOf(key: CurveSeries): string {
      const pts = (this.curve?.points || []).filter(p => p[key] != null)
      if (pts.length < 2) return ''
      return pts.map((p, i) => (i === 0 ? 'M' : 'L') + this.xFor(p.t).toFixed(1) + ',' + this.yFor(p[key]!).toFixed(1)).join(' ')
    },
    monthLabel(t: number): string {
      return fmtMonthYear(t)
    },
  },
})
</script>

<style scoped>
.progress-wrap { display: flex; flex-direction: column; background: var(--white); border: 1px solid var(--gray-300); border-radius: var(--radius-md); overflow: hidden; }

.progress-section { border-bottom: 1px solid var(--gray-300); }
.progress-section:last-child { border-bottom: none; }
.section-head-static { display: flex; align-items: center; gap: var(--space-4); padding: var(--space-3) var(--space-4); background: var(--gray-100); flex-wrap: wrap; }
.section-title { font-weight: 600; color: var(--ink); white-space: nowrap; }
.section-title em { font-style: normal; color: var(--accent); font-family: var(--font-mono); }
.section-hint { font: var(--text-small); color: var(--gray-700); flex: 1; }
.section-body { padding: var(--space-4); }
.section-note { font: var(--text-small); color: var(--gray-700); margin: 0 0 var(--space-4); font-style: italic; }
.empty-state { font: var(--text-small); color: var(--ok); }
.empty-state.warn { color: var(--near); }

.week-toggle { display: flex; gap: 2px; }
.week-toggle button { font: var(--text-small); padding: 4px 10px; border: 1px solid var(--gray-300); background: var(--white); cursor: pointer; }
.week-toggle button:first-child { border-radius: var(--radius-sm) 0 0 var(--radius-sm); }
.week-toggle button:last-child { border-radius: 0 var(--radius-sm) var(--radius-sm) 0; border-left: none; }
.week-toggle button.active { background: var(--accent-soft); color: var(--accent); border-color: var(--accent); font-weight: 700; }

.progress-table { width: 100%; border-collapse: collapse; font: var(--text-small); }
.progress-table th { text-align: left; font: var(--text-micro); text-transform: uppercase; color: var(--gray-700); background: var(--gray-100); border-bottom: 2px solid var(--gray-300); padding: var(--space-2) var(--space-3); }
.progress-table td { padding: 6px var(--space-3); border-bottom: 1px solid var(--gray-150); }
.jump-row { cursor: pointer; }
.jump-row:hover td { background: var(--accent-soft); }
.jump-row.critical td { border-left: 3px solid var(--crit); }
.code { font-family: var(--font-mono); font-weight: 600; color: var(--accent); white-space: nowrap; }
.name-cell { color: var(--ink-soft); }
.num-cell { font-family: var(--font-mono); text-align: right; white-space: nowrap; }
.lag-neg { color: var(--crit); font-weight: 700; }
.lag-warn { color: var(--near); font-weight: 700; }

.status-chip { font: var(--text-micro); padding: 1px 8px; border-radius: 10px; font-weight: 600; }
.status-achieved { background: var(--ok-tint); color: var(--ok); }
.status-on-track { background: var(--ok-tint); color: var(--ok); }
.status-watch { background: var(--near-tint); color: var(--near); }
.status-at-risk { background: var(--crit-tint); color: var(--crit); }
.status-unknown { background: var(--gray-150); color: var(--gray-700); }

.scurve-svg { width: 100%; height: auto; max-height: 320px; }
.grid-line { stroke: var(--gray-150); stroke-width: 1; }
.axis-label { font: var(--text-micro); fill: var(--gray-700); font-family: var(--font-mono); }
.data-date-line { stroke: var(--ink); stroke-width: 1.5; stroke-dasharray: 4 3; }
.data-date-label { fill: var(--ink); font-weight: 600; }
.curve-forecast { fill: none; stroke: var(--crit); stroke-width: 2; stroke-dasharray: 5 4; }
.series-forecast { fill: var(--crit); }
.curve-planned { fill: none; stroke: var(--ink-3); stroke-width: 2; }
.curve-actual { fill: none; stroke: var(--crit); stroke-width: 3; }
.curve-gap { fill: var(--crit-soft); stroke: none; }
.series-label { font-family: var(--font-mono); font-size: 11px; font-weight: 600; }
.series-planned { fill: var(--ink-3); }
.series-actual { fill: var(--crit); }
.scurve-legend { display: flex; gap: var(--space-5); margin-top: var(--space-2); }
.legend-item { display: flex; align-items: center; gap: 5px; font: var(--text-small); color: var(--gray-700); }
.swatch { width: 14px; height: 3px; display: inline-block; }
.swatch-planned { background: var(--active); }
.swatch-actual { background: var(--ok); }
</style>
