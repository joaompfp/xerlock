<template>
  <!-- Every filter sits on this one row, and a control that is narrowing the view is
       drawn in the accent colour, so a filtered chart can't be read as the whole programme.
       The default slot carries what else shares the row (trace, views, count). -->
  <div class="filter-strip">
    <input type="text" :value="filter.text" class="filter-input fb-search" :class="{ set: filter.text.trim() }" placeholder="Search…" title="Search activity code, name or WBS path" @input="set('text', ($event.target as HTMLInputElement).value)" />
    <select :value="filter.status" class="fb-select" :class="{ set: filter.status }" title="Status" @change="set('status', ($event.target as HTMLSelectElement).value)">
      <option value="">Status</option>
      <option v-for="(label, value) in STATUS_LABELS" :key="value" :value="value">{{ label }}</option>
    </select>
    <select :value="filter.constraint" class="fb-select" :class="{ set: filter.constraint }" title="Constraint" @change="set('constraint', ($event.target as HTMLSelectElement).value)">
      <option value="">Constraint</option>
      <option v-for="o in constraintOptions" :key="o.value" :value="o.value" :disabled="o.count === 0">{{ o.label }} ({{ o.count }})</option>
    </select>
    <select :value="filter.notes" class="fb-select" :class="{ set: filter.notes }" title="Your review notes (the dot after an activity's name)" @change="set('notes', ($event.target as HTMLSelectElement).value as NoteFilter)">
      <option value="">Notes</option>
      <option v-for="o in noteOptions" :key="o.value" :value="o.value" :disabled="o.count === 0">{{ o.label }} ({{ o.count }})</option>
    </select>
    <button class="tb-chip" :class="{ on: filter.criticalOnly }" @click="set('criticalOnly', !filter.criticalOnly)" title="Critical activities only, on the current basis"><i></i>Critical only</button>
    <span class="fb-dates" :class="{ set: filter.from || filter.to }" title="Date window: activities touching it">
      <input type="date" :value="filter.from" class="filter-date" aria-label="From" @input="set('from', ($event.target as HTMLInputElement).value)" />
      <span class="fb-dash">–</span>
      <input type="date" :value="filter.to" class="filter-date" aria-label="To" @input="set('to', ($event.target as HTMLInputElement).value)" />
    </span>
    <template v-if="dataDate">
      <button v-for="d in LOOK_AHEAD_DAYS" :key="d" class="btn-tiny-light la-btn" :class="{ active: lookAheadActive(filter, dataDate, d) }" :title="`Data date + ${d / 7} weeks`" @click="update(toggleLookAhead(filter, dataDate, d))">{{ d / 7 }} wk</button>
    </template>
    <select v-if="codeTypes.length" class="fb-select" title="P6 activity codes, read verbatim from this file's ACTVTYPE table" @change="addCode">
      <option value="">Activity code</option>
      <optgroup v-for="t in codeTypes" :key="t" :label="t">
        <option v-for="c in codeValues.get(t)" :key="c" :value="JSON.stringify([t, c])">{{ c }}</option>
      </optgroup>
    </select>
    <button v-for="[type, code] in activeCodes(filter)" :key="type" class="fs-chip" @click="update(withoutChip(filter, 'code:' + type))" :title="`Remove: ${type}: ${code}`">
      {{ type }}: {{ code }}<span class="fs-x">&times;</span>
    </button>
    <button v-if="isFilterSet(filter)" class="btn-tiny-light" @click="$emit('clear')">Clear</button>
    <slot />
  </div>
</template>

<script lang="ts">
import { defineComponent, type PropType } from 'vue'
import type { Activity } from '../types/schedule'
import type { Annotations, NoteFilter } from '../utils/annotations'
import {
  STATUS_LABELS, LOOK_AHEAD_DAYS, activeCodes, isFilterSet, withoutChip, lookAheadActive, toggleLookAhead,
  constraintOptions, noteOptions, codeValuesByType, type GanttFilter,
} from '../utils/ganttFilter'

export default defineComponent({
  name: 'GanttFilterBar',
  props: {
    filter: { type: Object as PropType<GanttFilter>, required: true },
    activities: { type: Array as PropType<Activity[]>, required: true },
    annotations: { type: Object as PropType<Annotations>, required: true },
    /** The file's activity code types; empty when it has none. */
    codeTypes: { type: Array as PropType<string[]>, required: true },
    dataDate: { type: String as PropType<string | null>, default: null },
  },
  emits: ['update:filter', 'clear'],
  data() {
    return { STATUS_LABELS, LOOK_AHEAD_DAYS }
  },
  computed: {
    constraintOptions() { return constraintOptions(this.activities) },
    noteOptions() { return noteOptions(this.activities, this.annotations) },
    codeValues(): Map<string, string[]> { return codeValuesByType(this.activities, this.codeTypes) },
  },
  methods: {
    activeCodes,
    isFilterSet,
    withoutChip,
    lookAheadActive,
    toggleLookAhead,
    update(f: GanttFilter) {
      this.$emit('update:filter', f)
    },
    set<K extends keyof GanttFilter>(key: K, value: GanttFilter[K]) {
      this.update({ ...this.filter, [key]: value })
    },
    // The code picker is a one-shot menu: a pick sets that category's filter (shown as a
    // chip beside it) and the menu returns to its prompt for the next pick.
    addCode(e: Event) {
      const sel = e.target as HTMLSelectElement
      if (sel.value) {
        const [type, code] = JSON.parse(sel.value) as [string, string]
        this.update({ ...this.filter, codes: { ...this.filter.codes, [type]: code } })
      }
      sel.value = ''
    },
  },
})
</script>

<style scoped>
.filter-strip { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; min-height: 34px; padding: 5px var(--space-4); background: var(--panel-2); border-bottom: 1px solid var(--line); }
.fs-chip { display: inline-flex; align-items: center; gap: 6px; border: 1px solid var(--accent); background: var(--accent-soft); color: var(--accent); border-radius: 14px; padding: 2px 5px 2px 10px; cursor: pointer; font: var(--text-small); font-weight: 600; }
.fs-chip:hover { background: var(--panel); }
.fs-x { font-size: 14px; line-height: 1; opacity: 0.75; }
.filter-input { padding: 6px 12px; border: 1px solid var(--gray-300); border-radius: var(--radius-sm); font: var(--text-small); width: 240px; background: var(--white); color: var(--ink); }
.filter-strip .fb-search { width: 124px; padding: 3px 8px; }
.filter-strip .fb-select { height: 26px; padding: 0 4px; border: 1px solid var(--gray-300); border-radius: var(--radius-sm); font: var(--text-small); background: var(--white); color: var(--ink-2); max-width: 118px; }
.filter-strip .fb-select.set { max-width: 180px; }
.filter-strip .tb-chip { padding: 3px 9px; }
.fb-dates { display: inline-flex; align-items: center; gap: 2px; }
.filter-date { border: 1px solid var(--gray-300); border-radius: var(--radius-sm); padding: 4px 6px; background: var(--white); font-family: var(--font-mono); font-size: 12px; color: var(--ink); }
.filter-strip .fb-dates .filter-date { height: 26px; box-sizing: border-box; padding: 0 2px; width: 108px; font-size: 11px; }
.fb-dash { color: var(--ink-3); }
.filter-strip .set, .fb-dates.set .filter-date { border-color: var(--accent); background: var(--accent-soft); color: var(--accent); font-weight: 600; }
.filter-strip .la-btn { padding: 3px 7px; }
.la-btn.active { background: var(--accent-soft); border-color: var(--accent); color: var(--accent); font-weight: 700; }
</style>
