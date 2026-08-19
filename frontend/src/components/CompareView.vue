<template>
  <div class="compare-wrap">
    <div class="view-bar">
      <div class="strip-title">
        <span class="strip-sub">{{ current.project.proj_short_name }} vs "{{ baselineFilename }}"</span>
      </div>
      <button class="btn-tiny-light" @click="$emit('reset')">Compare a different file</button>
    </div>

    <!-- Headline verdict: the so-what before any table -->
    <div v-if="finishDelta !== null" class="cmp-verdict" :class="finishDelta > 0 ? 'v-slip' : finishDelta < 0 ? 'v-gain' : 'v-hold'">
      <div class="verdict-main">
        <span class="verdict-label">Project finish</span>
        <span class="verdict-dates">{{ formatDate(baseline.project.latest_end) }} <span class="verdict-arrow">→</span> {{ formatDate(current.project.latest_end) }}</span>
        <span class="verdict-delta">{{ finishDelta > 0 ? '+' : '' }}{{ finishDelta }}d</span>
        <span class="verdict-word">{{ finishDelta > 0 ? 'slipped' : finishDelta < 0 ? 'gained' : 'held' }}</span>
      </div>
      <div class="verdict-sub">
        <template v-if="ddAdvance !== null">Data date advanced {{ ddAdvance }}d ({{ formatDate(baseline.project.data_date) }} → {{ formatDate(current.project.data_date) }}) &middot; </template>
        {{ dateChanges.length }} finish date{{ dateChanges.length === 1 ? '' : 's' }} moved &middot; {{ durationChanges.length }} duration edit{{ durationChanges.length === 1 ? '' : 's' }}
      </div>
    </div>

    <div class="scorecard">
      <div class="score-item"><div class="score-count">{{ matched.length }}</div><div class="score-label">Matched</div></div>
      <div class="score-item" :class="{ fail: added.length > 0 }"><div class="score-count">{{ added.length }}</div><div class="score-label">Added</div></div>
      <div class="score-item" :class="{ fail: removed.length > 0 }"><div class="score-count">{{ removed.length }}</div><div class="score-label">Removed</div></div>
      <div class="score-item" :class="stability.pct === 100 ? 'pass' : 'fail'"><div class="score-count">{{ stability.pct }}%</div><div class="score-label">Critical Path Stability</div></div>
      <div class="score-item" :class="{ fail: durationChanges.length > 0 }"><div class="score-count">{{ durationChanges.length }}</div><div class="score-label">Duration Changes</div></div>
      <div class="score-item" :class="{ fail: floatErosion.length > 0 }"><div class="score-count">{{ floatErosion.length }}</div><div class="score-label">Float Erosion</div></div>
      <div class="score-item" :class="{ fail: logicChanges.length > 0 }"><div class="score-count">{{ logicChanges.length }}</div><div class="score-label">Logic Changes</div></div>
    </div>
    <p class="stability-note">
      {{ stability.retained }} of {{ stability.baseCount }} longest-path activities retained &middot;
      {{ stability.newlyCritical }} newly critical &middot; {{ stability.dropped }} dropped from longest path
      <span v-if="stability.driverChanged"> &middot; the finish-driving activity changed</span>
    </p>

    <div class="cmp-side-by-side">
    <!-- Milestone movement (dumbbells) -->
    <section class="compare-section" v-if="milestoneMoves.length">
      <button class="section-head" @click="toggle('milestones')">
        <span class="section-title">Milestone Movement <em>({{ milestoneMoves.filter(m => m.delta !== 0).length }})</em></span>
        <span class="section-hint">Baseline &rarr; current date per milestone — the exhibit that goes in front of the client</span>
        <span class="chevron" :class="{ open: expanded.milestones }">&rsaquo;</span>
      </button>
      <div v-if="expanded.milestones" class="section-body">
        <div class="dumbbell-chart">
          <div v-for="m in milestoneMoves" :key="m.code" class="db-row jump-row" title="Show in Gantt" @click="$emit('jump', m.cur.task_id)">
            <span class="db-label"><span class="code">{{ m.code }}</span> {{ m.cur.task_name }}</span>
            <div class="db-track">
              <div v-if="m.delta !== 0" class="db-join" :class="m.delta > 0 ? 'db-slip' : 'db-gain'" :style="{ left: Math.min(m.baseX, m.curX) + '%', width: Math.abs(m.curX - m.baseX) + '%' }"></div>
              <span class="db-dot db-base" :style="{ left: m.baseX + '%' }" :title="'Baseline: ' + formatDate(m.baseDate)"></span>
              <span class="db-dot db-cur" :class="m.delta > 0 ? 'db-slip' : m.delta < 0 ? 'db-gain' : 'db-hold'" :style="{ left: m.curX + '%' }" :title="'Current: ' + formatDate(m.curDate)"></span>
            </div>
            <span class="db-delta" :class="m.delta > 0 ? 'lag-neg' : m.delta < 0 ? 'lag-pos' : 'db-zero'">{{ m.delta > 0 ? '+' : '' }}{{ m.delta }}d</span>
          </div>
          <div class="db-axis">
            <span>{{ formatDate(msDomain.min) }}</span>
            <span class="db-axis-legend"><span class="db-dot db-base db-inline"></span> baseline &nbsp; <span class="db-dot db-cur db-slip db-inline"></span> current</span>
            <span>{{ formatDate(msDomain.max) }}</span>
          </div>
        </div>
      </div>
    </section>

    <!-- Slip tornado -->
    <section class="compare-section" v-if="tornadoRows.length">
      <button class="section-head" @click="toggle('tornado')">
        <span class="section-title">Biggest Movers <em>({{ dateChanges.length }})</em></span>
        <span class="section-hint">Finish-date change per activity — slips grow right, gains grow left</span>
        <span class="chevron" :class="{ open: expanded.tornado }">&rsaquo;</span>
      </button>
      <div v-if="expanded.tornado" class="section-body">
        <div class="tornado">
          <div v-for="d in tornadoRows" :key="d.code" class="tor-row jump-row" title="Show in Gantt" @click="$emit('jump', d.cur.task_id)">
            <span class="tor-label"><span class="code">{{ d.code }}</span> {{ d.cur.task_name }}</span>
            <div class="tor-track">
              <div class="tor-half tor-left">
                <div v-if="d.deltaDays < 0" class="tor-bar tor-gain" :style="{ width: (100 * -d.deltaDays / tornadoMax) + '%' }"></div>
              </div>
              <div class="tor-half tor-right">
                <div v-if="d.deltaDays > 0" class="tor-bar tor-slip" :style="{ width: (100 * d.deltaDays / tornadoMax) + '%' }"></div>
              </div>
            </div>
            <span class="tor-delta" :class="d.deltaDays > 0 ? 'lag-neg' : 'lag-pos'">{{ d.deltaDays > 0 ? '+' : '' }}{{ d.deltaDays }}d</span>
          </div>
          <p v-if="dateChanges.length > tornadoRows.length" class="tor-note">Showing the {{ tornadoRows.length }} biggest of {{ dateChanges.length }} moved activities — the full list is in Date Changes below.</p>
        </div>
      </div>
    </section>
    </div>

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
          <thead><tr><th>Code</th><th>Activity</th><th class="num">Baseline Finish</th><th class="num">Current Finish</th><th class="num">Change</th></tr></thead>
          <tbody>
            <tr v-for="d in dateChanges" :key="d.code" class="jump-row" title="Show in Gantt" @click="$emit('jump', d.cur.task_id)">
              <td class="code">{{ d.code }}</td>
              <td class="name-cell">{{ d.cur.task_name }}</td>
              <td class="num-cell">{{ formatDate(displayEnd(d.base)) }}</td>
              <td class="num-cell">{{ formatDate(displayEnd(d.cur)) }}</td>
              <td class="num-cell" :class="d.deltaDays > 0 ? 'lag-neg' : 'lag-pos'">{{ d.deltaDays > 0 ? '+' : '' }}{{ d.deltaDays }}d</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- Duration changes -->
    <section class="compare-section">
      <button class="section-head" @click="toggle('durations')">
        <span class="section-title">Duration Changes <em>({{ durationChanges.length }})</em></span>
        <span class="section-hint">Activities whose original duration was edited since the baseline</span>
        <span class="chevron" :class="{ open: expanded.durations }">&rsaquo;</span>
      </button>
      <div v-if="expanded.durations" class="section-body">
        <div v-if="durationChanges.length === 0" class="empty-state">No duration changes.</div>
        <table v-else class="compare-table">
          <thead><tr><th>Code</th><th>Activity</th><th class="num">Baseline Dur</th><th class="num">Current Dur</th><th class="num">Change</th></tr></thead>
          <tbody>
            <tr v-for="d in durationChanges" :key="d.code" class="jump-row" title="Show in Gantt" @click="$emit('jump', d.cur.task_id)">
              <td class="code">{{ d.code }}</td>
              <td class="name-cell">{{ d.cur.task_name }}</td>
              <td class="num-cell">{{ formatHours(d.base.duration_hrs, d.base.calendar_hrs_per_day) }}</td>
              <td class="num-cell">{{ formatHours(d.cur.duration_hrs, d.cur.calendar_hrs_per_day) }}</td>
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
          <thead><tr><th>Code</th><th>Activity</th><th class="num">Baseline Float</th><th class="num">Current Float</th><th class="num">Change</th></tr></thead>
          <tbody>
            <tr v-for="d in floatErosion" :key="d.code" class="jump-row" title="Show in Gantt" @click="$emit('jump', d.cur.task_id)">
              <td class="code">{{ d.code }}</td>
              <td class="name-cell">{{ d.cur.task_name }}</td>
              <td class="num-cell">{{ formatFloat(d.base.total_float_hrs, d.base.calendar_hrs_per_day) }}</td>
              <td class="num-cell" :class="d.cur.is_negative_float ? 'lag-neg' : ''">{{ formatFloat(d.cur.total_float_hrs, d.cur.calendar_hrs_per_day) }}</td>
              <td class="num-cell lag-neg">{{ formatFloat(d.delta, d.cur.calendar_hrs_per_day) }}</td>
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
            <thead><tr><th>Code</th><th>Activity</th><th class="num">Current Float</th></tr></thead>
            <tbody>
              <tr v-for="d in criticalEntered" :key="d.code" class="jump-row" title="Show in Gantt" @click="$emit('jump', d.cur.task_id)">
                <td class="code">{{ d.code }}</td>
                <td class="name-cell">{{ d.cur.task_name }}</td>
                <td class="num-cell lag-neg">{{ formatFloat(d.cur.total_float_hrs, d.cur.calendar_hrs_per_day) }}</td>
              </tr>
            </tbody>
          </table>
          <h4 v-if="criticalLeft.length">Dropped from critical ({{ criticalLeft.length }})</h4>
          <table v-if="criticalLeft.length" class="compare-table">
            <thead><tr><th>Code</th><th>Activity</th><th class="num">Current Float</th></tr></thead>
            <tbody>
              <tr v-for="d in criticalLeft" :key="d.code" class="jump-row" title="Show in Gantt" @click="$emit('jump', d.cur.task_id)">
                <td class="code">{{ d.code }}</td>
                <td class="name-cell">{{ d.cur.task_name }}</td>
                <td class="num-cell">{{ formatFloat(d.cur.total_float_hrs, d.cur.calendar_hrs_per_day) }}</td>
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
            <tr v-for="d in logicChanges" :key="d.code" class="jump-row" title="Show in Gantt" @click="$emit('jump', d.cur.task_id)">
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
            <thead><tr><th>Code</th><th>Activity</th><th class="num">Start</th><th class="num">Finish</th></tr></thead>
            <tbody>
              <tr v-for="a in added" :key="a.task_id" class="jump-row" title="Show in Gantt" @click="$emit('jump', a.task_id)">
                <td class="code">{{ a.task_code }}</td>
                <td class="name-cell">{{ a.task_name }}</td>
                <td class="num-cell">{{ formatDate(displayStart(a)) }}</td>
                <td class="num-cell">{{ formatDate(displayEnd(a)) }}</td>
              </tr>
            </tbody>
          </table>
          <h4 v-if="removed.length">Removed ({{ removed.length }})</h4>
          <table v-if="removed.length" class="compare-table">
            <thead><tr><th>Code</th><th>Activity</th><th class="num">Start</th><th class="num">Finish</th></tr></thead>
            <tbody>
              <tr v-for="a in removed" :key="a.task_id">
                <td class="code">{{ a.task_code }}</td>
                <td class="name-cell">{{ a.task_name }}</td>
                <td class="num-cell">{{ formatDate(displayStart(a)) }}</td>
                <td class="num-cell">{{ formatDate(displayEnd(a)) }}</td>
              </tr>
            </tbody>
          </table>
        </template>
      </div>
    </section>
  </div>
