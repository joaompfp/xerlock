<template>
  <div class="app">
    <!-- Upload screen -->
    <div v-if="!data" class="upload-screen">
      <div class="upload-card">
        <div class="logo">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" class="logo-icon" stroke-width="1.5">
            <rect x="3" y="3" width="18" height="18" rx="2" />
            <path d="M3 9h18" />
            <path d="M9 3v18" />
            <path d="M7 12l2 2 4-4" />
          </svg>
        </div>
        <h1>Schedule App</h1>
        <p class="subtitle">Primavera P6 XER viewer with critical path analysis</p>

        <div class="reopen-card" v-if="lastFile">
          <div class="reopen-info">
            <strong>{{ lastFile.filename }}</strong>
            <span>Last opened {{ timeAgo(lastFile.savedAt) }}</span>
          </div>
          <div class="reopen-actions">
            <button class="btn-outline" @click="reopenLastFile">Reopen</button>
            <button class="btn-forget" title="Forget this file" @click="forgetLastFile">&times;</button>
          </div>
        </div>

        <div
          class="drop-zone"
          @dragover.prevent="dragOver = true"
          @dragleave="dragOver = false"
          @drop.prevent="handleDrop"
          :class="{ active: dragOver }"
        >
          <input type="file" accept=".xer" @change="handleFile" id="fileInput" />
          <label for="fileInput">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M12 5v14M5 12h14" />
            </svg>
            <span v-if="!loading">Drop a .xer file here, or click to browse</span>
            <span v-else class="loading">Parsing schedule...</span>
          </label>
        </div>
        <p class="hint">Files are parsed on the server in memory and never stored. Your last file is kept in this browser only, so you can reopen it without re-uploading.</p>
        <a class="gh-link" href="https://github.com/joaompfp/schedule-app" target="_blank" rel="noopener">
          <svg width="15" height="15" viewBox="0 0 16 16" fill="currentColor"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27s1.36.09 2 .27c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8z"/></svg>
          Open source on GitHub
        </a>
      </div>
    </div>

    <!-- Dashboard -->
    <div v-else class="dashboard" :class="{ 'header-collapsed': headerCollapsed }">
      <!-- Parse warnings (multi-project file, suspect encoding, …) — a reviewer must never
           discover these by accident, so they persist until explicitly dismissed. -->
      <div v-if="visibleWarnings.length" class="parse-warnings">
        <div v-for="(w, i) in visibleWarnings" :key="i" class="parse-warning">
          <span>{{ w }}</span>
          <button class="warning-dismiss" @click="dismissWarning(w)" title="Dismiss">&times;</button>
        </div>
      </div>
      <template v-if="!headerCollapsed">
        <!-- Header -->
        <header class="header">
          <div class="header-left">
            <h1>{{ data.project.proj_short_name }}</h1>
            <span class="header-meta">{{ data.project.total_activities }} activities &middot; {{ data.project.total_wbs }} WBS nodes &middot; {{ data.project.earliest_start ? formatDate(data.project.earliest_start) : '—' }} &rarr; {{ data.project.latest_end ? formatDate(data.project.latest_end) : '—' }}</span>
          </div>
          <div class="header-right">
            <button class="btn-outline" v-if="annotationCount > 0" @click="doExport(() => exportReviewReport(data, annotations))">
              Export Review Report ({{ annotationCount }})
            </button>
            <button class="btn-outline" @click="doExport(() => exportWorkbook(data))">
              Export to Excel (.xlsx)
            </button>
            <button class="btn-outline" @click="data = null">Load another</button>
          </div>
        </header>

        <!-- Key metrics strip -->
        <div class="metrics-strip">
          <div class="metric">
            <strong>{{ data.project.total_activities }}</strong>
            <span>Activities</span>
          </div>
          <div class="metric">
            <strong :class="data.project.total_critical > 0 ? 'is-crit' : 'is-ok'">{{ data.project.total_critical }}</strong>
            <span>Critical (TF&le;0)</span>
          </div>
          <div class="metric" v-if="data.project.total_negative_float > 0">
            <strong class="is-crit">{{ data.project.total_negative_float }}</strong>
            <span>Negative Float</span>
          </div>
          <div class="metric">
            <strong :class="data.project.total_longest_path > 0 ? 'is-crit' : 'is-ok'">{{ data.project.total_longest_path }}</strong>
            <span>Longest Path</span>
          </div>
          <div class="metric">
            <strong>{{ data.project.total_milestones }}</strong>
            <span>Milestones</span>
          </div>
          <div class="metric">
            <strong>{{ data.project.pct_complete }}%</strong>
            <span>Complete</span>
          </div>
        </div>
      </template>

      <!-- Tab navigation -->
      <nav class="tabs">
        <a class="brand" href="https://github.com/joaompfp/schedule-app" target="_blank" rel="noopener" title="Schedule App on GitHub">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" class="brand-icon" stroke-width="1.8">
            <rect x="3" y="3" width="18" height="18" rx="2" />
            <path d="M3 9h18" />
            <path d="M9 3v18" />
            <path d="M7 12l2 2 4-4" />
          </svg>
          <span class="brand-name">Schedule App</span>
        </a>
        <button :class="{ active: tab === 'gantt' }" @click="tab = 'gantt'">Gantt Chart</button>
        <button :class="{ active: tab === 'story' }" @click="tab = 'story'">Critical Path</button>
        <button :class="{ active: tab === 'table' }" @click="tab = 'table'">Activity Table</button>
        <button :class="{ active: tab === 'wbs' }" @click="tab = 'wbs'">WBS Tree</button>
        <button :class="{ active: tab === 'progress' }" @click="tab = 'progress'">Progress</button>
        <button :class="{ active: tab === 'health' }" @click="tab = 'health'">Health Check</button>
        <button :class="{ active: tab === 'compare' }" @click="tab = 'compare'">Compare</button>
        <select class="theme-select" v-model="theme" title="Color theme">
          <option v-for="(label, key) in themeOptions" :key="key" :value="key">{{ label }}</option>
        </select>
        <button class="btn-collapse" @click="headerCollapsed = !headerCollapsed" :title="headerCollapsed ? 'Show header' : 'Hide header for more room'">
          {{ headerCollapsed ? '⌄ Show header' : '⌃ Hide header' }}
        </button>
      </nav>

      <!-- Gantt Chart (primary view) -->
      <div v-if="tab === 'gantt'" class="section section-full">
        <GanttChart
          :data="data"
          :extra-room="headerCollapsed"
          :jump-to="pendingJump"
          :annotations="annotations"
          @jumped="pendingJump = null"
          @annotate="setAnnotation"
          @unannotate="removeAnnotationFor"
        />
      </div>

      <!-- Critical Path Graph -->
      <div v-if="tab === 'story'" class="section section-full">
        <CriticalPathGraph
          :activities="data.activities"
          :extra-room="headerCollapsed"
          :annotations="annotations"
          @annotate="setAnnotation"
          @unannotate="removeAnnotationFor"
        />
      </div>
      <div v-if="tab === 'story'" class="section">
        <!-- Near-critical watchlist -->
        <div class="insight-card" v-if="nearCritical.length > 0">
          <h3>Near-critical watchlist</h3>
          <p class="subtitle">Activities with low float that could become critical.</p>
          <table class="data-table">
            <thead>
              <tr>
                <th>Code</th>
                <th>Activity</th>
                <th>Float</th>
                <th>Duration</th>
                <th>End</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="act in nearCritical" :key="act.task_id">
                <td class="code">{{ act.task_code }}</td>
                <td class="name-cell">{{ act.task_name }}</td>
                <td class="float-cell num-cell">{{ formatFloat(act.total_float_hrs, act.calendar_hrs_per_day) }}</td>
                <td class="num-cell">{{ formatHours(act.duration_hrs, act.calendar_hrs_per_day) }}</td>
                <td class="num-cell">{{ formatDate(displayEnd(act)) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Activity Table -->
      <div v-if="tab === 'table'" class="section">
        <div class="table-controls">
          <input
            type="text"
            v-model="search"
            placeholder="Search code, name, or WBS..."
            class="search-input"
          />
          <select v-model="statusFilter" class="filter-select">
            <option value="">All statuses</option>
            <option value="TK_NotStart">Not Started</option>
            <option value="TK_Active">Active</option>
            <option value="TK_Complete">Complete</option>
          </select>
          <label class="filter-toggle">
            <input type="checkbox" v-model="showCriticalOnly" />
            Critical only
          </label>
          <select v-for="t in codeTypesAvailable" :key="t" v-model="codeFilters[t]" class="filter-select">
            <option value="">All {{ t }}</option>
            <option v-for="c in codeValuesByType.get(t)" :key="c" :value="c">{{ c }}</option>
          </select>
          <button class="btn-outline btn-export-view" @click="doExport(() => exportActivitiesCsv(data, filteredActivities, slugName() + '-filtered.csv'))">
            Export view (.csv)
          </button>
        </div>
        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th @click="sortBy('task_code')" class="sortable">Code {{ sortIcon('task_code') }}</th>
                <th @click="sortBy('task_name')" class="sortable name-col">Activity {{ sortIcon('task_name') }}</th>
                <th @click="sortBy('status')" class="sortable">Status {{ sortIcon('status') }}</th>
                <th @click="sortBy('pct_complete')" class="sortable">% {{ sortIcon('pct_complete') }}</th>
                <th @click="sortBy('duration_hrs')" class="sortable">Dur {{ sortIcon('duration_hrs') }}</th>
                <th @click="sortBy('early_start')" class="sortable">Start {{ sortIcon('early_start') }}</th>
                <th @click="sortBy('early_end')" class="sortable">End {{ sortIcon('early_end') }}</th>
                <th @click="sortBy('total_float_hrs')" class="sortable">Float {{ sortIcon('total_float_hrs') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="act in filteredActivities"
                :key="act.task_id"
                :class="{ critical: act.is_critical, 'negative-float': act.is_negative_float, milestone: isMilestone(act) }"
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
      </div>

      <!-- WBS Tree -->
      <div v-if="tab === 'wbs'" class="section">
        <div class="wbs-tree">
          <WBSNode
            v-for="(node, i) in data.wbs_tree"
            :key="node.wbs_id"
            :node="node"
            :level="0"
            :index="i"
          />
        </div>
      </div>

      <!-- Progress -->
      <div v-if="tab === 'progress'" class="section section-full">
        <ProgressView :data="data" @jump="jumpToActivity" />
      </div>

      <!-- Health Check -->
      <div v-if="tab === 'health'" class="section section-full">
        <HealthCheck :data="data" @jump="jumpToActivity" />
      </div>

      <!-- Compare -->
      <div v-if="tab === 'compare'" class="section section-full">
        <CompareView
          v-if="compareData"
          :current="data"
          :baseline="compareData"
          :baseline-filename="compareFilename"
          @jump="jumpToActivity"
          @reset="compareData = null"
        />
        <div v-else class="compare-upload-card">
          <h2>Compare against a previous snapshot</h2>
          <p class="subtitle">Upload an earlier export of this same project (e.g. last month's contractor submission) to see what changed — slipped dates, float erosion, logic changes, and critical path movement.</p>
          <div
            class="drop-zone"
            @dragover.prevent="compareDragOver = true"
            @dragleave="compareDragOver = false"
            @drop.prevent="handleCompareDrop"
            :class="{ active: compareDragOver }"
          >
            <input type="file" accept=".xer" @change="handleCompareFile" id="compareFileInput" />
            <label for="compareFileInput">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                <path d="M12 5v14M5 12h14" />
              </svg>
              <span v-if="!compareLoading">Drop a .xer file here, or click to browse</span>
              <span v-else class="loading">Parsing schedule...</span>
            </label>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import WBSNode from './components/WBSNode.vue'
import CriticalPathGraph from './components/CriticalPathGraph.vue'
import GanttChart from './components/GanttChart.vue'
import HealthCheck from './components/HealthCheck.vue'
import ProgressView from './components/ProgressView.vue'
import CompareView from './components/CompareView.vue'
import { formatDate, formatHours, statusLabel, isMilestone, formatFloat, timeAgo } from './utils/format'
import { exportWorkbook, exportActivitiesCsv, exportReviewReport } from './utils/export'
import { loadLastFile, saveLastFile, clearLastFile } from './utils/lastFile'
import { loadAnnotations, saveAnnotation, removeAnnotation } from './utils/annotations'
import { displayStart, displayEnd } from './utils/p6'

function applyTheme(theme) {
  // Default theme lives on :root directly; named themes override via the attribute.
  if (theme === 'sepia') document.documentElement.removeAttribute('data-theme')
  else document.documentElement.setAttribute('data-theme', theme)
}

export default {
  name: 'App',
  components: { WBSNode, CriticalPathGraph, GanttChart, HealthCheck, ProgressView, CompareView },
  data() {
    return {
      data: null,
      loading: false,
      dragOver: false,
      tab: 'gantt',
      headerCollapsed: true,
      search: '',
      statusFilter: '',
      showCriticalOnly: false,
      sortField: 'total_float_hrs',
      sortDir: 'asc',
      selectedAct: null,
      exporting: false,
      lastFile: loadLastFile(),
      pendingJump: null,
      codeFilters: {},
      annotations: {},
      compareData: null,
      compareFilename: '',
      dismissedWarnings: [],
      theme: localStorage.getItem('schedule-app:theme') || 'sepia',
      themeOptions: { sepia: 'Sepia', slate: 'Slate', clay: 'Clay', ink: 'Ink' },
      compareLoading: false,
      compareDragOver: false,
    }
  },
  created() {
    applyTheme(this.theme)
  },
  watch: {
    theme(t) {
      applyTheme(t)
      try { localStorage.setItem('schedule-app:theme', t) } catch { /* storage unavailable */ }
    },
  },
  computed: {
    filteredActivities() {
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
      // Sort
      acts.sort((a, b) => {
        const get = x =>
          this.sortField === 'early_start' ? displayStart(x) :
          this.sortField === 'early_end' ? displayEnd(x) : x[this.sortField]
        let va = get(a)
        let vb = get(b)
        if (typeof va === 'string') va = (va || '').toLowerCase()
        if (typeof vb === 'string') vb = (vb || '').toLowerCase()
        if (va == null) va = ''
        if (vb == null) vb = ''
        if (va < vb) return this.sortDir === 'asc' ? -1 : 1
        if (va > vb) return this.sortDir === 'asc' ? 1 : -1
        return 0
      })
      return acts
    },
    nearCritical() {
      if (!this.data) return []
      // Completed activities can't become critical — a watchlist entry for finished work
      // is pure noise to a reviewer.
      return this.data.activities
        .filter(a => a.status !== 'TK_Complete' && !a.is_critical && a.total_float_hrs > 0 && a.total_float_hrs <= 80)
        .sort((a, b) => a.total_float_hrs - b.total_float_hrs)
        .slice(0, 15)
    },
    visibleWarnings() {
      const ws = (this.data && this.data.warnings) || []
      return ws.filter(w => !this.dismissedWarnings.includes(w))
    },
    projectKey() {
      return this.data ? this.data.project.proj_short_name : null
    },
    annotationCount() {
      return Object.keys(this.annotations).length
    },
    codeTypesAvailable() {
      return this.data && this.data.project.has_activity_codes ? this.data.project.activity_code_types : []
    },
    codeValuesByType() {
      const m = new Map()
      for (const t of this.codeTypesAvailable) m.set(t, new Set())
      if (this.data) {
        for (const a of this.data.activities) {
          for (const c of a.activity_codes) {
            if (m.has(c.type)) m.get(c.type).add(c.code)
          }
        }
      }
      for (const [t, set] of m) m.set(t, [...set].sort())
      return m
    },
  },
  methods: {
    async handleDrop(e) {
      this.dragOver = false
      const file = e.dataTransfer.files[0]
      if (file) await this.uploadFile(file)
    },
    async handleFile(e) {
      const file = e.target.files[0]
      if (file) await this.uploadFile(file)
    },
    async handleCompareDrop(e) {
      this.compareDragOver = false
      const file = e.dataTransfer.files[0]
      if (file) await this.uploadCompareFile(file)
    },
    async handleCompareFile(e) {
      const file = e.target.files[0]
      if (file) await this.uploadCompareFile(file)
    },
    async uploadCompareFile(file) {
      if (!file.name.toLowerCase().endsWith('.xer')) {
        alert('Only .xer files are accepted')
        return
      }
      this.compareLoading = true
      const form = new FormData()
      form.append('file', file)
      try {
        const res = await fetch('/api/upload', { method: 'POST', body: form })
        if (!res.ok) {
          const err = await res.text()
          throw new Error(err)
        }
        this.compareData = await res.json()
        this.compareFilename = file.name
      } catch (e) {
        alert('Failed to parse: ' + e.message)
      } finally {
        this.compareLoading = false
      }
    },
    async uploadFile(file) {
      if (!file.name.toLowerCase().endsWith('.xer')) {
        alert('Only .xer files are accepted')
        return
      }
      this.loading = true
      const form = new FormData()
      form.append('file', file)
      try {
        const res = await fetch('/api/upload', { method: 'POST', body: form })
        if (!res.ok) {
          const err = await res.text()
          throw new Error(err)
        }
        const parsed = await res.json()
        this.activateData(parsed)
        saveLastFile(file.name, parsed)
        this.lastFile = loadLastFile()
      } catch (e) {
        alert('Failed to parse: ' + e.message)
      } finally {
        this.loading = false
      }
    },
    activateData(parsed) {
      this.data = parsed
      this.tab = 'gantt'
      this.search = ''
      this.statusFilter = ''
      this.showCriticalOnly = false
      this.selectedAct = null
      this.codeFilters = {}
      this.annotations = loadAnnotations(parsed.project.proj_short_name)
      this.dismissedWarnings = []
      this.compareData = null
      this.compareFilename = ''
    },
    reopenLastFile() {
      if (!this.lastFile) return
      this.activateData(this.lastFile.data)
    },
    forgetLastFile() {
      clearLastFile()
      this.lastFile = null
    },
    sortBy(field) {
      if (this.sortField === field) {
        this.sortDir = this.sortDir === 'asc' ? 'desc' : 'asc'
      } else {
        this.sortField = field
        this.sortDir = 'asc'
      }
    },
    sortIcon(field) {
      if (this.sortField !== field) return ''
      return this.sortDir === 'asc' ? '\u25B2' : '\u25BC'
    },
    formatDate,
    formatHours,
    displayStart,
    displayEnd,
    statusLabel,
    isMilestone,
    formatFloat,
    timeAgo,
    // Same 0h / ≤80h (10d) thresholds as the Gantt and network diagram, so "critical" and
    // "near-critical" mean exactly the same thing — and use exactly the same colors — in
    // every view instead of each surface inventing its own float-banding scheme.
    floatClass(f) {
      if (f == null) return ''
      if (f < 0) return 'float-neg'
      if (f === 0) return 'float-crit'
      if (f <= 80) return 'float-near'
      return ''
    },
    getActCode(tid) {
      const a = this.data.activities.find(a => a.task_id === tid)
      return a ? a.task_code : '?' + tid
    },
    dismissWarning(w) {
      this.dismissedWarnings.push(w)
    },
    jumpToActivity(taskId) {
      this.tab = 'gantt'
      this.pendingJump = taskId
    },
    slugName() {
      return (this.data.project.proj_short_name || 'schedule')
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/(^-|-$)/g, '')
    },
    async doExport(fn) {
      if (this.exporting) return
      this.exporting = true
      try {
        await fn()
      } catch (e) {
        alert('Export failed: ' + e.message)
      } finally {
        this.exporting = false
      }
    },
    exportWorkbook,
    exportActivitiesCsv,
    exportReviewReport,
    setAnnotation(taskId, patch) {
      this.annotations = saveAnnotation(this.projectKey, taskId, patch)
    },
    removeAnnotationFor(taskId) {
      this.annotations = removeAnnotation(this.projectKey, taskId)
    },
  },
}
</script>

<style>
/* ── Design tokens ──────────────────────────────────────────────────────── */
:root {
  /* Brand / structural */
  --ink: #1C1917;
  --ink-soft: #4A4038;
  --accent: #2951C4;
  --accent-soft: #E4EAFB;

  /* Semantic state — the ONLY colors allowed to represent criticality/float/status,
     used identically across the Gantt, network diagram, and activity table. */
  --crit: #A5291D;
  --crit-tint: #F7E1DC;
  --near: #8F6300;
  --near-tint: #F5EBD3;
  --ok: #3F7355;
  --ok-tint: #E2ECE3;
  --milestone: #6A3E9E;

  /* Neutrals (warm stone scale — paper/graphite, not blue-gray) */
  --gray-900: #1F1B17;
  --gray-700: #5C5347;
  --gray-500: #8C8175;
  --gray-300: #DCD5C9;
  --gray-150: #F1ECE4;
  --gray-100: #F8F5F0;
  --white: #FFFFFF;

  /* Type */
  --font-ui: "IBM Plex Sans", -apple-system, "Segoe UI", Roboto, sans-serif;
  --font-mono: "IBM Plex Mono", "SF Mono", "Fira Code", ui-monospace, monospace;
  --text-h1: 700 23px/1.3 var(--font-ui);
  --text-h2: 700 17px/1.3 var(--font-ui);
  --text-body: 400 14px/1.5 var(--font-ui);
  --text-small: 500 13px/1.4 var(--font-ui);
  --text-micro: 600 11px/1.3 var(--font-ui);

  /* Spacing & radius */
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-6: 24px;
  --space-8: 32px;
  --radius-sm: 4px;
  --radius-md: 8px;
}

/* ── Alternate themes ──────────────────────────────────────────────────────
   Only the structural colors (ink/accent/neutrals) re-theme. The semantic status
   colors (--crit/--near/--ok/--milestone) are deliberately IDENTICAL across themes:
   criticality must read the same no matter the wallpaper. */

/* Slate — cool graphite neutrals, deep indigo accent. */
[data-theme="slate"] {
  --ink: #16181D;
  --ink-soft: #3A414E;
  --accent: #3A55C0;
  --accent-soft: #E3E8FA;
  --gray-900: #191B1F;
  --gray-700: #4A5160;
  --gray-500: #7C8494;
  --gray-300: #D4D8DF;
  --gray-150: #ECEEF2;
  --gray-100: #F5F6F8;
}

/* Clay — the sepia warmth pushed further: terracotta accent on warm paper. */
[data-theme="clay"] {
  --ink: #221A15;
  --ink-soft: #52453C;
  --accent: #A6491F;
  --accent-soft: #F6E2D7;
  --gray-900: #241C16;
  --gray-700: #5E5248;
  --gray-500: #8E8276;
  --gray-300: #DED5CA;
  --gray-150: #F2ECE4;
  --gray-100: #F9F5F0;
}

/* Ink — near-monochrome: pure neutrals, near-black accent, minimal chrome. */
[data-theme="ink"] {
  --ink: #111111;
  --ink-soft: #3D3D3D;
  --accent: #1F1F1F;
  --accent-soft: #E9E9E9;
  --gray-900: #1A1A1A;
  --gray-700: #4F4F4F;
  --gray-500: #8A8A8A;
  --gray-300: #D9D9D9;
  --gray-150: #EFEFEF;
  --gray-100: #F7F7F7;
}

/* ── Reset & base ── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: var(--font-ui); background: var(--white); color: var(--ink); font-size: 16px; line-height: 1.5; -webkit-font-smoothing: antialiased; }

/* Every number in the app reads as instrument output, not prose — codes, dates,
   durations, floats, percentages all get tabular monospace digits. */
.code, .g-act-code, .rel-code, .detail-code, .float-cell, .float-crit, .float-near,
.num-cell {
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
}

/* ── Upload screen ── */
.upload-screen { display: flex; align-items: center; justify-content: center; min-height: 100vh; padding: var(--space-6); }
.upload-card { text-align: center; max-width: 480px; }
.upload-card .logo { margin-bottom: var(--space-4); }
.logo-icon { stroke: var(--accent); }
.upload-card h1 { font: var(--text-h1); color: var(--ink); margin-bottom: var(--space-1); }
.upload-card .subtitle { font: var(--text-body); color: var(--gray-700); margin-bottom: var(--space-8); }
.reopen-card { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); background: var(--accent-soft); border: 1px solid var(--accent); border-radius: var(--radius-md); padding: var(--space-3) var(--space-4); margin-bottom: var(--space-4); text-align: left; }
.reopen-info { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.reopen-info strong { font: var(--text-body); color: var(--ink); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.reopen-info span { font: var(--text-micro); color: var(--gray-700); text-transform: uppercase; letter-spacing: 0.04em; }
.reopen-actions { display: flex; align-items: center; gap: var(--space-2); flex-shrink: 0; }
.btn-forget { border: none; background: none; color: var(--gray-500); font-size: 19px; line-height: 1; cursor: pointer; padding: 4px 6px; border-radius: var(--radius-sm); }
.btn-forget:hover { background: var(--white); color: var(--crit); }
.compare-upload-card { max-width: 560px; margin: var(--space-8) auto; text-align: center; }
.compare-upload-card h2 { font: var(--text-h2); color: var(--ink); margin-bottom: var(--space-2); }
.compare-upload-card .subtitle { color: var(--gray-700); margin-bottom: var(--space-5); }
.drop-zone { border: 1px solid var(--gray-300); border-radius: var(--radius-md); padding: 48px var(--space-6); cursor: pointer; transition: all 0.2s; background: var(--gray-100); }
.drop-zone:hover, .drop-zone.active { border-color: var(--accent); background: var(--accent-soft); }
.drop-zone input { display: none; }
.drop-zone label { display: flex; flex-direction: column; align-items: center; gap: var(--space-3); cursor: pointer; color: var(--gray-700); font: var(--text-body); }
.drop-zone label svg { color: var(--accent); }
.drop-zone .loading { color: var(--accent); font-weight: 600; }
.hint { font: var(--text-small); color: var(--gray-500); margin-top: var(--space-4); }
.gh-link { display: inline-flex; align-items: center; gap: 6px; margin-top: var(--space-4); font: var(--text-small); color: var(--gray-700); text-decoration: none; }
.gh-link:hover { color: var(--accent); }

/* ── Dashboard ── */
.dashboard { max-width: 1200px; margin: 0 auto; padding: var(--space-6); }
.dashboard.header-collapsed { padding-top: 10px; }

/* Header */
.header { display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--space-6); padding-bottom: var(--space-4); border-bottom: 2px solid var(--ink); }
.header h1 { font: var(--text-h1); color: var(--ink); }
.header-meta { font: var(--text-small); color: var(--gray-700); }
.btn-outline { padding: 6px 16px; border: 1px solid var(--gray-300); border-radius: var(--radius-sm); background: var(--white); cursor: pointer; font: var(--text-small); color: var(--gray-700); transition: background 0.15s, border-color 0.15s; }
.btn-outline:hover { background: var(--gray-100); border-color: var(--gray-500); }
.header-right { display: flex; gap: var(--space-2); align-items: center; }

/* Metrics strip — one band with dividers, not seven separate cards */
.parse-warnings { margin-bottom: var(--space-4); display: flex; flex-direction: column; gap: 6px; }
.parse-warning { display: flex; align-items: baseline; gap: var(--space-3); background: var(--near-tint); border: 1px solid var(--near); border-radius: var(--radius-sm); padding: 8px 12px; font: var(--text-small); color: var(--ink-soft); }
.parse-warning span { flex: 1; }
.warning-dismiss { border: none; background: none; color: var(--near); font-size: 17px; line-height: 1; cursor: pointer; padding: 0 4px; }

.metrics-strip { display: flex; background: var(--gray-100); border: 1px solid var(--gray-300); border-radius: var(--radius-md); margin-bottom: var(--space-6); overflow: hidden; }
.metric { flex: 1; min-width: 100px; padding: var(--space-3) var(--space-4); text-align: center; border-right: 1px solid var(--gray-300); }
.metric:last-child { border-right: none; }
.metric strong { display: block; font-family: var(--font-mono); font-variant-numeric: tabular-nums; font-size: 23px; font-weight: 700; color: var(--ink); }
.metric strong.is-crit { color: var(--crit); }
.metric strong.is-ok { color: var(--ok); }
.metric span { font: var(--text-micro); color: var(--gray-700); text-transform: uppercase; letter-spacing: 0.04em; }

/* Tabs */
.tabs { display: flex; align-items: center; gap: var(--space-1); margin-bottom: var(--space-6); border-bottom: 1px solid var(--gray-300); }
.brand { display: flex; align-items: center; gap: 7px; margin-right: var(--space-4); text-decoration: none; padding-bottom: 2px; }
.brand-icon { stroke: var(--accent); flex-shrink: 0; }
.brand-name { font: var(--text-small); font-weight: 700; color: var(--ink); letter-spacing: 0.01em; white-space: nowrap; }
.brand:hover .brand-name { color: var(--accent); }
.theme-select { margin-left: auto; margin-bottom: 4px; padding: 5px 8px; border: 1px solid var(--gray-300); border-radius: var(--radius-sm); font: var(--text-small); color: var(--gray-700); background: var(--white); cursor: pointer; }
.header-collapsed .tabs { margin-bottom: var(--space-3); }
.tabs button { padding: var(--space-2) var(--space-4); border: none; background: none; cursor: pointer; font: var(--text-small); color: var(--gray-700); border-bottom: 3px solid transparent; margin-bottom: -1px; transition: color 0.15s, border-color 0.2s; }
.tabs button:hover { color: var(--ink); }
.tabs button.active { color: var(--ink); border-bottom-color: var(--accent); font-weight: 700; }
.tabs .btn-collapse { margin-left: var(--space-2); padding: 6px 14px; font: var(--text-small); color: var(--gray-500); border: 1px solid var(--gray-300); border-radius: var(--radius-sm); margin-bottom: 4px; background: none; cursor: pointer; }
.tabs .btn-collapse:hover { color: var(--gray-700); background: var(--gray-100); }

/* Section */
.section { margin-bottom: var(--space-8); }
/* Break a section out of the dashboard's max-width so it gets the full viewport
   width to work with — used by the Gantt and Critical Path canvases. */
.section-full { width: 100vw; position: relative; left: 50%; right: 50%; margin-left: -50vw; margin-right: -50vw; padding: 0 var(--space-6); box-sizing: border-box; }

/* Insight card */
.insight-card { background: var(--gray-100); border: 1px solid var(--gray-300); border-radius: var(--radius-md); padding: var(--space-4); margin-bottom: var(--space-4); }
.insight-card h3 { font: var(--text-h2); color: var(--ink); margin-bottom: 2px; }
.insight-card .subtitle { font: var(--text-small); color: var(--gray-700); margin-bottom: var(--space-3); }

/* Table controls */
.table-controls { display: flex; gap: var(--space-2); align-items: center; margin-bottom: var(--space-3); flex-wrap: wrap; }
.search-input { padding: 6px 12px; border: 1px solid var(--gray-300); border-radius: var(--radius-sm); font: var(--text-small); width: 220px; }
.filter-select { padding: 6px 8px; border: 1px solid var(--gray-300); border-radius: var(--radius-sm); font: var(--text-small); background: var(--white); }
.filter-toggle { font: var(--text-small); color: var(--gray-700); display: flex; align-items: center; gap: var(--space-1); cursor: pointer; }
.filter-toggle input { margin: 0; }
.btn-export-view { margin-left: auto; }

/* Table */
.table-wrap { overflow-x: auto; border: 1px solid var(--gray-300); border-radius: var(--radius-md); }
.data-table { width: 100%; border-collapse: collapse; font: var(--text-body); }
.data-table th { text-align: left; padding: var(--space-2) var(--space-3); border-bottom: 2px solid var(--gray-300); font: var(--text-micro); text-transform: uppercase; color: var(--gray-700); letter-spacing: 0.04em; white-space: nowrap; background: var(--gray-100); }
.data-table th.sortable { cursor: pointer; user-select: none; }
.data-table th.sortable:hover { background: var(--gray-150); }
.data-table td { padding: 6px var(--space-3); border-bottom: 1px solid var(--gray-150); vertical-align: middle; white-space: nowrap; }
.data-table tbody tr:hover td { background: var(--gray-100); }
.data-table tbody tr.critical td { border-left: 3px solid var(--crit); }
.data-table tbody tr.negative-float td { background: var(--crit-tint); }
.data-table tbody tr.milestone td { border-left: 3px solid var(--milestone); }
.data-table .code { color: var(--gray-700); }
.data-table .name-cell { max-width: 280px; overflow: hidden; text-overflow: ellipsis; }
.data-table .name-col { min-width: 200px; }
.act-name { font-weight: 500; }
.annotation-dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; background: var(--gray-500); margin-right: 5px; vertical-align: middle; }
.annotation-dot.sev-query { background: var(--accent); }
.annotation-dot.sev-risk { background: var(--near); }
.annotation-dot.sev-logic { background: var(--crit); }
.annotation-dot.sev-resolved { background: var(--ok); }
.badge-milestone { display: inline-block; padding: 0 5px; border-radius: var(--radius-sm); font: var(--text-micro); background: color-mix(in srgb, var(--milestone) 12%, white); color: var(--milestone); margin-left: var(--space-1); vertical-align: middle; }

/* Status badges */
.status-badge { display: inline-flex; align-items: center; gap: 5px; padding: 2px 8px; border-radius: var(--radius-sm); font: var(--text-small); }
.status-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.status-badge.TK_Complete { background: var(--ok-tint); color: var(--ok); }
.status-badge.TK_Complete .status-dot { background: var(--ok); }
.status-badge.TK_Active { background: var(--accent-soft); color: var(--accent); }
.status-badge.TK_Active .status-dot { background: var(--accent); }
.status-badge.TK_NotStart { background: var(--gray-150); color: var(--gray-700); }
.status-badge.TK_NotStart .status-dot { background: var(--gray-500); }

/* Progress bar */
.prog-bar { display: inline-block; width: 40px; height: 4px; background: var(--gray-300); border-radius: 2px; overflow: hidden; vertical-align: middle; margin-right: var(--space-1); }
.prog-fill { height: 100%; background: var(--accent); border-radius: 2px; }
.prog-text { font: var(--text-small); color: var(--gray-700); }

/* Float colors — same crit/near tokens as every other surface */
.float-crit { color: var(--crit); font-weight: 700; }
.float-near { color: var(--near); font-weight: 600; }
.float-neg { color: var(--white); background: var(--crit); font-weight: 700; padding: 1px 6px; border-radius: var(--radius-sm); }

/* Relationship panel (inline) */
.rel-row td { background: var(--gray-100) !important; padding: var(--space-3) var(--space-4); }
.rel-wbs-path { font: var(--text-small); color: var(--gray-700); margin-bottom: var(--space-3); font-family: var(--font-mono); }
.rel-panel { display: flex; gap: var(--space-8); }
.rel-col { flex: 1; }
.rel-col h4 { font: var(--text-micro); text-transform: uppercase; color: var(--gray-700); letter-spacing: 0.04em; margin-bottom: var(--space-2); }
.rel-empty { font: var(--text-small); color: var(--gray-500); font-style: italic; }
.rel-item { font: var(--text-small); padding: 2px 0; display: flex; gap: var(--space-2); align-items: center; }
.rel-code { color: var(--accent); font-weight: 600; min-width: 60px; }
.rel-type { color: var(--gray-700); font: var(--text-micro); }
.rel-lag { color: var(--gray-500); font: var(--text-micro); }

/* WBS tree */
.wbs-tree { border: 1px solid var(--gray-300); border-radius: var(--radius-md); overflow: hidden; }
</style>
