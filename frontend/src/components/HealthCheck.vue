<template>
  <div class="health-wrap">
    <div class="health-strip">
      <div class="strip-title">
        <h2>Health Check</h2>
        <span class="strip-sub">{{ data.activities.length }} activities &middot; DCMA-14-inspired logic &amp; quality checks</span>
      </div>
    </div>

    <div class="scorecard">
      <div v-for="item in scorecard" :key="item.key" class="score-item" :class="item.pass ? 'pass' : 'fail'">
        <div class="score-count">{{ item.display }}</div>
        <div class="score-label">{{ item.label }}</div>
      </div>
    </div>

    <!-- Open Ends -->
    <section class="health-section">
      <button class="section-head" @click="toggle('openEnds')">
        <span class="section-title">Open Ends <em :class="{ pass: openEnds.length === 0 }">({{ openEnds.length }})</em></span>
        <span class="section-hint">Activities missing a driving predecessor or successor — can float freely with no network effect</span>
        <span class="chevron" :class="{ open: expanded.openEnds }">&rsaquo;</span>
      </button>
      <div v-if="expanded.openEnds" class="section-body">
        <div v-if="openEnds.length === 0" class="empty-state">✓ Every activity is tied into the network at both ends.</div>
        <table v-else class="health-table">
          <thead><tr><th>Code</th><th>Activity</th><th>Issue</th><th>WBS</th></tr></thead>
          <tbody>
            <tr v-for="a in openEnds" :key="a.task_id" class="jump-row" title="Show in Gantt" @click="$emit('jump', a.task_id)">
              <td class="code">{{ a.task_code }}</td>
              <td class="name-cell">{{ a.task_name }}</td>
              <td><span class="issue-badge" :class="a.bothOpen ? 'issue-severe' : 'issue-warn'">{{ a.bothOpen ? 'Fully dangling' : (a.openStart ? 'Open start' : 'Open finish') }}</span></td>
              <td class="wbs-cell">{{ a.wbs_path }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- Relationship type mix & lag/lead audit -->
    <section class="health-section">
      <button class="section-head" @click="toggle('rel')">
        <span class="section-title">Relationship &amp; Lag Audit <em>({{ relationshipStats.leads.length + relationshipStats.bigLags.length }})</em></span>
        <span class="section-hint">FS/SS/FF/SF mix, negative lags ("leads"), and unusually large lags</span>
        <span class="chevron" :class="{ open: expanded.rel }">&rsaquo;</span>
      </button>
      <div v-if="expanded.rel" class="section-body">
        <div class="rel-mix">
          <div v-for="t in relTypeOrder" :key="t" class="rel-mix-item">
            <strong>{{ relationshipStats.counts[t] || 0 }}</strong>
            <span>{{ relTypeLabels[t] }} ({{ relationshipStats.total ? Math.round(100 * (relationshipStats.counts[t] || 0) / relationshipStats.total) : 0 }}%)</span>
          </div>
        </div>
        <p class="section-note" v-if="relationshipStats.total">Industry rule of thumb: &ge;90% of relationships should be Finish-to-Start. This schedule is {{ relationshipStats.pctFs }}% FS.</p>

        <h4 v-if="relationshipStats.leads.length">Negative lag ("leads") — {{ relationshipStats.leads.length }}</h4>
        <table v-if="relationshipStats.leads.length" class="health-table">
          <thead><tr><th>Predecessor</th><th>Type</th><th>Successor</th><th class="num">Lag</th></tr></thead>
          <tbody>
            <tr v-for="(r, i) in relationshipStats.leads" :key="'lead' + i" class="jump-row" title="Show in Gantt" @click="$emit('jump', r.succ.task_id)">
              <td class="code">{{ codeOf(r.predId) }}</td>
              <td>{{ relTypeLabels[r.type] || r.type }}</td>
              <td class="code">{{ r.succ.task_code }}</td>
              <td class="num-cell lag-neg">{{ r.lag }}h</td>
            </tr>
          </tbody>
        </table>

        <h4 v-if="relationshipStats.bigLags.length">Large lag (&gt;10 working days) — {{ relationshipStats.bigLags.length }}</h4>
        <table v-if="relationshipStats.bigLags.length" class="health-table">
          <thead><tr><th>Predecessor</th><th>Type</th><th>Successor</th><th class="num">Lag</th></tr></thead>
          <tbody>
            <tr v-for="(r, i) in relationshipStats.bigLags" :key="'lag' + i" class="jump-row" title="Show in Gantt" @click="$emit('jump', r.succ.task_id)">
              <td class="code">{{ codeOf(r.predId) }}</td>
              <td>{{ relTypeLabels[r.type] || r.type }}</td>
              <td class="code">{{ r.succ.task_code }}</td>
              <td class="num-cell">{{ r.lag }}h</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- Constraint register -->
    <section class="health-section">
      <button class="section-head" @click="toggle('constraints')">
        <span class="section-title">Constraint Register <em>({{ constraintList.length }})</em></span>
        <span class="section-hint">Imposed dates that can override network logic — hard constraints can produce negative float</span>
        <span class="chevron" :class="{ open: expanded.constraints }">&rsaquo;</span>
      </button>
      <div v-if="expanded.constraints" class="section-body">
        <div v-if="constraintList.length === 0" class="empty-state">✓ No imposed dates — the network logic alone drives every date.</div>
        <table v-else class="health-table">
          <thead><tr><th>Code</th><th>Activity</th><th>Constraint</th><th class="num">Date</th><th>Severity</th><th>Note</th></tr></thead>
          <tbody>
            <tr v-for="a in constraintList" :key="a.task_id" class="jump-row" title="Show in Gantt" @click="$emit('jump', a.task_id)">
              <td class="code">{{ a.task_code }}</td>
              <td class="name-cell">{{ a.task_name }}</td>
              <td>{{ cstrLabels[a.cstr_type] || a.cstr_type }}</td>
              <td class="num-cell">{{ formatDate(a.cstr_date) }}</td>
              <td><span class="issue-badge" :class="a.hard ? 'issue-severe' : 'issue-warn'">{{ a.hard ? 'Hard' : 'Soft' }}</span></td>
              <td class="section-note-cell">{{ a.criticalOnlyByConstraint ? 'Critical only due to this constraint, not network logic' : '' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- Negative float -->
    <section class="health-section">
      <button class="section-head" @click="toggle('negfloat')">
        <span class="section-title">Negative Float <em :class="{ pass: negativeFloatList.length === 0 }">({{ negativeFloatList.length }})</em></span>
        <span class="section-hint">Activities already behind an imposed date — the schedule is telling you it can't hit its own constraints</span>
        <span class="chevron" :class="{ open: expanded.negfloat }">&rsaquo;</span>
      </button>
      <div v-if="expanded.negfloat" class="section-body">
        <div v-if="negativeFloatList.length === 0" class="empty-state">✓ No activity is behind its constraints.</div>
        <table v-else class="health-table">
          <thead><tr><th>Code</th><th>Activity</th><th class="num">Float</th><th class="num">Finish</th></tr></thead>
          <tbody>
            <tr v-for="a in negativeFloatList" :key="a.task_id" class="jump-row" title="Show in Gantt" @click="$emit('jump', a.task_id)">
              <td class="code">{{ a.task_code }}</td>
              <td class="name-cell">{{ a.task_name }}</td>
              <td class="num-cell lag-neg">{{ formatFloat(a.total_float_hrs, a.calendar_hrs_per_day) }}</td>
              <td class="num-cell">{{ formatDate(a.early_end) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- High duration -->
    <section class="health-section">
      <button class="section-head" @click="toggle('highdur')">
        <span class="section-title">High Duration <em>({{ highDurationList.length }})</em></span>
        <span class="section-hint">Task activities over 44 working days — usually should be broken into smaller steps for meaningful progress tracking</span>
        <span class="chevron" :class="{ open: expanded.highdur }">&rsaquo;</span>
      </button>
      <div v-if="expanded.highdur" class="section-body">
        <div v-if="highDurationList.length === 0" class="empty-state">✓ No task runs long enough to need breaking down.</div>
        <table v-else class="health-table">
          <thead><tr><th>Code</th><th>Activity</th><th class="num">Duration</th></tr></thead>
          <tbody>
            <tr v-for="a in highDurationList" :key="a.task_id" class="jump-row" title="Show in Gantt" @click="$emit('jump', a.task_id)">
              <td class="code">{{ a.task_code }}</td>
              <td class="name-cell">{{ a.task_name }}</td>
              <td class="num-cell">{{ formatHours(a.duration_hrs, a.calendar_hrs_per_day) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- LOE on critical path -->
    <section class="health-section">
      <button class="section-head" @click="toggle('loe')">
        <span class="section-title">LOE on Critical Path <em>({{ loeOnCriticalList.length }})</em></span>
        <span class="section-hint">Level-of-Effort/hammock activities shouldn't normally drive the critical path — usually a sign of inverted logic</span>
        <span class="chevron" :class="{ open: expanded.loe }">&rsaquo;</span>
      </button>
      <div v-if="expanded.loe" class="section-body">
        <div v-if="loeOnCriticalList.length === 0" class="empty-state">✓ No level-of-effort activity drives the critical path.</div>
        <table v-else class="health-table">
          <thead><tr><th>Code</th><th>Activity</th></tr></thead>
          <tbody>
            <tr v-for="a in loeOnCriticalList" :key="a.task_id" class="jump-row" title="Show in Gantt" @click="$emit('jump', a.task_id)">
              <td class="code">{{ a.task_code }}</td>
              <td class="name-cell">{{ a.task_name }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- Driving path cross-check -->
    <section class="health-section" v-if="drivingPathAvailable">
      <button class="section-head" @click="toggle('driving')">
        <span class="section-title">Driving Path Cross-Check <em>({{ drivingMismatchList.length }})</em></span>
        <span class="section-hint">Where P6's own driving-path flag disagrees with this app's computed longest path</span>
        <span class="chevron" :class="{ open: expanded.driving }">&rsaquo;</span>
      </button>
      <div v-if="expanded.driving" class="section-body">
        <div v-if="drivingMismatchList.length === 0" class="empty-state">No discrepancies — computed longest path matches P6's driving path flag.</div>
        <table v-else class="health-table">
          <thead><tr><th>Code</th><th>Activity</th><th>P6 driving?</th><th>App longest path?</th></tr></thead>
          <tbody>
            <tr v-for="a in drivingMismatchList" :key="a.task_id" class="jump-row" title="Show in Gantt" @click="$emit('jump', a.task_id)">
              <td class="code">{{ a.task_code }}</td>
              <td class="name-cell">{{ a.task_name }}</td>
              <td>{{ a.driving_path_flag ? 'Yes' : 'No' }}</td>
              <td>{{ a.is_longest_path ? 'Yes' : 'No' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- Out-of-sequence progress -->
    <section class="health-section">
      <button class="section-head" @click="toggle('oos')">
        <span class="section-title">Out-of-Sequence Progress <em>({{ outOfSequenceList.length }})</em></span>
        <span class="section-hint">Activities progressed before their Finish-to-Start predecessor actually finished</span>
        <span class="chevron" :class="{ open: expanded.oos }">&rsaquo;</span>
      </button>
      <div v-if="expanded.oos" class="section-body">
        <div v-if="outOfSequenceList.length === 0" class="empty-state">✓ All recorded progress respects the network logic.</div>
        <table v-else class="health-table">
          <thead><tr><th>Activity</th><th class="num">Started</th><th>Predecessor</th><th class="num">Predecessor finished</th></tr></thead>
          <tbody>
            <tr v-for="(r, i) in outOfSequenceList" :key="i" class="jump-row" title="Show in Gantt" @click="$emit('jump', r.activity.task_id)">
              <td class="code">{{ r.activity.task_code }}</td>
              <td class="num-cell">{{ formatDate(r.activity.act_start) }}</td>
              <td class="code">{{ r.predecessor.task_code }}</td>
              <td class="num-cell">{{ r.predecessor.act_end ? formatDate(r.predecessor.act_end) : 'Not finished' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- Resource coverage -->
    <section class="health-section" v-if="data.project.has_resources">
      <button class="section-head" @click="toggle('resources')">
        <span class="section-title">Missing Resources <em>({{ noResourceList.length }})</em></span>
        <span class="section-hint">Incomplete task activities with no resource assigned</span>
        <span class="chevron" :class="{ open: expanded.resources }">&rsaquo;</span>
      </button>
      <div v-if="expanded.resources" class="section-body">
        <div v-if="noResourceList.length === 0" class="empty-state">Every incomplete activity has a resource assigned.</div>
        <table v-else class="health-table">
          <thead><tr><th>Code</th><th>Activity</th></tr></thead>
          <tbody>
            <tr v-for="a in noResourceList" :key="a.task_id" class="jump-row" title="Show in Gantt" @click="$emit('jump', a.task_id)">
              <td class="code">{{ a.task_code }}</td>
              <td class="name-cell">{{ a.task_name }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<script>
import { formatDate, formatHours, formatFloat } from '../utils/format'

import { REL_TYPE_LABELS, CSTR_LABELS, HARD_CONSTRAINT_TYPES } from '../utils/p6'
const LARGE_LAG_HRS = 80 // ~10 working days at a standard 8h calendar

export default {
  name: 'HealthCheck',
  props: {
    data: { type: Object, required: true },
  },
  emits: ['jump'],
  data() {
    return {
      expanded: {
        openEnds: true,
        rel: true,
        constraints: false,
        negfloat: true,
        highdur: false,
        loe: false,
        driving: false,
        oos: false,
        resources: false,
      },
      cstrLabels: CSTR_LABELS,
      relTypeLabels: REL_TYPE_LABELS,
      relTypeOrder: ['PR_FS', 'PR_SS', 'PR_FF', 'PR_SF'],
    }
  },
  computed: {
    activitiesById() {
      const m = new Map()
      for (const a of this.data.activities) m.set(a.task_id, a)
      return m
    },
    openEnds() {
      const list = []
      for (const a of this.data.activities) {
        const noPred = a.predecessors.length === 0
        const noSucc = a.successors.length === 0
        const flagStart = noPred && a.task_type !== 'TT_StartMile'
        const flagFinish = noSucc && a.task_type !== 'TT_FinMile'
        if (flagStart || flagFinish) {
          list.push({ ...a, openStart: flagStart, openFinish: flagFinish, bothOpen: flagStart && flagFinish })
        }
      }
      return list
    },
    relationshipStats() {
      const counts = {}
      const leads = []
      const bigLags = []
      let total = 0
      for (const a of this.data.activities) {
        for (const p of a.predecessors) {
          total++
          counts[p.type] = (counts[p.type] || 0) + 1
          if (p.lag_hrs < 0) leads.push({ succ: a, predId: p.task_id, type: p.type, lag: p.lag_hrs })
          else if (p.lag_hrs > LARGE_LAG_HRS) bigLags.push({ succ: a, predId: p.task_id, type: p.type, lag: p.lag_hrs })
        }
      }
      leads.sort((x, y) => x.lag - y.lag)
      bigLags.sort((x, y) => y.lag - x.lag)
      const pctFs = total ? Math.round((100 * (counts.PR_FS || 0)) / total) : 100
      return { total, counts, leads, bigLags, pctFs }
    },
    constraintList() {
      return this.data.activities
        .filter(a => a.cstr_type)
        .map(a => ({
          ...a,
          hard: HARD_CONSTRAINT_TYPES.has(a.cstr_type),
          criticalOnlyByConstraint: a.is_critical && !a.is_longest_path,
        }))
        .sort((a, b) => (b.hard === a.hard ? 0 : b.hard ? 1 : -1))
    },
    negativeFloatList() {
      return this.data.activities
        .filter(a => a.is_negative_float)
        .sort((a, b) => a.total_float_hrs - b.total_float_hrs)
    },
    highDurationList() {
      return this.data.activities
        .filter(a => a.task_type === 'TT_Task' && a.duration_hrs / (a.calendar_hrs_per_day || 8) > 44)
        .sort((a, b) => b.duration_hrs - a.duration_hrs)
    },
    loeOnCriticalList() {
      return this.data.activities.filter(a => a.task_type === 'TT_LOE' && (a.is_critical || a.is_longest_path))
    },
    drivingPathAvailable() {
      return this.data.activities.some(a => a.driving_path_flag)
    },
    drivingMismatchList() {
      if (!this.drivingPathAvailable) return []
      return this.data.activities.filter(a => a.driving_path_flag !== a.is_longest_path)
    },
    outOfSequenceList() {
      const byId = this.activitiesById
      const list = []
      for (const a of this.data.activities) {
        if (!a.act_start) continue
        for (const p of a.predecessors) {
          if (p.type !== 'PR_FS') continue
          const pred = byId.get(p.task_id)
          if (!pred) continue
          if (!pred.act_end || new Date(pred.act_end) > new Date(a.act_start)) {
            list.push({ activity: a, predecessor: pred })
          }
        }
      }
      return list
    },
    noResourceList() {
      if (!this.data.project.has_resources) return []
      return this.data.activities.filter(
        a => a.task_type === 'TT_Task' && a.status !== 'TK_Complete' && a.resource_names.length === 0
      )
    },
    scorecard() {
      const total = this.data.activities.length || 1
      const pct = n => Math.round((1000 * n) / total) / 10
      const items = [
        { key: 'openends', label: 'Open Ends', count: this.openEnds.length, display: this.openEnds.length, pass: pct(this.openEnds.length) < 5 },
        { key: 'leads', label: 'Leads', count: this.relationshipStats.leads.length, display: this.relationshipStats.leads.length, pass: this.relationshipStats.leads.length === 0 },
        { key: 'lags', label: 'Large Lags', count: this.relationshipStats.bigLags.length, display: this.relationshipStats.bigLags.length, pass: pct(this.relationshipStats.bigLags.length) < 5 },
        { key: 'fs', label: 'FS Relationships', count: this.relationshipStats.pctFs, display: this.relationshipStats.pctFs + '%', pass: this.relationshipStats.pctFs >= 90 },
        { key: 'hardcstr', label: 'Hard Constraints', count: this.constraintList.filter(c => c.hard).length, display: this.constraintList.filter(c => c.hard).length, pass: pct(this.constraintList.filter(c => c.hard).length) < 5 },
        { key: 'highdur', label: 'High Duration', count: this.highDurationList.length, display: this.highDurationList.length, pass: pct(this.highDurationList.length) < 5 },
        { key: 'negfloat', label: 'Negative Float', count: this.negativeFloatList.length, display: this.negativeFloatList.length, pass: this.negativeFloatList.length === 0 },
        { key: 'oos', label: 'Out-of-Sequence', count: this.outOfSequenceList.length, display: this.outOfSequenceList.length, pass: this.outOfSequenceList.length === 0 },
      ]
      if (this.drivingPathAvailable) {
        items.push({ key: 'driving', label: 'Driving Path Mismatches', count: this.drivingMismatchList.length, display: this.drivingMismatchList.length, pass: this.drivingMismatchList.length === 0 })
      }
      if (this.data.project.has_resources) {
        items.push({ key: 'noresource', label: 'Missing Resources', count: this.noResourceList.length, display: this.noResourceList.length, pass: pct(this.noResourceList.length) < 5 })
      }
      return items
    },
  },
  methods: {
    formatDate,
    formatHours,
    formatFloat,
    codeOf(taskId) {
      const a = this.activitiesById.get(taskId)
      return a ? a.task_code : '?' + taskId
    },
    toggle(key) {
      this.expanded[key] = !this.expanded[key]
    },
  },
}
</script>

<style scoped>
.health-wrap { display: flex; flex-direction: column; background: var(--white); border: 1px solid var(--gray-300); border-radius: var(--radius-md); overflow: hidden; }
.health-strip { background: var(--ink); color: var(--white); padding: var(--space-3) var(--space-4); }
.strip-title { display: flex; align-items: baseline; gap: var(--space-3); }
.strip-title h2 { font: var(--text-h2); margin: 0; }
.strip-sub { font: var(--text-small); color: var(--gray-300); }

.scorecard { display: flex; flex-wrap: wrap; gap: 1px; background: var(--gray-300); border-bottom: 1px solid var(--gray-300); }
.score-item { flex: 1; min-width: 110px; background: var(--white); padding: var(--space-3); text-align: center; }
.score-item.pass .score-count { color: var(--ok); }
.score-item.fail .score-count { color: var(--crit); }
.score-count { font-family: var(--font-mono); font-size: 23px; font-weight: 700; }
.score-label { font: var(--text-micro); color: var(--gray-700); text-transform: uppercase; letter-spacing: 0.03em; }

.health-section { border-bottom: 1px solid var(--gray-300); }
.health-section:last-child { border-bottom: none; }
.section-title { font: 600 15px/1.4 var(--font-ui); }
.section-head { width: 100%; display: flex; align-items: center; gap: var(--space-4); padding: var(--space-3) var(--space-4); background: var(--gray-100); border: none; cursor: pointer; text-align: left; }
.section-head:hover { background: var(--gray-150); }
.section-title { font-weight: 600; color: var(--ink); white-space: nowrap; }
.section-title em { font-style: normal; color: var(--accent); font-family: var(--font-mono); }
.section-title em.pass { color: var(--ok); }
.section-hint { font: var(--text-small); color: var(--gray-700); flex: 1; }
.chevron { transition: transform 0.15s; color: var(--gray-500); font-size: 19px; }
.chevron.open { transform: rotate(90deg); }
.section-body { padding: var(--space-4); }
.section-note { font: var(--text-small); color: var(--gray-700); margin: var(--space-2) 0 var(--space-4); }
.section-body h4 { font: var(--text-small); font-weight: 700; color: var(--ink); margin: var(--space-4) 0 var(--space-2); }
.section-body h4:first-child { margin-top: 0; }
.empty-state { font: var(--text-small); color: var(--ok); }

.rel-mix { display: flex; gap: var(--space-6); flex-wrap: wrap; }
.rel-mix-item { display: flex; flex-direction: column; gap: 2px; }
.rel-mix-item strong { font-family: var(--font-mono); font-size: 19px; color: var(--ink); }
.rel-mix-item span { font: var(--text-micro); color: var(--gray-700); }

.health-table { width: 100%; border-collapse: collapse; font: var(--text-small); }
.health-table th { text-align: left; font: var(--text-micro); text-transform: uppercase; color: var(--gray-700); background: var(--gray-100); border-bottom: 2px solid var(--gray-300); padding: var(--space-2) var(--space-3); }
.health-table td { padding: 6px var(--space-3); border-bottom: 1px solid var(--gray-150); }
.jump-row { cursor: pointer; }
.jump-row:hover td { background: var(--accent-soft); }
.code { font-family: var(--font-mono); font-weight: 600; color: var(--accent); white-space: nowrap; }
.name-cell { color: var(--ink-soft); }
.wbs-cell { color: var(--gray-700); font: var(--text-micro); font-family: var(--font-mono); }
.num-cell { font-family: var(--font-mono); text-align: right; white-space: nowrap; }
.section-note-cell { color: var(--near); font: var(--text-micro); font-style: italic; }
.lag-neg { color: var(--crit); font-weight: 700; }

.issue-badge { font: var(--text-micro); padding: 1px 7px; border-radius: var(--radius-sm); font-weight: 600; }
.issue-severe { background: var(--crit); color: var(--white); }
.issue-warn { background: var(--near-tint); color: var(--near); }
</style>
