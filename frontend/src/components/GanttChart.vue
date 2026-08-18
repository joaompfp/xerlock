<template>
  <div class="gantt-wrap" :class="{ 'is-fullscreen': isFullscreen, 'extra-room': extraRoom }" ref="wrapEl">
    <div class="gantt-strip">
      <div class="strip-title">
        <h2>Gantt Chart</h2>
        <span class="strip-sub">{{ data.project.total_activities }} activities</span>
      </div>
      <div class="basis-group">
        <span class="basis-label">Critical basis</span>
        <button :class="{ active: criticalBasis === 'tf0' }" @click="criticalBasis = 'tf0'">TF &le; 0</button>
        <button :class="{ active: criticalBasis === 'longest' }" @click="criticalBasis = 'longest'">Longest Path</button>
      </div>
    </div>

    <div class="gantt-controls">
      <div class="legend">
        <template v-if="criticalBasis === 'tf0'">
          <span class="legend-item"><i class="lg-bar lg-critical"></i>Critical (TF&le;0)</span>
          <span class="legend-item"><i class="lg-bar lg-near"></i>Near-critical</span>
          <span class="legend-item"><i class="lg-bar lg-normal"></i>Normal</span>
        </template>
        <template v-else>
          <span class="legend-item"><i class="lg-bar lg-critical"></i>On longest path</span>
          <span class="legend-item"><i class="lg-bar lg-normal"></i>Normal</span>
        </template>
        <span class="legend-item"><i class="lg-bar lg-negative"></i>Negative float (late)</span>
        <span class="legend-item"><i class="diamond"></i>Milestone</span>
        <span class="legend-item"><i class="bar-wbs"></i>WBS rollup</span>
        <span class="legend-item" v-if="baseline && showBaseline"><i class="lg-bar lg-ghost"></i>Baseline</span>
        <span class="legend-item" v-if="showProgressLine"><i class="progress-swatch"></i>Progress line</span>
      </div>

      <div class="control-divider"></div>

      <label class="ctrl-toggle"><input type="checkbox" v-model="showLinks" /> Links</label>
      <label class="ctrl-toggle"><input type="checkbox" v-model="showProgressLine" /> Progress line</label>
      <label v-if="baseline" class="ctrl-toggle" title="Ghost bars at each activity's position in the compared snapshot"><input type="checkbox" v-model="showBaseline" /> Baseline</label>
      <div class="zoom-group">
        <button
          v-for="z in zoomLevels"
          :key="z"
          :class="{ active: !dayWidthOverride && zoom === z }"
          @click="selectZoomPreset(z)"
        >{{ zoomLabel(z) }}</button>
      </div>
      <div class="zoom-adjust">
        <button class="zbtn" title="Zoom out" @click="zoomOut">−</button>
        <button class="zbtn" title="Fit to available width" @click="fitToWidth">Fit</button>
        <button class="zbtn" title="Zoom in" @click="zoomIn">+</button>
      </div>
      <button class="ctrl-btn" @click="expandAll">Expand all</button>
      <button class="ctrl-btn" @click="collapseAll">Collapse all</button>
      <button class="ctrl-btn" :disabled="todayX === null" @click="scrollToToday">Today</button>
      <button class="ctrl-btn ctrl-btn-accent" @click="toggleFullscreen">{{ isFullscreen ? 'Exit fullscreen' : 'Fullscreen' }}</button>
      <button class="ctrl-btn" @click="printGantt">Print</button>
      <span class="gesture-hint">Ctrl+scroll to zoom &middot; drag to pan &middot; Esc closes</span>
    </div>

    <!-- Filter bar: narrows which rows are shown (not just dimmed), the way P6's activity filter works.
         The same search box doubles as "find" — clicking a filtered result scrolls/centers on it. -->
    <div class="filter-bar">
      <input type="text" v-model="filterText" class="filter-input" placeholder="Search code, name, or WBS…" />
      <select v-model="filterStatus" class="filter-select">
        <option value="">All statuses</option>
        <option value="TK_NotStart">Not started</option>
        <option value="TK_Active">Active</option>
        <option value="TK_Complete">Complete</option>
      </select>
      <label class="filter-check"><input type="checkbox" v-model="filterCriticalOnly" /> Critical only</label>
      <span v-for="t in codeTypesAvailable" :key="t" class="code-filter-group">
        <span class="code-filter-src" aria-hidden="true">{{ t }}</span>
        <select v-model="filterCodes[t]" class="filter-select" :title="`P6 activity code category '${t}' — name and values read verbatim from this file's ACTVTYPE/ACTVCODE tables`">
          <option value="">All {{ t }}</option>
          <option v-for="c in codeValuesByType.get(t)" :key="c" :value="c">{{ c }}</option>
        </select>
      </span>
      <span class="date-range-filter" title="Show only activities whose dates touch this window">
        <input type="date" v-model="filterFrom" class="filter-date" title="Window start — activities finishing before this are hidden" />
        <span class="date-range-sep">&ndash;</span>
        <input type="date" v-model="filterTo" class="filter-date" title="Window end — activities starting after this are hidden" />
        <template v-if="data.project.data_date">
          <button class="btn-tiny-light la-btn" :class="{ active: lookAheadActive(28) }" @click="setLookAhead(28)" title="4-week look-ahead from the data date">4 wk</button>
          <button class="btn-tiny-light la-btn" :class="{ active: lookAheadActive(56) }" @click="setLookAhead(56)" title="8-week look-ahead from the data date">8 wk</button>
        </template>
      </span>
      <button v-if="returnTab" class="return-chip" @click="$emit('return-to-origin')">&larr; Back to {{ returnTab }}</button>
      <span v-if="isolationActive" class="isolation-chip">
        Chain trace &middot; {{ isolatedIds.size }} {{ isolatedIds.size === 1 ? 'activity' : 'activities' }}
        <button class="isolation-exit" @click="exitIsolation">Show all</button>
      </span>
      <span class="filter-count">{{ matchCount }} of {{ data.activities.length }} activities</span>
      <button class="btn-tiny-light" v-if="isFilterActive && !isolationActive" @click="clearFilters">Clear filters</button>
    </div>

    <div class="gantt-body">
    <div
      class="gantt-scroll"
      :class="{ panning }"
      ref="scrollEl"
      @scroll="onScroll"
      @wheel="onWheel"
      @mousedown="onPanStart"
    >
      <div
        class="gantt-grid"
        :style="{ gridTemplateColumns: labelColWidth + 'px ' + totalWidth + 'px', width: (labelColWidth + totalWidth) + 'px', height: (HEADER_HEIGHT + bodyHeight) + 'px' }"
      >
        <!-- Header + label column are positioned manually (top/left tracked from the @scroll
             handler) instead of using position:sticky — Chromium mis-renders sticky grid items
             whose own box exactly fills a narrow track once you scroll near the content's end. -->
        <div class="g-cell g-corner" :style="{ top: scrollTopPx + 'px', left: scrollLeftPx + 'px', width: labelColWidth + 'px' }">
          <span class="g-corner-name">Activity</span>
          <span class="g-col-dur g-corner-col">Dur</span>
          <span class="g-col-date g-corner-col">Start</span>
          <span class="g-col-date g-corner-col">Finish</span>
        </div>
        <div class="g-cell g-timeline-header" :style="{ top: scrollTopPx + 'px', left: labelColWidth + 'px', width: totalWidth + 'px' }">
          <div class="g-header-year-row">
            <div
              v-for="t in yearTicks"
              :key="'y' + t.x"
              class="g-year-tick"
              :style="{ left: t.x + 'px' }"
            >{{ t.label }}</div>
          </div>
          <div class="g-header-detail-row">
            <div
              v-for="t in detailTicks"
              :key="'d' + t.x"
              class="g-detail-tick"
              :class="{ weekend: t.weekend }"
              :style="{ left: t.x + 'px' }"
            >{{ t.label }}</div>
          </div>
        </div>

        <!-- Background layer: weekend shading + gridlines — sits BELOW bars -->
        <svg
          class="g-overlay g-overlay-bg"
          :style="{ left: labelColWidth + 'px', top: HEADER_HEIGHT + 'px', width: totalWidth + 'px', height: bodyHeight + 'px' }"
          :width="totalWidth"
          :height="bodyHeight"
        >
          <rect
            v-for="r in weekendRects"
            :key="'we' + r.x"
            :x="r.x" y="0" :width="r.w" :height="bodyHeight"
            class="g-weekend"
          />
          <line
            v-for="t in detailTicks"
            :key="'gl' + t.x"
            :x1="t.x" :x2="t.x" y1="0" :y2="bodyHeight"
            class="g-gridline"
          />
          <line
            v-for="t in secondaryMonthGridlines"
            :key="'glm' + t.x"
            :x1="t.x" :x2="t.x" y1="0" :y2="bodyHeight"
            class="g-gridline-month"
          />
        </svg>

        <!-- Foreground layer: critical links + progress line — sits ABOVE bars, so a link never
             visually disappears behind an unrelated activity's bar. -->
        <svg
          class="g-overlay g-overlay-fg"
          :style="{ left: labelColWidth + 'px', top: HEADER_HEIGHT + 'px', width: totalWidth + 'px', height: bodyHeight + 'px' }"
          :width="totalWidth"
          :height="bodyHeight"
        >
          <defs>
            <marker id="gantt-arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M0 0L8 4L0 8z" class="g-link-arrow" />
            </marker>
            <marker id="gantt-arrow-chain" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M0 0L8 4L0 8z" class="g-link-arrow-chain" />
            </marker>
          </defs>
          <path
            v-for="l in links"
            :key="l.id"
            :d="l.d"
            class="g-link"
            :class="{ 'g-link-chain': l.chain }"
            :marker-end="l.chain ? 'url(#gantt-arrow-chain)' : 'url(#gantt-arrow)'"
          />
          <path v-if="progressLinePath" :d="progressLinePath" class="g-progress-line" />
          <circle
            v-for="(p, i) in progressLinePoints"
            :key="'pp' + i"
            :cx="p.x" :cy="p.y" r="2.5"
            class="g-progress-dot"
          />
        </svg>

        <!-- Today line (above everything but the frozen header/label) -->
        <div
          v-if="todayX !== null"
          class="g-today-line"
          :style="{ left: (labelColWidth + todayX) + 'px', top: HEADER_HEIGHT + 'px', height: bodyHeight + 'px' }"
        ><span class="g-today-flag">Today</span></div>

        <!-- Data date line: the schedule's own status date — the anchor every
             progress/forecast judgement should be made against, not "today". -->
        <div
          v-if="dataDateX !== null"
          class="g-dd-line"
          :style="{ left: (labelColWidth + dataDateX) + 'px', top: HEADER_HEIGHT + 'px', height: bodyHeight + 'px' }"
          :title="'Data date: ' + formatDate(data.project.data_date)"
        ><span class="g-dd-flag">Data date</span></div>

        <!-- Resize handle for the label column, tracked against horizontal scroll manually
             (position:sticky inside a CSS-grid item gets unreliable with explicit track spans,
             so we just follow scrollLeftPx from the @scroll handler instead). -->
        <div
          class="g-resize-handle"
          :class="{ resizing }"
          :style="{ left: (scrollLeftPx + labelColWidth - 3) + 'px', height: (HEADER_HEIGHT + bodyHeight) + 'px' }"
          @mousedown.stop="onResizeStart"
          title="Drag to resize"
        ></div>

        <!-- Rows -->
        <template v-for="row in rows" :key="row.key">
          <div
            class="g-cell g-label"
            :class="{ 'g-label-wbs': row.type === 'wbs', stripe: row.index % 2 === 1, selected: row.type === 'activity' && row.activity.task_id === selectedTaskId }"
            :style="{ top: (HEADER_HEIGHT + row.index * ROW_HEIGHT) + 'px', left: scrollLeftPx + 'px', width: labelColWidth + 'px', paddingLeft: (8 + row.level * 11) + 'px' }"
            @click="row.type === 'wbs' ? toggleWbs(row.wbsId) : selectActivity(row.activity)"
          >
            <template v-if="row.type === 'wbs'">
              <IconChevron class="g-toggle" :expanded="isFilterActive ? !filterCollapsed.has(row.wbsId) : expandedWbs.has(row.wbsId)" />
              <span class="g-wbs-name">{{ row.name }}</span>
              <span class="g-wbs-count">{{ row.count }}</span>
              <span class="g-col-dur"></span>
              <span class="g-col-date">{{ row.start ? formatDateShort(row.start) : '' }}</span>
              <span class="g-col-date">{{ row.finish ? formatDateShort(row.finish) : '' }}</span>
            </template>
            <template v-else>
              <i v-if="annotations[row.activity.task_id]" class="annotation-flag" :class="'sev-' + annotations[row.activity.task_id].severity" :title="annotations[row.activity.task_id].note"></i>
              <span class="g-act-code">{{ row.activity.task_code }}</span>
              <span class="g-act-name">{{ row.activity.task_name }}</span>
              <span class="g-col-dur">{{ formatHours(row.activity.duration_hrs, row.activity.calendar_hrs_per_day) }}</span>
              <span class="g-col-date">{{ formatDateShort(displayStart(row.activity)) }}</span>
              <span class="g-col-date">{{ formatDateShort(displayEnd(row.activity)) }}</span>
            </template>
          </div>
          <div
            class="g-cell g-timeline-row"
            :class="{ stripe: row.index % 2 === 1 }"
            :style="{ gridRow: (row.index + 2), gridColumn: 2, width: totalWidth + 'px' }"
          >
            <div
              v-if="row.type === 'wbs'"
              class="g-bar-wbs"
              :style="wbsBarStyle(row)"
              :title="row.name + ' — ' + row.count + ' activities'"
            ></div>
            <template v-else-if="row.milestone">
              <div
                v-if="ghostFor(row.activity)"
                class="g-milestone-ghost"
                :style="{ left: ghostFor(row.activity).x + 'px' }"
                :title="'Baseline: ' + ghostFor(row.activity).label"
              ></div>
              <div
                class="g-milestone"
                :class="row.cls"
                :style="{ left: row.x + 'px' }"
                :title="milestoneTitle(row.activity)"
                @click="selectActivity(row.activity)"
              ></div>
            </template>
            <template v-else>
              <div
                v-if="ghostFor(row.activity)"
                class="g-bar-ghost"
                :style="{ left: ghostFor(row.activity).x + 'px', width: ghostFor(row.activity).w + 'px' }"
                :title="'Baseline: ' + ghostFor(row.activity).label"
              ></div>
              <div
                class="g-bar"
                :class="[row.cls, { selected: row.activity.task_id === selectedTaskId }]"
                :style="{ left: row.x + 'px', width: row.w + 'px' }"
                :title="barTitle(row.activity)"
                @click="selectActivity(row.activity)"
              >
                <div class="g-bar-progress" :style="{ width: row.activity.pct_complete + '%' }"></div>
              </div>
            </template>
          </div>
        </template>
      </div>
    </div>

    <Transition name="detail-slide">
      <aside class="detail-drawer" v-if="selectedActivity">
        <div class="detail-header">
          <button class="detail-close" @click="selectedTaskId = null" title="Close" aria-label="Close">&times;</button>
          <span class="detail-code">{{ selectedActivity.task_code }}</span>
          <h3 class="detail-name">{{ selectedActivity.task_name }}</h3>
          <div v-if="selectedActivity.wbs_path" class="detail-wbs-path">{{ selectedActivity.wbs_path }}</div>
          <div class="detail-actions">
            <button v-if="!isolationActive" class="btn-tiny-light btn-isolate" @click="isolateSelected" title="Clear the chart down to just this activity, then click predecessors/successors below to rebuild its chain link by link">
              Isolate &amp; trace chain
            </button>
            <span v-else class="trace-hint">Tracing — click a predecessor or successor below to add it and walk the chain.</span>
          </div>
        </div>

        <div class="detail-stat-grid">
          <div class="stat-tile">
            <div class="stat-value">{{ formatHours(selectedActivity.duration_hrs, selectedActivity.calendar_hrs_per_day) }}</div>
            <div class="stat-label">Duration</div>
          </div>
          <div class="stat-tile" :class="floatTileClass(selectedActivity)">
            <div class="stat-value">{{ formatFloat(selectedActivity.total_float_hrs, selectedActivity.calendar_hrs_per_day) }}</div>
            <div class="stat-label">Float</div>
          </div>
          <div class="stat-tile">
            <div class="stat-value stat-value-date">{{ formatDate(displayStart(selectedActivity)) }}</div>
            <div class="stat-label">Start</div>
          </div>
          <div class="stat-tile">
            <div class="stat-value stat-value-date">{{ formatDate(displayEnd(selectedActivity)) }}</div>
            <div class="stat-label">Finish</div>
          </div>
          <div class="stat-tile">
            <div class="stat-value stat-status" :class="'status-' + selectedActivity.status">{{ statusLabel(selectedActivity.status) }}</div>
            <div class="stat-label">Status</div>
          </div>
          <div class="stat-tile">
            <div class="stat-value">{{ selectedActivity.pct_complete }}%</div>
            <div class="stat-progress"><div class="stat-progress-fill" :style="{ width: selectedActivity.pct_complete + '%' }"></div></div>
            <div class="stat-label">Complete</div>
          </div>
        </div>

        <!-- An imposed date is often the single fact explaining an activity's float —
             surface it here instead of making the reviewer hunt in the Health Check. -->
        <div v-if="selectedActivity.cstr_type" class="detail-constraint">
          <span class="constraint-label">Constraint</span>
          <strong>{{ cstrLabel(selectedActivity.cstr_type) }}</strong>
          <span v-if="selectedActivity.cstr_date">&middot; {{ formatDate(selectedActivity.cstr_date) }}</span>
          <template v-if="selectedActivity.cstr_type2">
            <span>&middot; plus {{ cstrLabel(selectedActivity.cstr_type2) }}</span>
            <span v-if="selectedActivity.cstr_date2">{{ formatDate(selectedActivity.cstr_date2) }}</span>
          </template>
        </div>

        <div class="detail-rels">
          <div class="rel-section">
            <h4>Predecessors <em>{{ selectedPredecessors.length }}</em></h4>
            <div v-if="selectedPredecessors.length === 0" class="rel-empty">None</div>
            <button v-for="p in selectedPredecessors" :key="p.task_id" class="rel-item-btn" @click="revealAndSelect(p.task_id)">
              <div class="rel-item-row">
                <span class="rel-code">{{ p.activity ? p.activity.task_code : '?' + p.task_id }}</span>
                <span class="rel-item-name">{{ p.activity ? p.activity.task_name : '' }}</span>
                <span v-if="p.driving" class="rel-driving" title="This link controls the dates — P6's 'driving' relationship flag">Driving</span>
              </div>
              <div class="rel-item-row rel-item-sub">
                <span class="rel-type">{{ relTypeLabel(p.type) }}</span>
                <template v-if="p.activity">
                  <span class="rel-dates">{{ formatDate(displayStart(p.activity)) }} → {{ formatDate(displayEnd(p.activity)) }}</span>
                  <span class="rel-dur">{{ formatHours(p.activity.duration_hrs, p.activity.calendar_hrs_per_day) }}</span>
                </template>
                <span v-if="p.lag_hrs" class="rel-lag">{{ formatLag(p.lag_hrs, selectedActivity.calendar_hrs_per_day) }} lag</span>
              </div>
            </button>
          </div>
          <div class="rel-section">
            <h4>Successors <em>{{ selectedSuccessors.length }}</em></h4>
            <div v-if="selectedSuccessors.length === 0" class="rel-empty">None</div>
            <button v-for="s in selectedSuccessors" :key="s.task_id" class="rel-item-btn" @click="revealAndSelect(s.task_id)">
              <div class="rel-item-row">
                <span class="rel-code">{{ s.activity ? s.activity.task_code : '?' + s.task_id }}</span>
                <span class="rel-item-name">{{ s.activity ? s.activity.task_name : '' }}</span>
                <span v-if="s.driving" class="rel-driving" title="This link controls the dates — P6's 'driving' relationship flag">Driving</span>
              </div>
              <div class="rel-item-row rel-item-sub">
                <span class="rel-type">{{ relTypeLabel(s.type) }}</span>
                <template v-if="s.activity">
                  <span class="rel-dates">{{ formatDate(displayStart(s.activity)) }} → {{ formatDate(displayEnd(s.activity)) }}</span>
                  <span class="rel-dur">{{ formatHours(s.activity.duration_hrs, s.activity.calendar_hrs_per_day) }}</span>
                </template>
                <span v-if="s.lag_hrs" class="rel-lag">{{ formatLag(s.lag_hrs, selectedActivity.calendar_hrs_per_day) }} lag</span>
              </div>
            </button>
          </div>
        </div>

        <AnnotationEditor
          :key="selectedActivity.task_id"
          :annotation="annotations[selectedActivity.task_id] || null"
          @save="patch => $emit('annotate', selectedActivity.task_id, patch)"
          @remove="$emit('unannotate', selectedActivity.task_id)"
        />
      </aside>
    </Transition>
    </div>
  </div>
