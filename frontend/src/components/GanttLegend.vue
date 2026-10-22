<template>
  <!-- The bar encoding, stated once: in the sidebar beneath the navigation while the
       Gantt is open, and in place above the chart when it is fullscreen. -->
  <Teleport v-if="active" to="#sb-legend" defer :disabled="inline">
    <div class="sb-legend" :class="{ 'legend-inline': inline }">
      <div class="sb-legend-title">Legend</div>
      <div class="legend">
        <template v-if="basis === 'tf0'">
          <span class="legend-item"><i class="lg-bar lg-critical"></i>Critical (TF&le;0)</span>
          <span class="legend-item"><i class="lg-bar lg-near"></i>Near-critical</span>
          <span class="legend-item"><i class="lg-bar lg-normal"></i>Normal</span>
        </template>
        <template v-else>
          <span class="legend-item"><i class="lg-bar lg-critical"></i>On longest path</span>
          <span class="legend-item"><i class="lg-bar lg-normal"></i>Normal</span>
        </template>
        <span class="legend-item"><i class="lg-bar lg-negative"></i>Negative float</span>
        <span class="legend-item"><i class="diamond"></i>Milestone</span>
        <span class="legend-item"><i class="bar-wbs"></i>WBS rollup</span>
        <span class="legend-item" v-if="baseline"><i class="lg-bar lg-ghost"></i>Baseline</span>
      </div>
    </div>
  </Teleport>
</template>

<script lang="ts">
import { defineComponent, type PropType } from 'vue'
import type { CriticalBasis } from '../utils/ganttRows'

export default defineComponent({
  name: 'GanttLegend',
  props: {
    /** The Gantt is the open view (the sidebar slot is its to fill). */
    active: { type: Boolean, default: false },
    /** Fullscreen: the sidebar is hidden, so the legend stays in place. */
    inline: { type: Boolean, default: false },
    basis: { type: String as PropType<CriticalBasis>, required: true },
    /** Compared-schedule bars are drawn. */
    baseline: { type: Boolean, default: false },
  },
})
</script>

<style scoped>
.legend { display: grid; grid-template-columns: 1fr 1fr; gap: 6px 10px; align-items: center; }
.legend-item { display: flex; align-items: center; gap: 6px; font-size: 11px; line-height: 1.3; color: var(--nav-ink-2); white-space: nowrap; }
.sb-legend .lg-bar { width: 16px; }
.sb-legend { padding: 0 2px var(--space-3); margin-bottom: var(--space-3); border-bottom: 1px solid var(--nav-line); }
.sb-legend-title { font-family: var(--font-mono); font-size: 9px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.14em; color: var(--nav-ink-3); margin-bottom: 7px; }
.sb-legend .bar-wbs { background: var(--nav-ink-3); }
/* Fullscreen hides the sidebar, so the legend comes back as a row above the toolbar. */
.legend-inline { display: flex; align-items: center; gap: var(--space-3); padding: 6px var(--space-4); margin: 0; background: var(--panel-2); border-bottom: 1px solid var(--line); }
.legend-inline .sb-legend-title { margin: 0; color: var(--ink-3); }
.legend-inline .legend { display: flex; flex-wrap: wrap; gap: 14px; }
.legend-inline .legend-item { color: var(--gray-700); font: var(--text-small); }
.legend-inline .bar-wbs { background: var(--gray-700); }
/* Legend swatches ARE miniature bars — same fills and borders as the chart itself, so
   the legend teaches the encoding instead of adding a second one to decode. */
.lg-bar { width: 20px; height: 10px; border-radius: 3px; display: inline-block; box-sizing: border-box; border: 1.5px solid; }
.lg-critical { background: var(--crit-tint); border-color: var(--crit); }
.lg-near { background: var(--near-tint); border-color: var(--near); }
.lg-normal { background: var(--accent-soft); border-color: var(--accent); }
.lg-negative { background: repeating-linear-gradient(135deg, rgba(255,255,255,0.45) 0 2px, transparent 2px 5px), var(--crit); border-color: var(--crit-deep); }
.lg-ghost { background: transparent !important; border-color: var(--gray-500) !important; height: 5px !important; }
.diamond { width: 8px; height: 8px; background: var(--milestone); display: inline-block; transform: rotate(45deg); }
.bar-wbs { width: 16px; height: 7px; border-radius: 3px; background: var(--gray-700); display: inline-block; }
</style>
