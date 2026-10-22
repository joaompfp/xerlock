<template>
  <div class="app">
    <!-- Upload screen -->
    <div v-if="!data" class="upload-screen">
      <div class="upload-card">
        <div class="logo">
          <XerlockMark :size="64" />
        </div>
        <h1>XERlock</h1>
        <p class="subtitle">Review Primavera P6 and Microsoft Project schedules — no licence required.</p>
        <p class="feature-strip">Interactive Gantt &middot; critical-path network &middot; configurable health checks &middot; calendar &amp; raw-table audit &middot; snapshot compare &middot; Excel review reports</p>

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
          <input type="file" :accept="accept" @change="handleFile" id="fileInput" />
          <label for="fileInput">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M12 5v14M5 12h14" />
            </svg>
            <span v-if="!loading">{{ dropPrompt }}</span>
            <span v-else class="loading">{{ parsingMessage }}</span>
          </label>
        </div>
        <p v-if="uploadError" class="upload-error">{{ uploadError }}</p>
        <button v-if="!loading" class="sample-link" @click="loadSample()">
          No file handy? <strong>Load the sample project &rarr;</strong>
        </button>
        <p v-if="!loading" class="sample-sub">A 24-activity data-centre fit-out with a real critical path, negative float, and in-progress work. <button class="sample-alt" @click="loadSample('xml')">The same project as Microsoft Project XML &rarr;</button></p>
        <p v-if="parserMode === 'local'" class="hint">XERlock is read-only by design — the lock in the name. <strong>Your file is parsed on this computer and never uploaded</strong>: it works with the network unplugged. Your last file is kept in this browser only, so you can reopen it without reloading.</p>
        <p v-else class="hint">XERlock is read-only by design — the lock in the name: files are parsed in memory, never stored, never modified. Your last file is kept in this browser only, so you can reopen it without re-uploading.</p>
        <a class="gh-link" href="https://github.com/joaompfp/xerlock" target="_blank" rel="noopener">
          <svg width="15" height="15" viewBox="0 0 16 16" fill="currentColor"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27s1.36.09 2 .27c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8z"/></svg>
          Open source on GitHub
        </a>
        <!-- Appropriate Legal Notices (AGPL-3.0 s.0 and s.13) and the author attribution
             that NOTICE's s.7(b) term requires derivatives to keep. -->
        <p class="legal-notice">
          AGPL-3.0 &middot; Based on XERlock by joaompfp &middot;
          <a href="https://github.com/joaompfp/xerlock" target="_blank" rel="noopener">source</a>
        </p>
      </div>
    </div>

    <!-- Dashboard -->
    <div v-else class="app-shell" :class="{ 'sb-collapsed': sidebarCollapsed }">
      <!-- Sidebar: grouped navigation. Replaces a flat row of nine tabs, which gave the
           programme views, the analysis views and the file-audit views equal billing. -->
      <aside class="sidebar" :class="{ open: navOpen }" id="app-sidebar">
        <div class="sb-brand">
          <a class="sb-logo" href="https://github.com/joaompfp/xerlock" target="_blank" rel="noopener" title="XERlock on GitHub">
            <XerlockMark :size="22" surface="var(--nav)" />
            <span>XERlock</span>
          </a>
          <span class="sb-readonly" title="XERlock never modifies or stores your file">read only</span>
          <button class="sb-collapse" title="Hide the sidebar" aria-label="Hide the sidebar" @click="sidebarCollapsed = true">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 7l-5 5 5 5M18 7l-5 5 5 5"/></svg>
          </button>
        </div>

        <div class="sb-project">
          <div class="sb-proj-name" :title="data.project.proj_short_name">{{ data.project.proj_short_name }}</div>
          <div class="sb-proj-meta">{{ data.project.total_activities }} activities &middot; {{ data.project.total_wbs }} WBS</div>
          <div v-if="data.project.data_date" class="sb-datadate">
            <i></i><span>DATA DATE</span><b>{{ formatDate(data.project.data_date) }}</b>
          </div>
          <!-- The headline figures, read once per file: they sit with the project, not
               in a strip above every view. -->
          <div class="sb-metrics">
            <div class="sb-metric"><b :class="data.project.total_critical > 0 ? 'is-crit' : 'is-ok'">{{ data.project.total_critical }}</b><span>Critical</span></div>
            <div class="sb-metric"><b>{{ data.project.total_milestones }}</b><span>Milestones</span></div>
            <div class="sb-metric" :class="{ 'sb-metric-wide': !data.project.total_negative_float }"><b>{{ data.project.total_longest_path }}</b><span>Longest path</span></div>
            <div class="sb-metric" v-if="data.project.total_negative_float > 0"><b class="is-crit">{{ data.project.total_negative_float }}</b><span>Neg. float</span></div>
            <div class="sb-metric sb-metric-pct" title="Share of activities with status Complete. A count, not weighted by duration, cost or units; per-activity % complete uses each activity's own percent-complete type.">
              <b>{{ data.project.pct_complete }}%</b><span>Done</span>
              <i class="tb-bar"><u :style="{ width: data.project.pct_complete + '%' }"></u></i>
            </div>
          </div>
        </div>

        <nav class="sb-nav">
          <template v-for="g in navGroups" :key="g.label">
            <div class="sb-group">{{ g.label }}</div>
            <button
              v-for="it in g.items"
              :key="it.id"
              class="sb-item"
              :class="{ active: tab === it.id }"
              @click="selectTab(it.id); navOpen = false"
            >
              <span class="sb-item-label">{{ it.label }}</span>
              <span v-if="it.id === 'health' && healthScore !== null" class="sb-score" :class="healthScoreClass">{{ healthScore }}%</span>
              <span v-else-if="it.id === 'compare' && compareData" class="sb-dot" title="A baseline is loaded"></span>
            </button>
          </template>
        </nav>

        <div class="sb-footer">
          <!-- The open view's legend, when it has one (the Gantt teleports its own here). -->
          <div id="sb-legend"></div>
          <div class="sb-actions">
            <button v-if="annotationCount > 0" class="sb-load" :disabled="exporting" @click="doExport(() => exportReviewReport(data!, annotations))" title="Download the annotated Review Report (.xlsx)">
              {{ exportLabel('Review notes (' + annotationCount + ')') }}
            </button>
            <div class="tb-export">
              <button class="sb-load" :disabled="exporting" @click="exportMenuOpen = !exportMenuOpen" :aria-expanded="exportMenuOpen ? 'true' : 'false'">{{ exportLabel('Export') }} &#9662;</button>
              <div v-if="exportMenuOpen" class="tb-menu sb-export-menu">
                <button @click="exportMenuOpen = false; doExport(() => exportWorkbook(data!))">Schedule workbook (.xlsx)</button>
                <button :disabled="annotationCount === 0" @click="exportMenuOpen = false; doExport(() => exportReviewReport(data!, annotations))">Review report (.xlsx)</button>
              </div>
            </div>
          </div>
          <div class="sb-theme" role="group" aria-label="Colour theme">
            <button v-for="(label, key) in themeOptions" :key="key" :class="{ active: theme === key }" @click="theme = key">{{ label }}</button>
          </div>
          <button class="sb-load" @click="data = null">Load another file</button>
          <!-- Same notice as the upload screen, so it stays reachable while the app is in use. -->
          <p class="sb-legal">
            AGPL-3.0 &middot; Based on XERlock by joaompfp &middot;
            <a href="https://github.com/joaompfp/xerlock" target="_blank" rel="noopener">source</a>
          </p>
        </div>
      </aside>
      <div v-if="navOpen" class="sb-backdrop" @click="navOpen = false"></div>
      <button v-if="sidebarCollapsed" class="sb-rail" title="Show the sidebar" aria-label="Show the sidebar" @click="sidebarCollapsed = false">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 7l5 5-5 5M13 7l5 5-5 5"/></svg>
      </button>

      <div class="main">
        <header class="topbar">
          <button class="nav-toggle" @click="navOpen = !navOpen" aria-controls="app-sidebar" :aria-expanded="navOpen ? 'true' : 'false'" aria-label="Navigation">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18M3 12h18M3 18h18"/></svg>
          </button>
          <h1 class="topbar-title">{{ tabLabels[tab] }}</h1>

        </header>

        <div class="views">
      <!-- Parse warnings (multi-project file, suspect encoding, …) — a reviewer must never
           discover these by accident, so they persist until explicitly dismissed. -->
      <div v-if="visibleWarnings.length" class="parse-warnings">
        <div v-for="(w, i) in visibleWarnings" :key="i" class="parse-warning">
          <span>{{ w }}</span>
          <button class="warning-dismiss" @click="dismissWarning(w)" title="Dismiss">&times;</button>
        </div>
      </div>

      <!-- Gantt Chart (primary view) -->
      <div v-if="opened.includes('gantt')" v-show="tab === 'gantt'" class="section section-full">
        <GanttChart
          :data="data"
          :baseline="compareData"
          :baseline-filename="compareFilename"
          :jump-to="pendingJump"
          :annotations="annotations"
          :return-tab="jumpOrigin ? (tabLabels[jumpOrigin] || '') : ''"
          :active="tab === 'gantt'"
          @jumped="pendingJump = null"
          @return-to-origin="returnToOrigin"
          @annotate="setAnnotation"
          @unannotate="removeAnnotationFor"
          @callout="setCalloutFor"
        />
      </div>

      <!-- Critical Path Graph -->
      <div v-if="opened.includes('story')" v-show="tab === 'story'" class="section section-full">
        <CriticalPathGraph
          :activities="data.activities"
          :visible="tab === 'story'"
          :annotations="annotations"
          :project-name="data.project.proj_short_name"
          @annotate="setAnnotation"
          @unannotate="removeAnnotationFor"
        />
      </div>
      <div v-if="opened.includes('story')" v-show="tab === 'story'" class="section cp-below-section">
        <!-- Near-critical watchlist -->
        <div class="insight-card" v-if="nearCritical.length > 0">
          <h3>Near-critical watchlist</h3>
          <p class="subtitle">Activities with low float that could become critical.</p>
          <table class="data-table">
            <thead>
              <tr>
                <th>Code</th>
                <th>Activity</th>
                <th class="num">Float</th>
                <th class="num">Duration</th>
                <th class="num">End</th>
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
      <div v-if="opened.includes('table')" v-show="tab === 'table'" class="section">
        <ActivityTable
          :data="data"
          :annotations="annotations"
          @export-view="(list: Activity[]) => doExport(() => exportActivitiesCsv(data!, list, slugName() + '-filtered.csv'))"
        />