</template>

<script>
import { formatDate, formatDateShort, formatHours, isMilestone, formatFloat, formatLag, statusLabel } from '../utils/format'
import { relTypeLabel, cstrLabel, displayStart, displayEnd } from '../utils/p6'
import IconChevron from './IconChevron.vue'
import AnnotationEditor from './AnnotationEditor.vue'

const LABEL_COL_WIDTH_DEFAULT = 460
const LABEL_COL_MIN = 200
const LABEL_COL_MAX = 700
const HEADER_HEIGHT = 52
const ROW_HEIGHT = 20
const ZOOM_DAY_WIDTH = { day: 32, week: 9, month: 3, quarter: 1.1 }
const MIN_DAY_WIDTH = 0.4
const MAX_DAY_WIDTH = 60
const VIEW_STORAGE_KEY = 'schedule-app:gantt-view'

function loadSavedView() {
  try {
    const raw = localStorage.getItem(VIEW_STORAGE_KEY)
    return raw ? JSON.parse(raw) : {}
  } catch {
    return {}
  }
}

function saveView(view) {
  try {
    localStorage.setItem(VIEW_STORAGE_KEY, JSON.stringify(view))
  } catch {
    // localStorage unavailable (private browsing, quota) — view just won't persist.
  }
}

export default {
  name: 'GanttChart',
  components: { IconChevron, AnnotationEditor },
  props: {
    data: { type: Object, required: true },
    extraRoom: { type: Boolean, default: false },
    jumpTo: { type: [Number, String], default: null },
    annotations: { type: Object, default: () => ({}) },
    returnTab: { type: String, default: '' },
    // Parsed baseline schedule (from the Compare tab's snapshot/upload). When present,
    // activities matched by code can draw a ghost bar at their baseline position.
    baseline: { type: Object, default: null },
  },
  emits: ['jumped', 'annotate', 'unannotate', 'return-to-origin'],
  data() {
    const saved = loadSavedView()

    const start = this.data.project.earliest_start ? new Date(this.data.project.earliest_start) : new Date()
    const end = this.data.project.latest_end ? new Date(this.data.project.latest_end) : new Date()
    const days = Math.max(1, (end - start) / 86400000)
    const autoZoom = days > 300 ? 'month' : days > 100 ? 'week' : 'day'

    const expandedWbs = new Set()
    const markExpanded = (node, level) => {
      if (level < 1) expandedWbs.add(node.wbs_id)
      for (const c of node.children || []) markExpanded(c, level + 1)
    }
    for (const root of this.data.wbs_tree || []) markExpanded(root, 0)

    return {
      HEADER_HEIGHT,
      ROW_HEIGHT,
      zoom: saved.zoom || autoZoom,
      zoomLevels: ['day', 'week', 'month', 'quarter'],
      dayWidthOverride: saved.dayWidthOverride ?? null,
      labelColWidth: Math.min(saved.labelColWidth || LABEL_COL_WIDTH_DEFAULT, Math.max(220, Math.floor(window.innerWidth * 0.55))),
      criticalBasis: saved.criticalBasis || 'tf0',
      expandedWbs,
      // WBS ids collapsed while a filter is active. Filtering auto-expands everything so
      // matches are revealed, but a collapse click during filtering must still stick —
      // this set records those, and clears when filters clear.
      filterCollapsed: new Set(),
      showBaseline: true,
      showLinks: saved.showLinks ?? true,
      showProgressLine: saved.showProgressLine ?? false,
      selectedTaskId: null,
      isFullscreen: false,
      filterText: '',
      filterStatus: '',
      filterCriticalOnly: false,
      filterFrom: '',
      filterTo: '',
      filterCodes: Object.fromEntries((this.data.project.activity_code_types || []).map(t => [t, ''])),
      // Chain tracing: null = off; a Set of task_ids = show ONLY these activities.
      // Grown one activity at a time by clicking predecessors/successors in the drawer,
      // letting a reviewer reconstruct a driving chain link by link.
      isolatedIds: null,
      scrollLeftPx: 0,
      scrollTopPx: 0,
      panning: false,
      resizing: false,
    }
  },
  mounted() {
    document.addEventListener('fullscreenchange', this.onFullscreenChange)
    window.addEventListener('keydown', this.onKeydown)
    // The drawer is a fixed overlay; a click on app chrome outside this component
    // (tab bar, summary toggle, another tab's controls) dismisses it instead of the
    // overlay swallowing the interaction context.
    this._onDocMousedown = e => {
      if (this.selectedTaskId && this.$el.offsetParent !== null && !this.$el.contains(e.target)) {
        this.selectedTaskId = null
      }
    }
    document.addEventListener('mousedown', this._onDocMousedown)
  },
  beforeUnmount() {
    document.removeEventListener('fullscreenchange', this.onFullscreenChange)
    document.removeEventListener('mousedown', this._onDocMousedown)
    window.removeEventListener('keydown', this.onKeydown)
    window.removeEventListener('mousemove', this.onPanMove)
    window.removeEventListener('mouseup', this.onPanEnd)
    window.removeEventListener('mousemove', this.onResizeMove)
    window.removeEventListener('mouseup', this.onResizeEnd)
  },
  watch: {
    // The component survives file swaps (tabs use v-show), so reseed the per-category
    // filter keys for the new file — an undefined v-model renders the select blank.
    data() {
      this.clearFilters()
    },
    zoom() { this.persistView() },
    criticalBasis() { this.persistView() },
    showLinks() { this.persistView() },
    showProgressLine() { this.persistView() },
    dayWidthOverride() { this.persistView() },
    jumpTo: {
      immediate: true,
      handler(taskId) {
        if (taskId == null) return
        this.revealAndSelect(taskId)
        this.$emit('jumped')
      },
    },
  },
  computed: {
    actLookup() {
      const m = new Map()
      for (const a of this.data.activities) m.set(a.task_id, a)
      return m
    },
    selectedActivity() {
      return this.selectedTaskId != null ? this.actLookup.get(this.selectedTaskId) : null
    },
    selectedPredecessors() {
      if (!this.selectedActivity) return []
      return this.selectedActivity.predecessors.map(p => ({ ...p, activity: this.actLookup.get(p.task_id) || null }))
    },
    selectedSuccessors() {
      if (!this.selectedActivity) return []
      return this.selectedActivity.successors.map(s => ({ ...s, activity: this.actLookup.get(s.task_id) || null }))
    },
    wbsParentOf() {
      const map = new Map()
      const walk = (node, parentId) => {
        if (parentId != null) map.set(node.wbs_id, parentId)
        for (const c of node.children || []) walk(c, node.wbs_id)
      }
      for (const root of this.data.wbs_tree || []) walk(root, null)
      return map
    },
    activitiesByWbs() {
      const map = new Map()
      for (const a of this.data.activities) {
        if (!map.has(a.wbs_id)) map.set(a.wbs_id, [])
        map.get(a.wbs_id).push(a)
      }
      for (const list of map.values()) {
        list.sort((a, b) => {
          const da = displayStart(a) || ''
          const db = displayStart(b) || ''
          if (da !== db) return da < db ? -1 : 1
          return a.task_code < b.task_code ? -1 : a.task_code > b.task_code ? 1 : 0
        })
      }
      return map
    },
    rollups() {
      return this.computeRollups(null)
    },
    rollupsFiltered() {
      return this.matchedTaskIds ? this.computeRollups(a => this.matchedTaskIds.has(a.task_id)) : null
    },
    activeRollups() {
      return this.isFilterActive && this.rollupsFiltered ? this.rollupsFiltered : this.rollups
    },
    rangeStart() {
      const d = this.data.project.earliest_start ? new Date(this.data.project.earliest_start) : new Date()
      d.setDate(d.getDate() - 5)
      return d
    },
    rangeEnd() {
      const d = this.data.project.latest_end ? new Date(this.data.project.latest_end) : new Date()
      d.setDate(d.getDate() + 5)
      return d
    },
    dayWidth() {
      return this.dayWidthOverride ?? ZOOM_DAY_WIDTH[this.zoom]
    },
    totalWidth() {
      const days = Math.max(1, (this.rangeEnd - this.rangeStart) / 86400000)
      return Math.round(days * this.dayWidth)
    },
    bodyHeight() {
      return this.rows.length * ROW_HEIGHT
    },
    yearTicks() {
      const ticks = []
      const startY = this.rangeStart.getFullYear()
      const endY = this.rangeEnd.getFullYear()
      for (let y = startY; y <= endY; y++) {
        const boundary = new Date(y, 0, 1)
        const clamped = boundary < this.rangeStart ? this.rangeStart : boundary
        if (clamped > this.rangeEnd) break
        const x = Math.round(((clamped - this.rangeStart) / 86400000) * this.dayWidth)
        ticks.push({ x, label: String(y) })
      }
      return ticks
    },
    monthTicks() {
      const ticks = []
      let cur = new Date(this.rangeStart.getFullYear(), this.rangeStart.getMonth(), 1)
      while (cur <= this.rangeEnd) {
        const x = Math.round(((cur - this.rangeStart) / 86400000) * this.dayWidth)
        ticks.push({ x, label: cur.toLocaleDateString('en-GB', { month: 'short' }) })
        cur = new Date(cur.getFullYear(), cur.getMonth() + 1, 1)
      }
      return ticks
    },
    weekTicks() {
      const ticks = []
      let cur = new Date(this.rangeStart)
      while (cur <= this.rangeEnd) {
        const x = Math.round(((cur - this.rangeStart) / 86400000) * this.dayWidth)
        ticks.push({ x, label: cur.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' }) })
        cur = new Date(cur.getTime() + 7 * 86400000)
      }
      return ticks
    },
    dayTicks() {
      const ticks = []
      const cur = new Date(this.rangeStart)
      cur.setHours(0, 0, 0, 0)
      while (cur <= this.rangeEnd) {
        const x = Math.round(((cur - this.rangeStart) / 86400000) * this.dayWidth)
        const dow = cur.getDay()
        ticks.push({ x, label: String(cur.getDate()), weekend: dow === 0 || dow === 6 })
        cur.setDate(cur.getDate() + 1)
      }
      return ticks
    },
    detailTicks() {
      if (this.zoom === 'month' || this.zoom === 'quarter') return this.monthTicks
      if (this.zoom === 'week') return this.weekTicks
      return this.dayTicks
    },
    secondaryMonthGridlines() {
      return this.zoom === 'day' || this.zoom === 'week' ? this.monthTicks : []
    },
    weekendRects() {
      if (this.zoom !== 'day') return []
      return this.dayTicks.filter(t => t.weekend).map(t => ({ x: t.x, w: this.dayWidth }))
    },
    todayX() {
      const today = new Date()
      if (today < this.rangeStart || today > this.rangeEnd) return null
      return Math.round(((today - this.rangeStart) / 86400000) * this.dayWidth)
    },
    dataDateX() {
      if (!this.data.project.data_date) return null
      const dd = new Date(this.data.project.data_date)
      if (isNaN(dd) || dd < this.rangeStart || dd > this.rangeEnd) return null
      const x = Math.round(((dd - this.rangeStart) / 86400000) * this.dayWidth)
      // When the file is fresh, data date ≈ today — don't stack two flags on one pixel.
      return this.todayX !== null && Math.abs(x - this.todayX) < 3 ? null : x
    },
    codeTypesAvailable() {
      return this.data.project.has_activity_codes ? this.data.project.activity_code_types : []
    },
    codeValuesByType() {
      const m = new Map()
      for (const t of this.codeTypesAvailable) m.set(t, new Set())
      for (const a of this.data.activities) {
        for (const c of a.activity_codes) {
          if (m.has(c.type)) m.get(c.type).add(c.code)
        }
      }
      for (const [t, set] of m) m.set(t, [...set].sort())
      return m
    },
    activeCodeFilters() {
      return Object.entries(this.filterCodes).filter(([, v]) => v)
    },
    isolationActive() {
      return this.isolatedIds !== null
    },
    isFilterActive() {
      return this.isolationActive || !!(this.filterText.trim() || this.filterStatus || this.filterCriticalOnly || this.filterFrom || this.filterTo || this.activeCodeFilters.length)
    },
    matchedTaskIds() {
      // Isolation takes precedence over the text/status/code filters: the trace IS the view.
      if (this.isolatedIds) return this.isolatedIds
      if (!this.isFilterActive) return null
      const q = this.filterText.trim().toLowerCase()
      const ids = new Set()
      for (const a of this.data.activities) {
        if (q && !(a.task_code.toLowerCase().includes(q) || a.task_name.toLowerCase().includes(q) || (a.wbs_path && a.wbs_path.toLowerCase().includes(q)))) continue
        if (this.filterStatus && a.status !== this.filterStatus) continue
        if (this.filterFrom || this.filterTo) {
          // Window-intersection on the display dates (actual once started, else early):
          // an activity is shown if any part of it touches [from, to]. ISO date-prefix
          // string comparison is deliberate — no timezone surprises.
          const aStart = (displayStart(a) || '').slice(0, 10)
          const aEnd = (displayEnd(a) || aStart || '').slice(0, 10)
          if (!aStart) continue
          if (this.filterFrom && aEnd < this.filterFrom) continue
          if (this.filterTo && aStart > this.filterTo) continue
        }
        if (this.filterCriticalOnly && !this.isBasisCritical(a)) continue
        if (this.activeCodeFilters.length) {
          const matchesAll = this.activeCodeFilters.every(([type, code]) =>
            a.activity_codes.some(c => c.type === type && c.code === code)
          )
          if (!matchesAll) continue
        }
        ids.add(a.task_id)
      }
      return ids
    },
    baselineByCode() {
      if (!this.baseline) return null
      const m = new Map()
      for (const a of this.baseline.activities) m.set(a.task_code, a)
      return m
    },
    matchCount() {
      return this.matchedTaskIds ? this.matchedTaskIds.size : this.data.activities.length
    },
    rows() {
      const rows = []
      const filtering = this.isFilterActive
      const matched = this.matchedTaskIds
      const rollups = this.activeRollups
      const walk = (nodes, level) => {
        const sorted = [...nodes].sort((a, b) => a.seq_num - b.seq_num)
        for (const node of sorted) {
          const roll = rollups.get(node.wbs_id) || { start: null, finish: null, count: 0 }
          if (filtering && roll.count === 0) continue
          rows.push({
            type: 'wbs',
            key: 'w' + node.wbs_id,
            wbsId: node.wbs_id,
            level,
            name: node.wbs_short_name ? `${node.wbs_short_name} ${node.wbs_name}` : node.wbs_name,
            count: roll.count,
            start: roll.start,
            finish: roll.finish,
          })
          const expanded = filtering ? !this.filterCollapsed.has(node.wbs_id) : this.expandedWbs.has(node.wbs_id)
          if (expanded) {
            walk(node.children || [], level + 1)
            for (const a of this.activitiesByWbs.get(node.wbs_id) || []) {
              if (filtering && !matched.has(a.task_id)) continue
              rows.push(this.buildActivityRow(a, level + 1))
            }
          }
        }
      }
      walk(this.data.wbs_tree || [], 0)

      const orphansAll = this.data.activities.filter(a => !this.allWbsIds.has(a.wbs_id))
      const orphans = filtering ? orphansAll.filter(a => matched.has(a.task_id)) : orphansAll
      if (orphans.length) {
        rows.push({ type: 'wbs', key: 'w-unassigned', wbsId: '__unassigned', level: 0, name: '(Unassigned)', count: orphans.length })
        if (filtering ? !this.filterCollapsed.has('__unassigned') : this.expandedWbs.has('__unassigned')) {
          for (const a of orphans) rows.push(this.buildActivityRow(a, 1))
        }
      }

      rows.forEach((r, i) => { r.index = i })
      return rows
    },
    allWbsIds() {
      const ids = new Set()
      const walk = (nodes) => {
        for (const n of nodes) { ids.add(n.wbs_id); walk(n.children || []) }
      }
      walk(this.data.wbs_tree || [])
      return ids
    },
    rowIndexByTaskId() {
      const map = new Map()
      this.rows.forEach(r => { if (r.type === 'activity') map.set(r.activity.task_id, r.index) })
      return map
    },
    links() {
      // Chain tracing draws its links regardless of the Links toggle — they're the point.
      if (!this.showLinks && !this.isolationActive) return []
      const out = []
      const rowByIndex = this.rows
      for (const row of rowByIndex) {
        if (row.type !== 'activity') continue
        // Normal mode: only critical-to-critical links (per the selected basis).
        // Isolation mode: every relationship between two traced activities, with
        // non-critical ones styled as "chain" links so the critical core still stands out.
        if (!this.isolationActive && !this.isBasisCritical(row.activity)) continue
        for (const p of row.activity.predecessors || []) {
          const predIdx = this.rowIndexByTaskId.get(p.task_id)
          if (predIdx === undefined) continue
          const predRow = rowByIndex[predIdx]
          const bothCritical = this.isBasisCritical(row.activity) && this.isBasisCritical(predRow.activity)
          if (!this.isolationActive && !bothCritical) continue
          const predX = this.dateToX(displayEnd(predRow.activity))
          const predY = predIdx * ROW_HEIGHT + ROW_HEIGHT / 2
          const succX = row.x
          const succY = row.index * ROW_HEIGHT + ROW_HEIGHT / 2
          if (predX === null || succX === null) continue
          const midX = predX + 8
          out.push({
            id: `${p.task_id}-${row.activity.task_id}-${p.type}-${out.length}`,
            d: `M${predX},${predY} L${midX},${predY} L${midX},${succY} L${succX},${succY}`,
            chain: !bothCritical,
          })
        }
      }
      return out
    },
    progressLinePoints() {
      if (!this.showProgressLine) return []
      const pts = []
      for (const row of this.rows) {
        if (row.type !== 'activity' || row.milestone) continue
        const px = row.x + row.w * (row.activity.pct_complete / 100)
        const py = row.index * ROW_HEIGHT + ROW_HEIGHT / 2
        pts.push({ x: px, y: py })
      }
      return pts
    },
    progressLinePath() {
      if (this.progressLinePoints.length < 2) return ''
      return 'M' + this.progressLinePoints.map(p => `${p.x},${p.y}`).join(' L')
    },
  },
  methods: {
    computeRollups(matchFn) {
      const map = new Map()
      const activitiesByWbs = this.activitiesByWbs
      const visit = (node) => {
        let start = null, finish = null, count = 0
        for (const a of activitiesByWbs.get(node.wbs_id) || []) {
          if (matchFn && !matchFn(a)) continue
          count++
          const ds = displayStart(a)
          const de = displayEnd(a)
          if (ds) {
            const d = new Date(ds)
            if (!start || d < start) start = d
          }
          if (de) {
            const d = new Date(de)
            if (!finish || d > finish) finish = d
          }
        }
        for (const child of node.children || []) {
          const r = visit(child)
          count += r.count
          if (r.start && (!start || r.start < start)) start = r.start
          if (r.finish && (!finish || r.finish > finish)) finish = r.finish
        }
        const roll = { start, finish, count }
        map.set(node.wbs_id, roll)
        return roll
      }
      for (const root of this.data.wbs_tree || []) visit(root)
      return map
    },
    dateToX(dateStr) {
      if (!dateStr) return null
      const d = new Date(dateStr)
      if (isNaN(d)) return null
      return Math.round(((d - this.rangeStart) / 86400000) * this.dayWidth)
    },
    isBasisCritical(a) {
      return this.criticalBasis === 'longest' ? a.is_longest_path : a.is_critical
    },
    classifyActivity(a) {
      const base = this.isBasisCritical(a)
        ? 'critical'
        : (this.criticalBasis === 'tf0' && a.total_float_hrs > 0 && a.total_float_hrs <= 80 ? 'near' : 'other')
      // Negative float means the activity is already behind an imposed date — flag it
      // regardless of critical basis, since that's a property of the activity itself.
      return a.is_negative_float ? `${base} negative` : base
    },
    buildActivityRow(a, level) {
      const milestone = isMilestone(a)
      const x = this.dateToX(displayStart(a))
      const xEnd = this.dateToX(displayEnd(a))
      const w = milestone ? 0 : Math.max((xEnd ?? x ?? 0) - (x ?? 0), 3)
      return {
        type: 'activity', key: 'a' + a.task_id, level, activity: a,
        milestone, x: x ?? 0, w, cls: this.classifyActivity(a),
      }
    },
    wbsBarStyle(row) {
      if (!row.start || !row.finish) return { display: 'none' }
      const x = this.dateToX(row.start.toISOString())
      const xEnd = this.dateToX(row.finish.toISOString())
      return { left: x + 'px', width: Math.max(xEnd - x, 3) + 'px' }
    },
    ghostFor(a) {
      if (!this.showBaseline || !this.baselineByCode) return null
      const b = this.baselineByCode.get(a.task_code)
      if (!b) return null
      const s = displayStart(b)
      const e = displayEnd(b)
      if (!s) return null
      const x = this.dateToX(s)
      const xEnd = e ? this.dateToX(e) : x
      return {
        x,
        w: Math.max(xEnd - x, 3),
        label: `${formatDateShort(s)}${e && e !== s ? ' → ' + formatDateShort(e) : ''}`,
      }
    },
    toggleWbs(wbsId) {
      if (this.isFilterActive) {
        if (this.filterCollapsed.has(wbsId)) this.filterCollapsed.delete(wbsId)
        else this.filterCollapsed.add(wbsId)
        // Force reactivity: Set mutations aren't tracked by Vue 3 unless reassigned.
        this.filterCollapsed = new Set(this.filterCollapsed)
        return
      }
      if (this.expandedWbs.has(wbsId)) this.expandedWbs.delete(wbsId)
      else this.expandedWbs.add(wbsId)
      this.expandedWbs = new Set(this.expandedWbs)
    },
    allWbsIdSet() {
      const all = new Set()
      const walk = (nodes) => {
        for (const n of nodes) { all.add(n.wbs_id); walk(n.children || []) }
      }
      walk(this.data.wbs_tree || [])
      all.add('__unassigned')
      return all
    },
    expandAll() {
      if (this.isFilterActive) {
        this.filterCollapsed = new Set()
        return
      }
      this.expandedWbs = this.allWbsIdSet()
    },
    collapseAll() {
      if (this.isFilterActive) {
        this.filterCollapsed = this.allWbsIdSet()
        return
      }
      this.expandedWbs = new Set()
    },
    selectActivity(a) {
      const wasSelected = this.selectedTaskId === a.task_id
      this.selectedTaskId = wasSelected ? null : a.task_id
      if (!wasSelected) {
        this.$nextTick(() => this.scrollToActivity(a.task_id))
      }
    },
    // Defers a scrollTo past two animation frames. Chromium can leave
    // position:sticky elements mis-computed if scrollLeft/scrollTop are set
    // right alongside a reactive DOM mutation (e.g. the .selected class toggle
    // that triggers this scroll) — two rAFs guarantee a real layout+paint has
    // settled first. Cheap enough that it's used for every programmatic scroll.
    deferredScrollTo(el, opts) {
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          el.scrollTo(opts)
        })
      })
    },
    scrollToActivity(taskId) {
      const idx = this.rowIndexByTaskId.get(taskId)
      if (idx === undefined || !this.$refs.scrollEl) return
      const el = this.$refs.scrollEl
      const row = this.rows[idx]
      const top = Math.max(0, idx * ROW_HEIGHT - el.clientHeight / 2)
      let left = el.scrollLeft
      if (row && row.type === 'activity') {
        left = Math.max(0, row.x - el.clientWidth / 2 + this.labelColWidth)
      }
      this.deferredScrollTo(el, { top, left, behavior: 'smooth' })
    },
    onKeydown(e) {
      // Only when this tab is actually on screen (tabs stay mounted via v-show).
      if (!this.$el || this.$el.offsetParent === null) return
      const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName || '')
      if (e.key === 'Escape') {
        if (this.selectedTaskId != null) { this.selectedTaskId = null; return }
        if (this.isolationActive) this.exitIsolation()
      } else if (e.key === '/' && !typing) {
        e.preventDefault()
        this.$el.querySelector('.filter-input')?.focus()
      } else if ((e.key === 'ArrowDown' || e.key === 'ArrowUp') && !typing) {
        e.preventDefault()
        this.moveSelection(e.key === 'ArrowDown' ? 1 : -1)
      }
    },
    // ↑/↓ walk the visible activity rows (skipping WBS headers); the drawer follows.
    moveSelection(dir) {
      const actRows = this.rows.filter(r => r.type === 'activity')
      if (!actRows.length) return
      let idx = actRows.findIndex(r => r.activity.task_id === this.selectedTaskId)
      idx = idx === -1 ? (dir > 0 ? 0 : actRows.length - 1) : Math.min(actRows.length - 1, Math.max(0, idx + dir))
      const next = actRows[idx].activity
      if (next.task_id === this.selectedTaskId) return
      this.selectedTaskId = next.task_id
      this.$nextTick(() => this.scrollToActivity(next.task_id))
    },
    clearFilters() {
      this.filterCollapsed = new Set()
      this.filterText = ''
      this.filterStatus = ''
      this.filterCriticalOnly = false
      this.filterFrom = ''
      this.filterTo = ''
      // Reseed one '' entry per category — an undefined v-model renders the select blank.
      this.filterCodes = Object.fromEntries((this.data.project.activity_code_types || []).map(t => [t, '']))
      this.isolatedIds = null
    },
    // Look-ahead: the window every site meeting asks for — data date + N days.
    lookAheadWindow(days) {
      const dd = this.data.project.data_date
      if (!dd) return null
      const from = dd.slice(0, 10)
      const end = new Date(from + 'T12:00:00')
      end.setDate(end.getDate() + days)
      const to = `${end.getFullYear()}-${String(end.getMonth() + 1).padStart(2, '0')}-${String(end.getDate()).padStart(2, '0')}`
      return { from, to }
    },
    lookAheadActive(days) {
      const w = this.lookAheadWindow(days)
      return !!w && this.filterFrom === w.from && this.filterTo === w.to
    },
    setLookAhead(days) {
      const w = this.lookAheadWindow(days)
      if (!w) return
      if (this.lookAheadActive(days)) {
        this.filterFrom = ''
        this.filterTo = ''
      } else {
        this.filterFrom = w.from
        this.filterTo = w.to
      }
    },
    isolateSelected() {
      if (this.selectedTaskId == null) return
      this.isolatedIds = new Set([this.selectedTaskId])
      this.$nextTick(() => this.scrollToActivity(this.selectedTaskId))
    },
    exitIsolation() {
      const keep = this.selectedTaskId
      this.isolatedIds = null
      // Re-reveal the activity we were parked on so the exit doesn't strand the
      // selection under a collapsed WBS branch.
      if (keep != null) this.revealAndSelect(keep)
    },
    scrollToToday() {
      if (this.todayX === null || !this.$refs.scrollEl) return
      const el = this.$refs.scrollEl
      this.deferredScrollTo(el, { left: Math.max(0, this.todayX - el.clientWidth / 2), behavior: 'smooth' })
    },
    toggleFullscreen() {
      if (document.fullscreenElement) {
        document.exitFullscreen()
      } else if (this.$refs.wrapEl.requestFullscreen) {
        this.$refs.wrapEl.requestFullscreen()
      }
    },
    onFullscreenChange() {
      this.isFullscreen = !!document.fullscreenElement
    },
    printGantt() {
      window.print()
    },
    persistView() {
      saveView({
        zoom: this.zoom,
        criticalBasis: this.criticalBasis,
        showLinks: this.showLinks,
        showProgressLine: this.showProgressLine,
        labelColWidth: this.labelColWidth,
        dayWidthOverride: this.dayWidthOverride,
      })
    },
    zoomLabel(z) {
      return z.charAt(0).toUpperCase() + z.slice(1)
    },
    barTitle(a) {
      return `${a.task_code} — ${a.task_name}\n${formatDate(displayStart(a))} → ${formatDate(displayEnd(a))}\n` +
        `Duration: ${formatHours(a.duration_hrs, a.calendar_hrs_per_day)} · Float: ${formatFloat(a.total_float_hrs, a.calendar_hrs_per_day)} · ${a.pct_complete}% complete`
    },
    milestoneTitle(a) {
      return `${a.task_code} — ${a.task_name}\n${formatDate(displayStart(a))}\nFloat: ${formatFloat(a.total_float_hrs, a.calendar_hrs_per_day)}`
    },
    // Same 0h / negative / ≤80h(10d) severity bands used everywhere else in the app,
    // applied to the whole stat tile so float is legible without reading the number.
    floatTileClass(a) {
      if (a.is_negative_float) return 'stat-tile-neg'
      if (a.total_float_hrs === 0) return 'stat-tile-crit'
      if (a.total_float_hrs != null && a.total_float_hrs <= 80) return 'stat-tile-near'
      return ''
    },
    formatDate,
    formatDateShort,
    formatLag,
    formatHours,
    formatFloat,
    statusLabel,
    relTypeLabel,
    cstrLabel,
    displayStart,
    displayEnd,
    // Selects a predecessor/successor from the detail panel: expands every WBS
    // ancestor so the row actually renders (it may be tucked under a collapsed
    // branch, or hidden by an active filter), then scrolls to it.
    revealAndSelect(taskId) {
      const a = this.actLookup.get(taskId)
      if (!a) return
      if (this.isolationActive) {
        // Chain tracing: clicking a predecessor/successor ADDS it to the traced set and
        // walks the selection onto it, growing the chain one link at a time.
        const next = new Set(this.isolatedIds)
        next.add(taskId)
        this.isolatedIds = next
        this.selectedTaskId = taskId
        this.$nextTick(() => this.scrollToActivity(taskId))
        return
      }
      if (this.isFilterActive) this.clearFilters()
      const toExpand = new Set(this.expandedWbs)
      let cur = a.wbs_id
      while (cur != null) {
        toExpand.add(cur)
        cur = this.wbsParentOf.get(cur) ?? null
      }
      this.expandedWbs = toExpand
      this.selectedTaskId = taskId
      this.$nextTick(() => this.scrollToActivity(taskId))
    },

    // ── Zoom (presets + continuous) ──────────────────────────────────────
    selectZoomPreset(z) {
      this.zoom = z
      this.dayWidthOverride = null
    },
    setDayWidth(v) {
      this.dayWidthOverride = Math.min(MAX_DAY_WIDTH, Math.max(MIN_DAY_WIDTH, v))
    },
    zoomIn() {
      this.setDayWidth(this.dayWidth * 1.3)
    },
    zoomOut() {
      this.setDayWidth(this.dayWidth / 1.3)
    },
    fitToWidth() {
      const el = this.$refs.scrollEl
      if (!el) return
      const availableWidth = Math.max(100, el.clientWidth - this.labelColWidth)
      const totalDays = Math.max(1, (this.rangeEnd - this.rangeStart) / 86400000)
      this.setDayWidth(availableWidth / totalDays)
    },
    onWheel(e) {
      if (!e.ctrlKey && !e.metaKey) return
      e.preventDefault()
      const el = this.$refs.scrollEl
      if (!el) return
      const rect = el.getBoundingClientRect()
      const viewportX = e.clientX - rect.left
      const contentXOld = el.scrollLeft + viewportX - this.labelColWidth
      const dateDays = contentXOld / this.dayWidth
      const factor = Math.exp(-e.deltaY * 0.0015)
      this.setDayWidth(this.dayWidth * factor)
      // Chromium can leave position:sticky elements mis-computed if scrollLeft is
      // reassigned in the same tick as the content-width change that just happened
      // (grid-template-columns resize from the new dayWidth). Deferring past two
      // animation frames guarantees a real layout+paint has settled first.
      this.$nextTick(() => {
        requestAnimationFrame(() => {
          requestAnimationFrame(() => {
            const contentXNew = dateDays * this.dayWidth
            el.scrollLeft = Math.max(0, contentXNew - viewportX + this.labelColWidth)
          })
        })
      })
    },

    // ── Pan (drag on the timeline; native scrollbars still work too) ────
    onScroll(e) {
      this.scrollLeftPx = e.target.scrollLeft
      this.scrollTopPx = e.target.scrollTop
    },
    onPanStart(e) {
      if (e.button !== 0) return
      if (e.target.closest('.g-label') || e.target.closest('.g-resize-handle')) return
      this.panning = true
      this._panStartX = e.clientX
      this._panStartY = e.clientY
      this._panScrollLeft = this.$refs.scrollEl.scrollLeft
      this._panScrollTop = this.$refs.scrollEl.scrollTop
      window.addEventListener('mousemove', this.onPanMove)
      window.addEventListener('mouseup', this.onPanEnd)
    },
    onPanMove(e) {
      if (!this.panning || !this.$refs.scrollEl) return
      const el = this.$refs.scrollEl
      el.scrollLeft = this._panScrollLeft - (e.clientX - this._panStartX)
      el.scrollTop = this._panScrollTop - (e.clientY - this._panStartY)
    },
    onPanEnd() {
      this.panning = false
      window.removeEventListener('mousemove', this.onPanMove)
      window.removeEventListener('mouseup', this.onPanEnd)
    },

    // ── Resizable label column ───────────────────────────────────────────
    onResizeStart(e) {
      e.preventDefault()
      this.resizing = true
      this._resizeStartX = e.clientX
      this._resizeStartWidth = this.labelColWidth
      window.addEventListener('mousemove', this.onResizeMove)
      window.addEventListener('mouseup', this.onResizeEnd)
    },
    onResizeMove(e) {
      if (!this.resizing) return
      const dx = e.clientX - this._resizeStartX
      this.labelColWidth = Math.min(LABEL_COL_MAX, Math.max(LABEL_COL_MIN, this._resizeStartWidth + dx))
    },
    onResizeEnd() {
      if (!this.resizing) return
      this.resizing = false
      window.removeEventListener('mousemove', this.onResizeMove)
      window.removeEventListener('mouseup', this.onResizeEnd)
      this.persistView()
    },
  },
}
</script>

