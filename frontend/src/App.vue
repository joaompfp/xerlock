<template>
  <div class="app">
    <!-- Upload screen -->
    <div v-if="!data" class="upload-screen">
      <div class="upload-card">
        <div class="logo">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#2F5496" stroke-width="1.5">
            <rect x="3" y="3" width="18" height="18" rx="2" />
            <path d="M3 9h18" />
            <path d="M9 3v18" />
            <path d="M7 12l2 2 4-4" />
          </svg>
        </div>
        <h1>Schedule App</h1>
        <p class="subtitle">Primavera P6 XER viewer with critical path analysis</p>
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
        <p class="hint">Files are parsed in-browser via the server. No data is stored.</p>
      </div>
    </div>

    <!-- Dashboard -->
    <div v-else class="dashboard" :class="{ 'header-collapsed': headerCollapsed }">
      <template v-if="!headerCollapsed">
        <!-- Header -->
        <header class="header">
          <div class="header-left">
            <h1>{{ data.project.proj_short_name }}</h1>
            <span class="header-meta">{{ data.project.total_activities }} activities &middot; {{ data.project.total_wbs }} WBS nodes</span>
          </div>
          <div class="header-right">
            <button class="btn-outline" @click="doExport(() => exportWorkbook(data))">
              Export to Excel (.xlsx)
            </button>
            <button class="btn-outline" @click="data = null">Load another</button>
          </div>
        </header>

        <!-- Key stats row -->
        <div class="stats-row">
          <div class="stat-card">
            <strong>{{ data.project.total_activities }}</strong>
            <span>Activities</span>
          </div>
          <div class="stat-card">
            <strong :style="{ color: data.project.total_critical > 0 ? '#c0392b' : '#27ae60' }">{{ data.project.total_critical }}</strong>
            <span>Critical (TF=0)</span>
          </div>
          <div class="stat-card">
            <strong :style="{ color: data.project.total_longest_path > 0 ? '#c0392b' : '#27ae60' }">{{ data.project.total_longest_path }}</strong>
            <span>Longest Path</span>
          </div>
          <div class="stat-card">
            <strong>{{ data.project.total_milestones }}</strong>
            <span>Milestones</span>
          </div>
          <div class="stat-card">
            <strong>{{ data.project.pct_complete }}%</strong>
            <span>Complete</span>
          </div>
          <div class="stat-card">
            <strong>{{ data.project.earliest_start ? formatDate(data.project.earliest_start) : '--' }}</strong>
            <span>Earliest start</span>
          </div>
          <div class="stat-card">
            <strong>{{ data.project.latest_end ? formatDate(data.project.latest_end) : '--' }}</strong>
            <span>Latest end</span>
          </div>
        </div>
      </template>

      <!-- Tab navigation -->
      <nav class="tabs">
        <button :class="{ active: tab === 'gantt' }" @click="tab = 'gantt'">Gantt Chart</button>
        <button :class="{ active: tab === 'story' }" @click="tab = 'story'">Critical Path</button>
        <button :class="{ active: tab === 'table' }" @click="tab = 'table'">Activity Table</button>
        <button :class="{ active: tab === 'wbs' }" @click="tab = 'wbs'">WBS Tree</button>
        <button class="btn-collapse" @click="headerCollapsed = !headerCollapsed" :title="headerCollapsed ? 'Show header' : 'Hide header for more room'">
          {{ headerCollapsed ? '⌄ Show header' : '⌃ Hide header' }}
        </button>
      </nav>

      <!-- Gantt Chart (primary view) -->
      <div v-if="tab === 'gantt'" class="section section-full">
        <GanttChart :data="data" :extra-room="headerCollapsed" />
      </div>

      <!-- Critical Path Graph -->
      <div v-if="tab === 'story'" class="section">
        <div class="story-header">
          <h2>Critical Path</h2>
          <p class="subtitle">{{ data.project.total_critical }} critical activities. Drag to pan, scroll to zoom, click a node for detail, click ⊕ to expand its neighbors.</p>
        </div>

        <CriticalPathGraph :activities="data.activities" />

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
                <td class="float-cell">{{ act.total_float_hrs }}h</td>
                <td>{{ formatHours(act.duration_hrs) }}</td>
                <td>{{ formatDate(act.early_end) }}</td>
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
            placeholder="Search code or name..."
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
                :class="{ critical: act.is_critical, milestone: isMilestone(act) }"
                @click="selectedAct = selectedAct?.task_id === act.task_id ? null : act"
              >
                <td class="code">{{ act.task_code }}</td>
                <td class="name-cell">
                  <span class="act-name">{{ act.task_name }}</span>
                  <span v-if="isMilestone(act)" class="badge-milestone">M</span>
                </td>
                <td><span class="status-badge" :class="act.status">{{ statusLabel(act.status) }}</span></td>
                <td>
                  <div class="prog-bar">
                    <div class="prog-fill" :style="{ width: act.pct_complete + '%' }"></div>
                  </div>
                  <span class="prog-text">{{ act.pct_complete }}%</span>
                </td>
                <td>{{ formatHours(act.duration_hrs) }}</td>
                <td>{{ formatDate(act.early_start) }}</td>
                <td>{{ formatDate(act.early_end) }}</td>
                <td :class="floatClass(act.total_float_hrs)">{{ formatFloat(act.total_float_hrs) }}</td>
              </tr>
              <tr v-if="selectedAct" class="rel-row">
                <td colspan="8">
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
            v-for="node in data.wbs_tree"
            :key="node.wbs_id"
            :node="node"
            :level="0"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import WBSNode from './components/WBSNode.vue'
