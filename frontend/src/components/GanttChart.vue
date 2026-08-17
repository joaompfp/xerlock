<template>
  <div class="gantt-wrap" :class="{ 'is-fullscreen': isFullscreen, 'extra-room': extraRoom }" ref="wrapEl">
    <div class="gantt-toolbar">
      <div class="toolbar-title">
        <h2>Gantt Chart</h2>
        <span class="toolbar-sub">{{ data.project.total_activities }} activities · click a WBS row to expand</span>
      </div>
      <div class="toolbar-actions">
        <div class="basis-group">
          <span class="basis-label">Critical basis</span>
          <button :class="{ active: criticalBasis === 'tf0' }" @click="criticalBasis = 'tf0'">TF = 0</button>
          <button :class="{ active: criticalBasis === 'longest' }" @click="criticalBasis = 'longest'">Longest Path</button>
        </div>
        <label class="filter-toggle"><input type="checkbox" v-model="showLinks" /> Links</label>
        <div class="zoom-group">
          <button
            v-for="z in zoomLevels"
            :key="z"
            :class="{ active: zoom === z }"
            @click="zoom = z"
          >{{ zoomLabel(z) }}</button>
        </div>
        <button class="btn-tiny" @click="expandAll">Expand all</button>
        <button class="btn-tiny" @click="collapseAll">Collapse all</button>
        <button class="btn-tiny" :disabled="todayX === null" @click="scrollToToday">Today</button>
        <button class="btn-tiny btn-fullscreen" @click="toggleFullscreen">{{ isFullscreen ? 'Exit fullscreen' : 'Fullscreen' }}</button>
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
    </div>

    <div class="gantt-scroll" ref="scrollEl">
      <div class="gantt-grid" :style="{ gridTemplateColumns: LABEL_COL_WIDTH + 'px ' + totalWidth + 'px' }">
        <!-- Header (two rows: year, then zoom-dependent detail) -->
        <div class="g-cell g-corner"></div>
        <div class="g-cell g-timeline-header" :style="{ width: totalWidth + 'px' }">
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

        <!-- Background layer: weekend shading + gridlines + links -->
        <svg
          class="g-overlay"
          :style="{ left: LABEL_COL_WIDTH + 'px', top: HEADER_HEIGHT + 'px', width: totalWidth + 'px', height: bodyHeight + 'px' }"
          :width="totalWidth"
          :height="bodyHeight"
        >
          <defs>
            <marker id="gantt-arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M0 0L8 4L0 8z" fill="#e74c3c" />
            </marker>
          </defs>
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
          <path
            v-for="l in links"
            :key="l.id"
            :d="l.d"
            class="g-link"
            marker-end="url(#gantt-arrow)"
          />
        </svg>

        <!-- Today line (above bars) -->
        <div
          v-if="todayX !== null"
          class="g-today-line"
          :style="{ left: (LABEL_COL_WIDTH + todayX) + 'px', top: HEADER_HEIGHT + 'px', height: bodyHeight + 'px' }"
        ><span class="g-today-flag">Today</span></div>

        <!-- Rows -->
        <template v-for="row in rows" :key="row.key">
          <div
            class="g-cell g-label"
            :class="{ 'g-label-wbs': row.type === 'wbs', stripe: row.index % 2 === 1, selected: row.type === 'activity' && row.activity.task_id === selectedTaskId }"
            :style="{ paddingLeft: (10 + row.level * 16) + 'px' }"
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
          <div class="g-cell g-timeline-row" :class="{ stripe: row.index % 2 === 1 }" :style="{ width: totalWidth + 'px' }">
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

const LABEL_COL_WIDTH = 340
const HEADER_HEIGHT = 52
const ROW_HEIGHT = 32
const ZOOM_DAY_WIDTH = { day: 32, week: 9, month: 3, quarter: 1.1 }

