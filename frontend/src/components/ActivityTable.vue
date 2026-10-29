<template>
  <div class="table-controls">
    <input
      type="text"
      v-model="search"
      placeholder="Search code, name, or WBS..."
      class="search-input"
    />
    <select v-model="statusFilter" class="filter-select" aria-label="Status">
      <option value="">All statuses</option>
      <option value="TK_NotStart">Not Started</option>
      <option value="TK_Active">Active</option>
      <option value="TK_Complete">Complete</option>
    </select>
    <label class="filter-toggle">
      <input type="checkbox" v-model="showCriticalOnly" />
      Critical only
    </label>
    <span v-for="t in codeTypesAvailable" :key="t" class="code-filter-group">
      <span class="code-filter-src" aria-hidden="true">{{ t }}</span>
      <select v-model="codeFilters[t]" class="filter-select" :aria-label="t" :title="`P6 activity code category '${t}' — name and values read verbatim from this file's ACTVTYPE/ACTVCODE tables`">
        <option value="">All {{ t }}</option>
        <option v-for="c in codeValuesByType.get(t)" :key="c" :value="c">{{ c }}</option>
      </select>
    </span>
    <button class="btn-outline btn-export-view" @click="$emit('export-view', filteredActivities)">
      Export view (.csv)
    </button>
  </div>
  <div class="table-wrap" ref="wrap" tabindex="0" aria-label="Activities" @scroll="onScroll">
    <table class="data-table">
      <thead>
        <tr>
          <th @click="sortBy('task_code')" class="sortable">Code {{ sortIcon('task_code') }}</th>
          <th @click="sortBy('task_name')" class="sortable name-col">Activity {{ sortIcon('task_name') }}</th>
          <th @click="sortBy('status')" class="sortable">Status {{ sortIcon('status') }}</th>
          <th @click="sortBy('pct_complete')" class="sortable num">% {{ sortIcon('pct_complete') }}</th>
          <th @click="sortBy('duration_hrs')" class="sortable num">Dur {{ sortIcon('duration_hrs') }}</th>
          <th @click="sortBy('early_start')" class="sortable num">Start {{ sortIcon('early_start') }}</th>
          <th @click="sortBy('early_end')" class="sortable num">End {{ sortIcon('early_end') }}</th>
          <th @click="sortBy('total_float_hrs')" class="sortable num">Float {{ sortIcon('total_float_hrs') }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="filteredActivities.length === 0" class="table-empty-row">
          <td :colspan="8">
            <span class="table-empty">No activities match the current filters.</span>
          </td>
        </tr>
        <!-- Only the rows in view are drawn; these keep the scroll height of the rest. -->
        <tr v-if="padTop" class="vt-pad" aria-hidden="true"><td colspan="8" :style="{ height: padTop + 'px' }"></td></tr>
        <tr
          v-for="act in shownActivities"
          :key="act.task_id"
          :class="['act-row', { critical: act.is_critical, 'negative-float': act.is_negative_float, milestone: isMilestone(act) }]"
          @click="selectedAct = selectedAct?.task_id === act.task_id ? null : act"
        >
          <td class="code">{{ act.task_code }}</td>
          <td class="name-cell">
            <i v-if="annotations[act.task_id]" class="annotation-dot" :class="'sev-' + annotations[act.task_id].severity" :title="annotations[act.task_id].note"></i>
            <span class="act-name">{{ act.task_name }}</span>
            <span v-if="isMilestone(act)" class="badge-milestone">M</span>
          </td>
          <td><span class="status-badge" :class="act.status"><i class="status-dot"></i>{{ statusLabel(act.status) }}</span></td>
          <td class="num-cell">
            <div class="prog-bar">
              <div class="prog-fill" :style="{ width: act.pct_complete + '%' }"></div>
            </div>
            <span class="prog-text">{{ act.pct_complete }}%</span>
          </td>
          <td class="num-cell">{{ formatHours(act.duration_hrs, act.calendar_hrs_per_day) }}</td>
          <td class="num-cell">{{ formatDate(displayStart(act)) }}</td>
          <td class="num-cell">{{ formatDate(displayEnd(act)) }}</td>
          <td class="num-cell" :class="floatClass(act.total_float_hrs)">{{ formatFloat(act.total_float_hrs, act.calendar_hrs_per_day) }}</td>
        </tr>
        <tr v-if="padBottom" class="vt-pad" aria-hidden="true"><td colspan="8" :style="{ height: padBottom + 'px' }"></td></tr>
        <tr v-if="selectedAct" class="rel-row">
          <td colspan="8">
            <div class="rel-wbs-path" v-if="selectedAct.wbs_path">{{ selectedAct.wbs_path }}</div>
            <div class="rel-panel">
              <div class="rel-col">
                <h4>Predecessors ({{ selectedAct.predecessors.length }})</h4>
                <div v-if="selectedAct.predecessors.length === 0" class="rel-empty">None</div>
                <div v-for="p in selectedAct.predecessors" :key="p.task_id" class="rel-item">
                  <span class="rel-code">{{ getActCode(p.task_id) }}</span>
                  <span class="rel-type">{{ p.type }}</span>
                  <span v-if="p.lag_hrs" class="rel-lag">{{ p.lag_hrs }}h</span>
                </div>
              </div>
              <div class="rel-col">
                <h4>Successors ({{ selectedAct.successors.length }})</h4>
                <div v-if="selectedAct.successors.length === 0" class="rel-empty">None</div>
                <div v-for="s in selectedAct.successors" :key="s.task_id" class="rel-item">
                  <span class="rel-code">{{ getActCode(s.task_id) }}</span>
                  <span class="rel-type">{{ s.type }}</span>
                  <span v-if="s.lag_hrs" class="rel-lag">{{ s.lag_hrs }}h</span>
                </div>
              </div>
            </div>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script lang="ts">
import { defineComponent, type PropType } from 'vue'
import type { Activity, Schedule } from '../types/schedule'
import type { Annotations } from '../utils/annotations'
import { compareBy, type SortDir } from '../utils/sort'
import { formatDate, formatHours, formatFloat, statusLabel, isMilestone } from '../utils/format'
import { displayStart, displayEnd } from '../utils/p6'
import { visibleRowRange } from '../utils/virtual'

// Kept off the component's reactive state.
const resizeObservers = new WeakMap<object, ResizeObserver>()

type SortField = 'task_code' | 'task_name' | 'status' | 'pct_complete' | 'duration_hrs' | 'early_start' | 'early_end' | 'total_float_hrs'

// The activity list: every activity of the file, searchable, filterable and sortable,
// with an activity's links shown when it is clicked.
export default defineComponent({
  name: 'ActivityTable',
  props: {
    data: { type: Object as PropType<Schedule>, required: true },
    annotations: { type: Object as PropType<Annotations>, default: () => ({}) },
  },
  emits: ['export-view'],
  mounted() {
    const wrap = this.$refs.wrap as HTMLElement
    this.viewH = wrap.clientHeight || this.viewH
    resizeObservers.set(this, new ResizeObserver(() => { this.viewH = wrap.clientHeight || this.viewH }))
    resizeObservers.get(this)!.observe(wrap)
    this.measureRow()
  },
  updated() {
    this.measureRow()
  },
  beforeUnmount() {
    resizeObservers.get(this)?.disconnect()
  },
  data() {
    return {
      search: '',
      statusFilter: '',
      showCriticalOnly: false,
      sortField: 'total_float_hrs' as SortField,
      sortDir: 'asc' as SortDir,
      selectedAct: null as Activity | null,
      // Windowing: the list's scroll position and height, and one row's height.
      scrollTop: 0,
      viewH: 800,
      rowH: 34,
      codeFilters: Object.fromEntries((this.data.project.activity_code_types || []).map(t => [t, ''])) as Record<string, string>,
    }
  },
  computed: {
    filteredActivities(): Activity[] {
      let acts = [...this.data.activities]
      if (this.search) {
        const q = this.search.toLowerCase()
        acts = acts.filter(a =>
          a.task_code.toLowerCase().includes(q) ||
          a.task_name.toLowerCase().includes(q) ||
          (a.wbs_path && a.wbs_path.toLowerCase().includes(q))
        )
      }
      if (this.statusFilter) {
        acts = acts.filter(a => a.status === this.statusFilter)
      }
      if (this.showCriticalOnly) {
        acts = acts.filter(a => a.is_critical)
      }
      const activeCodeFilters = Object.entries(this.codeFilters).filter(([, v]) => v)
      if (activeCodeFilters.length) {
        acts = acts.filter(a =>
          activeCodeFilters.every(([type, code]) => a.activity_codes.some(c => c.type === type && c.code === code))
        )
      }
      // Sort. Unknown values (P6 leaves total float blank on completed work) sort
      // last rather than being treated as zero — see utils/sort.js.
      acts.sort(compareBy((x: Activity) =>
        this.sortField === 'early_start' ? displayStart(x) :
        this.sortField === 'early_end' ? displayEnd(x) : x[this.sortField],
      this.sortDir))
      return acts
    },
    rowWindow(): { from: number; to: number } {
      return visibleRowRange(this.scrollTop, this.viewH, this.rowH, this.filteredActivities.length)
    },
    shownActivities(): Activity[] {
      return this.filteredActivities.slice(this.rowWindow.from, this.rowWindow.to)
    },
    padTop(): number {
      return this.rowWindow.from * this.rowH
    },
    padBottom(): number {
      return (this.filteredActivities.length - this.rowWindow.to) * this.rowH
    },
    codeById(): Map<number, string> {
      return new Map(this.data.activities.map(a => [a.task_id, a.task_code]))
    },
    codeTypesAvailable(): string[] {
      return this.data.project.has_activity_codes ? this.data.project.activity_code_types : []
    },
    codeValuesByType(): Map<string, string[]> {
      const sets = new Map<string, Set<string>>()
      for (const t of this.codeTypesAvailable) sets.set(t, new Set())
      for (const a of this.data.activities) {
        for (const c of a.activity_codes) {
          sets.get(c.type)?.add(c.code)
        }
      }
      const m = new Map<string, string[]>()
      for (const [t, set] of sets) m.set(t, [...set].sort())
      return m
    },
  },
  methods: {
    sortBy(field: SortField) {
      if (this.sortField === field) {
        this.sortDir = this.sortDir === 'asc' ? 'desc' : 'asc'
      } else {
        this.sortField = field
        this.sortDir = 'asc'
      }
    },
    sortIcon(field: SortField) {
      if (this.sortField !== field) return ''
      return this.sortDir === 'asc' ? '\u25B2' : '\u25BC'
    },
    // Same 0h / ≤80h (10d) thresholds as the Gantt and network diagram, so "critical" and
    // "near-critical" mean exactly the same thing — and use exactly the same colors — in
    // every view instead of each surface inventing its own float-banding scheme.
    floatClass(f: number | null | undefined) {
      if (f == null) return ''
      if (f < 0) return 'float-neg'
      if (f === 0) return 'float-crit'
      if (f <= 80) return 'float-near'
      return ''
    },
    getActCode(tid: number) {
      return this.codeById.get(tid) ?? '?' + tid
    },
    onScroll(e: Event) {
      this.scrollTop = (e.target as HTMLElement).scrollTop
    },
    // Rows are one line each (cells don't wrap), so the drawn rows' mean height sizes
    // them all. Measured across the rows, not rounded from one: collapsed borders make
    // heights fractional, and a rounding error repeated over thousands of rows adds up.
    measureRow() {
      const wrap = this.$refs.wrap as HTMLElement | undefined
      const rows = wrap?.querySelectorAll<HTMLElement>('tbody tr.act-row')
      if (!rows || rows.length < 2) return
      const h = (rows[rows.length - 1].getBoundingClientRect().bottom - rows[0].getBoundingClientRect().top) / rows.length
      if (h > 0 && Math.abs(h - this.rowH) > 0.01) this.rowH = h
    },
    formatDate,
    formatHours,
    formatFloat,
    statusLabel,
    isMilestone,
    displayStart,
    displayEnd,
  },
})
</script>

<style scoped>
.vt-pad td { padding: 0; border: 0; }
.data-table tbody tr.vt-pad:hover td { background: none; }
</style>