</template>

<script>
import { formatDate, formatFloat, formatHours, formatLag } from '../utils/format'
import { REL_TYPE_LABELS, displayStart, displayEnd } from '../utils/p6'


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
      expanded: { milestones: true, tornado: true, dates: false, durations: true, float: true, critical: true, logic: false, addrem: false },
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
        .filter(d => displayEnd(d.cur) && displayEnd(d.base) && displayEnd(d.cur) !== displayEnd(d.base))
        .map(d => ({ ...d, deltaDays: Math.round((new Date(displayEnd(d.cur)) - new Date(displayEnd(d.base))) / 86400000) }))
        .filter(d => d.deltaDays !== 0)
        .sort((a, b) => b.deltaDays - a.deltaDays)
    },
    finishDelta() {
      const c = this.current.project.latest_end
      const b = this.baseline.project.latest_end
      if (!c || !b) return null
      return Math.round((new Date(c) - new Date(b)) / 86400000)
    },
    ddAdvance() {
      const c = this.current.project.data_date
      const b = this.baseline.project.data_date
      if (!c || !b) return null
      return Math.round((new Date(c) - new Date(b)) / 86400000)
    },
    milestoneMoves() {
      const rows = this.matched
        .filter(d => (d.cur.task_type || '').includes('Mile'))
        .map(d => {
          const curDate = displayEnd(d.cur) || displayStart(d.cur)
          const baseDate = displayEnd(d.base) || displayStart(d.base)
          return { ...d, curDate, baseDate, delta: curDate && baseDate ? Math.round((new Date(curDate) - new Date(baseDate)) / 86400000) : 0 }
        })
        .filter(m => m.curDate && m.baseDate)
        .sort((a, b) => new Date(a.curDate) - new Date(b.curDate))
      const dom = this.msDomain
      const span = Math.max(1, new Date(dom.max) - new Date(dom.min))
      for (const m of rows) {
        m.baseX = (100 * (new Date(m.baseDate) - new Date(dom.min))) / span
        m.curX = (100 * (new Date(m.curDate) - new Date(dom.min))) / span
      }
      return rows
    },
    msDomain() {
      const dates = []
      for (const d of this.matched) {
        if (!(d.cur.task_type || '').includes('Mile')) continue
        const c = displayEnd(d.cur) || displayStart(d.cur)
        const b = displayEnd(d.base) || displayStart(d.base)
        if (c) dates.push(new Date(c))
        if (b) dates.push(new Date(b))
      }
      if (!dates.length) return { min: null, max: null }
      const min = new Date(Math.min(...dates))
      const max = new Date(Math.max(...dates))
      // 4% padding each side so edge dots don't clip
      const pad = Math.max(86400000, (max - min) * 0.04)
      return { min: new Date(min - pad).toISOString(), max: new Date(+max + pad).toISOString() }
    },
    tornadoRows() {
      return [...this.dateChanges].sort((a, b) => Math.abs(b.deltaDays) - Math.abs(a.deltaDays)).slice(0, 30)
    },
    tornadoMax() {
      return Math.max(1, ...this.tornadoRows.map(d => Math.abs(d.deltaDays)))
    },
    durationChanges() {
      // The forensic reviewer proved this gap with a hand-perturbed file: a quiet
      // duration edit between submissions is exactly the kind of change a diff must
      // surface. Compares original (target) durations, in the activity's own calendar.
      return this.matched
        .filter(d => d.cur.duration_hrs !== d.base.duration_hrs)
        .map(d => ({ ...d, deltaDays: Math.round(((d.cur.duration_hrs - d.base.duration_hrs) / (d.cur.calendar_hrs_per_day || 8)) * 10) / 10 }))
        .sort((a, b) => Math.abs(b.deltaDays) - Math.abs(a.deltaDays))
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
          set.add(`${code} (${REL_TYPE_LABELS[p.type] || p.type}${p.lag_hrs ? ' ' + formatLag(p.lag_hrs) : ''})`)
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
    formatFloat,
    formatHours,
    displayStart,
    displayEnd,
    toggle(key) {
      this.expanded[key] = !this.expanded[key]
    },
  },
}
</script>