</div>

      <!-- WBS Tree -->
      <div v-if="opened.includes('wbs')" v-show="tab === 'wbs'" class="section">
        <div class="wbs-tree">
          <div class="wbs-head">
            <span class="wbs-head-name">WBS</span>
            <span class="wbs-m">Critical</span>
            <span class="wbs-m">Act.</span>
            <span class="wbs-m wbs-date">Start</span>
            <span class="wbs-m wbs-date">Finish</span>
            <span class="wbs-prog-head">Progress</span>
          </div>
          <WBSNode
            v-for="(node, i) in data.wbs_tree"
            :key="node.wbs_id"
            :node="node"
            :level="0"
            :index="i"
            :rollups="wbsRollups"
          />
        </div>
      </div>

      <!-- Progress -->
      <div v-if="opened.includes('progress')" v-show="tab === 'progress'" class="section section-full">
        <ProgressView :data="data" @jump="jumpToActivity" />
      </div>

      <!-- Health Check -->
      <div v-if="opened.includes('health')" v-show="tab === 'health'" class="section section-full">
        <HealthCheck
          :data="data"
          :annotations="annotations"
          @score="liveHealthScore = $event"
          @jump="jumpToActivity"
          @annotate="setAnnotation"
          @unannotate="removeAnnotationFor"
        />
      </div>

      <!-- Calendars -->
      <div v-if="opened.includes('calendars')" v-show="tab === 'calendars'" class="section section-full">
        <CalendarView :data="data" @jump="jumpToActivity" />
      </div>

      <!-- Raw table inspector -->
      <div v-if="opened.includes('tables')" v-show="tab === 'tables'" class="section section-full">
        <TableInspector :data="data" />
      </div>

      <!-- Compare -->
      <div v-if="opened.includes('compare')" v-show="tab === 'compare'" class="section section-full">
        <CompareView
          v-if="compareData"
          :current="data"
          :baseline="compareData"
          :baseline-filename="compareFilename"
          @jump="jumpToActivity"
          @reset="compareData = null"
        />
        <div v-else class="compare-entry">
          <header class="compare-entry__head">
            <h2>Compare against a previous snapshot</h2>
            <p class="subtitle">Diff this file against an earlier export of the same project — slipped dates, duration edits, float erosion, logic changes and critical-path movement. The current file stays loaded; the snapshot is only used for the diff.</p>
          </header>

          <div class="compare-entry__cols">
          <!-- Snapshot register: monthly-cycle reviews shouldn't require carrying old
               .xer files around — save this month's parse now, diff against it next month. -->
          <div class="snap-register">
            <div class="snap-head">
              <h3>Snapshot register</h3>
              <button class="btn-outline snap-save" :disabled="snapshotSaving" @click="saveCurrentSnapshot">
                {{ snapshotSaving ? 'Saving…' : (snapshotJustSaved ? 'Saved ✓' : 'Save current file as snapshot') }}
              </button>
            </div>
            <p v-if="snapshots.length === 0" class="snap-empty">Nothing saved yet. Snapshots live in this browser only (IndexedDB) — nothing is uploaded anywhere.</p>
            <table v-else class="snap-table">
              <colgroup>
                <col class="c-proj"><col class="c-file"><col class="c-date">
                <col class="c-acts"><col class="c-saved"><col class="c-act">
              </colgroup>
              <thead><tr><th>Project</th><th>File</th><th class="num">Data date</th><th class="num">Activities</th><th class="num">Saved</th><th></th></tr></thead>
              <tbody>
                <tr v-for="snap in snapshots" :key="snap.id" :class="{ 'snap-other-proj': snap.proj !== data.project.proj_short_name }" :title="snap.proj !== data.project.proj_short_name ? 'Saved under a different internal project name — P6 short names often change per draft. Compare still works: activities are matched by code, not project name.' : ''">
                  <td class="code">{{ snap.proj }}</td>
                  <td class="snap-file" :title="snap.filename">{{ snap.filename }}</td>
                  <td class="num-cell">{{ snap.dataDate ? formatDate(snap.dataDate) : '—' }}</td>
                  <td class="num-cell">{{ snap.activities }}</td>
                  <td class="num-cell">{{ timeAgo(snap.savedAt) }}</td>
                  <td class="snap-actions-cell">
                    <div class="snap-actions">
                      <button class="btn-outline" @click="compareAgainstSnapshot(snap)">Compare</button>
                      <button class="btn-forget" title="Delete snapshot" @click="removeSnapshot(snap)">&times;</button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="compare-upload">
          <h3 class="compare-upload__title">Or upload a file</h3>
          <div
            class="drop-zone"
            @dragover.prevent="compareDragOver = true"
            @dragleave="compareDragOver = false"
            @drop.prevent="handleCompareDrop"
            :class="{ active: compareDragOver }"
          >
            <input type="file" :accept="accept" @change="handleCompareFile" id="compareFileInput" />
            <label for="compareFileInput">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                <path d="M12 5v14M5 12h14" />
              </svg>
              <span v-if="!compareLoading">{{ dropPrompt }}</span>
              <span v-else class="loading">Parsing schedule...</span>
            </label>
          </div>
          <p class="compare-upload__note">Nothing is uploaded anywhere — the snapshot is parsed in memory for the diff.</p>
          </div>
          </div>
        </div>
      </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent } from 'vue'
import WBSNode from './components/WBSNode.vue'
import XerlockMark from './components/XerlockMark.vue'
import CriticalPathGraph from './components/CriticalPathGraph.vue'
import GanttChart from './components/GanttChart.vue'
import HealthCheck from './components/HealthCheck.vue'
import CalendarView from './components/CalendarView.vue'
import ActivityTable from './components/ActivityTable.vue'
import TableInspector from './components/TableInspector.vue'
import ProgressView from './components/ProgressView.vue'
import CompareView from './components/CompareView.vue'
import { formatDate, formatHours, statusLabel, isMilestone, formatFloat, timeAgo } from './utils/format'
import { exportWorkbook, exportActivitiesCsv, exportReviewReport } from './utils/export'
import { runChecks, weightedScore, loadHealthConfig } from './utils/healthChecks'
import { loadLastFile, saveLastFile, clearLastFile, type LastFile, type StoredSchedule } from './utils/lastFile'
import { loadAnnotations, saveAnnotation, removeAnnotation, setCallout, type Annotations, type CalloutOffset, type Severity } from './utils/annotations'
import { listSnapshots, saveSnapshot, getSnapshotData, deleteSnapshot, type SnapshotMeta } from './utils/snapshots'
import { displayStart, displayEnd } from './utils/p6'
import { buildWbsRollups, type WbsRollup } from './utils/wbs'
import type { Activity } from './types/schedule'
import { parseSchedule, prepareParser, PARSER_MODE } from './utils/parseSchedule'
import { ACCEPT, DROP_PROMPT, unsupportedFileMessage } from './utils/source'