export default {
  name: 'GanttChart',
  props: {
    data: { type: Object, required: true },
    extraRoom: { type: Boolean, default: false },
  },
  data() {
    const start = this.data.project.earliest_start ? new Date(this.data.project.earliest_start) : new Date()
    const end = this.data.project.latest_end ? new Date(this.data.project.latest_end) : new Date()
    const days = Math.max(1, (end - start) / 86400000)
    const zoom = days > 300 ? 'month' : days > 100 ? 'week' : 'day'

    const expandedWbs = new Set()
    const markExpanded = (node, level) => {
      if (level < 1) expandedWbs.add(node.wbs_id)
      for (const c of node.children || []) markExpanded(c, level + 1)
    }
    for (const root of this.data.wbs_tree || []) markExpanded(root, 0)

    return {
      LABEL_COL_WIDTH,
      HEADER_HEIGHT,
      zoom,
      zoomLevels: ['day', 'week', 'month', 'quarter'],
      criticalBasis: 'tf0',
      expandedWbs,
      showLinks: true,
      selectedTaskId: null,
      isFullscreen: false,
    }
  },
  mounted() {
    document.addEventListener('fullscreenchange', this.onFullscreenChange)
  },
  beforeUnmount() {
    document.removeEventListener('fullscreenchange', this.onFullscreenChange)
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
      const map = new Map()
      const activitiesByWbs = this.activitiesByWbs
      const visit = (node) => {
        let start = null, finish = null, count = 0
        for (const a of activitiesByWbs.get(node.wbs_id) || []) {
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
      return ZOOM_DAY_WIDTH[this.zoom]
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
    rows() {
      const rows = []
      const walk = (nodes, level) => {
        const sorted = [...nodes].sort((a, b) => a.seq_num - b.seq_num)
        for (const node of sorted) {
          const roll = this.rollups.get(node.wbs_id) || { start: null, finish: null, count: 0 }
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
          if (this.expandedWbs.has(node.wbs_id)) {
            walk(node.children || [], level + 1)
            for (const a of this.activitiesByWbs.get(node.wbs_id) || []) {
              rows.push(this.buildActivityRow(a, level + 1))
            }
          }
        }
      }
      walk(this.data.wbs_tree || [], 0)

      const orphans = this.data.activities.filter(a => !this.allWbsIds.has(a.wbs_id))
      if (orphans.length) {
        rows.push({ type: 'wbs', key: 'w-unassigned', wbsId: '__unassigned', level: 0, name: '(Unassigned)', count: orphans.length })
        if (this.expandedWbs.has('__unassigned')) {
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
  },
  methods: {
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
      this.selectedTaskId = this.selectedTaskId === a.task_id ? null : a.task_id
    },
    scrollToToday() {
      if (this.todayX === null || !this.$refs.scrollEl) return
      const el = this.$refs.scrollEl
      el.scrollTo({ left: Math.max(0, this.todayX - el.clientWidth / 2), behavior: 'smooth' })
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

.gantt-scroll { overflow: auto; max-height: min(75vh, 900px); position: relative; }
.gantt-wrap.extra-room .gantt-scroll { max-height: min(92vh, 1400px); }
.gantt-grid { display: grid; position: relative; }

.g-cell { min-width: 0; }
.g-corner { position: sticky; top: 0; left: 0; z-index: 6; background: #fafbfc; border-bottom: 1px solid #ddd; border-right: 1px solid #eee; height: 52px; }
.g-timeline-header { position: sticky; top: 0; z-index: 5; background: #fafbfc; border-bottom: 1px solid #ddd; height: 52px; }
.g-header-year-row { position: relative; height: 22px; border-bottom: 1px solid #eee; }
.g-header-detail-row { position: relative; height: 30px; }
.g-year-tick { position: absolute; top: 0; height: 100%; padding-left: 6px; padding-top: 3px; font-size: 12px; font-weight: 700; color: #1a1a2e; border-left: 1px solid #ccc; white-space: nowrap; }
.g-detail-tick { position: absolute; top: 0; padding-top: 8px; padding-left: 4px; font-size: 11px; color: #888; white-space: nowrap; border-left: 1px solid #eee; height: 100%; box-sizing: border-box; }
.g-detail-tick.weekend { color: #c0392b; font-weight: 600; }

.g-overlay { position: absolute; pointer-events: none; z-index: 1; }
.g-weekend { fill: #f5f6f8; }
.g-gridline { stroke: #f0f1f3; stroke-width: 1; }
.g-gridline-month { stroke: #dfe1e6; stroke-width: 1; }
.g-link { fill: none; stroke: #e74c3c; stroke-width: 1.5; opacity: 0.6; }

.g-today-line { position: absolute; width: 2px; background: #2f5496; z-index: 3; pointer-events: none; }
.g-today-flag { position: absolute; top: -18px; left: 2px; font-size: 10px; font-weight: 700; color: #2f5496; white-space: nowrap; }

.g-label { position: sticky; left: 0; z-index: 4; background: #fff; display: flex; align-items: center; gap: 6px; height: 32px; border-bottom: 1px solid #f2f2f2; font-size: 12px; white-space: nowrap; overflow: hidden; cursor: pointer; }
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
</style>