<style scoped>
.compare-wrap { display: flex; flex-direction: column; background: var(--white); border: 1px solid var(--gray-300); border-radius: var(--radius-md); overflow: hidden; }

.scorecard { display: flex; flex-wrap: wrap; gap: 1px; background: var(--gray-300); border-bottom: 1px solid var(--gray-300); }
.score-item { flex: 1; min-width: 110px; background: var(--white); padding: var(--space-3); text-align: center; }
.score-item.pass .score-count { color: var(--ok); }
.score-item.fail .score-count { color: var(--crit); }
.score-count { font-family: var(--font-mono); font-size: 23px; font-weight: 700; }
.score-label { font: var(--text-micro); color: var(--gray-700); text-transform: uppercase; letter-spacing: 0.03em; }
.stability-note { font: var(--text-small); color: var(--gray-700); padding: var(--space-2) var(--space-4); margin: 0; background: var(--gray-100); border-bottom: 1px solid var(--gray-300); }

.compare-section { border-bottom: 1px solid var(--gray-300); }
.compare-section:last-child { border-bottom: none; }
.section-title { font: 600 15px/1.4 var(--font-ui); }
.section-head { width: 100%; display: flex; align-items: center; gap: var(--space-4); padding: var(--space-3) var(--space-4); background: var(--gray-100); border: none; cursor: pointer; text-align: left; }
.section-head:hover { background: var(--gray-150); }
.section-title { font-weight: 600; color: var(--ink); white-space: nowrap; }
.section-title em { font-style: normal; color: var(--accent); font-family: var(--font-mono); }
.section-hint { font: var(--text-small); color: var(--gray-700); flex: 1; }
.chevron { transition: transform 0.15s; color: var(--gray-500); font-size: 19px; }
.chevron.open { transform: rotate(90deg); }
.section-body { padding: var(--space-4); }
.section-body h4 { font: var(--text-small); font-weight: 700; color: var(--ink); margin: var(--space-4) 0 var(--space-2); }
.section-body h4:first-child { margin-top: 0; }
.empty-state { font: var(--text-small); color: var(--ok); }