type Theme = 'light' | 'dark'

const PARSE_STAGES = [
  'Reading XER tables…',
  'Building the WBS tree…',
  'Computing the longest path…',
  'Laying out the Gantt…',
]

// Sepia/Slate/Clay/Ink were four variations of one light theme. They collapse into
// Light; anyone carrying a stored value for them lands there rather than on a broken
// picker. The storage key is unchanged.
function normaliseTheme(v: string | null): Theme {
  return v === 'dark' ? 'dark' : 'light'
}

function applyTheme(theme: Theme): void {
  // Light lives on :root directly; dark overrides via the attribute.
  if (theme === 'dark') document.documentElement.setAttribute('data-theme', 'dark')
  else document.documentElement.removeAttribute('data-theme')
}

export default defineComponent({
  name: 'App',
  components: { WBSNode, XerlockMark, CriticalPathGraph, GanttChart, HealthCheck, ProgressView, CompareView, CalendarView, TableInspector, ActivityTable },
  data() {
    return {
      data: null as StoredSchedule | null,
      loading: false,
      parsingNote: '',
      parserMode: PARSER_MODE,
      accept: ACCEPT,
      dropPrompt: DROP_PROMPT,
      dragOver: false,
      tab: 'gantt',
      exporting: false,
      lastFile: loadLastFile() as LastFile | null,
      pendingJump: null as number | null,
      annotations: {} as Annotations,
      compareData: null as StoredSchedule | null,
      snapshots: [] as SnapshotMeta[],
      snapshotSaving: false,
      snapshotJustSaved: false,
      currentFilename: '',
      compareFilename: '',
      dismissedWarnings: [] as string[],
      theme: normaliseTheme(localStorage.getItem('schedule-app:theme')),
      uploadError: null as string | null,
      parsingStage: 0,
      jumpOrigin: null as string | null,
      tabLabels: { gantt: 'Gantt chart', story: 'Critical path', table: 'Activity table', wbs: 'WBS tree', progress: 'Progress', health: 'Health check', calendars: 'Calendars', tables: 'Raw tables', compare: 'Compare' } as Record<string, string>,
      // Three jobs, not one row of nine: the programme, the analysis of it, and the
      // audit of the file it came from.
      navGroups: [
        { label: 'Programme', items: [
          { id: 'gantt', label: 'Gantt chart' },
          { id: 'story', label: 'Critical path' },
          { id: 'progress', label: 'Progress' },
        ] },
        { label: 'Analysis', items: [
          { id: 'health', label: 'Health check' },
          { id: 'compare', label: 'Compare' },
        ] },
        { label: 'Audit', items: [
          { id: 'table', label: 'Activity table' },
          { id: 'wbs', label: 'WBS tree' },
          { id: 'calendars', label: 'Calendars' },
          { id: 'tables', label: 'Raw tables' },
        ] },
      ],
      navOpen: false,
      // Wide screens: the sidebar can be put away for more chart; remembered.
      sidebarCollapsed: (() => { try { return localStorage.getItem('schedule-app:sidebar-collapsed') === '1' } catch { return false } })(),
      exportMenuOpen: false,
      // Reported up by HealthCheck so the score is visible from any view.
      // The views opened since this file was loaded. A view is built the first time it is
      // shown and then kept (switching back keeps its state); one never opened costs
      // nothing, which matters on a large file.
      opened: ['gantt'] as string[],
      // The Health check view's score once it is open (it follows edits to targets and weights).
      liveHealthScore: null as number | null,
      exportState: '',
      themeOptions: { light: 'Light', dark: 'Dark' } as Record<Theme, string>,
      compareLoading: false,
      compareDragOver: false,
    }
  },
  // The listeners are methods (bound once by Vue), so add and remove get the same reference.
  mounted() {
    // Standalone build: start loading Python now, while the user picks a file.
    prepareParser()
    document.addEventListener('mousedown', this.onShellDocClick)
    window.addEventListener('keydown', this.onShellKey)
  },
  beforeUnmount() {
    document.removeEventListener('mousedown', this.onShellDocClick)
    window.removeEventListener('keydown', this.onShellKey)
  },
  created() {
    applyTheme(this.theme)
  },
  watch: {
    tab(t: string) {
      if (!this.opened.includes(t)) this.opened.push(t)
    },
    sidebarCollapsed(v: boolean) {
      try { localStorage.setItem('schedule-app:sidebar-collapsed', v ? '1' : '0') } catch { /* not remembered */ }
    },
    theme(t: Theme) {
      applyTheme(t)
      try { localStorage.setItem('schedule-app:theme', t) } catch { /* storage unavailable */ }
    },
  },
  computed: {
    wbsRollups(): Map<number, WbsRollup> | null {
      return this.data ? buildWbsRollups(this.data.wbs_tree, this.data.activities) : null
    },
    // Shown on the Health check nav item from any view, so it is worked out here rather
    // than waiting for that view to be opened.
    healthScore(): number | null {
      if (this.liveHealthScore !== null) return this.liveHealthScore
      if (!this.data) return null
      const cfg = loadHealthConfig()
      return weightedScore(runChecks(this.data, cfg).results, cfg)
    },
    healthScoreClass(): string {
      if (this.healthScore === null) return ''
      return this.healthScore >= 80 ? 'is-ok' : this.healthScore >= 60 ? 'is-near' : 'is-crit'
    },
    nearCritical(): Activity[] {
      if (!this.data) return []
      // Completed activities can't become critical — a watchlist entry for finished work
      // is pure noise to a reviewer.
      return this.data.activities
        .filter(a => a.status !== 'TK_Complete' && !a.is_critical && a.total_float_hrs != null && a.total_float_hrs > 0 && a.total_float_hrs <= 80)
        .sort((a, b) => a.total_float_hrs! - b.total_float_hrs!)
        .slice(0, 15)
    },
    parsingMessage(): string {
      // A parser that reports real progress (the in-browser one) wins over the cycling hints.
      return this.parsingNote || PARSE_STAGES[this.parsingStage % PARSE_STAGES.length]
    },
    visibleWarnings(): string[] {
      const ws = (this.data && this.data.warnings) || []
      return ws.filter(w => !this.dismissedWarnings.includes(w))
    },
    projectKey(): string | null {
      return this.data ? this.data.project.proj_short_name : null
    },
    annotationCount(): number {
      return Object.keys(this.annotations).length
    },
  },
  methods: {
    onShellDocClick(e: MouseEvent) {
      if (this.exportMenuOpen && !(e.target as Element).closest('.tb-export')) this.exportMenuOpen = false
    },
    onShellKey(e: KeyboardEvent) {
      if (e.key !== 'Escape') return
      if (this.exportMenuOpen) this.exportMenuOpen = false
      else if (this.navOpen) this.navOpen = false
    },
    // A drop event always carries a dataTransfer; a file input always has a file list.
    async handleDrop(e: DragEvent) {
      this.dragOver = false
      const file = e.dataTransfer!.files[0]
      if (file) await this.uploadFile(file)
    },
    async handleFile(e: Event) {
      const file = (e.target as HTMLInputElement).files![0]
      if (file) await this.uploadFile(file)
    },
    async handleCompareDrop(e: DragEvent) {
      this.compareDragOver = false
      const file = e.dataTransfer!.files[0]
      if (file) await this.uploadCompareFile(file)
    },
    async saveCurrentSnapshot() {
      if (!this.data || this.snapshotSaving) return
      this.snapshotSaving = true
      try {
        await saveSnapshot(this.currentFilename || this.data.project.proj_short_name + '.xer', this.data)
        this.snapshots = await listSnapshots()
        this.snapshotJustSaved = true
        setTimeout(() => { this.snapshotJustSaved = false }, 1800)
      } catch {
        this.uploadError = ''
        alert('Could not save the snapshot (browser storage unavailable or full).')
      } finally {
        this.snapshotSaving = false
      }
    },
    async compareAgainstSnapshot(snap: SnapshotMeta) {
      const data = await getSnapshotData(snap.id)
      if (!data) {
        alert('This snapshot could not be loaded — it may have been deleted by the browser.')
        this.snapshots = await listSnapshots()
        return
      }
      this.compareData = data
      // formatDate(null) returns '--', so the fallback has to be chosen before formatting.
      this.compareFilename = `${snap.filename} (snapshot, ${snap.dataDate ? formatDate(snap.dataDate) : 'no data date'})`
    },
    async removeSnapshot(snap: SnapshotMeta) {
      await deleteSnapshot(snap.id)
      this.snapshots = await listSnapshots()
    },
    async handleCompareFile(e: Event) {
      const file = (e.target as HTMLInputElement).files![0]
      if (file) await this.uploadCompareFile(file)
    },
    async uploadCompareFile(file: File) {
      const refused = unsupportedFileMessage(file.name)
      if (refused) {
        alert(refused)
        return
      }
      this.compareLoading = true
      try {
        this.compareData = await parseSchedule(file)
        this.compareFilename = file.name
      } catch (e) {
        alert('Failed to parse: ' + (e as Error).message)
      } finally {
        this.compareLoading = false
      }
    },
    async uploadFile(file: File) {
      const refused = unsupportedFileMessage(file.name)
      if (refused) {
        alert(refused)
        return
      }
      this.loading = true
      this.uploadError = null
      this.parsingStage = 0
      this.parsingNote = ''
      const stageTimer = setInterval(() => { this.parsingStage++ }, 800)
      try {
        const parsed = await parseSchedule(file, msg => { this.parsingNote = msg })
        this.activateData(parsed)
        this.currentFilename = file.name
        saveLastFile(file.name, parsed)
        this.lastFile = loadLastFile()
      } catch (e) {
        this.uploadError = `${(e as Error).message} — check the file is a P6 .xer export or a Microsoft Project XML or .mpp file, or try the sample project below.`
      } finally {
        clearInterval(stageTimer)
        this.loading = false
      }
    },
    async loadSample(kind: 'xer' | 'xml' = 'xer') {
      // The bundled demo schedule (fully synthetic), as a P6 export or as Project would
      // save it — fetched from our own static assets and pushed through the exact same
      // upload path as a user file.
      try {
        const name = 'sample-schedule.' + kind
        const res = await fetch(import.meta.env.BASE_URL + name)
        const blob = await res.blob()
        await this.uploadFile(new File([blob], name))
      } catch {
        this.uploadError = 'Could not load the sample project.'
      }
    },
    activateData(parsed: StoredSchedule) {
      this.data = parsed
      this.tab = 'gantt'
      this.opened = ['gantt']
      this.liveHealthScore = null
      this.annotations = loadAnnotations(parsed.project.proj_short_name)
      this.dismissedWarnings = []
      this.compareData = null
      this.compareFilename = ''
      listSnapshots().then(list => { this.snapshots = list })
    },
    reopenLastFile() {
      if (!this.lastFile) return
      this.activateData(this.lastFile.data)
      this.currentFilename = this.lastFile.filename
    },
    forgetLastFile() {
      clearLastFile()
      this.lastFile = null
    },
    formatDate,
    formatHours,
    displayStart,
    displayEnd,
    statusLabel,
    isMilestone,
    formatFloat,
    timeAgo,
    dismissWarning(w: string) {
      this.dismissedWarnings.push(w)
    },
    jumpToActivity(taskId: number) {
      // Remember where the jump came from so the Gantt can offer a way back.
      this.jumpOrigin = this.tab !== 'gantt' ? this.tab : null
      this.tab = 'gantt'
      this.pendingJump = taskId
    },
    selectTab(t: string) {
      this.tab = t
      this.jumpOrigin = null
    },
    returnToOrigin() {
      if (this.jumpOrigin) {
        this.tab = this.jumpOrigin
        this.jumpOrigin = null
      }
    },
    exportLabel(idle: string) {
      if (this.exportState === 'working') return 'Generating…'
      if (this.exportState === 'done') return 'Saved ✓'
      return idle
    },
    slugName() {
      return (this.data!.project.proj_short_name || 'schedule')
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/(^-|-$)/g, '')
    },
    async doExport(fn: () => unknown) {
      if (this.exporting) return
      this.exporting = true
      this.exportState = 'working'
      try {
        await fn()
        this.exportState = 'done'
        setTimeout(() => { this.exportState = '' }, 2000)
      } catch (e) {
        this.exportState = ''
        // The .xlsx export lazy-loads ExcelJS as a separate chunk; if the page has been
        // open across a deploy, that chunk's content-hashed filename no longer exists on
        // the server (the old build was replaced) and the dynamic import 404s. A plain
        // "Export failed" message is misleading here — the fix is just reloading.
        const message = (e as Error).message
        const stale = /dynamically imported module|error loading dynamically imported module/i.test(message || '')
        if (stale) {
          if (confirm('XERlock was updated since you opened this page. Reload to get the latest version? (Your file will need to be re-opened.)')) {
            window.location.reload()
          }
        } else {
          alert('Export failed: ' + message)
        }
      } finally {
        this.exporting = false
      }
    },
    exportWorkbook,
    exportActivitiesCsv,
    exportReviewReport,
    setAnnotation(taskId: number, patch: { severity: Severity | null; note: string }) {
      this.annotations = saveAnnotation(this.projectKey, taskId, patch)
    },
    removeAnnotationFor(taskId: number) {
      this.annotations = removeAnnotation(this.projectKey, taskId)
    },
    setCalloutFor(taskId: number, callout: CalloutOffset | null) {
      this.annotations = setCallout(this.projectKey, taskId, callout)
    },
  },
})
</script>

