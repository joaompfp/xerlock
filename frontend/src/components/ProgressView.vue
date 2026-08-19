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
        <span class="section-hint">Cumulative % of activities planned to finish (target dates) vs actually finished (actual dates)</span>
      </div>
      <div class="section-body">
        <p class="section-note">"Planned" uses this file's current target dates, not a locked baseline — re-upload an earlier snapshot and compare visually if you need a true baseline trend.</p>
        <div v-if="sCurve.months.length < 2" class="empty-state warn">Not enough date data to draw a trend.</div>
        <svg v-else :viewBox="`0 0 ${chartW} ${chartH}`" class="scurve-svg">
          <line v-for="g in 5" :key="'g'+g" :x1="padL" :x2="chartW - padR" :y1="yFor(g * 20)" :y2="yFor(g * 20)" class="grid-line" />
          <text v-for="g in 5" :key="'gl'+g" :x="padL - 6" :y="yFor(g * 20) + 3" class="axis-label" text-anchor="end">{{ g * 20 }}%</text>
          <template v-for="(m, i) in sCurve.months" :key="'ml'+i">
            <text v-if="i % monthLabelStep === 0" :x="xFor(i)" :y="chartH - 6" class="axis-label" text-anchor="middle">{{ monthLabel(m) }}</text>
          </template>
          <line v-if="dataDateX != null" :x1="dataDateX" :x2="dataDateX" :y1="padT" :y2="chartH - padB" class="data-date-line" />
          <text v-if="dataDateX != null" :x="dataDateX" :y="padT - 2" class="axis-label data-date-label" text-anchor="middle">Data date</text>
          <path :d="pathFor(sCurve.planned)" class="curve-planned" />
          <path :d="pathFor(sCurve.actual)" class="curve-actual" />
        </svg>
        <div class="scurve-legend">
          <span class="legend-item"><i class="swatch swatch-planned"></i>Planned</span>
          <span class="legend-item"><i class="swatch swatch-actual"></i>Actual</span>
        </div>
      </div>
    </section>
  </div>
</template>

<script>
import { formatDate, formatHours, formatFloat, isMilestone } from '../utils/format'
import { displayEnd } from '../utils/p6'

const STATUS_LABELS = { achieved: 'Achieved', 'on-track': 'On track', watch: 'Watch', 'at-risk': 'At risk', unknown: 'Unknown' }

export default {
  name: 'ProgressView',
  props: {
    data: { type: Object, required: true },
  },
  emits: ['jump'],
  data() {
    return {
      lookaheadWeeks: 4,
      statusLabels: STATUS_LABELS,
      chartW: 900,
      chartH: 280,
      padL: 44,
      padR: 16,
      padT: 24,
      padB: 26,
    }
  },
  computed: {
    dataDateObj() {
      return this.data.project.data_date ? new Date(this.data.project.data_date) : null
    },
    milestoneList() {
      return this.data.activities
        .filter(isMilestone)
        .map(a => {
          const forecast = displayEnd(a) || a.act_start || a.early_start
          const target = a.target_end || a.target_start
          const achieved = a.status === 'TK_Complete' || !!a.act_end || !!a.act_start
          let varianceDays = null
          if (forecast && target) {
            varianceDays = Math.round((new Date(forecast) - new Date(target)) / 86400000)
          }
          let status
          if (achieved) status = 'achieved'
          else if (varianceDays == null) status = 'unknown'
          else if (varianceDays <= 0) status = 'on-track'
          else if (varianceDays <= 10) status = 'watch'
          else status = 'at-risk'
          return { ...a, forecast, target, varianceDays, achieved, status }
        })
        .sort((x, y) => new Date(x.forecast || 0) - new Date(y.forecast || 0))
    },
    lookaheadList() {
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
        .sort((a, b) => new Date(a.early_start) - new Date(b.early_start))
    },
    sCurve() {
      const acts = this.data.activities
      const dates = []
      for (const a of acts) {
        const t = a.target_end || a.target_start
        if (t) dates.push(new Date(t))
        if (a.early_end) dates.push(new Date(a.early_end))
      }
      if (dates.length < 2) return { months: [], planned: [], actual: [] }
      let minD = new Date(Math.min(...dates))
      let maxD = new Date(Math.max(...dates))
      minD = new Date(minD.getFullYear(), minD.getMonth(), 1)
      maxD = new Date(maxD.getFullYear(), maxD.getMonth() + 1, 1)
      const months = []
      let cur = new Date(minD)
      let guard = 0
      while (cur <= maxD && guard < 240) {
        months.push(new Date(cur))
        cur = new Date(cur.getFullYear(), cur.getMonth() + 1, 1)
        guard++
      }
      const total = acts.length || 1
      const planned = months.map(m => {
        const n = acts.filter(a => {
          const t = a.target_end || a.target_start
          return t && new Date(t) <= m
        }).length
        return Math.round((1000 * n) / total) / 10
      })
      const actual = months.map(m => {
        const n = acts.filter(a => a.act_end && new Date(a.act_end) <= m).length
        return Math.round((1000 * n) / total) / 10
      })
      return { months, planned, actual, minD, maxD }
    },
    monthLabelStep() {
      const n = this.sCurve.months.length
      return n > 18 ? 3 : n > 9 ? 2 : 1
    },
    dataDateX() {
      const { minD, maxD } = this.sCurve
      const dd = this.dataDateObj
      if (!minD || !maxD || !dd) return null
      const total = maxD - minD
      if (total <= 0) return null
      const frac = (dd - minD) / total
      return this.padL + frac * (this.chartW - this.padL - this.padR)
    },
  },
  methods: {
    formatDate,
    formatHours,
    formatFloat,
    varianceClass(m) {
      if (m.status === 'at-risk') return 'lag-neg'
      if (m.status === 'watch') return 'lag-warn'
      return ''
    },
    xFor(i) {
      const n = this.sCurve.months.length
      if (n < 2) return this.padL
      return this.padL + (i * (this.chartW - this.padL - this.padR)) / (n - 1)
    },
    yFor(pct) {
      return this.padT + (this.chartH - this.padT - this.padB) * (1 - pct / 100)
    },
    pathFor(values) {
      if (!values || values.length < 2) return ''
      return values.map((v, i) => (i === 0 ? 'M' : 'L') + this.xFor(i).toFixed(1) + ',' + this.yFor(v).toFixed(1)).join(' ')
    },
    monthLabel(d) {
      return d.toLocaleDateString('en-GB', { month: 'short', year: '2-digit' })
    },
  },
}
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
.curve-planned { fill: none; stroke: var(--active); stroke-width: 2.5; }
.curve-actual { fill: none; stroke: var(--ok); stroke-width: 2.5; }
.scurve-legend { display: flex; gap: var(--space-5); margin-top: var(--space-2); }
.legend-item { display: flex; align-items: center; gap: 5px; font: var(--text-small); color: var(--gray-700); }
.swatch { width: 14px; height: 3px; display: inline-block; }
.swatch-planned { background: var(--active); }
.swatch-actual { background: var(--ok); }
</style>