.compare-table { width: 100%; border-collapse: collapse; font: var(--text-small); }
.compare-table th { text-align: left; font: var(--text-micro); text-transform: uppercase; color: var(--gray-700); background: var(--gray-100); border-bottom: 2px solid var(--gray-300); padding: var(--space-2) var(--space-3); }
.compare-table td { padding: 6px var(--space-3); border-bottom: 1px solid var(--gray-150); }
.jump-row { cursor: pointer; }
.jump-row:hover td { background: var(--accent-soft); }
.code { font-family: var(--font-mono); font-weight: 600; color: var(--accent); white-space: nowrap; }
.name-cell { color: var(--ink-soft); }
.num-cell { font-family: var(--font-mono); text-align: right; white-space: nowrap; }
/* Verdict banner */
.cmp-verdict { padding: var(--space-4); border-bottom: 1px solid var(--gray-300); }
.cmp-verdict.v-slip { background: var(--crit-tint); }
.cmp-verdict.v-gain { background: var(--ok-tint); }
.cmp-verdict.v-hold { background: var(--gray-100); }
.verdict-main { display: flex; align-items: baseline; gap: var(--space-3); flex-wrap: wrap; }
.verdict-label { font: var(--text-micro); text-transform: uppercase; letter-spacing: 0.05em; color: var(--gray-700); }
.verdict-dates { font-family: var(--font-mono); font-size: 19px; font-weight: 600; color: var(--ink); }
.verdict-arrow { color: var(--gray-500); }
.verdict-delta { font-family: var(--font-mono); font-size: 27px; font-weight: 800; }
.v-slip .verdict-delta, .v-slip .verdict-word { color: var(--crit); }
.v-gain .verdict-delta, .v-gain .verdict-word { color: var(--ok); }
.v-hold .verdict-delta, .v-hold .verdict-word { color: var(--gray-700); }
.verdict-word { font-weight: 700; }
.verdict-sub { font: var(--text-small); color: var(--gray-700); margin-top: 2px; }

