<template>
  <!-- One compact toolbar row, every control in sight: icons where the meaning is
       plain, a short word where it isn't. Grouped left to right as scale, structure,
       basis, overlays, markup, then the once-a-session actions. -->
  <div class="gantt-toolbar" ref="root">
    <div class="seg" role="group" aria-label="Scale">
      <button
        v-for="z in ZOOM_LEVELS"
        :key="z"
        :class="{ active: !zoomOverridden && zoom === z }"
        :title="zoomLabel(z)"
        @click="$emit('zoom-preset', z)"
      >{{ zoomLabel(z).charAt(0) }}</button>
    </div>
    <div class="seg" role="group" aria-label="Zoom">
      <button title="Zoom out" @click="$emit('zoom-out')"><Icon name="zoom-out" /></button>
      <button title="Fit to the available width" @click="$emit('fit')"><Icon name="fit" /></button>
      <button title="Zoom in" @click="$emit('zoom-in')"><Icon name="zoom-in" /></button>
    </div>

    <span class="tb-div"></span>

    <div class="seg" role="group" aria-label="WBS">
      <button title="Collapse all WBS" @click="$emit('wbs', 'collapse-all')"><Icon name="collapse-all" /></button>
      <button title="Collapse the deepest expanded WBS level" @click="$emit('wbs', 'collapse-level')"><Icon name="level-up" /></button>
      <button title="Expand one more WBS level" @click="$emit('wbs', 'expand-level')"><Icon name="level-down" /></button>
      <button title="Expand all WBS" @click="$emit('wbs', 'expand-all')"><Icon name="expand-all" /></button>
    </div>

    <div class="tb-group basis-group" title="Critical basis: total float ≤ 0, or the longest path">
      <button :class="{ active: basis === 'tf0' }" @click="$emit('update:basis', 'tf0')">TF &le; 0</button>
      <button :class="{ active: basis === 'longest' }" @click="$emit('update:basis', 'longest')">Longest</button>
    </div>

    <span class="tb-div"></span>

    <!-- Overlay chips: solid and in the accent colour when on, dashed when off. -->
    <button class="tb-chip" :class="{ on: showLinks }" title="Relationship lines" @click="$emit('update:showLinks', !showLinks)"><Icon name="link" :size="13" />Links</button>
    <select v-if="showLinks" :value="linksScope" class="tb-select" title="Which relationships to draw" @change="$emit('update:linksScope', ($event.target as HTMLSelectElement).value)">
      <option value="critical">Critical</option>
      <option value="all">All</option>
    </select>
    <button class="tb-chip" :class="{ on: showProgress }" title="Progress line through the data date" @click="$emit('update:showProgress', !showProgress)"><Icon name="progress" :size="13" />Progress</button>
    <button v-if="hasBaseline" class="tb-chip" :class="{ on: showBaseline }" title="Outlined bars at each activity's position in the earlier file loaded in Compare" @click="$emit('update:showBaseline', !showBaseline)"><Icon name="baseline" :size="13" />Compared</button>
    <button v-if="hasBaseline && showBaseline" class="tb-chip" :class="{ on: showSlipArrows }" title="An arrow under each moved activity, from its compared finish to its current one" @click="$emit('update:showSlipArrows', !showSlipArrows)"><Icon name="slip" :size="13" />Slip</button>

    <span class="tb-div"></span>

    <div class="tb-pop tb-markup">
      <button class="tb-chip" :class="{ on: showMarkup && hasMarkup }" :title="hasMarkup ? 'Show or hide your key dates, periods, highlights and text boxes' : 'Add key dates, periods and highlights'" @click="hasMarkup ? $emit('update:showMarkup', !showMarkup) : (markupOpen = !markupOpen)"><Icon name="flag" :size="13" />Key dates</button>
      <button class="tb-icon" :class="{ active: markupOpen }" title="Edit key dates, periods and highlights" @click="markupOpen = !markupOpen"><Icon name="pencil" :size="14" /></button>
      <button class="tb-icon" title="Add a text box to the chart" @click="$emit('add-text')"><Icon name="text" :size="14" /></button>
      <div v-if="markupOpen" class="tb-panel">
        <GanttMarkupPanel :markup="markup" :default-date="markupDefaultDate" @change="m => $emit('markup', m)" />
      </div>
    </div>

    <div class="tb-right">
      <button class="tb-icon" :disabled="!canScrollToToday" title="Scroll to today" @click="$emit('today')"><Icon name="today" :size="14" /></button>
      <button class="tb-icon" :class="{ active: fullscreen }" :title="fullscreen ? 'Exit fullscreen' : 'Fullscreen'" @click="$emit('fullscreen')"><Icon name="fullscreen" :size="14" /></button>
      <span class="tb-print">
        <button class="tb-icon" title="Print the chart as it is, fitted to the paper width" @click="$emit('print')"><Icon name="print" :size="14" /></button>
        <select :value="paper" class="tb-select tb-paper" title="Paper" @change="$emit('update:paper', ($event.target as HTMLSelectElement).value)">
          <option v-for="key in Object.keys(PAPER_SIZES)" :key="key" :value="key">{{ key.toUpperCase() }}</option>
        </select>
      </span>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, type PropType } from 'vue'
import type { Zoom } from '../utils/ganttGeometry'
import type { CriticalBasis } from '../utils/ganttRows'
import type { Markup } from '../utils/markup'
import { PAPER_SIZES } from '../utils/paper'
import GanttMarkupPanel from './GanttMarkupPanel.vue'
import Icon from './Icon.vue'

