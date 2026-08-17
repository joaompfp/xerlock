<template>
  <div class="gantt-wrap" :class="{ 'is-fullscreen': isFullscreen, 'extra-room': extraRoom }" ref="wrapEl">
    <div class="gantt-toolbar">
      <div class="toolbar-title">
        <h2>Gantt Chart</h2>
        <span class="toolbar-sub">{{ data.project.total_activities }} activities · click a WBS row to expand · Ctrl+scroll or drag timeline to zoom/pan</span>
      </div>
      <div class="toolbar-actions">
        <div class="basis-group">
          <span class="basis-label">Critical basis</span>
          <button :class="{ active: criticalBasis === 'tf0' }" @click="criticalBasis = 'tf0'">TF = 0</button>
          <button :class="{ active: criticalBasis === 'longest' }" @click="criticalBasis = 'longest'">Longest Path</button>
        </div>
        <label class="filter-toggle"><input type="checkbox" v-model="showLinks" /> Links</label>
        <label class="filter-toggle"><input type="checkbox" v-model="showProgressLine" /> Progress line</label>
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
        <button class="btn-tiny" @click="expandAll">Expand all</button>
        <button class="btn-tiny" @click="collapseAll">Collapse all</button>
        <button class="btn-tiny" :disabled="todayX === null" @click="scrollToToday">Today</button>
        <button class="btn-tiny btn-fullscreen" @click="toggleFullscreen">{{ isFullscreen ? 'Exit fullscreen' : 'Fullscreen' }}</button>
        <button class="btn-tiny" @click="printGantt">Print</button>
      </div>
    </div>

    <div class="legend">
      <template v-if="criticalBasis === 'tf0'">
        <span class="legend-item"><i class="dot dot-critical"></i>Critical (TF=0)</span>
        <span class="legend-item"><i class="dot dot-near"></i>Near-critical</span>
        <span class="legend-item"><i class="dot dot-other"></i>Normal</span>
      </template>
      <template v-else>
        <span class="legend-item"><i class="dot dot-critical"></i>On longest path</span>
        <span class="legend-item"><i class="dot dot-other"></i>Normal</span>
      </template>
      <span class="legend-item"><i class="diamond"></i>Milestone</span>
      <span class="legend-item"><i class="bar-wbs"></i>WBS rollup</span>
      <span class="legend-item" v-if="showProgressLine"><i class="progress-swatch"></i>Progress line</span>
    </div>

    <!-- Filter bar: narrows which rows are shown (not just dimmed), the way P6's activity filter works.
         The same search box doubles as "find" — clicking a filtered result scrolls/centers on it. -->
    <div class="filter-bar">
      <input type="text" v-model="filterText" class="filter-input" placeholder="Search activity code or name…" />
      <select v-model="filterStatus" class="filter-select">
        <option value="">All statuses</option>
        <option value="TK_NotStart">Not started</option>
        <option value="TK_Active">Active</option>
        <option value="TK_Complete">Complete</option>
      </select>
      <label class="filter-check"><input type="checkbox" v-model="filterCriticalOnly" /> Critical only</label>
      <span class="filter-count">{{ matchCount }} of {{ data.activities.length }} activities</span>
      <button class="btn-tiny-light" v-if="isFilterActive" @click="clearFilters">Clear filters</button>
    </div>

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
        <div class="g-cell g-corner" :style="{ top: scrollTopPx + 'px', left: scrollLeftPx + 'px', width: labelColWidth + 'px' }"></div>
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
              <path d="M0 0L8 4L0 8z" fill="#e74c3c" />
            </marker>
          </defs>
          <path
            v-for="l in links"
            :key="l.id"
            :d="l.d"
            class="g-link"
            marker-end="url(#gantt-arrow)"
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
            :style="{ top: (HEADER_HEIGHT + row.index * ROW_HEIGHT) + 'px', left: scrollLeftPx + 'px', width: labelColWidth + 'px', paddingLeft: (10 + row.level * 16) + 'px' }"
            @click="row.type === 'wbs' ? toggleWbs(row.wbsId) : selectActivity(row.activity)"
          >
            <template v-if="row.type === 'wbs'">
              <span class="g-toggle">{{ expandedWbs.has(row.wbsId) ? '▼' : '▶' }}</span>
              <span class="g-wbs-name">{{ row.name }}</span>
              <span class="g-wbs-count">{{ row.count }}</span>
            </template>
            <template v-else>
              <span class="g-act-code">{{ row.activity.task_code }}</span>
              <span class="g-act-name">{{ row.activity.task_name }}</span>
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
                class="g-milestone"
                :class="row.cls"
                :style="{ left: row.x + 'px' }"
                :title="milestoneTitle(row.activity)"
              ></div>
            </template>
            <div
              v-else
              class="g-bar"
              :class="[row.cls, { selected: row.activity.task_id === selectedTaskId }]"
              :style="{ left: row.x + 'px', width: row.w + 'px' }"
              :title="barTitle(row.activity)"
            >
              <div class="g-bar-progress" :style="{ width: row.activity.pct_complete + '%' }"></div>
            </div>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script>