<style>
/* ── Design tokens ──────────────────────────────────────────────────────── */
:root {
  /* ─────────────────────────────────────────────────────────────────────────
     Two real themes: light (cool paper) and dark (graphite). Structural colours
     re-theme; SEMANTIC STATE COLOURS ARE RE-LIT PER THEME BUT KEEP THEIR MEANING,
     so criticality never changes meaning with the theme.
     Legacy names at the bottom alias onto these, so components that have not been
     migrated to the new names still repaint correctly in both themes.
     ───────────────────────────────────────────────────────────────────────── */

  /* Surfaces & lines */
  --bg: #F1F3F5;
  --panel: #FFFFFF;
  --panel-2: #F7F8FA;
  --chip: #EDF0F3;
  --line: #DEE2E7;
  --line-soft: #EBEEF1;
  --weekend: #F2F4F6;

  /* Text */
  --ink: #14181D;
  --ink-2: #454E58;
  --ink-3: #616B76;

  /* Interactive */
  --accent: #2456E6;
  --accent-soft: #E8EDFD;

  /* Semantic state */
  --crit: #B4291B;
  --crit-soft: #FBE7E3;
  --near: #8A5F00;
  --near-soft: #FAF1DA;
  --ok: #2F6B4A;
  --ok-soft: #E5EFE8;
  --ms: #6A3E9E;

  /* Text drawn ON a solid semantic fill. Must flip: dark-theme semantics are
     luminous, so white lettering on them would be unreadable. */
  --on-solid: #FFFFFF;

  /* Navigation / section strips — graphite in BOTH themes */
  --nav: #171C23;
  --nav-2: #1F262F;
  --nav-line: #2B333D;
  --nav-ink: #FFFFFF;
  --nav-ink-2: #AAB4C0;
  --nav-ink-3: #8C96A2;

  /* Semantic variants for use on the graphite ground, where the standard
     light-theme semantics fail contrast. */
  --crit-bright: #FF8272;
  --near-bright: #E3B341;
  --ok-bright: #7FC49A;

  /* Derived chart values */
  --crit-deep: #7A1A10;
  --float-tail: #CBD2D9;
  --bar-normal-fill: rgba(36,86,230,0.16);
  --bar-progress: rgba(20,24,29,0.30);

  /* Legacy aliases — resolved at use time, so they re-theme automatically.
     Components adopt the names above view by view as the redesign lands. */
  --white: var(--panel);
  --ink-soft: var(--ink-2);
  --gray-100: var(--panel-2);
  --gray-150: var(--chip);
  --gray-300: var(--line);
  --gray-500: var(--ink-3);
  --gray-700: var(--ink-2);
  --gray-900: var(--ink);
  --crit-tint: var(--crit-soft);
  --near-tint: var(--near-soft);
  --ok-tint: var(--ok-soft);
  --milestone: var(--ms);
  --active: var(--accent);
  --active-soft: var(--accent-soft);

  /* Type */
  --font-ui: "IBM Plex Sans", -apple-system, "Segoe UI", Roboto, sans-serif;
  --font-mono: "IBM Plex Mono", "SF Mono", "Fira Code", ui-monospace, monospace;
  --text-h1: 700 23px/1.3 var(--font-ui);
  --text-h2: 700 17px/1.3 var(--font-ui);
  --text-h3: 700 15px/1.35 var(--font-ui);
  --text-body: 400 14px/1.5 var(--font-ui);
  --text-small: 500 13px/1.4 var(--font-ui);
  --text-micro: 600 11px/1.3 var(--font-ui);

  /* Spacing & radius */
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-8: 32px;
  --radius-sm: 4px;
  --radius-md: 8px;
  /* Reviewer markup (key dates, periods): muted, so it never competes with the bars. */
  --mk-slate: #5B6B7F;
  --mk-teal: #1F7A72;
  --mk-amber: #A86A00;
  --mk-rose: #B2456E;
  --mk-violet: #6B4FB0;
  --mk-band-opacity: 0.08;
}