import CriticalPathGraph from './components/CriticalPathGraph.vue'
import GanttChart from './components/GanttChart.vue'
import { formatDate, formatHours, statusLabel, isMilestone, formatFloat } from './utils/format'
import { exportWorkbook, exportActivitiesCsv } from './utils/export'

export default {
  name: 'App',
  components: { WBSNode, CriticalPathGraph, GanttChart },
  data() {
    return {
      data: null,
      loading: false,
      dragOver: false,
      tab: 'gantt',
      headerCollapsed: false,
      search: '',
      statusFilter: '',
      showCriticalOnly: false,
      sortField: 'total_float_hrs',
      sortDir: 'asc',
      selectedAct: null,
      exporting: false,
    }
  },
  computed: {
    filteredActivities() {
      let acts = [...this.data.activities]
      if (this.search) {
        const q = this.search.toLowerCase()
        acts = acts.filter(a =>
          a.task_code.toLowerCase().includes(q) ||
          a.task_name.toLowerCase().includes(q)
        )
      }
      if (this.statusFilter) {
        acts = acts.filter(a => a.status === this.statusFilter)
      }
      if (this.showCriticalOnly) {
        acts = acts.filter(a => a.is_critical)
      }
      // Sort
      acts.sort((a, b) => {
        let va = a[this.sortField]
        let vb = b[this.sortField]
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
      return this.data.activities
        .filter(a => !a.is_critical && a.total_float_hrs > 0 && a.total_float_hrs <= 80)
        .sort((a, b) => a.total_float_hrs - b.total_float_hrs)
        .slice(0, 15)
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
        this.data = await res.json()
        this.tab = 'gantt'
        this.search = ''
        this.statusFilter = ''
        this.showCriticalOnly = false
        this.selectedAct = null
      } catch (e) {
        alert('Failed to parse: ' + e.message)
      } finally {
        this.loading = false
      }
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
    statusLabel,
    isMilestone,
    formatFloat,
    floatClass(f) {
      if (f == null) return ''
      if (f === 0) return 'float-crit'
      if (f <= 40) return 'float-near'
      if (f <= 80) return 'float-watch'
      return ''
    },
    getActCode(tid) {
      const a = this.data.activities.find(a => a.task_id === tid)
      return a ? a.task_code : '?' + tid
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
  },
}
</script>

<style>
/* ── Reset & base ── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #fff; color: #1a1a2e; font-size: 14px; line-height: 1.5; -webkit-font-smoothing: antialiased; }

/* ── Upload screen ── */
.upload-screen { display: flex; align-items: center; justify-content: center; min-height: 100vh; padding: 24px; }
.upload-card { text-align: center; max-width: 480px; }
.upload-card .logo { margin-bottom: 16px; }
.upload-card h1 { font-size: 28px; font-weight: 700; color: #1a1a2e; margin-bottom: 4px; }
.upload-card .subtitle { font-size: 14px; color: #888; margin-bottom: 32px; }
.drop-zone { border: 2px dashed #ccc; border-radius: 12px; padding: 48px 24px; cursor: pointer; transition: all 0.2s; background: #fafbfc; }
.drop-zone:hover, .drop-zone.active { border-color: #2F5496; background: #f0f4ff; }
.drop-zone input { display: none; }
.drop-zone label { display: flex; flex-direction: column; align-items: center; gap: 12px; cursor: pointer; color: #555; font-size: 14px; }
.drop-zone label svg { color: #2F5496; }
.drop-zone .loading { color: #2F5496; font-weight: 600; }
.hint { font-size: 12px; color: #aaa; margin-top: 16px; }

/* ── Dashboard ── */
.dashboard { max-width: 1200px; margin: 0 auto; padding: 24px; }
.dashboard.header-collapsed { padding-top: 10px; }

/* Header */
.header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; padding-bottom: 16px; border-bottom: 2px solid #1a1a2e; }
.header h1 { font-size: 24px; font-weight: 700; }
.header-meta { font-size: 13px; color: #888; }
.btn-outline { padding: 6px 16px; border: 1px solid #ccc; border-radius: 6px; background: white; cursor: pointer; font-size: 13px; color: #555; }
.btn-outline:hover { background: #f5f5f5; }
.header-right { display: flex; gap: 8px; align-items: center; }

/* Stats */
.stats-row { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 24px; }
.stat-card { flex: 1; min-width: 120px; background: #f8f9fc; border: 1px solid #e8e8e8; border-radius: 8px; padding: 12px 16px; text-align: center; transition: transform 0.15s, box-shadow 0.15s; }
.stat-card:hover { transform: translateY(-1px); box-shadow: 0 4px 14px rgba(26,26,46,0.08); }
.stat-card strong { display: block; font-size: 22px; font-weight: 700; color: #1a1a2e; }
.stat-card span { font-size: 11px; color: #888; text-transform: uppercase; letter-spacing: 0.3px; }

/* Tabs */
.tabs { display: flex; align-items: center; gap: 4px; margin-bottom: 24px; border-bottom: 1px solid #e8e8e8; }
.header-collapsed .tabs { margin-bottom: 12px; }
.tabs button { padding: 8px 20px; border: none; background: none; cursor: pointer; font-size: 14px; color: #888; border-bottom: 2px solid transparent; margin-bottom: -1px; transition: color 0.15s, border-color 0.2s; }
.tabs button:hover { color: #555; }
.tabs button.active { color: #1a1a2e; border-bottom-color: #2F5496; font-weight: 600; }
.tabs .btn-collapse { margin-left: auto; padding: 6px 14px; font-size: 12px; color: #999; border: 1px solid #ddd; border-radius: 6px; margin-bottom: 4px; }
.tabs .btn-collapse:hover { color: #555; background: #f5f5f5; }

/* Section */
.section { margin-bottom: 40px; }
/* Break the Gantt out of the dashboard's max-width so it gets the full viewport
   width to work with — it's the app's primary view and needs the room. */
.section-full { width: 100vw; position: relative; left: 50%; right: 50%; margin-left: -50vw; margin-right: -50vw; padding: 0 24px; box-sizing: border-box; }
.story-header { margin-bottom: 24px; }
.story-header h2 { font-size: 20px; font-weight: 700; }
.story-header .subtitle { font-size: 13px; color: #888; margin-top: 4px; }

/* Insight card */
.insight-card { background: #f8f9fc; border: 1px solid #e8e8e8; border-radius: 8px; padding: 20px; margin-bottom: 16px; }
.insight-card h3 { font-size: 16px; font-weight: 700; margin-bottom: 2px; }
.insight-card .subtitle { font-size: 12px; color: #888; margin-bottom: 12px; }

/* Table controls */
.table-controls { display: flex; gap: 8px; align-items: center; margin-bottom: 12px; flex-wrap: wrap; }
.search-input { padding: 6px 12px; border: 1px solid #ccc; border-radius: 6px; font-size: 13px; width: 220px; }
.filter-select { padding: 6px 8px; border: 1px solid #ccc; border-radius: 6px; font-size: 13px; background: white; }
.filter-toggle { font-size: 13px; color: #555; display: flex; align-items: center; gap: 4px; cursor: pointer; }
.filter-toggle input { margin: 0; }
.btn-export-view { margin-left: auto; }

/* Table */
.table-wrap { overflow-x: auto; border: 1px solid #e8e8e8; border-radius: 8px; }
.data-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.data-table th { text-align: left; padding: 8px 10px; border-bottom: 2px solid #ddd; font-size: 10px; text-transform: uppercase; color: #888; letter-spacing: 0.3px; white-space: nowrap; background: #fafbfc; }
.data-table th.sortable { cursor: pointer; user-select: none; }
.data-table th.sortable:hover { background: #f0f2f5; }
.data-table td { padding: 6px 10px; border-bottom: 1px solid #f0f0f0; vertical-align: middle; white-space: nowrap; }
.data-table tbody tr:hover td { background: #f5f6f8; }
.data-table tbody tr.critical td { border-left: 3px solid #e74c3c; }
.data-table tbody tr.milestone td { border-left: 3px solid #8e44ad; }
.data-table .code { font-family: 'SF Mono', 'Fira Code', monospace; font-size: 12px; color: #555; }
.data-table .name-cell { max-width: 280px; overflow: hidden; text-overflow: ellipsis; }
.data-table .name-col { min-width: 200px; }
.act-name { font-weight: 500; }
.badge-milestone { display: inline-block; padding: 0 5px; border-radius: 3px; font-size: 9px; font-weight: 700; background: #f0eaf5; color: #8e44ad; margin-left: 4px; vertical-align: middle; }

/* Status badges */
.status-badge { display: inline-block; padding: 1px 8px; border-radius: 10px; font-size: 11px; font-weight: 500; }
.status-badge.TK_Complete { background: #d5f5e3; color: #1e8449; }
.status-badge.TK_Active { background: #fef5e7; color: #b7950b; }
.status-badge.TK_NotStart { background: #f0f0f0; color: #666; }

/* Progress bar */
.prog-bar { display: inline-block; width: 40px; height: 4px; background: #e0e0e0; border-radius: 2px; overflow: hidden; vertical-align: middle; margin-right: 4px; }
.prog-fill { height: 100%; background: #2F5496; border-radius: 2px; }
.prog-text { font-size: 11px; color: #888; }

/* Float colors */
.float-crit { color: #c0392b; font-weight: 700; }
.float-near { color: #b7950b; font-weight: 600; }
.float-watch { color: #2471a3; font-weight: 600; }

/* Relationship panel (inline) */
.rel-row td { background: #f8f9fc !important; padding: 12px 16px; }
.rel-panel { display: flex; gap: 32px; }
.rel-col { flex: 1; }
.rel-col h4 { font-size: 11px; text-transform: uppercase; color: #888; letter-spacing: 0.3px; margin-bottom: 6px; }
.rel-empty { font-size: 12px; color: #aaa; font-style: italic; }
.rel-item { font-size: 12px; padding: 2px 0; display: flex; gap: 8px; align-items: center; }
.rel-code { font-family: monospace; font-weight: 600; color: #2F5496; min-width: 60px; }
.rel-type { color: #888; font-size: 11px; }
.rel-lag { color: #aaa; font-size: 11px; }

/* WBS tree */
.wbs-tree { border: 1px solid #e8e8e8; border-radius: 8px; overflow: hidden; }
</style>
