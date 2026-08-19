<template>
  <div
    class="graph-wrap"
    :class="{ 'is-fullscreen': isFullscreen }"
    :style="{ '--print-w': printTargetSize.w + 'px', '--print-h': printTargetSize.h + 'px' }"
    ref="wrapEl"
  >
    <div class="view-bar">
      <div class="strip-title">
        <span class="strip-sub">{{ activities.length }} activities &middot; {{ visibleIds.size }} shown</span>
      </div>
      <select v-model="printPaperSize" class="btn-tiny paper-size-select" title="Paper size to fit the printout to">
        <option v-for="(p, key) in paperSizes" :key="key" :value="key">{{ p.label }}</option>
      </select>
      <button class="btn-tiny" @click="printGraph">Print</button>
      <button class="ctrl-btn ctrl-btn-accent" @click="toggleFullscreen">{{ isFullscreen ? 'Exit fullscreen' : 'Fullscreen' }}</button>
    </div>

    <div class="graph-toolbar" :class="{ 'drawer-open': selected }">
      <div class="legend">
        <span class="legend-item"><i class="dot dot-critical"></i>Critical (TF&le;0)</span>
        <span class="legend-item"><i class="dot dot-near"></i>Near-critical (&le;10d float)</span>
        <span class="legend-item"><i class="dot dot-other"></i>Expanded</span>
        <span class="legend-item"><i class="lg-node-neg"></i>Negative float (late)</span>
        <span class="legend-item"><i class="diamond"></i>Milestone</span>
      </div>
      <div class="toolbar-actions">
        <span v-if="isolationActive" class="isolation-chip">
          Chain trace &middot; {{ isolatedIds.size }} {{ isolatedIds.size === 1 ? 'activity' : 'activities' }}
          <button class="isolation-exit" @click="exitIsolation">Show all</button>
        </span>
        <button v-else class="btn-tiny" :disabled="expandedExtra.size === 0" @click="resetGraph">Reset to critical path</button>
        <div class="zoom-adjust">
          <button class="zbtn" @click="zoomBy(1 / 1.3)">−</button>
          <button class="zbtn" @click="resetView">Fit</button>
          <button class="zbtn" @click="zoomBy(1.3)">+</button>
        </div>
        <span class="gesture-hint">Scroll to zoom &middot; drag to pan &middot; Esc closes</span>
      </div>
    </div>

    <div class="graph-body">
    <div
      class="graph-canvas"
      ref="canvas"
      @wheel.prevent="onWheel"
      @mousedown="onPanStart"
      @mousemove="onPanMove"
      @mouseup="onPanEnd"
      @mouseleave="onPanEnd"
      @touchstart="onTouchStart"
      @touchmove.prevent="onTouchMove"
      @touchend="onTouchEnd"
      :class="{ dragging: panning }"
    >
      <!-- Fills the canvas rather than sizing to the graph layout: pan/zoom happens via the
           inner <g> transform, so an SVG sized to the layout clips any content panned or
           zoomed beyond the graph's original footprint. -->
      <svg width="100%" height="100%">
        <defs>
          <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
            <path d="M0 0L10 5L0 10z" class="arrow-normal" />
          </marker>
          <marker id="arrow-critical" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
            <path d="M0 0L10 5L0 10z" class="arrow-critical" />
          </marker>
        </defs>
        <g class="viewport" :class="{ 'viewport-animated': animating }" :transform="`translate(${tx},${ty}) scale(${scale})`">
          <path
            v-for="e in edges"
            :key="e.id"
            :d="e.path"
            class="edge"
            :class="edgeClass(e)"
            :marker-end="edgeIsCritical(e) ? 'url(#arrow-critical)' : 'url(#arrow)'"
          >
            <title>{{ relTypeLabel(e.type) }}{{ e.lagHrs ? ` ${formatLag(e.lagHrs)} lag` : '' }}</title>
          </path>

          <g
            v-for="n in nodes"
            :key="n.id"
            class="node"
            :class="nodeClass(n)"
            :transform="`translate(${n.x - n.width / 2}, ${n.y - n.height / 2})`"
            @click.stop="selectNode(n)"
          >
            <title>{{ n.code }} — {{ n.name }}
{{ n.fullRangeLabel }} ({{ n.durationLabel }})</title>
            <rect :width="n.width" :height="n.height" rx="2" class="node-rect" />
            <rect v-if="n.negativeFloat" :width="n.width" height="4" class="node-neg-flag" />
            <circle v-if="annotations[n.id]" :cx="n.width - 8" cy="29" r="3.5" class="node-annotation-flag" :class="'sev-' + annotations[n.id].severity">
              <title>{{ annotations[n.id].note }}</title>
            </circle>
            <!-- Top row: code + duration, divided from the name/footer below -->
            <rect v-if="n.milestone" x="7" y="6" width="8" height="8" class="node-mile-icon" transform="rotate(45 11 10)" />
            <text class="node-code" :x="n.milestone ? 22 : 9" y="15">{{ n.code }}</text>
            <text class="node-duration" :x="n.width - 9" y="15" text-anchor="end">{{ n.durationLabel }}</text>
            <line x1="0" :x2="n.width" y1="20" y2="20" class="node-rule" />
            <!-- Name -->
            <text class="node-name" x="9" y="38">{{ truncate(n.name, 30) }}</text>
            <!-- Bottom strip: Start | Float -->
            <line x1="0" :x2="n.width" :y1="n.height - 18" :y2="n.height - 18" class="node-rule" />
            <line :x1="n.width / 2" :x2="n.width / 2" :y1="n.height - 18" :y2="n.height" class="node-rule" />
            <text class="node-meta" x="9" :y="n.height - 5">{{ n.dateRangeLabel }}</text>
            <text class="node-meta" :x="n.width - 9" :y="n.height - 5" text-anchor="end" :class="{ 'node-meta-neg': n.negativeFloat }">{{ n.floatDaysLabel }}</text>
            <g
              v-if="n.hiddenCount > 0"
              class="expand-btn"
              :transform="`translate(${n.width - 24}, ${n.height - 24})`"
              @click.stop="expandNode(n.id)"
            >
              <circle r="12" />
              <text x="0" y="4" text-anchor="middle">+{{ n.hiddenCount }}</text>
            </g>
          </g>
        </g>
      </svg>
    </div>

    <ActivityDetailDrawer
      :activity="selected"
      :lookup="actLookup"
      :annotations="annotations"
      :visible-ids="visibleIds"
      :project-name="projectName"
      @close="selectedId = null"
      @select="revealAndSelect"
      @annotate="(id, patch) => $emit('annotate', id, patch)"
      @unannotate="id => $emit('unannotate', id)"
    >
      <template #actions>
        <div class="detail-actions">
          <button v-if="!isolationActive" class="btn-tiny-light btn-isolate" @click="isolateSelected" title="Clear the diagram down to just this activity, then click predecessors/successors below to rebuild its chain link by link">
            Isolate &amp; trace chain
          </button>
          <span v-else class="trace-hint">Tracing — click a predecessor or successor below to add it and walk the chain.</span>
        </div>
      </template>
    </ActivityDetailDrawer>
    </div>
  </div>