export type WbsAction = 'collapse-all' | 'collapse-level' | 'expand-level' | 'expand-all'

export default defineComponent({
  name: 'GanttToolbar',
  components: { GanttMarkupPanel, Icon },
  props: {
    zoom: { type: String as PropType<Zoom>, required: true },
    /** A continuous zoom is set, so no preset shows as chosen. */
    zoomOverridden: { type: Boolean, default: false },
    basis: { type: String as PropType<CriticalBasis>, required: true },
    showLinks: { type: Boolean, required: true },
    linksScope: { type: String, required: true },
    showProgress: { type: Boolean, required: true },
    /** A compared schedule is loaded: its Compared and Slip toggles are offered. */
    hasBaseline: { type: Boolean, default: false },
    showBaseline: { type: Boolean, default: true },
    showSlipArrows: { type: Boolean, default: false },
    markup: { type: Object as PropType<Markup>, required: true },
    showMarkup: { type: Boolean, required: true },
    markupDefaultDate: { type: String, required: true },
    canScrollToToday: { type: Boolean, default: false },
    fullscreen: { type: Boolean, default: false },
    paper: { type: String, required: true },
  },
  emits: [
    'zoom-preset', 'zoom-in', 'zoom-out', 'fit', 'wbs', 'add-text', 'markup', 'today', 'fullscreen', 'print',
    'update:basis', 'update:showLinks', 'update:linksScope', 'update:showProgress', 'update:showBaseline',
    'update:showSlipArrows', 'update:showMarkup', 'update:paper',
  ],
  data() {
    return {
      ZOOM_LEVELS: ['day', 'week', 'month', 'quarter'] as Zoom[],
      PAPER_SIZES,
      markupOpen: false,
    }
  },
  computed: {
    hasMarkup(): boolean {
      const m = this.markup
      return m.keyDates.length + m.periods.length + m.groups.length + m.texts.length > 0
    },
  },
  mounted() {
    document.addEventListener('mousedown', this.onDocMousedown)
  },
  beforeUnmount() {
    document.removeEventListener('mousedown', this.onDocMousedown)
  },
  methods: {
    zoomLabel(z: string): string {
      return z.charAt(0).toUpperCase() + z.slice(1)
    },
    onDocMousedown(e: MouseEvent) {
      if (this.markupOpen && !(e.target as Element).closest('.tb-pop')) this.markupOpen = false
    },
  },
})
</script>

<style scoped>
.gantt-toolbar { display: flex; align-items: center; gap: 5px; flex-wrap: wrap; padding: 7px var(--space-4); background: var(--panel); border-bottom: 1px solid var(--line); }
.tb-div { width: 1px; align-self: stretch; background: var(--line); margin: 0 2px; }
.tb-group { display: flex; align-items: center; gap: 4px; }
.tb-right { margin-left: auto; display: flex; align-items: center; gap: 6px; }

.tb-pop { position: relative; }
.tb-markup { display: flex; align-items: center; gap: 2px; }
/* Segmented groups: one bordered strip of equal, compact buttons. */
.seg { display: flex; border: 1px solid var(--gray-300); border-radius: var(--radius-sm); overflow: hidden; flex-shrink: 0; }
.seg button { height: 26px; min-width: 26px; padding: 0 7px; border: none; border-right: 1px solid var(--gray-300); background: var(--white); color: var(--gray-700); cursor: pointer; display: inline-flex; align-items: center; justify-content: center; font: var(--text-small); font-weight: 600; }
.seg button:last-child { border-right: none; }
.seg button:hover:not(.active) { background: var(--gray-150); color: var(--ink); }
.seg button.active { background: var(--accent-soft); color: var(--accent); font-weight: 700; }
/* Icon-only actions: borderless until hovered, so a row of them stays quiet. */
.tb-icon { width: 26px; height: 26px; display: inline-flex; align-items: center; justify-content: center; border: 1px solid transparent; border-radius: var(--radius-sm); background: none; color: var(--ink-2); cursor: pointer; padding: 0; }
.tb-icon:hover:not(:disabled) { border-color: var(--gray-300); background: var(--panel); color: var(--ink); }
.tb-icon.active { border-color: var(--accent); color: var(--accent); background: var(--accent-soft); }
.tb-icon:disabled { opacity: 0.35; cursor: default; }
.tb-select { height: 26px; padding: 0 3px; border: 1px solid var(--gray-300); border-radius: var(--radius-sm); font: var(--text-small); background: var(--white); color: var(--ink-2); }
.tb-print { display: inline-flex; align-items: center; gap: 2px; }
.tb-paper { width: 50px; }
.gantt-toolbar .tb-chip { padding: 4px 7px; }
.tb-panel { position: absolute; right: 0; top: calc(100% + 5px); min-width: 250px; background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius-md); box-shadow: 0 10px 30px -12px rgba(0,0,0,0.35); padding: var(--space-3); z-index: 12; display: flex; flex-direction: column; gap: 7px; }

.basis-group { display: flex; align-items: center; gap: 6px; border: 1px solid var(--ink-soft); border-radius: var(--radius-sm); padding: 2px; flex-shrink: 0; }
.basis-group button { padding: 4px 8px; border: none; border-radius: 3px; background: none; cursor: pointer; font: var(--text-small); color: var(--ink-2); }
.basis-group button.active { background: var(--crit); color: var(--on-solid); font-weight: 700; }
.basis-group button:hover:not(.active) { background: var(--ink-soft); }
</style>
