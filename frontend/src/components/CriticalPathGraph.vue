<template>
  <div class="graph-wrap">
    <div class="graph-toolbar">
      <div class="legend">
        <span class="legend-item"><i class="dot dot-critical"></i>Critical (TF=0)</span>
        <span class="legend-item"><i class="dot dot-near"></i>Near-critical (≤10d float)</span>
        <span class="legend-item"><i class="dot dot-other"></i>Expanded</span>
        <span class="legend-item"><i class="dot dot-mile"></i>◆ Milestone</span>
      </div>
      <div class="toolbar-actions">
        <span class="node-count">{{ visibleIds.size }} of {{ activities.length }} activities shown</span>
        <button class="btn-tiny" :disabled="expandedExtra.size === 0" @click="resetGraph">Reset to critical path</button>
        <button class="btn-tiny" @click="zoomBy(1.3)">+</button>
        <button class="btn-tiny" @click="zoomBy(1 / 1.3)">−</button>
        <button class="btn-tiny" @click="resetView">Fit</button>
      </div>
    </div>

    <div
      class="graph-canvas"
      ref="canvas"
      @wheel.prevent="onWheel"
      @mousedown="onPanStart"
      @mousemove="onPanMove"
      @mouseup="onPanEnd"
      @mouseleave="onPanEnd"
      :class="{ dragging: panning }"
    >
      <svg :width="svgWidth" :height="svgHeight">
        <defs>
          <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M0 0L10 5L0 10z" fill="#aab0bb" />
          </marker>
          <marker id="arrow-critical" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M0 0L10 5L0 10z" fill="#e74c3c" />
          </marker>
        </defs>
        <g :transform="`translate(${tx},${ty}) scale(${scale})`">
          <path
            v-for="e in edges"
            :key="e.id"
            :d="e.path"
            class="edge"
            :class="edgeClass(e)"
            :marker-end="edgeIsCritical(e) ? 'url(#arrow-critical)' : 'url(#arrow)'"
          >
            <title>{{ e.type }}{{ e.lagHrs ? ` +${e.lagHrs}h lag` : '' }}</title>
          </path>

          <g
            v-for="n in nodes"
            :key="n.id"
            class="node"
            :class="nodeClass(n)"
            :transform="`translate(${n.x - n.width / 2}, ${n.y - n.height / 2})`"
            @click.stop="selectNode(n)"
          >
            <rect :width="n.width" :height="n.height" rx="8" class="node-rect" />
            <text v-if="n.milestone" class="node-mile-icon" x="10" y="18">◆</text>
            <text class="node-code" :x="n.milestone ? 22 : 10" y="18">{{ n.code }}</text>
            <text class="node-name" x="10" y="36">{{ truncate(n.name, 30) }}</text>
            <text class="node-meta" x="10" y="54">
              {{ n.durationLabel }}<template v-if="n.dateLabel"> · {{ n.dateLabel }}</template>
              <template v-if="n.floatHrs > 0"> · float {{ Math.round(n.floatHrs / 8) }}d</template>
            </text>
            <g
              v-if="n.hiddenCount > 0"
              class="expand-btn"
              :transform="`translate(${n.width - 22}, ${n.height - 22})`"
              @click.stop="expandNode(n.id)"
            >
              <circle r="10" />
              <text x="0" y="4" text-anchor="middle">+{{ n.hiddenCount }}</text>
            </g>
          </g>
        </g>
      </svg>
    </div>

    <div class="detail-panel" v-if="selected">
      <div class="detail-header">
        <div>
          <span class="detail-code">{{ selected.task_code }}</span>
          <span class="detail-name">{{ selected.task_name }}</span>
        </div>
        <button class="btn-tiny" @click="selected = null">Close</button>
      </div>
      <div class="detail-stats">
        <span><strong>{{ formatDate(selected.early_start) }}</strong> → <strong>{{ formatDate(selected.early_end) }}</strong></span>
        <span>{{ formatHours(selected.duration_hrs) }} duration</span>
        <span :class="selected.total_float_hrs === 0 ? 'float-crit' : ''">{{ selected.total_float_hrs }}h float</span>
        <span>{{ statusLabel(selected.status) }}</span>
      </div>
      <div class="detail-rels">
        <div class="rel-col">
          <h4>Predecessors ({{ selected.predecessors.length }})</h4>
          <div v-if="selected.predecessors.length === 0" class="rel-empty">None</div>
          <button v-for="p in selected.predecessors" :key="p.task_id" class="rel-item-btn" @click="revealAndSelect(p.task_id)">
            <span class="rel-code">{{ codeFor(p.task_id) }}</span>
            <span class="rel-type">{{ p.type }}</span>
            <span v-if="!visibleIds.has(p.task_id)" class="rel-hidden">not shown</span>
          </button>
        </div>
        <div class="rel-col">
          <h4>Successors ({{ selected.successors.length }})</h4>
          <div v-if="selected.successors.length === 0" class="rel-empty">None</div>
          <button v-for="s in selected.successors" :key="s.task_id" class="rel-item-btn" @click="revealAndSelect(s.task_id)">
            <span class="rel-code">{{ codeFor(s.task_id) }}</span>
            <span class="rel-type">{{ s.type }}</span>
            <span v-if="!visibleIds.has(s.task_id)" class="rel-hidden">not shown</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import dagre from 'dagre'