<style scoped>
.gantt-wrap { border: 1px solid var(--gray-300); border-radius: var(--radius-md); overflow: hidden; background: var(--white); margin-bottom: var(--space-6); box-shadow: 0 1px 3px rgba(28,25,23,0.06); font-family: var(--font-ui); }
.gantt-wrap.is-fullscreen { border-radius: 0; display: flex; flex-direction: column; height: 100vh; }
.gantt-wrap.is-fullscreen .gantt-body { flex: 1; min-height: 0; display: flex; }
.gantt-wrap.is-fullscreen .gantt-scroll { flex: 1; height: auto; max-height: none; }

/* Wraps just the scroll viewport so the detail drawer can anchor to its exact bounds
   (top/bottom) regardless of how tall the strip/controls/filter-bar above it are. */
.gantt-body { position: relative; }

/* Thin ink strip: title + the one highest-value toggle. Everything else lives in the
   light control row below, so there's no large dark panel to justify visually. */
.gantt-strip { display: flex; justify-content: space-between; align-items: center; padding: var(--space-3) var(--space-4); background: var(--ink); gap: var(--space-3); }
.strip-title { display: flex; align-items: baseline; gap: var(--space-2); }
.strip-title h2 { font: var(--text-h2); color: var(--white); }
.strip-sub { font: var(--text-micro); color: var(--gray-300); text-transform: uppercase; letter-spacing: 0.04em; }