/* ── Alternate themes ──────────────────────────────────────────────────────
   Only the structural colors (ink/accent/neutrals) re-theme. The semantic status
   colors (--crit/--near/--ok/--milestone) are deliberately IDENTICAL across themes:
   criticality must read the same no matter the wallpaper. */

/* Slate — cool graphite neutrals, deep indigo accent. */
[data-theme="dark"] {
  --bg: #0C0F13;
  --panel: #14181E;
  --panel-2: #191F26;
  --chip: #222A33;
  --line: #262E38;
  --line-soft: #1D242B;
  --weekend: #10151A;

  --ink: #E9EDF2;
  --ink-2: #AEB8C4;
  --ink-3: #8B96A2;

  --accent: #7BA2FF;
  --accent-soft: #1A2740;

  --crit: #FF8272;
  --crit-soft: #331A19;
  --near: #E3B341;
  --near-soft: #2E2413;
  --ok: #7FC49A;
  --ok-soft: #16261D;
  --ms: #B98BFF;

  /* the semantics are luminous here, so lettering on them goes dark */
  --on-solid: #12161B;

  --nav: #080B0E;
  --nav-2: #12171D;
  --nav-line: #1E252D;
  --nav-ink: #E9EDF2;
  --nav-ink-2: #A6B0BC;
  --nav-ink-3: #8A939E;

  /* already luminous — the graphite ground needs no separate variant */
  --crit-bright: #FF8272;
  --near-bright: #E3B341;
  --ok-bright: #7FC49A;

  --crit-deep: #FFB3A8;
  --float-tail: #39424D;
  --bar-normal-fill: rgba(123,162,255,0.20);
  --bar-progress: rgba(233,237,242,0.28);
  --mk-slate: #9AA8BA;
  --mk-teal: #5CC2B6;
  --mk-amber: #E0A84A;
  --mk-rose: #E58AAE;
  --mk-violet: #A992F0;
  --mk-band-opacity: 0.12;
}


/* ── Reset & base ── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
button, input, select, textarea { font: inherit; color: inherit; }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: var(--radius-sm); }
body { font-family: var(--font-ui); background: var(--bg); color: var(--ink); font-size: 16px; line-height: 1.5; -webkit-font-smoothing: antialiased; }

/* Every number in the app reads as instrument output, not prose — codes, dates,
   durations, floats, percentages all get tabular monospace digits. */
.code, .g-act-code, .rel-code, .detail-code, .float-cell, .float-crit, .float-near,
.num-cell {
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
}
.data-table thead th { position: sticky; top: 0; z-index: 3; }
.table-empty-row td { text-align: center; padding: var(--space-6) var(--space-3); }
.table-empty { font: var(--text-small); color: var(--gray-700); }
.num-cell { text-align: right; }
th.num { text-align: right !important; }