import { formatDate, formatHours, statusLabel } from '../utils/format'

const NEAR_CRITICAL_THRESHOLD_HRS = 80 // 10 working days
const NODE_WIDTH = 210
const NODE_HEIGHT = 64

export default {
  name: 'CriticalPathGraph',
  props: {
    activities: { type: Array, required: true },
  },
  data() {
    return {
      expandedExtra: new Set(), // task_ids manually revealed beyond critical+near-critical
      selectedId: null,
      scale: 1,
      tx: 40,
      ty: 40,
      panning: false,
      panStart: null,
    }
  },
  mounted() {
    this.$nextTick(this.resetView)
  },
  watch: {
    activities() {
      this.expandedExtra = new Set()
      this.selectedId = null
      this.$nextTick(this.resetView)
    },
  },
  computed: {
    actLookup() {
      const m = new Map()
      for (const a of this.activities) m.set(a.task_id, a)
      return m
    },
    criticalIds() {
      return new Set(this.activities.filter(a => a.is_critical).map(a => a.task_id))
    },
    baseVisibleIds() {
      const crit = this.criticalIds
      const ids = new Set(crit)
      for (const a of this.activities) {
        if (crit.has(a.task_id)) continue
        if (a.total_float_hrs > 0 && a.total_float_hrs <= NEAR_CRITICAL_THRESHOLD_HRS) {
          const touchesCritical =
            a.predecessors.some(p => crit.has(p.task_id)) || a.successors.some(s => crit.has(s.task_id))
          if (touchesCritical) ids.add(a.task_id)
        }
      }
      return ids
    },
    visibleIds() {
      const ids = new Set(this.baseVisibleIds)
      for (const id of this.expandedExtra) ids.add(id)
      return ids
    },
    selected() {
      return this.selectedId != null ? this.actLookup.get(this.selectedId) : null
    },
    layout() {
      const g = new dagre.graphlib.Graph()
      g.setGraph({ rankdir: 'LR', nodesep: 20, ranksep: 70, marginx: 20, marginy: 20 })
      g.setDefaultEdgeLabel(() => ({}))

      const crit = this.criticalIds
      const visible = this.visibleIds

      for (const id of visible) {
        const a = this.actLookup.get(id)
        if (!a) continue
        g.setNode(id, { width: NODE_WIDTH, height: NODE_HEIGHT })
      }

      const edgeMeta = []
      for (const id of visible) {
        const a = this.actLookup.get(id)
        if (!a) continue
        for (const p of a.predecessors) {
          if (!visible.has(p.task_id)) continue
          const edgeId = `${p.task_id}->${id}`
          g.setEdge(p.task_id, id, { id: edgeId })
          edgeMeta.push({ id: edgeId, from: p.task_id, to: id, type: p.type, lagHrs: p.lag_hrs })
        }
      }

      dagre.layout(g)

      const nodes = []
      let maxX = 0
      let maxY = 0
      for (const id of visible) {
        const a = this.actLookup.get(id)
        if (!a) continue
        const gn = g.node(id)
        if (!gn) continue
        const hiddenCount =
          a.predecessors.filter(p => !visible.has(p.task_id)).length +
          a.successors.filter(s => !visible.has(s.task_id)).length
        nodes.push({
          id,
          x: gn.x,
          y: gn.y,
          width: gn.width,
          height: gn.height,
          code: a.task_code,
          name: a.task_name,
          milestone: a.task_type === 'TT_Mile',
          critical: crit.has(id),
          nearCritical: !crit.has(id) && this.baseVisibleIds.has(id),
          floatHrs: a.total_float_hrs,
          durationLabel: formatHours(a.duration_hrs),
          dateLabel: a.early_start ? formatDate(a.early_start) : '',
          hiddenCount,
        })
        maxX = Math.max(maxX, gn.x + gn.width / 2)
        maxY = Math.max(maxY, gn.y + gn.height / 2)
      }

      const edges = edgeMeta.map(em => {
        const ge = g.edge(em.from, em.to)
        const pts = ge.points
        const path = pts.map((pt, i) => `${i === 0 ? 'M' : 'L'} ${pt.x} ${pt.y}`).join(' ')
        return { ...em, path, criticalEdge: crit.has(em.from) && crit.has(em.to) }
      })

      return { nodes, edges, width: maxX + 60, height: maxY + 60 }
    },
    nodes() {
      return this.layout.nodes
    },
    edges() {
      return this.layout.edges
    },
    svgWidth() {
      return Math.max(this.layout.width, 400)
    },
    svgHeight() {
      return Math.max(this.layout.height, 300)
    },
  },
  methods: {
    formatDate,
    formatHours,
    statusLabel,
    truncate(s, n) {
      if (!s) return ''
      return s.length > n ? s.slice(0, n - 1) + '…' : s
    },
    codeFor(id) {
      const a = this.actLookup.get(id)
      return a ? a.task_code : '?' + id
    },
    nodeClass(n) {
      return {
        critical: n.critical,
        'near-critical': n.nearCritical,
        other: !n.critical && !n.nearCritical,
        selected: this.selectedId === n.id,
        dimmed: this.selectedId != null && !this.isConnectedToSelected(n.id) && this.selectedId !== n.id,
      }
    },
    edgeClass(e) {
      return {
        'edge-critical': e.criticalEdge,
        dimmed: this.selectedId != null && e.from !== this.selectedId && e.to !== this.selectedId,
      }
    },
    edgeIsCritical(e) {
      return e.criticalEdge
    },
    isConnectedToSelected(id) {
      if (this.selectedId == null) return true
      return this.edges.some(
        e => (e.from === this.selectedId && e.to === id) || (e.to === this.selectedId && e.from === id)
      )
    },
    selectNode(n) {
      this.selectedId = this.selectedId === n.id ? null : n.id
    },
    expandNode(id) {
      const a = this.actLookup.get(id)
      if (!a) return
      for (const p of a.predecessors) this.expandedExtra.add(p.task_id)
      for (const s of a.successors) this.expandedExtra.add(s.task_id)
      this.expandedExtra = new Set(this.expandedExtra)
    },
    revealAndSelect(id) {
      if (!this.visibleIds.has(id)) {
        this.expandedExtra.add(id)
        this.expandedExtra = new Set(this.expandedExtra)
      }
      this.selectedId = id
    },
    resetGraph() {
      this.expandedExtra = new Set()
      this.selectedId = null
    },
    // Zoom while keeping the graph point under (cx, cy) — canvas-local coords — fixed on screen.
    // Without this, scaling around the origin flings the graph out of view after a couple of clicks.
    zoomAt(cx, cy, newScale) {
      const clamped = Math.min(2.5, Math.max(0.03, newScale))
      const gx = (cx - this.tx) / this.scale
      const gy = (cy - this.ty) / this.scale
      this.tx = cx - gx * clamped
      this.ty = cy - gy * clamped
      this.scale = clamped
    },
    zoomBy(factor) {
      const el = this.$refs.canvas
      const cx = el ? el.clientWidth / 2 : 0
      const cy = el ? el.clientHeight / 2 : 0
      this.zoomAt(cx, cy, this.scale * factor)
    },
    resetView() {
      const el = this.$refs.canvas
      const gw = this.layout.width
      const gh = this.layout.height
      if (!el || !gw || !gh) {
        this.scale = 1
        this.tx = 40
        this.ty = 40
        return
      }
      const pad = 40
      const s = Math.min((el.clientWidth - pad * 2) / gw, (el.clientHeight - pad * 2) / gh, 1.2)
      this.scale = Math.max(0.03, s)
      this.tx = (el.clientWidth - gw * this.scale) / 2
      this.ty = (el.clientHeight - gh * this.scale) / 2
    },
    onWheel(e) {
      const el = this.$refs.canvas
      const rect = el.getBoundingClientRect()
      const factor = e.deltaY > 0 ? 0.9 : 1.1
      this.zoomAt(e.clientX - rect.left, e.clientY - rect.top, this.scale * factor)
    },
    onPanStart(e) {
      this.panning = true
      this.panStart = { x: e.clientX - this.tx, y: e.clientY - this.ty }
    },
    onPanMove(e) {
      if (!this.panning || !this.panStart) return
      this.tx = e.clientX - this.panStart.x
      this.ty = e.clientY - this.panStart.y
    },
    onPanEnd() {
      this.panning = false
      this.panStart = null
    },
  },
}
</script>