.basis-group { display: flex; align-items: center; gap: 6px; border: 1px solid var(--ink-soft); border-radius: var(--radius-sm); padding: 2px; flex-shrink: 0; }
.basis-label { font: var(--text-micro); color: var(--gray-500); padding-left: 6px; text-transform: uppercase; letter-spacing: 0.04em; }
.basis-group button { padding: 4px 10px; border: none; border-radius: 3px; background: none; cursor: pointer; font: var(--text-small); color: var(--gray-300); }
.basis-group button.active { background: var(--crit); color: var(--white); font-weight: 700; }
.basis-group button:hover:not(.active) { background: var(--ink-soft); }

/* Light control row: legend + every interactive control, directly adjoining the light
   timeline header below — no light/dark/light seam. */
.gantt-controls { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; padding: var(--space-2) var(--space-4); background: var(--gray-100); border-bottom: 1px solid var(--gray-300); }
.control-divider { width: 1px; align-self: stretch; background: var(--gray-300); margin: 2px 0; }
.legend { display: flex; gap: 14px; flex-wrap: wrap; align-items: center; }
.legend-item { display: flex; align-items: center; gap: 5px; font: var(--text-small); color: var(--gray-700); }
/* Legend swatches ARE miniature bars — same fills and borders as the chart itself, so
   the legend teaches the encoding instead of adding a second one to decode. */
