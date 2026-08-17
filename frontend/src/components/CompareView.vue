<template>
  <div class="compare-wrap">
    <div class="compare-strip">
      <div class="strip-title">
        <h2>Programme Compare</h2>
        <span class="strip-sub">{{ current.project.proj_short_name }} vs "{{ baselineFilename }}"</span>
      </div>
      <button class="btn-tiny-light" @click="$emit('reset')">Compare a different file</button>
    </div>

    <div class="scorecard">
      <div class="score-item"><div class="score-count">{{ matched.length }}</div><div class="score-label">Matched</div></div>
      <div class="score-item" :class="{ fail: added.length > 0 }"><div class="score-count">{{ added.length }}</div><div class="score-label">Added</div></div>
      <div class="score-item" :class="{ fail: removed.length > 0 }"><div class="score-count">{{ removed.length }}</div><div class="score-label">Removed</div></div>
      <div class="score-item" :class="stability.pct === 100 ? 'pass' : 'fail'"><div class="score-count">{{ stability.pct }}%</div><div class="score-label">Critical Path Stability</div></div>
      <div class="score-item" :class="{ fail: floatErosion.length > 0 }"><div class="score-count">{{ floatErosion.length }}</div><div class="score-label">Float Erosion</div></div>
      <div class="score-item" :class="{ fail: logicChanges.length > 0 }"><div class="score-count">{{ logicChanges.length }}</div><div class="score-label">Logic Changes</div></div>
    </div>
    <p class="stability-note">
      {{ stability.retained }} of {{ stability.baseCount }} longest-path activities retained &middot;
      {{ stability.newlyCritical }} newly critical &middot; {{ stability.dropped }} dropped from longest path
      <span v-if="stability.driverChanged"> &middot; the finish-driving activity changed</span>
    </p>

    <!-- Slipped / pulled ahead -->
    <section class="compare-section">
      <button class="section-head" @click="toggle('dates')">
        <span class="section-title">Date Changes <em>({{ dateChanges.length }})</em></span>
        <span class="section-hint">Activities whose finish date moved since the baseline</span>
        <span class="chevron" :class="{ open: expanded.dates }">&rsaquo;</span>
      </button>
      <div v-if="expanded.dates" class="section-body">
        <div v-if="dateChanges.length === 0" class="empty-state">No finish-date changes.</div>
        <table v-else class="compare-table">
          <thead><tr><th>Code</th><th>Activity</th><th>Baseline Finish</th><th>Current Finish</th><th>Change</th></tr></thead>
          <tbody>
            <tr v-for="d in dateChanges" :key="d.code" class="jump-row" @click="$emit('jump', d.cur.task_id)">
              <td class="code">{{ d.code }}</td>
              <td class="name-cell">{{ d.cur.task_name }}</td>
              <td class="num-cell">{{ formatDate(d.base.early_end) }}</td>
              <td class="num-cell">{{ formatDate(d.cur.early_end) }}</td>
              <td class="num-cell" :class="d.deltaDays > 0 ? 'lag-neg' : 'lag-pos'">{{ d.deltaDays > 0 ? '+' : '' }}{{ d.deltaDays }}d</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- Float erosion -->
    <section class="compare-section">
      <button class="section-head" @click="toggle('float')">
        <span class="section-title">Float Erosion <em>({{ floatErosion.length }})</em></span>
        <span class="section-hint">Activities where total float got worse since the baseline</span>
        <span class="chevron" :class="{ open: expanded.float }">&rsaquo;</span>
      </button>
      <div v-if="expanded.float" class="section-body">
        <div v-if="floatErosion.length === 0" class="empty-state">No float erosion.</div>
        <table v-else class="compare-table">
          <thead><tr><th>Code</th><th>Activity</th><th>Baseline Float</th><th>Current Float</th><th>Change</th></tr></thead>
          <tbody>
            <tr v-for="d in floatErosion" :key="d.code" class="jump-row" @click="$emit('jump', d.cur.task_id)">
              <td class="code">{{ d.code }}</td>
              <td class="name-cell">{{ d.cur.task_name }}</td>
              <td class="num-cell">{{ d.base.total_float_hrs }}h</td>
              <td class="num-cell" :class="d.cur.is_negative_float ? 'lag-neg' : ''">{{ d.cur.total_float_hrs }}h</td>
              <td class="num-cell lag-neg">{{ d.delta }}h</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- Critical path changes -->
    <section class="compare-section">
      <button class="section-head" @click="toggle('critical')">
        <span class="section-title">Critical Path Changes <em>({{ criticalEntered.length + criticalLeft.length }})</em></span>
        <span class="section-hint">Activities that entered or left the critical set (TF&le;0)</span>
        <span class="chevron" :class="{ open: expanded.critical }">&rsaquo;</span>
      </button>
      <div v-if="expanded.critical" class="section-body">
        <div v-if="criticalEntered.length === 0 && criticalLeft.length === 0" class="empty-state">No change in the critical set.</div>
        <template v-else>
          <h4 v-if="criticalEntered.length">Newly critical ({{ criticalEntered.length }})</h4>
          <table v-if="criticalEntered.length" class="compare-table">
            <thead><tr><th>Code</th><th>Activity</th><th>Current Float</th></tr></thead>
            <tbody>
              <tr v-for="d in criticalEntered" :key="d.code" class="jump-row" @click="$emit('jump', d.cur.task_id)">
                <td class="code">{{ d.code }}</td>
                <td class="name-cell">{{ d.cur.task_name }}</td>
                <td class="num-cell lag-neg">{{ d.cur.total_float_hrs }}h</td>
              </tr>
            </tbody>
          </table>
          <h4 v-if="criticalLeft.length">Dropped from critical ({{ criticalLeft.length }})</h4>
          <table v-if="criticalLeft.length" class="compare-table">
            <thead><tr><th>Code</th><th>Activity</th><th>Current Float</th></tr></thead>
            <tbody>
              <tr v-for="d in criticalLeft" :key="d.code" class="jump-row" @click="$emit('jump', d.cur.task_id)">
                <td class="code">{{ d.code }}</td>
                <td class="name-cell">{{ d.cur.task_name }}</td>
                <td class="num-cell">{{ d.cur.total_float_hrs }}h</td>
              </tr>
            </tbody>
          </table>
        </template>
      </div>
    </section>

    <!-- Logic changes -->
    <section class="compare-section">
      <button class="section-head" @click="toggle('logic')">
        <span class="section-title">Logic Changes <em>({{ logicChanges.length }})</em></span>
        <span class="section-hint">Activities with added or removed predecessor links since the baseline</span>
        <span class="chevron" :class="{ open: expanded.logic }">&rsaquo;</span>
      </button>
      <div v-if="expanded.logic" class="section-body">
        <div v-if="logicChanges.length === 0" class="empty-state">No logic changes.</div>
        <table v-else class="compare-table">
          <thead><tr><th>Code</th><th>Activity</th><th>Added links</th><th>Removed links</th></tr></thead>
          <tbody>
            <tr v-for="d in logicChanges" :key="d.code" class="jump-row" @click="$emit('jump', d.cur.task_id)">
              <td class="code">{{ d.code }}</td>
              <td class="name-cell">{{ d.cur.task_name }}</td>
              <td class="links-cell added">{{ d.added.join(', ') || '—' }}</td>
              <td class="links-cell removed">{{ d.removed.join(', ') || '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- Added / removed activities -->
    <section class="compare-section">
      <button class="section-head" @click="toggle('addrem')">
        <span class="section-title">Added / Removed Activities <em>({{ added.length + removed.length }})</em></span>
        <span class="section-hint">Activities present in only one of the two files</span>
        <span class="chevron" :class="{ open: expanded.addrem }">&rsaquo;</span>
      </button>
      <div v-if="expanded.addrem" class="section-body">
        <div v-if="added.length === 0 && removed.length === 0" class="empty-state">No activities added or removed.</div>
        <template v-else>
          <h4 v-if="added.length">Added ({{ added.length }})</h4>
          <table v-if="added.length" class="compare-table">
            <thead><tr><th>Code</th><th>Activity</th><th>Start</th><th>Finish</th></tr></thead>
            <tbody>
              <tr v-for="a in added" :key="a.task_id" class="jump-row" @click="$emit('jump', a.task_id)">
                <td class="code">{{ a.task_code }}</td>
                <td class="name-cell">{{ a.task_name }}</td>
                <td class="num-cell">{{ formatDate(a.early_start) }}</td>
                <td class="num-cell">{{ formatDate(a.early_end) }}</td>
              </tr>
            </tbody>
          </table>
          <h4 v-if="removed.length">Removed ({{ removed.length }})</h4>
          <table v-if="removed.length" class="compare-table">
            <thead><tr><th>Code</th><th>Activity</th><th>Start</th><th>Finish</th></tr></thead>
            <tbody>
              <tr v-for="a in removed" :key="a.task_id">
                <td class="code">{{ a.task_code }}</td>
                <td class="name-cell">{{ a.task_name }}</td>
                <td class="num-cell">{{ formatDate(a.early_start) }}</td>
                <td class="num-cell">{{ formatDate(a.early_end) }}</td>
              </tr>
            </tbody>
          </table>
        </template>
      </div>
    </section>
  </div>
</template>

<script>
import { formatDate } from '../utils/format'

const REL_TYPE_LABELS = { PR_FS: 'FS', PR_SS: 'SS', PR_FF: 'FF', PR_SF: 'SF' }

export default {
  name: 'CompareView',
  props: {
    current: { type: Object, required: true },
    baseline: { type: Object, required: true },
    baselineFilename: { type: String, default: '' },
  },
  emits: ['jump', 'reset'],
  data() {
    return {
      expanded: { dates: true, float: true, critical: true, logic: false, addrem: false },
    }
  },
  computed: {
    curByCode() {
      const m = new Map()
      for (const a of this.current.activities) m.set(a.task_code, a)
      return m
    },
    baseByCode() {
      const m = new Map()
      for (const a of this.baseline.activities) m.set(a.task_code, a)
      return m
    },
    matched() {
      const out = []
      for (const [code, cur] of this.curByCode) {
        const base = this.baseByCode.get(code)
        if (base) out.push({ code, cur, base })
      }
      return out
    },
    added() {
      return this.current.activities.filter(a => !this.baseByCode.has(a.task_code))
    },
    removed() {
      return this.baseline.activities.filter(a => !this.curByCode.has(a.task_code))
    },
    dateChanges() {
      return this.matched
        .filter(d => d.cur.early_end && d.base.early_end && d.cur.early_end !== d.base.early_end)
        .map(d => ({ ...d, deltaDays: Math.round((new Date(d.cur.early_end) - new Date(d.base.early_end)) / 86400000) }))
        .filter(d => d.deltaDays !== 0)
        .sort((a, b) => b.deltaDays - a.deltaDays)
    },
    floatErosion() {
      return this.matched
        .filter(d => d.cur.total_float_hrs != null && d.base.total_float_hrs != null && d.cur.total_float_hrs < d.base.total_float_hrs)
        .map(d => ({ ...d, delta: Math.round((d.cur.total_float_hrs - d.base.total_float_hrs) * 10) / 10 }))
        .sort((a, b) => a.delta - b.delta)
    },
    criticalEntered() {
      return this.matched.filter(d => !d.base.is_critical && d.cur.is_critical)
    },
    criticalLeft() {
      return this.matched.filter(d => d.base.is_critical && !d.cur.is_critical)
    },
    logicChanges() {
      const linkSet = (activity, lookupById) => {
        const set = new Set()
        for (const p of activity.predecessors) {
          const predActivity = lookupById.get(p.task_id)
          const code = predActivity ? predActivity.task_code : '?' + p.task_id
          set.add(`${code} (${REL_TYPE_LABELS[p.type] || p.type}${p.lag_hrs ? ' +' + p.lag_hrs + 'h' : ''})`)
        }
        return set
      }
      const curById = new Map(this.current.activities.map(a => [a.task_id, a]))
      const baseById = new Map(this.baseline.activities.map(a => [a.task_id, a]))
      const out = []
      for (const d of this.matched) {
        const curLinks = linkSet(d.cur, curById)
        const baseLinks = linkSet(d.base, baseById)
        const added = [...curLinks].filter(l => !baseLinks.has(l))
        const removed = [...baseLinks].filter(l => !curLinks.has(l))
        if (added.length || removed.length) out.push({ ...d, added, removed })
      }
      return out
    },
    stability() {
      const baseLongest = new Set(this.baseline.activities.filter(a => a.is_longest_path).map(a => a.task_code))
      const curLongest = new Set(this.current.activities.filter(a => a.is_longest_path).map(a => a.task_code))
      const retained = [...baseLongest].filter(c => curLongest.has(c)).length
      const pct = baseLongest.size ? Math.round((100 * retained) / baseLongest.size) : 100
      const newlyCritical = [...curLongest].filter(c => !baseLongest.has(c)).length
      const dropped = [...baseLongest].filter(c => !curLongest.has(c)).length
      const driverOf = (data, codeSet) => {
        let best = null
        for (const a of data.activities) {
          if (!codeSet.has(a.task_code) || !a.early_end) continue
          if (!best || new Date(a.early_end) > new Date(best.early_end)) best = a
        }
        return best ? best.task_code : null
      }
      const baseDriver = driverOf(this.baseline, baseLongest)
      const curDriver = driverOf(this.current, curLongest)
      return { pct, retained, baseCount: baseLongest.size, newlyCritical, dropped, driverChanged: baseDriver && curDriver && baseDriver !== curDriver }
    },
  },
  methods: {
    formatDate,
    toggle(key) {
      this.expanded[key] = !this.expanded[key]
    },
  },
}
</script>

<style scoped>
.compare-wrap { display: flex; flex-direction: column; background: var(--white); border: 1px solid var(--gray-300); border-radius: var(--radius-md); overflow: hidden; }
.compare-strip { background: var(--ink); color: var(--white); padding: var(--space-3) var(--space-4); display: flex; align-items: center; justify-content: space-between; }
.strip-title { display: flex; align-items: baseline; gap: var(--space-3); }
.strip-title h2 { font: var(--text-h2); margin: 0; }
.strip-sub { font: var(--text-small); color: var(--gray-300); }

.scorecard { display: flex; flex-wrap: wrap; gap: 1px; background: var(--gray-300); border-bottom: 1px solid var(--gray-300); }
.score-item { flex: 1; min-width: 110px; background: var(--white); padding: var(--space-3); text-align: center; }
.score-item.pass .score-count { color: var(--ok); }
.score-item.fail .score-count { color: var(--crit); }
.score-count { font-family: var(--font-mono); font-size: 22px; font-weight: 700; }
.score-label { font: var(--text-micro); color: var(--gray-700); text-transform: uppercase; letter-spacing: 0.03em; }
.stability-note { font: var(--text-small); color: var(--gray-700); padding: var(--space-2) var(--space-4); margin: 0; background: var(--gray-100); border-bottom: 1px solid var(--gray-300); }

.compare-section { border-bottom: 1px solid var(--gray-300); }
.compare-section:last-child { border-bottom: none; }
.section-head { width: 100%; display: flex; align-items: center; gap: var(--space-4); padding: var(--space-3) var(--space-4); background: var(--gray-100); border: none; cursor: pointer; text-align: left; }
.section-head:hover { background: var(--gray-150); }
.section-title { font-weight: 600; color: var(--ink); white-space: nowrap; }
.section-title em { font-style: normal; color: var(--accent); font-family: var(--font-mono); }
.section-hint { font: var(--text-small); color: var(--gray-700); flex: 1; }
.chevron { transition: transform 0.15s; color: var(--gray-500); font-size: 18px; }
.chevron.open { transform: rotate(90deg); }
.section-body { padding: var(--space-4); }
.section-body h4 { font: var(--text-small); color: var(--ink); margin: var(--space-4) 0 var(--space-2); }
.section-body h4:first-child { margin-top: 0; }
.empty-state { font: var(--text-small); color: var(--ok); }

.compare-table { width: 100%; border-collapse: collapse; font: var(--text-small); }
.compare-table th { text-align: left; font: var(--text-micro); text-transform: uppercase; color: var(--gray-700); border-bottom: 1px solid var(--gray-300); padding: var(--space-2); }
.compare-table td { padding: var(--space-2); border-bottom: 1px solid var(--gray-150); }
.jump-row { cursor: pointer; }
.jump-row:hover td { background: var(--accent-soft); }
.code { font-family: var(--font-mono); font-weight: 600; color: var(--accent); white-space: nowrap; }
.name-cell { color: var(--ink-soft); }
.num-cell { font-family: var(--font-mono); text-align: right; white-space: nowrap; }
.lag-neg { color: var(--crit); font-weight: 700; }
.lag-pos { color: var(--ok); font-weight: 700; }
.links-cell { font: var(--text-micro); font-family: var(--font-mono); }
.links-cell.added { color: var(--ok); }
.links-cell.removed { color: var(--crit); }
</style>