/* ── Upload screen ── */
.upload-screen { display: flex; align-items: center; justify-content: center; min-height: 100vh; padding: var(--space-6); }
.upload-card { text-align: center; max-width: 480px; }
.upload-card .logo { margin-bottom: var(--space-4); }
.logo { color: var(--ink); }
.upload-card h1 { font: var(--text-h1); color: var(--ink); margin-bottom: var(--space-1); }
.upload-card .subtitle { font: var(--text-body); color: var(--gray-700); font-weight: 600; margin-bottom: 2px; }
.reopen-card { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); background: var(--accent-soft); border: 1px solid var(--accent); border-radius: var(--radius-md); padding: var(--space-3) var(--space-4); margin-bottom: var(--space-4); text-align: left; }
.reopen-info { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.reopen-info strong { font: var(--text-body); color: var(--ink); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.reopen-info span { font: var(--text-micro); color: var(--gray-700); text-transform: uppercase; letter-spacing: 0.04em; }
.reopen-actions { display: flex; align-items: center; gap: var(--space-2); flex-shrink: 0; }
.btn-forget { border: none; background: none; color: var(--gray-500); font-size: 19px; line-height: 1; cursor: pointer; padding: 4px 6px; border-radius: var(--radius-sm); }
.btn-forget:hover { background: var(--white); color: var(--crit); }
/* Entry state for Compare. Was a 560px centred column, which squeezed the snapshot
   register into a few characters per cell and centred a paragraph of prose. Now a
   normal reading measure with the register as the primary path and upload beside it. */
.compare-entry { max-width: 1100px; margin: var(--space-6) auto var(--space-8); text-align: left; }
.compare-entry__head { margin-bottom: var(--space-5); }
.compare-entry h2 { font: var(--text-h2); color: var(--ink); margin-bottom: var(--space-2); }
.compare-entry .subtitle { color: var(--gray-700); max-width: 68ch; margin: 0; }
.compare-entry__cols { display: grid; grid-template-columns: minmax(0, 1.55fr) minmax(260px, 1fr); gap: var(--space-5); align-items: start; }
.compare-upload__title { font: var(--text-h3); color: var(--ink); margin: 0 0 var(--space-2); }
.compare-upload__note { font: var(--text-micro); color: var(--gray-700); margin-top: var(--space-2); }
.compare-entry .drop-zone { padding: var(--space-6) var(--space-4); }
@media (max-width: 900px) {
  .compare-entry__cols { grid-template-columns: 1fr; }
}
.drop-zone { border: 1px solid var(--gray-300); border-radius: var(--radius-md); padding: 48px var(--space-6); cursor: pointer; transition: all 0.2s; background: var(--gray-100); }
.drop-zone:hover, .drop-zone.active { border-color: var(--accent); background: var(--accent-soft); }
.drop-zone input { position: absolute; width: 1px; height: 1px; clip-path: inset(50%); overflow: hidden; }
.drop-zone:focus-within { border-color: var(--accent); }
.drop-zone label { display: flex; flex-direction: column; align-items: center; gap: var(--space-3); cursor: pointer; color: var(--gray-700); font: var(--text-body); }
.drop-zone label svg { color: var(--accent); }
.drop-zone .loading { color: var(--accent); font-weight: 600; }
.hint { font: var(--text-small); color: var(--gray-500); margin-top: var(--space-4); }
.gh-link { display: inline-flex; align-items: center; gap: 6px; margin-top: var(--space-4); font: var(--text-small); color: var(--gray-700); text-decoration: none; }
.legal-notice { margin-top: var(--space-3); font: var(--text-micro); color: var(--gray-500); letter-spacing: 0.02em; }
.legal-notice a { color: inherit; text-decoration: underline; }
.feature-strip { font: var(--text-micro); color: var(--gray-500); text-transform: uppercase; letter-spacing: 0.06em; margin: 6px 0 var(--space-6); }
.sample-link { display: block; margin: var(--space-4) auto 0; border: none; background: none; cursor: pointer; font: var(--text-body); color: var(--gray-700); }
.sample-link strong { color: var(--accent); }
.sample-link:hover strong { text-decoration: underline; }
.sample-sub { font: var(--text-micro); color: var(--gray-500); margin-top: 4px; }
.sample-alt { border: none; background: none; cursor: pointer; font: inherit; color: var(--accent); padding: 0; }
.sample-alt:hover { text-decoration: underline; }
.upload-error { margin-top: var(--space-3); font: var(--text-small); color: var(--crit); background: var(--crit-tint); border: 1px solid var(--crit); border-radius: var(--radius-sm); padding: 8px 12px; }
.tab-report-btn { margin-left: var(--space-2); margin-bottom: 4px; padding: 5px 12px; font: var(--text-small); font-weight: 700; color: var(--on-solid); background: var(--accent); border: none; border-radius: var(--radius-sm); cursor: pointer; white-space: nowrap; }
.tab-report-btn:hover { opacity: 0.92; }
.tab-report-btn:disabled { opacity: 0.6; cursor: default; }
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
.table-wrap { overflow-x: auto; border: 1px solid var(--gray-300); border-radius: var(--radius-md); max-height: calc(100dvh - 190px); }
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
.annotation-dot.sev-query { background: var(--active); }
.annotation-dot.sev-risk { background: var(--near); }
.annotation-dot.sev-logic { background: var(--crit); }
.annotation-dot.sev-resolved { background: var(--ok); }
.badge-milestone { display: inline-block; padding: 0 5px; border-radius: var(--radius-sm); font: var(--text-micro); background: color-mix(in srgb, var(--milestone) 12%, white); color: var(--milestone); margin-left: var(--space-1); vertical-align: middle; }

/* Status badges */
.status-badge { display: inline-flex; align-items: center; gap: 5px; padding: 2px 8px; border-radius: var(--radius-sm); font: var(--text-small); }
.status-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.status-badge.TK_Complete { background: var(--ok-tint); color: var(--ok); }
.status-badge.TK_Complete .status-dot { background: var(--ok); }
.status-badge.TK_Active { background: var(--active-soft); color: var(--active); }
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
.float-neg { color: var(--on-solid); background: var(--crit); font-weight: 700; padding: 1px 6px; border-radius: var(--radius-sm); }

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
.wbs-head { display: flex; align-items: center; gap: 8px; padding: 6px 12px; background: var(--panel-2); border-bottom: 2px solid var(--line); font: var(--text-micro); text-transform: uppercase; letter-spacing: 0.04em; color: var(--ink-3); }
.wbs-head-name { flex: 1; }
.wbs-head .wbs-m { flex: none; text-align: right; }
.wbs-head .wbs-m:nth-of-type(1) { width: 42px; }
.wbs-head .wbs-m:nth-of-type(2) { width: 42px; }
.wbs-head .wbs-date { width: 62px; }
.wbs-prog-head { flex: none; width: 100px; text-align: right; }
.wbs-tree { border: 1px solid var(--gray-300); border-radius: var(--radius-md); overflow: hidden; }


.snap-register { text-align: left; background: var(--gray-100); border: 1px solid var(--gray-300); border-radius: var(--radius-md); padding: var(--space-3) var(--space-4); margin: 0; }
.snap-head { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); flex-wrap: wrap; }
.snap-head h3 { font: var(--text-h3); color: var(--ink); margin: 0; }
.snap-empty { font: var(--text-small); color: var(--gray-700); margin-top: var(--space-2); }
/* table-layout: fixed so the file column can be given a share of the width and
   truncate, instead of collapsing to a few characters wide and breaking a long
   P6 export name down the page one letter per line. */
.snap-table { width: 100%; table-layout: fixed; border-collapse: collapse; font: var(--text-small); margin-top: var(--space-3); }
.snap-table col.c-proj { width: 20%; }
.snap-table col.c-file { width: 34%; }
.snap-table col.c-date { width: 15%; }
.snap-table col.c-acts { width: 9%; }
.snap-table col.c-saved { width: 12%; }
.snap-table col.c-act { width: 10%; }
.snap-table th { text-align: left; font: var(--text-micro); text-transform: uppercase; color: var(--gray-700); border-bottom: 2px solid var(--gray-300); padding: var(--space-1) var(--space-2); }
.snap-table th.num { text-align: right; }
.snap-table td { padding: 6px var(--space-2); border-bottom: 1px solid var(--gray-150); }
.snap-table .code { font-family: var(--font-mono); font-weight: 600; color: var(--accent); white-space: nowrap; }
.snap-table .code { overflow: hidden; text-overflow: ellipsis; }
.snap-file { color: var(--ink-soft); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.snap-table .num-cell { font-family: var(--font-mono); text-align: right; white-space: nowrap; }
.snap-other-proj td { opacity: 0.55; }
/* the flex container is an inner div: a <td> set to display:flex drops out of the
   table's column model and its buttons escape the table box. */
.snap-actions-cell { padding-right: 0 !important; }
.snap-actions { display: flex; gap: var(--space-2); justify-content: flex-end; align-items: center; }
.snap-actions .btn-outline { white-space: nowrap; padding: 3px 10px; font: var(--text-micro); }

/* Code-filter provenance eyebrow: these dropdowns are generated from the file's own
   ACTVTYPE table — the tag says so at a glance, the tooltip spells it out. */
.code-filter-group { position: relative; display: inline-flex; }
.la-group { gap: 4px; }
.code-filter-src { position: absolute; top: -5px; left: 7px; padding: 0 3px; font-family: var(--font-mono); font-size: 8px; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: var(--gray-500); background: var(--white); line-height: 1; pointer-events: none; z-index: 1; max-width: calc(100% - 20px); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

/* ── Small screens ────────────────────────────────────────────────────────── */
@media (max-width: 900px) {
  .dashboard { padding: var(--space-3); }
  .tabs { flex-wrap: nowrap; overflow-x: auto; scrollbar-width: none; -webkit-overflow-scrolling: touch; }
  .tabs::-webkit-scrollbar { display: none; }
  .tabs button { white-space: nowrap; padding: var(--space-2) var(--space-3); }
  .header { flex-direction: column; align-items: flex-start; gap: var(--space-3); }
  .header-right { flex-wrap: wrap; }
  .metrics-strip { overflow-x: auto; scrollbar-width: none; }
  .metrics-strip::-webkit-scrollbar { display: none; }
  .metric { min-width: 84px; padding: var(--space-2) var(--space-3); }
  .gesture-hint { display: none !important; }
  .section-full { padding: 0 var(--space-3); }
  /* Wide tables scroll within themselves instead of forcing the page sideways */
  .data-table { display: block; overflow-x: auto; -webkit-overflow-scrolling: touch; }
}


/* ── App shell ────────────────────────────────────────────────────────────────
   A fixed graphite sidebar plus a 56px top bar, replacing the flat tab row, the
   project header and the six-cell metrics strip. Nothing needs hiding any more,
   so the collapse/expand summary toggle and its two-state layout maths are gone. */
.app-shell { min-height: 100vh; }
.main { margin-left: var(--sb-w); min-width: 0; }
:root { --sb-w: 236px; --topbar-h: 56px; }

.sidebar {
  position: fixed; inset: 0 auto 0 0; width: var(--sb-w); z-index: 30;
  background: var(--nav); color: var(--nav-ink);
  display: flex; flex-direction: column; overflow-y: auto;
}
.sb-brand { display: flex; align-items: center; gap: var(--space-2); padding: 14px var(--space-4) var(--space-3); }
.sb-logo { display: flex; align-items: center; gap: var(--space-2); color: var(--nav-ink); text-decoration: none; font-size: 16px; font-weight: 700; }
.sb-logo svg { color: var(--nav-ink); flex: none; }
.sb-readonly { margin-left: auto; font-family: var(--font-mono); font-size: 9px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.1em; color: var(--nav-ink-3); border: 1px solid var(--nav-line); border-radius: 4px; padding: 2px 6px; white-space: nowrap; }

.sb-project { padding: 0 var(--space-4) var(--space-3); border-bottom: 1px solid var(--nav-line); }
.sb-proj-name { font-size: 13px; font-weight: 600; color: var(--nav-ink); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.sb-proj-meta { font-family: var(--font-mono); font-size: 11px; color: var(--nav-ink-2); margin-top: 2px; }
.sb-datadate { display: flex; align-items: center; gap: 6px; margin-top: var(--space-2); background: var(--nav-2); border-radius: var(--radius-sm); padding: 5px 8px; }
.sb-datadate i { width: 6px; height: 6px; border-radius: 50%; background: var(--ms); flex: none; }
.sb-datadate span { font-family: var(--font-mono); font-size: 9px; font-weight: 600; letter-spacing: 0.1em; color: var(--nav-ink-3); }
.sb-datadate b { margin-left: auto; font-family: var(--font-mono); font-size: 11px; color: var(--nav-ink); font-weight: 500; }

.sb-collapse { flex: none; display: inline-flex; align-items: center; justify-content: center; width: 24px; height: 24px; border: none; border-radius: var(--radius-sm); background: none; color: var(--nav-ink-3); cursor: pointer; padding: 0; }
.sb-collapse:hover { background: var(--nav-2); color: var(--nav-ink); }
.sb-metrics { display: grid; grid-template-columns: 1fr 1fr; gap: 6px 10px; margin-top: var(--space-3); }
.sb-metric { display: flex; align-items: baseline; gap: 5px; white-space: nowrap; min-width: 0; }
.sb-metric b { font-family: var(--font-mono); font-size: 14px; font-weight: 600; color: var(--nav-ink); }
.sb-metric b.is-crit { color: var(--crit-bright); }
.sb-metric b.is-ok { color: var(--ok-bright); }
.sb-metric span { font: var(--text-micro); text-transform: uppercase; letter-spacing: 0.04em; color: var(--nav-ink-3); overflow: hidden; text-overflow: ellipsis; }
.sb-metric-pct, .sb-metric-wide { grid-column: 1 / -1; }
.sb-metric-pct .tb-bar { flex: 1; align-self: center; background: var(--nav-2); }
.sb-actions { display: flex; flex-direction: column; gap: 6px; margin-bottom: var(--space-2); }
.sb-actions .tb-export { position: relative; }
.sb-export-menu { left: 0; right: auto; top: auto; bottom: calc(100% + 4px); }
.sb-load:disabled { opacity: 0.5; cursor: default; }
.sb-rail { position: fixed; left: 0; top: 0; bottom: 0; width: 18px; z-index: 30; display: flex; align-items: flex-start; justify-content: center; padding-top: 18px; border: none; background: var(--nav); color: var(--nav-ink-3); cursor: pointer; }
.sb-rail:hover { color: var(--nav-ink); background: var(--nav-2); }
.sb-nav { flex: 1; padding: var(--space-2) var(--space-2); }
.sb-group { font-family: var(--font-mono); font-size: 9px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.14em; color: var(--nav-ink-3); padding: 10px var(--space-2) 4px; }
.sb-item { display: flex; align-items: center; gap: var(--space-2); width: 100%; text-align: left; background: none; border: none; border-radius: var(--radius-sm); padding: 6px 8px; cursor: pointer; font-size: 13px; color: var(--nav-ink-2); }
.sb-item:hover { background: var(--nav-2); color: var(--nav-ink); }
/* Active state is background + weight, not a left rail — one highlight convention. */
.sb-item.active { background: var(--nav-2); color: var(--nav-ink); font-weight: 600; }
.sb-item-label { flex: 1; }
.sb-score { font-family: var(--font-mono); font-size: 10px; font-weight: 700; border-radius: 4px; padding: 1px 5px; }
/* The chip sits on the graphite sidebar, so it takes a graphite ground and the
   on-graphite semantic variants — the light *-soft surfaces belong on --panel. */
.sb-score { background: var(--nav-2); }
.sb-score.is-ok { color: var(--ok-bright); }
.sb-score.is-near { color: var(--near-bright); }
.sb-score.is-crit { color: var(--crit-bright); }
.sb-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--accent); flex: none; }

.sb-footer { padding: var(--space-3) var(--space-3); border-top: 1px solid var(--nav-line); }
.sb-legal { margin: var(--space-3) 0 0; font: var(--text-micro); color: var(--nav-ink-3); text-align: center; line-height: 1.5; }
.sb-legal a { color: inherit; text-decoration: underline; }
.sb-theme { display: flex; background: var(--nav-2); border-radius: var(--radius-sm); padding: 2px; margin-bottom: var(--space-2); }
.sb-theme button { flex: 1; border: none; background: none; border-radius: 4px; padding: 5px; cursor: pointer; font: var(--text-small); color: var(--nav-ink-2); }
.sb-theme button.active { background: var(--accent); color: var(--on-solid); font-weight: 600; }
.sb-load { width: 100%; background: none; border: 1px solid var(--nav-line); border-radius: var(--radius-sm); color: var(--nav-ink-2); padding: 7px; cursor: pointer; font: var(--text-small); }
.sb-load:hover { border-color: var(--nav-ink-3); color: var(--nav-ink); }
.sb-backdrop { position: fixed; inset: 0; background: rgba(8,11,14,0.55); z-index: 25; }

/* ── Top bar ─────────────────────────────────────────────────────────────── */
.topbar { position: sticky; top: 0; z-index: 20; height: var(--topbar-h); display: flex; align-items: center; gap: var(--space-4); padding: 0 var(--space-4); background: var(--panel); border-bottom: 1px solid var(--line); }
.topbar-title { font: 600 17px/1.3 var(--font-ui); color: var(--ink); margin: 0; white-space: nowrap; }
.nav-toggle { display: none; align-items: center; justify-content: center; width: 32px; height: 32px; border: 1px solid var(--line); border-radius: var(--radius-sm); background: var(--panel); color: var(--ink-2); cursor: pointer; flex: none; }
.tb-bar { display: inline-block; width: 54px; height: 4px; border-radius: 2px; background: var(--chip); overflow: hidden; }
.tb-bar u { display: block; height: 100%; background: var(--accent); }
.tb-export { position: relative; }
.tb-menu { position: absolute; right: 0; top: calc(100% + 4px); min-width: 210px; background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius-sm); box-shadow: 0 8px 24px -10px rgba(0,0,0,0.35); padding: 4px; z-index: 30; }
.tb-menu button { display: block; width: 100%; text-align: left; background: none; border: none; border-radius: 4px; padding: 7px 10px; cursor: pointer; font: var(--text-small); color: var(--ink-2); }
.tb-menu button:hover:not(:disabled) { background: var(--chip); color: var(--ink); }
.tb-menu button:disabled { opacity: 0.45; cursor: default; }

.views { padding: var(--space-4); }
.views .section-full { width: auto; position: static; left: auto; right: auto; margin-left: 0; margin-right: 0; padding: 0; }

/* Wide screens have no top bar: the page is named by the highlighted sidebar item, and
   the figures and exports live in the sidebar. Narrow screens keep it for the menu. */
@media (min-width: 1101px) {
  .topbar { display: none; }
  .app-shell.sb-collapsed .sidebar { transform: translateX(-100%); }
  .app-shell.sb-collapsed .main { margin-left: 18px; }
}
@media (max-width: 1100px) { .sb-rail, .sb-collapse { display: none; } }

/* ── Below 1100px the sidebar slides over instead of holding a column ────── */
@media (max-width: 1100px) {
  .main { margin-left: 0; }
  .sidebar { transform: translateX(-100%); transition: transform 0.18s ease; box-shadow: none; }
  .sidebar.open { transform: translateX(0); box-shadow: 8px 0 28px -12px rgba(0,0,0,0.6); }
  .nav-toggle { display: inline-flex; }
}
@media (prefers-reduced-motion: reduce) { .sidebar { transition: none; } }
@media (max-width: 760px) {
  .views { padding: var(--space-2); }
  .topbar { gap: var(--space-3); padding: 0 var(--space-3); }
  .topbar-title { font-size: 15px; }
}

/* Per-view context bar. Carries the sub-line and any view-level controls; the
   view's name lives in the top bar, so it is not repeated here. */
.view-bar { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; padding: var(--space-2) var(--space-4); background: var(--panel-2); border-bottom: 1px solid var(--line); }
.view-bar .strip-title { display: flex; align-items: baseline; gap: var(--space-3); flex-wrap: wrap; min-width: 0; }
.view-bar .strip-sub { font: var(--text-small); color: var(--ink-3); }

/* Toggle chip, shared by the Gantt and Critical Path toolbars: solid border with
   a dot when on, dashed when off. Global because both components use it — defined
   in one component's scoped block it renders as an unstyled UA button in the other. */
.mk-slate { --mk: var(--mk-slate); }
.mk-teal { --mk: var(--mk-teal); }
.mk-amber { --mk: var(--mk-amber); }
.mk-rose { --mk: var(--mk-rose); }
.mk-violet { --mk: var(--mk-violet); }
.tb-chip { display: inline-flex; align-items: center; gap: 5px; border: 1px dashed var(--line); border-radius: 14px; background: var(--panel); color: var(--ink-3); padding: 4px 9px; cursor: pointer; font: var(--text-small); }
.tb-chip i { width: 6px; height: 6px; border-radius: 50%; background: transparent; border: 1px solid var(--ink-3); }
.tb-chip:hover { border-color: var(--ink-3); color: var(--ink-2); }
.tb-chip.on { border-style: solid; border-color: var(--accent); color: var(--accent); font-weight: 600; }
.tb-chip.on i { background: var(--accent); border-color: var(--accent); }


/* ── Shared small buttons ─────────────────────────────────────────────────────
   These three class names are used across five components but each was defined
   in a single component's *scoped* block, so everywhere else they rendered as
   unstyled UA buttons (most visibly the annotation editor's Save). Defined once
   here, globally, where the tokens already live. */
.btn-tiny, .btn-tiny-light, .ctrl-btn {
  padding: 4px 10px; border: 1px solid var(--line); border-radius: var(--radius-sm);
  background: var(--panel); cursor: pointer; font: var(--text-small); color: var(--ink-2);
}
.btn-tiny:hover:not(:disabled), .btn-tiny-light:hover:not(:disabled), .ctrl-btn:hover:not(:disabled) {
  background: var(--chip);
}
.btn-tiny:disabled, .btn-tiny-light:disabled, .ctrl-btn:disabled { opacity: 0.4; cursor: default; }
.ctrl-btn-accent { border-color: var(--accent); color: var(--accent); font-weight: 600; }
.ctrl-btn-accent:hover:not(:disabled) { background: var(--accent-soft); }

/* ── Shared detail drawer (Gantt + Critical Path) ─────────────────────────── */
.detail-drawer { position: fixed; top: var(--topbar-h); right: 0; bottom: 0; height: calc(100vh - var(--topbar-h)); width: 420px; max-width: 92vw; background: var(--white); border-left: 1px solid var(--gray-300); box-shadow: -8px 0 24px rgba(28,25,23,0.14); z-index: 15; overflow-y: auto; box-sizing: border-box; padding: var(--space-4); display: flex; flex-direction: column; gap: var(--space-5); }
.detail-slide-enter-active, .detail-slide-leave-active { transition: transform 0.2s ease, opacity 0.2s ease; }
.detail-slide-enter-from, .detail-slide-leave-to { transform: translateX(24px); opacity: 0; }

.detail-header { position: relative; padding-right: 26px; }
.detail-close { position: absolute; top: -6px; right: -6px; width: 26px; height: 26px; border: none; background: var(--gray-100); color: var(--gray-700); border-radius: 50%; font-size: 19px; line-height: 1; cursor: pointer; display: flex; align-items: center; justify-content: center; }
.detail-close:hover { background: var(--gray-150); color: var(--ink); }
.detail-code { display: block; font-family: var(--font-mono); font-weight: 700; font-size: 14px; color: var(--accent); margin-bottom: 3px; }
.detail-name { font-size: 17px; font-weight: 700; color: var(--ink); line-height: 1.35; margin: 0; }
.detail-wbs-path { font-size: 12px; color: var(--gray-700); font-family: var(--font-mono); margin-top: 6px; line-height: 1.5; }

.detail-stat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.stat-tile { background: var(--gray-100); border: 1px solid var(--gray-150); border-radius: var(--radius-md); padding: 8px 10px; }
.stat-value { font-family: var(--font-mono); font-size: 20px; font-weight: 700; color: var(--ink); line-height: 1.2; }
.stat-value-date { font-size: 16px; }
.stat-label { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; color: var(--gray-700); margin-top: 3px; }
.stat-status { font-size: 15px; }
.stat-status.status-TK_Complete { color: var(--ok); }
.stat-status.status-TK_Active { color: var(--active); }
.stat-status.status-TK_NotStart { color: var(--gray-700); }
.stat-progress { height: 4px; background: var(--gray-300); border-radius: 2px; margin-top: 6px; overflow: hidden; }
.stat-progress-fill { height: 100%; background: var(--accent); }
.stat-tile-crit { background: var(--crit-tint); border-color: var(--crit); }
.stat-tile-crit .stat-value { color: var(--crit); }
.stat-tile-near { background: var(--near-tint); border-color: var(--near); }
.stat-tile-near .stat-value { color: var(--near); }
.stat-tile-neg { background: var(--crit); border-color: var(--crit); }
.stat-tile-neg .stat-value, .stat-tile-neg .stat-label { color: var(--on-solid); }

.detail-constraint { background: var(--near-tint); border: 1px solid var(--near); border-radius: var(--radius-sm); padding: 7px 10px; font-size: 13px; color: var(--ink-soft); display: flex; gap: 6px; flex-wrap: wrap; align-items: baseline; }
.detail-constraint .constraint-label { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; color: var(--near); }
.detail-constraint strong { color: var(--ink); }

.detail-rels { display: flex; flex-direction: column; gap: var(--space-5); }
.rel-section h4 { font-size: 13px; text-transform: uppercase; letter-spacing: 0.04em; color: var(--gray-700); font-weight: 700; margin: 0 0 8px; }
.rel-section h4 em { font-style: normal; color: var(--accent); font-family: var(--font-mono); }
.rel-empty { font-size: 14px; color: var(--gray-500); font-style: italic; }
.rel-item-btn { display: flex; flex-direction: column; gap: 3px; font-size: 14px; padding: 8px 10px; border: none; background: var(--gray-100); cursor: pointer; border-radius: var(--radius-sm); width: 100%; text-align: left; margin-bottom: 5px; }
.rel-item-btn:hover { background: var(--accent-soft); }
.rel-item-row { display: flex; gap: 8px; align-items: baseline; flex-wrap: wrap; }
.rel-item-name { color: var(--ink-soft); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; min-width: 0; }
.rel-item-sub { color: var(--gray-700); }
.rel-code { font-family: var(--font-mono); font-weight: 700; color: var(--accent); font-size: 14px; flex-shrink: 0; }
.rel-type { color: var(--gray-700); font-size: 11px; font-weight: 700; text-transform: uppercase; flex-shrink: 0; }
.rel-dates { font-family: var(--font-mono); font-size: 12px; color: var(--gray-700); }
.rel-dur { font-family: var(--font-mono); font-size: 12px; color: var(--gray-700); margin-left: auto; }
.rel-lag { font-size: 11px; color: var(--gray-500); font-style: italic; }
.rel-driving { flex-shrink: 0; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.03em; color: var(--on-solid); background: var(--crit); padding: 1px 7px; border-radius: 9px; }
@media print {
  /* App chrome (nav tabs, header, metrics, warning banners) isn't part of the printed
     report — without hiding it, it sits in normal document flow at the top of page 1
     while the Gantt's own fixed, repeating column header (position: fixed, so it can
     repeat on every page) paints on top of it, since fixed elements ignore flow. */
  .detail-drawer, .tabs, .header, .metrics-strip, .parse-warnings, .cp-below-section { display: none; }
  .topbar, .sidebar { display: none !important; }
  /* The screen's tinted page background would otherwise print on every sheet (the Gantt
     prints its colours exactly). */
  html, body, .app-shell { background: #fff !important; }
  .dashboard, .dashboard.header-collapsed { padding: 0; }
}

/* Docked, not overlaying: the links and bars behind the panel stay visible while
   you read it. Only inside a chart body — the Health Check keeps the overlay,
   where there is no canvas to obscure. Below 900px it reverts to the overlay,
   since there is no width to give away. */
@media (min-width: 901px) {
  .gantt-body > .detail-drawer, .graph-body > .detail-drawer {
    position: static; width: 372px; max-width: 372px; flex: none; height: auto;
    box-shadow: none; z-index: auto;
  }
  /* A scrolling flex column squeezes children that have overflow:hidden instead
     of scrolling, which clips their content. */
  .gantt-body > .detail-drawer > *, .graph-body > .detail-drawer > * { flex-shrink: 0; }
}

@media (max-width: 540px) {
  .detail-drawer { width: 100vw; max-width: 100vw; border-left: none; }
  .theme-select { display: none; }
  .upload-screen { padding: var(--space-3); }
}

</style>