.lg-bar { width: 20px; height: 10px; border-radius: 3px; display: inline-block; box-sizing: border-box; border: 1.5px solid; }
.lg-critical { background: var(--crit-tint); border-color: var(--crit); }
.lg-near { background: var(--near-tint); border-color: var(--near); }
.lg-normal { background: var(--accent-soft); border-color: var(--accent); }
.lg-negative { background: repeating-linear-gradient(135deg, rgba(255,255,255,0.45) 0 2px, transparent 2px 5px), var(--crit); border-color: var(--crit-deep); }
.diamond { width: 8px; height: 8px; background: var(--milestone); display: inline-block; transform: rotate(45deg); }
.bar-wbs { width: 16px; height: 7px; border-radius: 3px; background: var(--gray-700); display: inline-block; }
.progress-swatch { width: 14px; height: 2px; background: var(--milestone); display: inline-block; }

.ctrl-toggle { font: var(--text-small); color: var(--gray-700); display: flex; align-items: center; gap: 4px; cursor: pointer; }
.zoom-group { display: flex; border: 1px solid var(--gray-300); border-radius: var(--radius-sm); overflow: hidden; }
.zoom-group button { padding: 4px 10px; border: none; border-right: 1px solid var(--gray-300); background: var(--white); cursor: pointer; font: var(--text-small); color: var(--gray-700); }
.zoom-group button:last-child { border-right: none; }
.zoom-group button.active { background: var(--accent-soft); color: var(--accent); font-weight: 700; }
.zoom-group button:hover:not(.active) { background: var(--gray-150); }
.zoom-adjust { display: flex; border: 1px solid var(--gray-300); border-radius: var(--radius-sm); overflow: hidden; }
.zbtn { padding: 4px 10px; border: none; border-right: 1px solid var(--gray-300); background: var(--white); cursor: pointer; font: var(--text-small); color: var(--gray-700); font-weight: 700; }
.zbtn:last-child { border-right: none; }
.zbtn:hover { background: var(--gray-150); }
.ctrl-btn { padding: 4px 10px; border: 1px solid var(--gray-300); border-radius: var(--radius-sm); background: var(--white); cursor: pointer; font: var(--text-small); color: var(--gray-700); }
.ctrl-btn:hover:not(:disabled) { background: var(--gray-150); }
.ctrl-btn:disabled { opacity: 0.4; cursor: default; }
.ctrl-btn-accent { border-color: var(--accent); color: var(--accent); font-weight: 600; }
.ctrl-btn-accent:hover { background: var(--accent-soft); }

