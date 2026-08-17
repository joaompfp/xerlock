<template>
  <div class="gantt-wrap">
    <div class="gantt-toolbar">
      <div class="legend">
        <span class="legend-item"><i class="dot dot-critical"></i>Critical</span>
        <span class="legend-item"><i class="dot dot-near"></i>Near-critical</span>
        <span class="legend-item"><i class="dot dot-other"></i>Normal</span>
        <span class="legend-item"><i class="diamond"></i>Milestone</span>
        <span class="legend-item"><i class="bar-wbs"></i>WBS rollup</span>
      </div>
      <div class="toolbar-actions">
        <label class="filter-toggle"><input type="checkbox" v-model="showLinks" /> Critical links</label>
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
      </div>
    </div>

    <div class="gantt-scroll" ref="scrollEl">
      <div class="gantt-grid" :style="{ gridTemplateColumns: LABEL_COL_WIDTH + 'px ' + totalWidth + 'px' }">
        <!-- Header -->
        <div class="g-cell g-corner"></div>
        <div class="g-cell g-timeline-header" :style="{ width: totalWidth + 'px' }">
          <div
            v-for="m in monthTicks"
            :key="m.x"
            class="g-month-tick"
            :style="{ left: m.x + 'px' }"
          >
            <span class="g-month-label">{{ m.label }}</span>
          </div>
        </div>

        <!-- Background layer: gridlines + critical links -->
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
          <line
            v-for="m in monthTicks"
            :key="'gl' + m.x"
            :x1="m.x" :x2="m.x" y1="0" :y2="bodyHeight"
            class="g-gridline"
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
        ></div>

        <!-- Rows -->
        <template v-for="row in rows" :key="row.key">
          <div
            class="g-cell g-label"
            :class="{ 'g-label-wbs': row.type === 'wbs', selected: row.type === 'activity' && row.activity.task_id === selectedTaskId }"
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
          <div class="g-cell g-timeline-row" :style="{ width: totalWidth + 'px' }">
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
import { formatDate, formatHours, isMilestone } from '../utils/format'

const LABEL_COL_WIDTH = 340
const HEADER_HEIGHT = 34
const ROW_HEIGHT = 28
const ZOOM_DAY_WIDTH = { day: 32, week: 9, month: 3, quarter: 1.1 }