<style scoped>
.graph-wrap { border: 1px solid #e8e8e8; border-radius: 10px; overflow: hidden; background: #fff; margin-bottom: 24px; }
.graph-toolbar { display: flex; justify-content: space-between; align-items: center; padding: 10px 14px; border-bottom: 1px solid #eee; background: #fafbfc; flex-wrap: wrap; gap: 8px; }
.legend { display: flex; gap: 14px; flex-wrap: wrap; }
.legend-item { display: flex; align-items: center; gap: 5px; font-size: 12px; color: #666; }
.dot { width: 9px; height: 9px; border-radius: 50%; display: inline-block; }
.dot-critical { background: #e74c3c; }
.dot-near { background: #d4a017; }
.dot-other { background: #b3b8c2; }
.dot-mile { background: #8e44ad; }
.toolbar-actions { display: flex; align-items: center; gap: 8px; }
.node-count { font-size: 11px; color: #999; margin-right: 4px; }
.btn-tiny { padding: 3px 10px; border: 1px solid #ccc; border-radius: 5px; background: white; cursor: pointer; font-size: 12px; color: #555; }
.btn-tiny:hover:not(:disabled) { background: #f0f2f5; }
.btn-tiny:disabled { opacity: 0.4; cursor: default; }

.graph-canvas { position: relative; overflow: hidden; height: 480px; background: radial-gradient(#f0f1f4 1px, transparent 1px) 0 0 / 16px 16px, #fff; cursor: grab; }
.graph-canvas.dragging { cursor: grabbing; }

.edge { fill: none; stroke: #aab0bb; stroke-width: 1.5; transition: opacity 0.15s, stroke 0.15s; }
.edge.edge-critical { stroke: #e74c3c; stroke-width: 2.5; }
.edge.dimmed { opacity: 0.15; }

.node { cursor: pointer; }
.node .node-rect { fill: #fafbfc; stroke: #d5d8de; stroke-width: 1.5; transition: filter 0.15s, opacity 0.15s; }
.node.critical .node-rect { fill: #fdf1f0; stroke: #e74c3c; stroke-width: 2; }
.node.near-critical .node-rect { fill: #fdf8ec; stroke: #d4a017; stroke-width: 1.5; }
.node.other .node-rect { fill: #f5f6f8; stroke: #c9cdd4; }
.node.selected .node-rect { stroke: #2f5496; stroke-width: 2.5; filter: drop-shadow(0 2px 6px rgba(47,84,150,0.35)); }
.node.dimmed { opacity: 0.25; }
.node:hover .node-rect { filter: drop-shadow(0 2px 5px rgba(0,0,0,0.12)); }

.node-mile-icon { font-size: 11px; fill: #8e44ad; }
.node-code { font-size: 10px; font-weight: 700; fill: #666; text-transform: uppercase; letter-spacing: 0.3px; }
.node-name { font-size: 12px; font-weight: 600; fill: #1a1a2e; }
.node-meta { font-size: 10px; fill: #888; }

.expand-btn circle { fill: #2f5496; opacity: 0.9; }
.expand-btn text { fill: white; font-size: 10px; font-weight: 700; }
.expand-btn:hover circle { fill: #1f3b6e; }

.detail-panel { border-top: 1px solid #eee; padding: 16px 18px; background: #f8f9fc; }
.detail-header { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 8px; }
.detail-code { font-family: monospace; font-weight: 700; color: #2f5496; margin-right: 8px; }
.detail-name { font-weight: 600; color: #1a1a2e; }
.detail-stats { display: flex; gap: 18px; font-size: 12px; color: #666; margin-bottom: 12px; flex-wrap: wrap; }
.float-crit { color: #c0392b; font-weight: 700; }
.detail-rels { display: flex; gap: 32px; flex-wrap: wrap; }
.rel-col { flex: 1; min-width: 200px; }
.rel-col h4 { font-size: 11px; text-transform: uppercase; color: #888; letter-spacing: 0.3px; margin-bottom: 6px; }
.rel-empty { font-size: 12px; color: #aaa; font-style: italic; }
.rel-item-btn { display: flex; gap: 8px; align-items: center; font-size: 12px; padding: 3px 6px; border: none; background: none; cursor: pointer; border-radius: 4px; width: 100%; text-align: left; }
.rel-item-btn:hover { background: #eef1f7; }
.rel-code { font-family: monospace; font-weight: 600; color: #2f5496; min-width: 60px; }
.rel-type { color: #888; font-size: 11px; }
.rel-hidden { color: #b3b8c2; font-size: 10px; font-style: italic; margin-left: auto; }
</style>