.filter-bar { display: flex; align-items: center; gap: 10px; padding: 10px var(--space-4); background: var(--white); border-bottom: 1px solid var(--gray-300); flex-wrap: wrap; }
.filter-input { padding: 6px 12px; border: 1px solid var(--gray-300); border-radius: var(--radius-sm); font: var(--text-small); width: 240px; }
.date-range-filter { display: inline-flex; align-items: center; gap: 4px; }
.filter-date { border: 1px solid var(--gray-300); border-radius: var(--radius-sm); padding: 4px 6px; background: var(--white); font-family: var(--font-mono); font-size: 12px; color: var(--ink); }
.date-range-sep { color: var(--gray-500); }
.la-btn.active { background: var(--active-soft); border-color: var(--active); color: var(--active); font-weight: 700; }
.filter-select { padding: 6px 8px; border: 1px solid var(--gray-300); border-radius: var(--radius-sm); font: var(--text-small); background: var(--white); }
.filter-check { font: var(--text-small); color: var(--gray-700); display: flex; align-items: center; gap: 4px; cursor: pointer; }
.filter-count { font: var(--text-small); color: var(--gray-500); margin-left: auto; }
.return-chip { display: inline-flex; align-items: center; background: var(--ink); color: var(--white); border: none; border-radius: 12px; padding: 3px 12px; font: var(--text-small); font-weight: 600; cursor: pointer; }
.return-chip:hover { opacity: 0.9; }
.gesture-hint { margin-left: auto; font: var(--text-micro); color: var(--gray-500); white-space: nowrap; }
.isolation-chip { display: inline-flex; align-items: center; gap: 8px; background: var(--accent-soft); color: var(--accent); border: 1px solid var(--accent); border-radius: 12px; padding: 2px 4px 2px 10px; font: var(--text-small); font-weight: 600; }
.isolation-exit { border: none; background: var(--accent); color: var(--white); border-radius: 9px; padding: 2px 9px; font: var(--text-small); font-weight: 600; cursor: pointer; }
.isolation-exit:hover { opacity: 0.9; }
.btn-tiny-light { padding: 4px 10px; border: 1px solid var(--gray-300); border-radius: var(--radius-sm); background: var(--white); cursor: pointer; font: var(--text-small); color: var(--gray-700); }
.btn-tiny-light:hover { background: var(--gray-150); }