export default {
  name: 'GanttChart',
  props: {
    data: { type: Object, required: true },
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
      expandedWbs,
      showLinks: true,
      selectedTaskId: null,
    }
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
    monthTicks() {
      const ticks = []
      let cur = new Date(this.rangeStart.getFullYear(), this.rangeStart.getMonth(), 1)
      let first = true
      while (cur <= this.rangeEnd) {
        const x = Math.round(((cur - this.rangeStart) / 86400000) * this.dayWidth)
        const label = cur.toLocaleDateString('en-GB', {
          month: 'short',
          year: first || cur.getMonth() === 0 ? 'numeric' : undefined,
        })
        ticks.push({ x, label })
        first = false
        cur = new Date(cur.getFullYear(), cur.getMonth() + 1, 1)
      }
      return ticks
    },
    todayX() {
      const today = new Date()
      if (today < this.rangeStart || today > this.rangeEnd) return null
      return Math.round(((today - this.rangeStart) / 86400000) * this.dayWidth)
    },
    allWbsIds() {
      const ids = new Set()
      const walk = (nodes) => {
        for (const n of nodes) { ids.add(n.wbs_id); walk(n.children || []) }
      }
      walk(this.data.wbs_tree || [])
      return ids
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

      // True orphans only: activities whose wbs_id doesn't exist anywhere in the
      // tree. Activities merely hidden behind a collapsed ancestor are not orphans.
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
        if (row.type !== 'activity' || !row.activity.is_critical) continue
        for (const p of row.activity.predecessors || []) {
          const predIdx = this.rowIndexByTaskId.get(p.task_id)
          if (predIdx === undefined) continue
          const predRow = rowByIndex[predIdx]
          if (!predRow.activity.is_critical) continue
          const predX = this.dateToX(predRow.activity.early_end)
          const predY = predIdx * ROW_HEIGHT + ROW_HEIGHT / 2
          const succX = row.x
          const succY = row.index * ROW_HEIGHT + ROW_HEIGHT / 2
          if (predX === null || succX === null) continue
          const midX = predX + 8
          out.push({
            id: p.task_id + '-' + row.activity.task_id,
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
    classifyActivity(a) {
      if (a.is_critical) return 'critical'
      if (a.total_float_hrs > 0 && a.total_float_hrs <= 80) return 'near'
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
    zoomLabel(z) {
      return z.charAt(0).toUpperCase() + z.slice(1)
    },
    barTitle(a) {
      return `${a.task_code} — ${a.task_name}\n${formatDate(a.early_start)} → ${formatDate(a.early_end)}\n` +
        `Duration: ${formatHours(a.duration_hrs)} · Float: ${a.total_float_hrs}h · ${a.pct_complete}% complete`
    },
    milestoneTitle(a) {
      return `${a.task_code} — ${a.task_name}\n${formatDate(a.early_start)}\nFloat: ${a.total_float_hrs}h`
    },
  },
}
</script>

<style scoped>
.gantt-wrap { border: 1px solid #e8e8e8; border-radius: 10px; overflow: hidden; background: #fff; margin-bottom: 24px; }
.gantt-toolbar { display: flex; justify-content: space-between; align-items: center; padding: 10px 14px; border-bottom: 1px solid #eee; background: #fafbfc; flex-wrap: wrap; gap: 8px; }
.legend { display: flex; gap: 14px; flex-wrap: wrap; align-items: center; }
.legend-item { display: flex; align-items: center; gap: 5px; font-size: 12px; color: #666; }
.dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
.dot-critical { background: #e74c3c; }
.dot-near { background: #d4a017; }
.dot-other { background: #2f5496; }
.diamond { width: 8px; height: 8px; background: #5a5f68; display: inline-block; transform: rotate(45deg); }
.bar-wbs { width: 14px; height: 6px; border-radius: 3px; background: #7d8592; display: inline-block; }
.toolbar-actions { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.filter-toggle { font-size: 12px; color: #555; display: flex; align-items: center; gap: 4px; cursor: pointer; }
.zoom-group { display: flex; border: 1px solid #ccc; border-radius: 6px; overflow: hidden; }
.zoom-group button { padding: 4px 10px; border: none; border-right: 1px solid #ccc; background: white; cursor: pointer; font-size: 12px; color: #555; }
.zoom-group button:last-child { border-right: none; }
.zoom-group button.active { background: #2f5496; color: white; }
.zoom-group button:hover:not(.active) { background: #f0f2f5; }
.btn-tiny { padding: 3px 10px; border: 1px solid #ccc; border-radius: 5px; background: white; cursor: pointer; font-size: 12px; color: #555; }
.btn-tiny:hover:not(:disabled) { background: #f0f2f5; }
.btn-tiny:disabled { opacity: 0.4; cursor: default; }

.gantt-scroll { overflow: auto; max-height: 640px; position: relative; }
.gantt-grid { display: grid; position: relative; }

.g-cell { min-width: 0; }
.g-corner { position: sticky; top: 0; left: 0; z-index: 6; background: #fafbfc; border-bottom: 1px solid #ddd; border-right: 1px solid #eee; height: 34px; }
.g-timeline-header { position: sticky; top: 0; z-index: 5; background: #fafbfc; border-bottom: 1px solid #ddd; height: 34px; }
.g-month-tick { position: absolute; top: 0; bottom: 0; border-left: 1px solid #ddd; }
.g-month-label { position: absolute; top: 9px; left: 4px; font-size: 11px; color: #777; white-space: nowrap; font-weight: 600; }

.g-overlay { position: absolute; pointer-events: none; z-index: 1; }
.g-gridline { stroke: #f0f1f3; stroke-width: 1; }
.g-link { fill: none; stroke: #e74c3c; stroke-width: 1.5; opacity: 0.6; }

.g-today-line { position: absolute; width: 2px; background: #2f5496; z-index: 3; pointer-events: none; opacity: 0.55; }

.g-label { position: sticky; left: 0; z-index: 4; background: #fff; display: flex; align-items: center; gap: 6px; height: 28px; border-bottom: 1px solid #f2f2f2; font-size: 12px; white-space: nowrap; overflow: hidden; cursor: pointer; }
.g-label:hover { background: #f5f6f8; }
.g-label.selected { background: #eef1f7; }
.g-label-wbs { font-weight: 600; background: #fafbfc; }
.g-label-wbs:hover { background: #f0f2f5; }
.g-toggle { width: 12px; text-align: center; font-size: 9px; color: #888; flex-shrink: 0; }
.g-wbs-name { overflow: hidden; text-overflow: ellipsis; color: #1a1a2e; }
.g-wbs-count { margin-left: auto; padding-right: 8px; font-size: 10px; color: #aaa; flex-shrink: 0; }
.g-act-code { font-family: 'SF Mono', 'Fira Code', monospace; font-size: 11px; color: #888; flex-shrink: 0; }
.g-act-name { overflow: hidden; text-overflow: ellipsis; color: #333; }

.g-timeline-row { position: relative; height: 28px; border-bottom: 1px solid #f2f2f2; z-index: 2; }

.g-bar { position: absolute; top: 6px; height: 16px; border-radius: 3px; overflow: hidden; background: #eef1f7; border: 1.5px solid #b9c0cc; box-sizing: border-box; }
.g-bar.critical { background: #fdeeed; border-color: #e74c3c; }
.g-bar.near { background: #fdf6e6; border-color: #d4a017; }
.g-bar.other { background: #eef1f7; border-color: #7d93bd; }
.g-bar.selected { box-shadow: 0 0 0 2px #2f5496; }
.g-bar-progress { height: 100%; background: rgba(0,0,0,0.18); }

.g-bar-wbs { position: absolute; top: 10px; height: 8px; border-radius: 4px; background: #7d8592; }

.g-milestone { position: absolute; top: 6px; width: 14px; height: 14px; margin-left: -7px; background: #5a5f68; transform: rotate(45deg); border-radius: 2px; }
.g-milestone.critical { background: #e74c3c; }
.g-milestone.near { background: #d4a017; }
</style>