</template>

<script>
import dagre from 'dagre'
import ActivityDetailDrawer from './ActivityDetailDrawer.vue'
import { formatDate, formatHours, formatLag, statusLabel, isMilestone, formatFloat, formatDateRange } from '../utils/format'
import fullscreenMixin from '../mixins/fullscreen'
import { relTypeLabel, cstrLabel, displayStart, displayEnd } from '../utils/p6'
import { PAPER_SIZES, usableWidthPx, usableHeightPx } from '../utils/paper'

const NEAR_CRITICAL_THRESHOLD_HRS = 80 // 10 working days
const NODE_WIDTH = 210
const NODE_HEIGHT = 64
const DAGRE_RANKSEP = 70 // spacing dagre uses internally, only needed to recover rank index from its output
const RANK_GAP_X = 50 // column gap in our own wrapped grid
const STACK_GAP_Y = 14 // gap between same-rank siblings stacked in one column
const ROW_GAP_Y = 46 // gap between wrapped rows
const CANVAS_PADDING = 30
// Usable print area per paper size, landscape: (dimension - 2x10mm margin) at 96 CSS
// px/inch, minus a ~15px safety buffer. Unlike the Gantt (a long row list needing real
// pagination), this diagram is a 2D layout — it just needs to fit on ONE page, so both
// width and height matter, not only width.
// 20px safety buffer: tuned against this diagram's printed output — deliberately
// not the Gantt's value (see utils/paper.js).
const PRINT_BUFFER_PX = 20