/* Milestone dumbbells */
.dumbbell-chart { display: flex; flex-direction: column; gap: 2px; }
.db-row { display: grid; grid-template-columns: minmax(180px, 320px) 1fr 52px; align-items: center; gap: var(--space-3); padding: 3px var(--space-2); border-radius: var(--radius-sm); cursor: pointer; }
.db-row:hover { background: var(--accent-soft); }
.db-label { font: var(--text-small); color: var(--ink-soft); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.db-track { position: relative; height: 18px; background: linear-gradient(to bottom, transparent 8px, var(--gray-150) 8px, var(--gray-150) 10px, transparent 10px); }
.db-join { position: absolute; top: 7px; height: 4px; border-radius: 2px; }
.db-join.db-slip { background: var(--crit); opacity: 0.45; }
.db-join.db-gain { background: var(--ok); opacity: 0.45; }
.db-dot { position: absolute; top: 4px; width: 10px; height: 10px; border-radius: 50%; transform: translateX(-5px); box-sizing: border-box; }
.db-base { background: var(--white); border: 2px solid var(--gray-500); }
.db-cur { border: 2px solid transparent; }
.db-cur.db-slip { background: var(--crit); }
.db-cur.db-gain { background: var(--ok); }
.db-cur.db-hold { background: var(--gray-500); }
.db-delta { font-family: var(--font-mono); font-size: 13px; text-align: right; white-space: nowrap; }
.db-zero { color: var(--gray-500); }
.db-axis { display: flex; justify-content: space-between; font: var(--text-micro); color: var(--gray-700); font-family: var(--font-mono); margin-top: var(--space-2); padding: 0 var(--space-2); }
.db-axis-legend { font-family: var(--font-ui); }
.db-inline { position: static; display: inline-block; transform: none; vertical-align: -1px; }

/* Slip tornado */
.tornado { display: flex; flex-direction: column; gap: 1px; }
.tor-row { display: grid; grid-template-columns: minmax(180px, 320px) 1fr 52px; align-items: center; gap: var(--space-3); padding: 2px var(--space-2); border-radius: var(--radius-sm); cursor: pointer; }
.tor-row:hover { background: var(--accent-soft); }
.tor-label { font: var(--text-small); color: var(--ink-soft); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.tor-track { display: flex; height: 14px; }
.tor-half { flex: 1; position: relative; }
.tor-left { border-right: 2px solid var(--gray-500); }
.tor-left .tor-bar { position: absolute; right: 0; top: 2px; bottom: 2px; border-radius: 3px 0 0 3px; }
.tor-right .tor-bar { position: absolute; left: 0; top: 2px; bottom: 2px; border-radius: 0 3px 3px 0; }
.tor-bar.tor-slip { background: var(--crit); }
.tor-bar.tor-gain { background: var(--ok); }
.tor-delta { font-family: var(--font-mono); font-size: 13px; text-align: right; white-space: nowrap; }
.tor-note { font: var(--text-micro); color: var(--gray-700); margin-top: var(--space-2); }

/* Milestone movement and the biggest movers answer the same question at two
   scales; side by side they are read together instead of scrolled between. */
.cmp-side-by-side { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 1px; background: var(--line); }
.cmp-side-by-side > .compare-section { background: var(--panel); border-bottom: none; }
@media (max-width: 1200px) { .cmp-side-by-side { grid-template-columns: 1fr; } }

.lag-neg { color: var(--crit); font-weight: 700; }
.lag-pos { color: var(--ok); font-weight: 700; }
.links-cell { font: var(--text-micro); font-family: var(--font-mono); }
.links-cell.added { color: var(--ok); }
.links-cell.removed { color: var(--crit); }
</style>