/* Fixed height, not max-height: with a collapsed WBS the viewport used to shrink to
   the handful of visible rows, leaving a cramped partial canvas. A constant-height
   viewport keeps the full working area available no matter how much is expanded. */
.gantt-scroll { overflow: auto; scrollbar-width: thin; scrollbar-color: var(--gray-300) transparent; height: min(75vh, 900px); position: relative; cursor: grab; }
.gantt-scroll.panning { cursor: grabbing; }
.gantt-wrap.extra-room .gantt-scroll { height: calc(100dvh - 258px); min-height: 320px; }
/* Controls + filter bar wrap taller on narrow screens — leave more room above the grid */
@media (max-width: 900px) {
  .gantt-scroll, .gantt-wrap.extra-room .gantt-scroll { height: calc(100dvh - 445px); min-height: 320px; }
}
.gantt-grid { display: grid; grid-template-rows: 52px; grid-auto-rows: 20px; position: relative; }

.g-cell { min-width: 0; }
.g-corner { position: absolute; z-index: 7; background: var(--gray-100); border-bottom: 1px solid var(--gray-300); border-right: 2px solid var(--gray-300); height: 52px; display: flex; align-items: flex-end; gap: 6px; padding: 0 8px 8px 8px; box-sizing: border-box; overflow: hidden; box-shadow: 2px 0 5px -3px rgba(28,25,23,0.18); }
.g-corner-name { flex: 1; min-width: 0; font: var(--text-micro); font-weight: 700; color: var(--gray-700); text-transform: uppercase; letter-spacing: 0.03em; }
.g-corner-col { font-weight: 700; text-transform: uppercase; letter-spacing: 0.03em; color: var(--gray-700) !important; }
.g-timeline-header { position: absolute; z-index: 6; background: var(--gray-100); border-bottom: 1px solid var(--gray-300); height: 52px; }
.g-header-year-row { position: relative; height: 22px; border-bottom: 1px solid var(--gray-150); }
.g-header-detail-row { position: relative; height: 30px; }
.g-year-tick { position: absolute; top: 0; height: 100%; padding-left: 6px; padding-top: 3px; font: var(--text-small); font-weight: 700; color: var(--ink); border-left: 1px solid var(--gray-300); white-space: nowrap; }
.g-detail-tick { position: absolute; top: 0; padding-top: 8px; padding-left: 4px; font: var(--text-micro); color: var(--gray-700); white-space: nowrap; border-left: 1px solid var(--gray-150); height: 100%; box-sizing: border-box; }
.g-detail-tick.weekend { color: var(--crit); font-weight: 700; }