export default {
  name: 'CriticalPathGraph',
  mixins: [fullscreenMixin],
  props: {
    activities: { type: Array, required: true },
    annotations: { type: Object, default: () => ({}) },
    visible: { type: Boolean, default: true },
    projectName: { type: String, default: '' },
  },
  emits: ['annotate', 'unannotate'],
  components: { ActivityDetailDrawer },
  data() {
    return {
      expandedExtra: new Set(), // task_ids manually revealed beyond critical+near-critical
      isolatedIds: null, // when set, the diagram shows ONLY this traced chain
      selectedId: null,
      scale: 1,
      tx: 40,
      ty: 40,
      panning: false,
      panStart: null,
      animating: false,
      canvasWidth: 900,
      printPaperSize: 'a4',
      paperSizes: PAPER_SIZES,
    }
  },
  mounted() {
    window.addEventListener('keydown', this._onKeydown = (e) => {
      if (e.key !== 'Escape' || !this.$el || this.$el.offsetParent === null) return
      if (this.selectedId != null) { this.selectedId = null; return }
      if (this.isolationActive) this.exitIsolation()
    })
    // Clicks on app chrome outside this component dismiss the fixed drawer overlay.
    document.addEventListener('mousedown', this._onDocMousedown = (e) => {
      if (this.selectedId != null && this.$el.offsetParent !== null && !this.$el.contains(e.target)) {
        this.selectedId = null
      }
    })
    if (this.$refs.canvas) {
      this.canvasWidth = this.$refs.canvas.clientWidth
      this._resizeObserver = new ResizeObserver(entries => {
        for (const entry of entries) this.canvasWidth = entry.contentRect.width
      })
      this._resizeObserver.observe(this.$refs.canvas)
    }
    this.$nextTick(this.resetView)
  },
  beforeUnmount() {
    window.removeEventListener('keydown', this._onKeydown)
    document.removeEventListener('mousedown', this._onDocMousedown)
    this._resizeObserver?.disconnect()
    clearTimeout(this._animTimer)
  },
  watch: {
    activities() {
      this.expandedExtra = new Set()
      this.selectedId = null
      this.$nextTick(this.resetView)
    },
    visible(v) {
      // Tabs stay mounted (v-show); the canvas measures 0x0 while hidden, so both the
      // mount-time layout (snake wrap uses canvasWidth) and fit are garbage. Flag a
      // pending fit — it runs from the canvasWidth watcher once the ResizeObserver
      // delivers the real width, i.e. after the layout has re-wrapped correctly.
      if (v && !this._fitDone) {
        this._pendingFit = true
      }
    },
    canvasWidth(w) {
      if (this._pendingFit && w > 0) {
        this._pendingFit = false
        this._fitDone = true
        this.$nextTick(this.resetView)
      }
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
      if (this.isolatedIds) return this.isolatedIds
      const ids = new Set(this.baseVisibleIds)
      for (const id of this.expandedExtra) ids.add(id)
      return ids
    },
    printTargetSize() {
      return {
        w: usableWidthPx(this.printPaperSize, PRINT_BUFFER_PX),
        h: usableHeightPx(this.printPaperSize, PRINT_BUFFER_PX),
      }
    },
    isolationActive() {
      return this.isolatedIds !== null
    },
    selected() {
      return this.selectedId != null ? this.actLookup.get(this.selectedId) : null
    },
    // Runs dagre once to get a correct topological rank + crossing-minimized order,
    // then re-flows that single wide row into wrapped, alternating-direction rows —
    // like a snake / wrapped paragraph — so long critical chains stay readable
    // instead of demanding a mile of horizontal scrolling.
    layout() {
      const g = new dagre.graphlib.Graph()
      g.setGraph({ rankdir: 'LR', nodesep: 20, ranksep: DAGRE_RANKSEP, marginx: 20, marginy: 20 })
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

      const raw = []
      for (const id of visible) {
        const a = this.actLookup.get(id)
        const gn = g.node(id)
        if (!a || !gn) continue
        raw.push({ id, a, gx: gn.x, gy: gn.y })
      }
      if (raw.length === 0) return { nodes: [], edges: [], width: 400, height: 300 }

      const minGx = Math.min(...raw.map(r => r.gx))
      const rankOf = r => Math.round((r.gx - minGx) / (NODE_WIDTH + DAGRE_RANKSEP))

      const rankGroups = new Map()
      for (const r of raw) {
        const rk = rankOf(r)
        if (!rankGroups.has(rk)) rankGroups.set(rk, [])
        rankGroups.get(rk).push(r)
      }
      for (const group of rankGroups.values()) group.sort((x, y) => x.gy - y.gy)

      const maxRank = Math.max(...rankGroups.keys())
      const ranksPerRow = Math.max(
        1,
        Math.floor((this.canvasWidth - CANVAS_PADDING * 2 + RANK_GAP_X) / (NODE_WIDTH + RANK_GAP_X))
      )
      const rowOf = rk => Math.floor(rk / ranksPerRow)
      const numRows = rowOf(maxRank) + 1

      const rowStackCount = new Array(numRows).fill(1)
      for (const [rk, group] of rankGroups) {
        const row = rowOf(rk)
        rowStackCount[row] = Math.max(rowStackCount[row], group.length)
      }
      const rowY = new Array(numRows).fill(0)
      for (let i = 1; i < numRows; i++) {
        rowY[i] = rowY[i - 1] + rowStackCount[i - 1] * (NODE_HEIGHT + STACK_GAP_Y) + ROW_GAP_Y
      }

      const posById = new Map()
      for (const [rk, group] of rankGroups) {
        const row = rowOf(rk)
        const dir = row % 2 === 0 ? 1 : -1
        const colInRow = rk - row * ranksPerRow
        const colPos = dir === 1 ? colInRow : ranksPerRow - 1 - colInRow
        const x = CANVAS_PADDING + colPos * (NODE_WIDTH + RANK_GAP_X) + NODE_WIDTH / 2
        group.forEach((r, stackIdx) => {
          const y = rowY[row] + stackIdx * (NODE_HEIGHT + STACK_GAP_Y) + NODE_HEIGHT / 2
          posById.set(r.id, { x, y, row, dir })
        })
      }

      const nodes = []
      let maxX = 0
      let maxY = 0
      for (const r of raw) {
        const pos = posById.get(r.id)
        const a = r.a
        const hiddenCount =
          a.predecessors.filter(p => !visible.has(p.task_id)).length +
          a.successors.filter(s => !visible.has(s.task_id)).length
        nodes.push({
          id: r.id,
          x: pos.x,
          y: pos.y,
          row: pos.row,
          dir: pos.dir,
          width: NODE_WIDTH,
          height: NODE_HEIGHT,
          code: a.task_code,
          name: a.task_name,
          milestone: isMilestone(a),
          critical: crit.has(r.id),
          nearCritical: !crit.has(r.id) && this.baseVisibleIds.has(r.id),
          negativeFloat: a.is_negative_float,
          floatHrs: a.total_float_hrs,
          durationLabel: formatHours(a.duration_hrs, a.calendar_hrs_per_day),
          // total_float_hrs is null when P6 didn't compute a float (typically completed
          // activities); a naive "> 0 ? ... : '0d float'" ternary would also silently
          // show negative float as "0d", hiding exactly the activities that most need
          // flagging — so every case (positive, zero, negative, null) is handled explicitly.
          floatDaysLabel: a.total_float_hrs == null ? '— float' : `${Math.round(a.total_float_hrs / (a.calendar_hrs_per_day || 8))}d float`,
          dateRangeLabel: formatDateRange(displayStart(a), displayEnd(a)),
          fullRangeLabel: `${formatDate(displayStart(a))} → ${formatDate(displayEnd(a))}`,
          hiddenCount,
        })
        maxX = Math.max(maxX, pos.x + NODE_WIDTH / 2)
        maxY = Math.max(maxY, pos.y + NODE_HEIGHT / 2)
      }

      const nodeById = new Map(nodes.map(n => [n.id, n]))
      // "forward" = the side a node's row is reading towards; "backward" = where it reads in from.
      // Anchoring every edge this way means a same-row hop is a gentle sideways curve, and a
      // row-wrap hop becomes a hairpin turn on the correct edge — like a snake game or a
      // wrapped paragraph, always readable without special-casing the two situations.
      const forwardAnchor = n => ({ x: n.x + (n.dir === 1 ? n.width / 2 : -n.width / 2), y: n.y })
      const backwardAnchor = n => ({ x: n.x + (n.dir === 1 ? -n.width / 2 : n.width / 2), y: n.y })
      const edges = edgeMeta.map(em => {
        const a = nodeById.get(em.from)
        const b = nodeById.get(em.to)
        const start = forwardAnchor(a)
        const end = backwardAnchor(b)
        const dx = Math.max(40, Math.abs(end.x - start.x) * 0.5)
        const c1x = start.x + (a.dir === 1 ? dx : -dx)
        const c2x = end.x + (b.dir === 1 ? -dx : dx)
        const path = `M ${start.x} ${start.y} C ${c1x} ${start.y}, ${c2x} ${end.y}, ${end.x} ${end.y}`
        return { ...em, path, criticalEdge: crit.has(em.from) && crit.has(em.to) }
      })

      return { nodes, edges, width: maxX + CANVAS_PADDING, height: maxY + CANVAS_PADDING }
    },
    nodes() {
      return this.layout.nodes
    },
    edges() {
      return this.layout.edges
    },
  },
  methods: {
    formatDate,
    formatHours,
    formatLag,
    statusLabel,
    formatFloat,
    relTypeLabel,
    cstrLabel,
    displayStart,
    displayEnd,
    truncate(s, n) {
      if (!s) return ''
      return s.length > n ? s.slice(0, n - 1) + '…' : s
    },
    nodeClass(n) {
      return {
        critical: n.critical,
        'near-critical': n.nearCritical,
        other: !n.critical && !n.nearCritical,
        negative: n.negativeFloat,
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
      if (this.selectedId === n.id) {
        this.selectedId = null
        return
      }
      this.selectedId = n.id
      this.$nextTick(() => this.centerOnNode(n.id))
    },
    expandNode(id) {
      const a = this.actLookup.get(id)
      if (!a) return
      for (const p of a.predecessors) this.expandedExtra.add(p.task_id)
      for (const s of a.successors) this.expandedExtra.add(s.task_id)
      this.expandedExtra = new Set(this.expandedExtra)
      this.$nextTick(() => this.centerOnNode(id))
    },
    revealAndSelect(id) {
      if (this.isolationActive) {
        // Chain tracing: clicking a predecessor/successor ADDS it to the traced set and
        // walks the selection onto it, growing the chain one link at a time.
        const next = new Set(this.isolatedIds)
        next.add(id)
        this.isolatedIds = next
        this.selectedId = id
        this.$nextTick(() => this.centerOnNode(id))
        return
      }
      if (!this.visibleIds.has(id)) {
        this.expandedExtra.add(id)
        this.expandedExtra = new Set(this.expandedExtra)
      }
      this.selectedId = id
      this.$nextTick(() => this.centerOnNode(id))
    },
    isolateSelected() {
      if (this.selectedId == null) return
      this.isolatedIds = new Set([this.selectedId])
      this.$nextTick(() => this.centerOnNode(this.selectedId))
    },
    exitIsolation() {
      const keep = this.selectedId
      this.isolatedIds = null
      // Re-reveal the activity we were parked on so exiting doesn't strand the
      // selection outside the critical+near-critical default view.
      if (keep != null) this.revealAndSelect(keep)
      else this.$nextTick(this.resetView)
    },
    resetGraph() {
      this.expandedExtra = new Set()
      this.isolatedIds = null
      this.selectedId = null
    },
    printGraph() {
      // Unlike the Gantt (a long row list needing real multi-page pagination), this is a
      // 2D diagram — it just needs to fit on ONE physical page, so there's no pagination
      // risk to work around: fit-scale it to the selected paper (never scale up), inject
      // the matching @page size, print, then restore the on-screen pan/zoom.
      const gw = this.layout.width
      const gh = this.layout.height
      if (!gw || !gh) { window.print(); return }
      const { w: targetW, h: targetH } = this.printTargetSize
      const fitScale = Math.min(1, targetW / gw, targetH / gh)
      const prev = { scale: this.scale, tx: this.tx, ty: this.ty }
      this.scale = fitScale
      this.tx = (targetW - gw * fitScale) / 2
      this.ty = (targetH - gh * fitScale) / 2

      const pageCss = (this.paperSizes[this.printPaperSize] || this.paperSizes.a4).pageCss
      const styleTag = document.createElement('style')
      styleTag.textContent = `@page { size: ${pageCss} landscape; margin: 10mm; }`
      document.head.appendChild(styleTag)
      const restore = () => {
        this.scale = prev.scale
        this.tx = prev.tx
        this.ty = prev.ty
        styleTag.remove()
      }
      window.addEventListener('afterprint', restore, { once: true })
      this.$nextTick(() => requestAnimationFrame(() => window.print()))
    },
    triggerAnimation() {
      this.animating = true
      clearTimeout(this._animTimer)
      this._animTimer = setTimeout(() => {
        this.animating = false
      }, 260)
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
      this.triggerAnimation()
      const el = this.$refs.canvas
      const cx = el ? el.clientWidth / 2 : 0
      const cy = el ? el.clientHeight / 2 : 0
      this.zoomAt(cx, cy, this.scale * factor)
    },
    // Smoothly pans (and, only if too zoomed-out to read, zooms in a little) so the given
    // node lands centered on screen — keeps you oriented after selecting or expanding.
    centerOnNode(id) {
      const el = this.$refs.canvas
      const n = this.nodes.find(nd => nd.id === id)
      if (!el || !n) return
      this.triggerAnimation()
      this.scale = Math.min(2.5, Math.max(this.scale, 0.85))
      this.tx = el.clientWidth / 2 - n.x * this.scale
      this.ty = el.clientHeight / 2 - n.y * this.scale
    },
    resetView() {
      this.triggerAnimation()
      const el = this.$refs.canvas
      const gw = this.layout.width
      const gh = this.layout.height
      if (!el || !gw || !gh) {
        this.scale = 1
        this.tx = 40
        this.ty = 40
        return
      }
      const pad = 30
      const widthScale = (el.clientWidth - pad * 2) / gw
      const heightScale = (el.clientHeight - pad * 2) / gh
      // Prioritize using the full canvas width — a tall (many-row) graph shouldn't
      // collapse horizontal usage just because it also doesn't fit vertically; the
      // canvas is scrollable/pannable, so let height overflow instead of shrinking
      // everything down to fit, which used to leave 60-70% of the width empty.
      const s = Math.min(widthScale, Math.max(heightScale, widthScale * 0.85), 1.2)
      this.scale = Math.max(0.1, s)
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
    // Touch: one finger pans, two fingers pinch-zoom around the midpoint.
    onTouchStart(e) {
      if (e.touches.length === 1) {
        this.panStart = { x: e.touches[0].clientX - this.tx, y: e.touches[0].clientY - this.ty }
        this.panning = true
        this._pinch = null
      } else if (e.touches.length >= 2) {
        this.panning = false
        this.panStart = null
        this._pinch = this._pinchState(e)
      }
    },
    onTouchMove(e) {
      if (e.touches.length === 1 && this.panStart) {
        this.tx = e.touches[0].clientX - this.panStart.x
        this.ty = e.touches[0].clientY - this.panStart.y
      } else if (e.touches.length >= 2 && this._pinch) {
        const p = this._pinchState(e)
        const rect = this.$refs.canvas.getBoundingClientRect()
        this.zoomAt(p.mx - rect.left, p.my - rect.top, this.scale * (p.dist / this._pinch.dist))
        this.tx += p.mx - this._pinch.mx
        this.ty += p.my - this._pinch.my
        this._pinch = p
      }
    },
    onTouchEnd(e) {
      if (e.touches.length === 0) {
        this.panning = false
        this.panStart = null
        this._pinch = null
      } else if (e.touches.length === 1) {
        this._pinch = null
        this.panStart = { x: e.touches[0].clientX - this.tx, y: e.touches[0].clientY - this.ty }
        this.panning = true
      }
    },
    _pinchState(e) {
      const [a, b] = [e.touches[0], e.touches[1]]
      return {
        dist: Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY),
        mx: (a.clientX + b.clientX) / 2,
        my: (a.clientY + b.clientY) / 2,
      }
    },
    // Hook called by the fullscreen mixin: the diagram must re-fit to the new
    // viewport, where the Gantt simply reflows.
    onFullscreenChanged() {
      this.$nextTick(this.resetView)
    },
  },
}
</script>

<style scoped>
.graph-wrap { border: 1px solid var(--gray-300); border-radius: var(--radius-md); overflow: hidden; background: var(--white); margin-bottom: var(--space-6); font-family: var(--font-ui); }
.graph-wrap.is-fullscreen { border-radius: 0; display: flex; flex-direction: column; height: 100vh; }
.graph-wrap.is-fullscreen .graph-body { flex: 1; min-height: 0; display: flex; }
.graph-wrap.is-fullscreen .graph-canvas { flex: 1; height: auto; }


.graph-toolbar { display: flex; justify-content: space-between; align-items: center; padding: var(--space-3) var(--space-4); border-bottom: 1px solid var(--gray-300); background: var(--gray-100); flex-wrap: wrap; gap: var(--space-2); }
.graph-toolbar.drawer-open { padding-right: 440px; }
.legend { display: flex; gap: 14px; flex-wrap: wrap; }
.legend-item { display: flex; align-items: center; gap: 5px; font: var(--text-small); color: var(--gray-700); }
.dot { width: 9px; height: 9px; border-radius: 50%; display: inline-block; }
.dot-critical { background: var(--crit); }
.dot-near { background: var(--near); }
.dot-other { background: var(--gray-500); }
.lg-node-neg { width: 16px; height: 11px; display: inline-block; box-sizing: border-box; background: var(--crit-tint); border: 1px solid var(--crit); border-top: 4px solid var(--crit); border-radius: 2px; }
.diamond { width: 8px; height: 8px; background: var(--milestone); display: inline-block; transform: rotate(45deg); }
.toolbar-actions { display: flex; align-items: center; gap: var(--space-2); }
.isolation-chip { display: inline-flex; align-items: center; gap: 8px; background: var(--accent-soft); color: var(--accent); border: 1px solid var(--accent); border-radius: 12px; padding: 2px 4px 2px 10px; font: var(--text-small); font-weight: 600; }
.isolation-exit { border: none; background: var(--accent); color: var(--on-solid); border-radius: 9px; padding: 2px 9px; font: var(--text-small); font-weight: 600; cursor: pointer; }
.isolation-exit:hover { opacity: 0.9; }
.detail-actions { margin-top: 10px; }
.btn-isolate { color: var(--accent); border-color: var(--accent); font-weight: 600; }
.btn-isolate:hover { background: var(--accent-soft); }
.trace-hint { display: block; font-size: 13px; color: var(--accent); font-weight: 600; background: var(--accent-soft); border-radius: var(--radius-sm); padding: 6px 9px; }
.paper-size-select { min-width: 0; }
.gesture-hint { font: var(--text-micro); color: var(--gray-500); white-space: nowrap; margin-left: var(--space-2); }
.zoom-adjust { display: flex; border: 1px solid var(--gray-300); border-radius: var(--radius-sm); overflow: hidden; }
.zbtn { padding: 4px 10px; border: none; border-right: 1px solid var(--gray-300); background: var(--white); cursor: pointer; font: var(--text-small); font-weight: 700; color: var(--gray-700); }
.zbtn:last-child { border-right: none; }
.zbtn:hover { background: var(--gray-150); }

.graph-canvas { flex: 1; min-width: 0; position: relative; overflow: hidden; touch-action: none; height: calc(100dvh - 212px); min-height: 320px; background: radial-gradient(var(--gray-150) 1.5px, transparent 1.5px) 0 0 / 18px 18px, var(--white); cursor: grab; }
/* Toolbar rows stack taller on narrow screens — leave more room above the canvas */
@media (max-width: 900px) {
  .graph-canvas { height: calc(100dvh - 250px); min-height: 320px; }
}
.graph-canvas.dragging { cursor: grabbing; }

/* No transition by default — dragging/wheel-zoom must track the pointer instantly.
   The animated class is toggled on only for programmatic camera moves (buttons,
   fit, select, expand) so those glide instead of snapping. */
.viewport-animated { transition: transform 0.26s cubic-bezier(0.22, 1, 0.36, 1); }

.arrow-normal { fill: var(--gray-500); }
.arrow-critical { fill: var(--crit); }
.edge { fill: none; stroke: var(--gray-500); stroke-width: 1.8; transition: opacity 0.15s, stroke 0.15s; }
.edge.edge-critical { stroke: var(--crit); stroke-width: 3; }
.edge.dimmed { opacity: 0.12; }

.node { cursor: pointer; }
.node .node-rect { fill: var(--gray-100); stroke: var(--gray-300); stroke-width: 1.5; transition: filter 0.15s, opacity 0.15s; }
.node.critical .node-rect { fill: var(--crit-tint); stroke: var(--crit); stroke-width: 2.5; }
.node.near-critical .node-rect { fill: var(--near-tint); stroke: var(--near); stroke-width: 2; }
.node.other .node-rect { fill: var(--gray-100); stroke: var(--gray-300); }
.node.negative .node-rect { stroke-width: 3.5; }
.node-neg-flag { fill: var(--crit); }
.node-annotation-flag { fill: var(--gray-500); stroke: var(--white); stroke-width: 1; }
.node-annotation-flag.sev-query { fill: var(--active); }
.node-annotation-flag.sev-risk { fill: var(--near); }
.node-annotation-flag.sev-logic { fill: var(--crit); }
.node-annotation-flag.sev-resolved { fill: var(--ok); }
.node.selected .node-rect { stroke: var(--accent); stroke-width: 3; filter: drop-shadow(0 3px 8px rgba(41,81,196,0.4)); }
.node.dimmed { opacity: 0.22; }
.node:hover .node-rect { filter: drop-shadow(0 2px 6px rgba(28,25,23,0.14)); }

.node-mile-icon { fill: var(--milestone); }
.node-rule { stroke: var(--gray-300); stroke-width: 1; }
.node-code { font-family: var(--font-mono); font-size: 12px; font-weight: 700; fill: var(--ink); letter-spacing: 0.02em; }
.node-duration { font-family: var(--font-mono); font-size: 11px; font-weight: 600; fill: var(--gray-700); }
.node-name { font-family: var(--font-ui); font-size: 13px; font-weight: 600; fill: var(--ink); }
.node-meta { font-family: var(--font-mono); font-size: 11px; fill: var(--gray-700); }
.node-meta.node-meta-neg { fill: var(--crit); font-weight: 700; }

.expand-btn circle { fill: var(--accent); opacity: 0.92; }
.expand-btn text { fill: var(--white); font-size: 12px; font-weight: 700; }
.expand-btn:hover circle { fill: var(--ink-soft); }

/* Wraps the canvas so the detail drawer anchors to exactly its bounds. */
.graph-body { position: relative; display: flex; align-items: stretch; }

@media print {
  @page { size: landscape; margin: 10mm; }
  .graph-strip, .graph-toolbar { display: none; }
  .graph-wrap, .graph-wrap.is-fullscreen { border: none; box-shadow: none; height: auto; overflow: visible; display: block; }
  .graph-body { height: auto; }
  /* --print-w / --print-h are NOT design tokens: they are set per-render as an inline
     style on the wrapper (see :style in the template) from the chosen paper size, so
     they deliberately have no :root definition.
     Sized to the selected paper's usable area (a --print-w/-h CSS var set from the
     component) rather than the on-screen min(75vh,900px) — printGraph() already fit
     the diagram's scale/pan to those exact dimensions before calling window.print(). */
  /* Overrides the on-screen height for print —
     app's default (header collapsed), and that on-screen rule would otherwise win
     over a plain .graph-canvas override here regardless of the media query. */
  .graph-wrap .graph-canvas { width: var(--print-w); height: var(--print-h); overflow: visible; background: none; }
  .expand-btn { display: none; }
}

</style>