import { formatDate, formatHours, isMilestone, formatFloat } from '../utils/format'

const LABEL_COL_WIDTH_DEFAULT = 340
const LABEL_COL_MIN = 200
const LABEL_COL_MAX = 600
const HEADER_HEIGHT = 52
const ROW_HEIGHT = 32
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
  props: {
    data: { type: Object, required: true },
    extraRoom: { type: Boolean, default: false },
  },
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
      labelColWidth: saved.labelColWidth || LABEL_COL_WIDTH_DEFAULT,
      criticalBasis: saved.criticalBasis || 'tf0',
      expandedWbs,
      showLinks: saved.showLinks ?? true,
      showProgressLine: saved.showProgressLine ?? false,
      selectedTaskId: null,
      isFullscreen: false,
      filterText: '',
      filterStatus: '',
      filterCriticalOnly: false,
      scrollLeftPx: 0,
      scrollTopPx: 0,
      panning: false,
      resizing: false,
    }
  },
  mounted() {
    document.addEventListener('fullscreenchange', this.onFullscreenChange)
  },
  beforeUnmount() {
    document.removeEventListener('fullscreenchange', this.onFullscreenChange)
    window.removeEventListener('mousemove', this.onPanMove)
    window.removeEventListener('mouseup', this.onPanEnd)
    window.removeEventListener('mousemove', this.onResizeMove)
    window.removeEventListener('mouseup', this.onResizeEnd)
  },
  watch: {
    zoom() { this.persistView() },
    criticalBasis() { this.persistView() },
    showLinks() { this.persistView() },
    showProgressLine() { this.persistView() },
    dayWidthOverride() { this.persistView() },
  },
  computed: {
    activitiesByWbs() {
      const map = new Map()
      for (const a of this.data.activities) {
        if (!map.has(a.wbs_id)) map.set(a.wbs_id, [])
        map.get(a.wbs_id).push(a)
      }
      for (const list of map.values()) {
        list.sort((a, b) => {
          const da = a.early_start || ''
          const db = b.early_start || ''
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
    isFilterActive() {
      return !!(this.filterText.trim() || this.filterStatus || this.filterCriticalOnly)
    },
    matchedTaskIds() {
      if (!this.isFilterActive) return null
      const q = this.filterText.trim().toLowerCase()
      const ids = new Set()
      for (const a of this.data.activities) {
        if (q && !(a.task_code.toLowerCase().includes(q) || a.task_name.toLowerCase().includes(q))) continue
        if (this.filterStatus && a.status !== this.filterStatus) continue
        if (this.filterCriticalOnly && !this.isBasisCritical(a)) continue
        ids.add(a.task_id)
      }
      return ids
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
          const expanded = filtering || this.expandedWbs.has(node.wbs_id)
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
        if (filtering || this.expandedWbs.has('__unassigned')) {
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
      if (!this.showLinks) return []
      const out = []
      const rowByIndex = this.rows
      for (const row of rowByIndex) {
        if (row.type !== 'activity' || !this.isBasisCritical(row.activity)) continue
        for (const p of row.activity.predecessors || []) {
          const predIdx = this.rowIndexByTaskId.get(p.task_id)
          if (predIdx === undefined) continue
          const predRow = rowByIndex[predIdx]
          if (!this.isBasisCritical(predRow.activity)) continue
          const predX = this.dateToX(predRow.activity.early_end)
          const predY = predIdx * ROW_HEIGHT + ROW_HEIGHT / 2
          const succX = row.x
          const succY = row.index * ROW_HEIGHT + ROW_HEIGHT / 2
          if (predX === null || succX === null) continue
          const midX = predX + 8
          out.push({
            id: `${p.task_id}-${row.activity.task_id}-${p.type}-${out.length}`,
            d: `M${predX},${predY} L${midX},${predY} L${midX},${succY} L${succX},${succY}`,
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
          if (a.early_start) {
            const d = new Date(a.early_start)
            if (!start || d < start) start = d
          }
          if (a.early_end) {
            const d = new Date(a.early_end)
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
      if (this.isBasisCritical(a)) return 'critical'
      if (this.criticalBasis === 'tf0' && a.total_float_hrs > 0 && a.total_float_hrs <= 80) return 'near'
      return 'other'
    },
    buildActivityRow(a, level) {
      const milestone = isMilestone(a)
      const x = this.dateToX(a.early_start)
      const xEnd = this.dateToX(a.early_end)
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
    toggleWbs(wbsId) {
      if (this.expandedWbs.has(wbsId)) this.expandedWbs.delete(wbsId)
      else this.expandedWbs.add(wbsId)
      // Force reactivity: Set mutations aren't tracked by Vue 3 unless reassigned.
      this.expandedWbs = new Set(this.expandedWbs)
    },
    expandAll() {
      const all = new Set()
      const walk = (nodes) => {
        for (const n of nodes) { all.add(n.wbs_id); walk(n.children || []) }
      }
      walk(this.data.wbs_tree || [])
      all.add('__unassigned')
      this.expandedWbs = all
    },
    collapseAll() {
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
    clearFilters() {
      this.filterText = ''
      this.filterStatus = ''
      this.filterCriticalOnly = false
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
      return `${a.task_code} — ${a.task_name}\n${formatDate(a.early_start)} → ${formatDate(a.early_end)}\n` +
        `Duration: ${formatHours(a.duration_hrs)} · Float: ${formatFloat(a.total_float_hrs)} · ${a.pct_complete}% complete`
    },
    milestoneTitle(a) {
      return `${a.task_code} — ${a.task_name}\n${formatDate(a.early_start)}\nFloat: ${formatFloat(a.total_float_hrs)}`
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
.gantt-wrap { border: 1px solid #e8e8e8; border-radius: 10px; overflow: hidden; background: #fff; margin-bottom: 24px; box-shadow: 0 1px 3px rgba(26,26,46,0.06); }
.gantt-wrap.is-fullscreen { border-radius: 0; display: flex; flex-direction: column; height: 100vh; }
.gantt-wrap.is-fullscreen .gantt-scroll { flex: 1; max-height: none; }

.gantt-toolbar { display: flex; justify-content: space-between; align-items: center; padding: 14px 18px; border-bottom: 1px solid #eee; background: #1a1a2e; flex-wrap: wrap; gap: 12px; }
.toolbar-title h2 { font-size: 17px; font-weight: 700; color: #fff; margin: 0; }
.toolbar-sub { font-size: 12px; color: #a8adc0; }
.toolbar-actions { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.filter-toggle { font-size: 12px; color: #d5d8e8; display: flex; align-items: center; gap: 4px; cursor: pointer; }

.basis-group { display: flex; align-items: center; gap: 6px; border: 1px solid #3a3f5c; border-radius: 6px; padding: 2px; }
.basis-label { font-size: 11px; color: #8890ac; padding-left: 6px; text-transform: uppercase; letter-spacing: 0.3px; }
.basis-group button { padding: 4px 10px; border: none; border-radius: 4px; background: none; cursor: pointer; font-size: 12px; color: #c5c9dc; }
.basis-group button.active { background: #e74c3c; color: white; font-weight: 600; }
.basis-group button:hover:not(.active) { background: #2a2f47; }

.zoom-group { display: flex; border: 1px solid #3a3f5c; border-radius: 6px; overflow: hidden; }
.zoom-group button { padding: 4px 10px; border: none; border-right: 1px solid #3a3f5c; background: none; cursor: pointer; font-size: 12px; color: #c5c9dc; }
.zoom-group button:last-child { border-right: none; }
.zoom-group button.active { background: #2f5496; color: white; }
.zoom-group button:hover:not(.active) { background: #2a2f47; }
.zoom-adjust { display: flex; border: 1px solid #3a3f5c; border-radius: 6px; overflow: hidden; }
.zbtn { padding: 4px 10px; border: none; border-right: 1px solid #3a3f5c; background: none; cursor: pointer; font-size: 13px; color: #c5c9dc; font-weight: 700; }
.zbtn:last-child { border-right: none; }
.zbtn:hover { background: #2a2f47; }
.btn-tiny { padding: 4px 10px; border: 1px solid #3a3f5c; border-radius: 5px; background: none; cursor: pointer; font-size: 12px; color: #c5c9dc; }
.btn-tiny:hover:not(:disabled) { background: #2a2f47; }
.btn-tiny:disabled { opacity: 0.35; cursor: default; }
.btn-fullscreen { border-color: #2f5496; color: #a9c2e8; }
.btn-fullscreen:hover { background: #2f5496; color: white; }

.legend { display: flex; gap: 16px; flex-wrap: wrap; align-items: center; padding: 8px 18px; background: #fafbfc; border-bottom: 1px solid #eee; }
.legend-item { display: flex; align-items: center; gap: 5px; font-size: 12px; color: #666; }
.dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
.dot-critical { background: #e74c3c; }
.dot-near { background: #d4a017; }
.dot-other { background: #2f5496; }
.diamond { width: 8px; height: 8px; background: #5a5f68; display: inline-block; transform: rotate(45deg); }
.bar-wbs { width: 16px; height: 7px; border-radius: 3px; background: #5a6472; display: inline-block; }
.progress-swatch { width: 14px; height: 2px; background: #8e44ad; display: inline-block; }

.filter-bar { display: flex; align-items: center; gap: 10px; padding: 10px 18px; background: #fff; border-bottom: 1px solid #eee; flex-wrap: wrap; }
.filter-input { padding: 6px 12px; border: 1px solid #ccc; border-radius: 6px; font-size: 13px; width: 240px; }
.filter-select { padding: 6px 8px; border: 1px solid #ccc; border-radius: 6px; font-size: 13px; background: white; }
.filter-check { font-size: 12px; color: #555; display: flex; align-items: center; gap: 4px; cursor: pointer; }
.filter-count { font-size: 12px; color: #888; margin-left: auto; }
.btn-tiny-light { padding: 4px 10px; border: 1px solid #ccc; border-radius: 5px; background: white; cursor: pointer; font-size: 12px; color: #555; }
.btn-tiny-light:hover { background: #f5f5f5; }

.gantt-scroll { overflow: auto; max-height: min(75vh, 900px); position: relative; cursor: grab; }
.gantt-scroll.panning { cursor: grabbing; }
.gantt-wrap.extra-room .gantt-scroll { max-height: min(92vh, 1400px); }
.gantt-grid { display: grid; grid-template-rows: 52px; grid-auto-rows: 32px; position: relative; }

.g-cell { min-width: 0; }
.g-corner { position: absolute; z-index: 7; background: #fafbfc; border-bottom: 1px solid #ddd; border-right: 1px solid #eee; height: 52px; }
.g-timeline-header { position: absolute; z-index: 6; background: #fafbfc; border-bottom: 1px solid #ddd; height: 52px; }
.g-header-year-row { position: relative; height: 22px; border-bottom: 1px solid #eee; }
.g-header-detail-row { position: relative; height: 30px; }
.g-year-tick { position: absolute; top: 0; height: 100%; padding-left: 6px; padding-top: 3px; font-size: 12px; font-weight: 700; color: #1a1a2e; border-left: 1px solid #ccc; white-space: nowrap; }
.g-detail-tick { position: absolute; top: 0; padding-top: 8px; padding-left: 4px; font-size: 11px; color: #888; white-space: nowrap; border-left: 1px solid #eee; height: 100%; box-sizing: border-box; }
.g-detail-tick.weekend { color: #c0392b; font-weight: 600; }

.g-overlay { position: absolute; pointer-events: none; }
.g-overlay-bg { z-index: 1; }
.g-overlay-fg { z-index: 3; }
.g-weekend { fill: #f5f6f8; }
.g-gridline { stroke: #f0f1f3; stroke-width: 1; }
.g-gridline-month { stroke: #dfe1e6; stroke-width: 1; }
.g-link { fill: none; stroke: #e74c3c; stroke-width: 1.5; opacity: 0.75; }
.g-progress-line { fill: none; stroke: #8e44ad; stroke-width: 2; stroke-dasharray: 4 3; opacity: 0.9; }
.g-progress-dot { fill: #8e44ad; }

.g-today-line { position: absolute; width: 2px; background: #2f5496; z-index: 4; pointer-events: none; }
.g-today-flag { position: absolute; top: -18px; left: 2px; font-size: 10px; font-weight: 700; color: #2f5496; white-space: nowrap; }

.g-resize-handle { position: absolute; top: 0; width: 7px; margin-left: -3px; cursor: col-resize; z-index: 8; background: transparent; }
.g-resize-handle:hover, .g-resize-handle.resizing { background: rgba(47,84,150,0.3); }

.g-label { position: absolute; z-index: 5; background: #fff; display: flex; align-items: center; gap: 6px; height: 32px; border-bottom: 1px solid #f2f2f2; font-size: 12px; white-space: nowrap; overflow: hidden; cursor: pointer; box-sizing: border-box; }
.g-label.stripe { background: #fafbfc; }
.g-label:hover { background: #eef1f7; }
.g-label.selected { background: #e4eaf6; }
.g-label-wbs { font-weight: 700; background: #f0f2f6; }
.g-label-wbs.stripe { background: #eceef3; }
.g-label-wbs:hover { background: #e4e7ee; }
.g-toggle { width: 12px; text-align: center; font-size: 9px; color: #888; flex-shrink: 0; }
.g-wbs-name { overflow: hidden; text-overflow: ellipsis; color: #1a1a2e; }
.g-wbs-count { margin-left: auto; padding-right: 8px; font-size: 10px; color: #aaa; flex-shrink: 0; }
.g-act-code { font-family: 'SF Mono', 'Fira Code', monospace; font-size: 11px; color: #888; flex-shrink: 0; }
.g-act-name { overflow: hidden; text-overflow: ellipsis; color: #333; }

.g-timeline-row { position: relative; height: 32px; border-bottom: 1px solid #f2f2f2; z-index: 2; }
.g-timeline-row.stripe { background: #fafbfc; }

.g-bar { position: absolute; top: 7px; height: 18px; border-radius: 4px; overflow: hidden; background: #aebbd6; border: 1.5px solid #2f5496; box-sizing: border-box; box-shadow: 0 1px 2px rgba(26,26,46,0.15); }
.g-bar.critical { background: #f0a099; border-color: #e74c3c; }
.g-bar.near { background: #f2d693; border-color: #d4a017; }
.g-bar.other { background: #aebbd6; border-color: #2f5496; }
.g-bar.selected { box-shadow: 0 0 0 2px #1a1a2e; }
.g-bar-progress { height: 100%; background: rgba(0,0,0,0.28); }

.g-bar-wbs { position: absolute; top: 12px; height: 9px; border-radius: 3px; background: #5a6472; }
.g-bar-wbs::before, .g-bar-wbs::after { content: ''; position: absolute; top: 100%; width: 0; height: 0; border-left: 5px solid transparent; border-right: 5px solid transparent; border-top: 6px solid #5a6472; }
.g-bar-wbs::before { left: -1px; }
.g-bar-wbs::after { right: -1px; }

.g-milestone { position: absolute; top: 6px; width: 16px; height: 16px; margin-left: -8px; background: #5a5f68; transform: rotate(45deg); border-radius: 2px; box-shadow: 0 1px 2px rgba(26,26,46,0.2); }
.g-milestone.critical { background: #e74c3c; }
.g-milestone.near { background: #d4a017; }

@media print {
  @page { size: landscape; margin: 10mm; }
  .gantt-toolbar, .filter-bar { display: none; }
  .gantt-wrap, .gantt-wrap.is-fullscreen { border: none; box-shadow: none; height: auto; display: block; }
  .gantt-scroll { max-height: none !important; overflow: visible; cursor: default; }
  .g-corner, .g-timeline-header, .g-label { position: static; }
  .g-resize-handle { display: none; }
  * { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
}
</style>