.g-overlay { position: absolute; pointer-events: none; }
.g-overlay-bg { z-index: 1; }
.g-overlay-fg { z-index: 3; }
.g-weekend { fill: var(--gray-150); }
.g-gridline { stroke: var(--gray-150); stroke-width: 1; }
.g-gridline-month { stroke: var(--gray-300); stroke-width: 1; }
.g-link { fill: none; stroke: var(--crit); stroke-width: 1.5; opacity: 0.75; }
.g-link-arrow { fill: var(--crit); }
.g-link.g-link-chain { stroke: var(--accent); stroke-width: 1.5; opacity: 0.85; }
.g-link-arrow-chain { fill: var(--accent); }
.g-progress-line { fill: none; stroke: var(--milestone); stroke-width: 2; stroke-dasharray: 4 3; opacity: 0.9; }
.g-progress-dot { fill: var(--milestone); }

.g-today-line { position: absolute; width: 2px; background: var(--accent); z-index: 4; pointer-events: none; }
.g-dd-line { position: absolute; width: 0; border-left: 2px dashed var(--milestone); z-index: 4; pointer-events: none; }
.g-dd-flag { position: absolute; top: 2px; left: 3px; font: var(--text-micro); font-weight: 700; color: var(--white); background: var(--milestone); padding: 0 5px; border-radius: var(--radius-sm); white-space: nowrap; }
.g-today-flag { position: absolute; top: -18px; left: 2px; font: var(--text-micro); font-weight: 700; color: var(--accent); white-space: nowrap; }

.g-resize-handle { position: absolute; top: 0; width: 7px; margin-left: -3px; cursor: col-resize; z-index: 8; background: transparent; }
.g-resize-handle:hover, .g-resize-handle.resizing { background: var(--accent-soft); }

.g-label { position: absolute; z-index: 5; background: var(--white); display: flex; align-items: center; gap: 6px; height: 20px; border-bottom: 1px solid var(--gray-150); border-right: 2px solid var(--gray-300); font: var(--text-small); white-space: nowrap; overflow: hidden; cursor: pointer; box-sizing: border-box; box-shadow: 2px 0 5px -3px rgba(28,25,23,0.1); }
.g-label.stripe { background: var(--gray-100); }
.g-label:hover { background: var(--accent-soft); }
.g-label.selected { background: var(--accent-soft); }
.g-label-wbs { font-weight: 700; background: var(--gray-150); }
.g-label-wbs.stripe { background: var(--gray-150); }
.g-label-wbs:hover { background: var(--accent-soft); }
.g-toggle { color: var(--gray-500); flex-shrink: 0; }
.g-wbs-name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; color: var(--ink); }
.g-wbs-count { padding-right: 4px; font: var(--text-micro); color: var(--gray-500); flex-shrink: 0; }
.g-act-code { font-family: var(--font-mono); font-size: 12px; color: var(--gray-500); flex-shrink: 0; }
.annotation-flag { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; background: var(--gray-500); }
.annotation-flag.sev-query { background: var(--active); }
.annotation-flag.sev-risk { background: var(--near); }
.annotation-flag.sev-logic { background: var(--crit); }
.annotation-flag.sev-resolved { background: var(--ok); }
.g-act-name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; color: var(--ink-soft); }
.g-col-dur, .g-col-date { flex-shrink: 0; text-align: right; font-family: var(--font-mono); font-size: 11px; color: var(--gray-500); }
.g-col-dur { width: 30px; }
.g-col-date { width: 42px; }
.g-col-date:last-child { margin-right: 8px; }

.g-timeline-row { position: relative; height: 20px; border-bottom: 1px solid var(--gray-150); z-index: 2; }
.g-timeline-row.stripe { background: var(--gray-100); }

.g-bar-ghost { position: absolute; top: 15px; height: 4px; border-radius: 2px; background: transparent; border: 1.5px solid var(--gray-500); box-sizing: border-box; pointer-events: auto; }
.g-milestone-ghost { position: absolute; top: 12px; width: 7px; height: 7px; transform: translateX(-4px) rotate(45deg); border: 1.5px solid var(--gray-500); background: transparent; box-sizing: border-box; }
.lg-ghost { background: transparent !important; border-color: var(--gray-500) !important; height: 5px !important; }
.g-bar { position: absolute; top: 5px; height: 10px; border-radius: var(--radius-sm); overflow: hidden; background: var(--accent-soft); border: 1.5px solid var(--accent); box-sizing: border-box; box-shadow: 0 1px 2px rgba(28,25,23,0.15); }
.g-bar.critical { background: var(--crit-tint); border-color: var(--crit); }
.g-bar.near { background: var(--near-tint); border-color: var(--near); }
.g-bar.other { background: var(--accent-soft); border-color: var(--accent); }
.g-bar.negative { background: repeating-linear-gradient(135deg, rgba(255,255,255,0.45) 0 2px, transparent 2px 5px), var(--crit); border-color: var(--crit-deep); }
.g-bar.negative .g-bar-progress { background: rgba(28,25,23,0.45); }
.g-bar.selected { box-shadow: 0 0 0 2px var(--ink); }
.g-bar-progress { height: 100%; background: rgba(28,25,23,0.28); }

.g-bar-wbs { position: absolute; top: 7px; height: 6px; border-radius: 3px; background: var(--gray-700); }
.g-bar-wbs::before, .g-bar-wbs::after { content: ''; position: absolute; top: 100%; width: 0; height: 0; border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 4px solid var(--gray-700); }
.g-bar-wbs::before { left: -1px; }
.g-bar-wbs::after { right: -1px; }

.g-milestone { position: absolute; top: 5px; width: 10px; height: 10px; margin-left: -5px; background: var(--milestone); transform: rotate(45deg); border-radius: 2px; box-shadow: 0 1px 2px rgba(28,25,23,0.2); }
.g-milestone.critical { background: var(--crit); }
.g-milestone.near { background: var(--near); }
.g-milestone.negative { background: var(--crit); box-shadow: 0 0 0 2px var(--white), 0 0 0 3.5px var(--crit); }


.detail-actions { margin-top: 10px; }
.btn-isolate { color: var(--accent); border-color: var(--accent); font-weight: 600; }
.btn-isolate:hover { background: var(--accent-soft); }
.trace-hint { display: block; font-size: 13px; color: var(--accent); font-weight: 600; background: var(--accent-soft); border-radius: var(--radius-sm); padding: 6px 9px; }

/* Duration/float lead the grid — the two numbers a reviewer needs first, sized to read
   at a glance instead of buried in an inline sentence. */


@media print {
  @page { size: landscape; margin: 10mm; }
  .gantt-strip, .gantt-controls, .filter-bar { display: none; }
  .gantt-wrap, .gantt-wrap.is-fullscreen { border: none; box-shadow: none; height: auto; display: block; }
  .gantt-scroll { height: auto !important; max-height: none !important; overflow: visible; cursor: default; }
  .g-corner, .g-timeline-header, .g-label { position: static; }
  .g-resize-handle { display: none; }
  * { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
}
</style>
