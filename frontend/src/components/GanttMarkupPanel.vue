<template>
  <div class="mk-panel">
    <section>
      <div class="mk-head">
        <span class="mk-title">Key dates</span>
        <button class="btn-tiny-light" @click="addKeyDate">+ Add</button>
      </div>
      <p v-if="!markup.keyDates.length" class="mk-empty">A thin line with its label in the header — client access, energisation, contract completion…</p>
      <div v-for="k in markup.keyDates" :key="k.id" class="mk-row">
        <button :aria-label="'Colour: ' + k.color + ' (click to change)'" class="mk-swatch" :class="'mk-' + k.color" :title="'Colour: ' + k.color + ' (click to change)'" @click="patchKeyDate(k.id, { color: nextColor(k.color) })"></button>
        <input class="mk-label" :value="k.label" placeholder="Label" maxlength="40" @input="patchKeyDate(k.id, { label: inputValue($event) })" />
        <DateField class="filter-date" :model-value="k.date" label="Key date (dd-mmm-yy)" @change="setKeyDateDate(k.id, $event)" />
        <button aria-label="Remove" class="mk-x" title="Remove" @click="removeKeyDate(k.id)">&times;</button>
      </div>
    </section>
    <section>
      <div class="mk-head">
        <span class="mk-title">Periods</span>
        <button class="btn-tiny-light" @click="addPeriod">+ Add</button>
      </div>
      <p v-if="!markup.periods.length" class="mk-empty">A faint band behind the bars — a shutdown, a permit window, a holiday…</p>
      <div v-for="p in markup.periods" :key="p.id" class="mk-row">
        <button :aria-label="'Colour: ' + p.color + ' (click to change)'" class="mk-swatch" :class="'mk-' + p.color" :title="'Colour: ' + p.color + ' (click to change)'" @click="patchPeriod(p.id, { color: nextColor(p.color) })"></button>
        <input class="mk-label" :value="p.label" placeholder="Label" maxlength="40" @input="patchPeriod(p.id, { label: inputValue($event) })" />
        <DateField class="filter-date" :model-value="p.from" label="Period from (dd-mmm-yy)" @change="setPeriodDate(p.id, 'from', $event)" />
        <span class="mk-dash">–</span>
        <DateField class="filter-date" :model-value="p.to" label="Period to (dd-mmm-yy)" @change="setPeriodDate(p.id, 'to', $event)" />
        <button aria-label="Remove" class="mk-x" title="Remove" @click="removePeriod(p.id)">&times;</button>
      </div>
    </section>
    <section>
      <div class="mk-head">
        <span class="mk-title">Highlights</span>
      </div>
      <p v-if="!markup.groups.length" class="mk-empty">A named set of activities in one colour; while it is on, everything else is dimmed. Start one from an activity's details (Highlight), or save a chain trace.</p>
      <div v-for="g in markup.groups" :key="g.id" class="mk-row">
        <input type="checkbox" :checked="g.on" :title="g.on ? 'Shown — click to hide' : 'Hidden — click to show'" @change="patchGroup(g.id, { on: !g.on })" />
        <button :aria-label="'Colour: ' + g.color + ' (click to change)'" class="mk-swatch" :class="'mk-' + g.color" :title="'Colour: ' + g.color + ' (click to change)'" @click="patchGroup(g.id, { color: nextColor(g.color) })"></button>
        <input class="mk-label" :value="g.label" placeholder="Label" maxlength="40" @input="patchGroup(g.id, { label: inputValue($event) })" />
        <span class="mk-count">{{ g.codes.length }} {{ g.codes.length === 1 ? 'activity' : 'activities' }}</span>
        <button aria-label="Remove" class="mk-x" title="Remove" @click="removeGroup(g.id)">&times;</button>
      </div>
    </section>
    <p class="mk-foot">Saved in this browser for this project.</p>
  </div>
</template>

<script lang="ts">
import { defineComponent, type PropType } from 'vue'
import { MARK_COLORS, newMarkId, nextColor, type HighlightGroup, type KeyDate, type Markup, type Period } from '../utils/markup'
import DateField from './DateField.vue'

export default defineComponent({
  name: 'GanttMarkupPanel',
  props: {
    markup: { type: Object as PropType<Markup>, required: true },
    /** Where a new key date or period starts: the data date, else today. */
    defaultDate: { type: String, required: true },
  },
  emits: ['change'],
  components: { DateField },
  methods: {
    nextColor,
    inputValue(e: Event): string {
      return (e.target as HTMLInputElement).value
    },
    emit(m: Partial<Markup>) {
      this.$emit('change', { ...this.markup, ...m })
    },
    // A new entry takes the next colour in the palette, so neighbours differ by default.
    freshColor(used: number) {
      return MARK_COLORS[used % MARK_COLORS.length]
    },
    addKeyDate() {
      const k: KeyDate = { id: newMarkId(), date: this.defaultDate, label: '', color: this.freshColor(this.markup.keyDates.length + 1) }
      this.emit({ keyDates: [...this.markup.keyDates, k] })
    },
    patchKeyDate(id: string, patch: Partial<KeyDate>) {
      this.emit({ keyDates: this.markup.keyDates.map(k => (k.id === id ? { ...k, ...patch } : k)) })
    },
    setKeyDateDate(id: string, v: string) {
      if (v) this.patchKeyDate(id, { date: v })
    },
    removeKeyDate(id: string) {
      this.emit({ keyDates: this.markup.keyDates.filter(k => k.id !== id) })
    },
    addPeriod() {
      const from = this.defaultDate
      const end = new Date(from + 'T12:00:00')
      end.setDate(end.getDate() + 13)
      const to = `${end.getFullYear()}-${String(end.getMonth() + 1).padStart(2, '0')}-${String(end.getDate()).padStart(2, '0')}`
      const p: Period = { id: newMarkId(), from, to, label: '', color: this.freshColor(this.markup.periods.length + 2) }
      this.emit({ periods: [...this.markup.periods, p] })
    },
    patchPeriod(id: string, patch: Partial<Period>) {
      this.emit({ periods: this.markup.periods.map(p => (p.id === id ? { ...p, ...patch } : p)) })
    },
    setPeriodDate(id: string, end: 'from' | 'to', v: string) {
      if (v) this.patchPeriod(id, { [end]: v })
    },
    removePeriod(id: string) {
      this.emit({ periods: this.markup.periods.filter(p => p.id !== id) })
    },
    patchGroup(id: string, patch: Partial<HighlightGroup>) {
      this.emit({ groups: this.markup.groups.map(g => (g.id === id ? { ...g, ...patch } : g)) })
    },
    removeGroup(id: string) {
      this.emit({ groups: this.markup.groups.filter(g => g.id !== id) })
    },
  },
})
</script>

<style scoped>
.mk-panel { display: flex; flex-direction: column; gap: 10px; min-width: min(460px, 100%); }
.mk-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px; }
.mk-title { font-family: var(--font-mono); font-size: 10px; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: var(--ink-3); }
.mk-empty { margin: 0; font: var(--text-small); color: var(--ink-3); max-width: 420px; }
.mk-row { display: flex; align-items: center; flex-wrap: wrap; gap: 5px; margin-top: 4px; }
.mk-swatch { width: 14px; height: 14px; border-radius: 50%; border: none; cursor: pointer; flex-shrink: 0; background: var(--mk); }
.mk-label { flex: 1; min-width: 90px; padding: 3px 6px; border: 1px solid var(--gray-300); border-radius: var(--radius-sm); font: var(--text-small); background: var(--white); color: var(--ink); }
.mk-row .filter-date { padding: 2px 3px; width: 132px; }
.mk-dash { color: var(--ink-3); }
.mk-x { border: none; background: none; cursor: pointer; color: var(--ink-3); font-size: 15px; line-height: 1; padding: 0 3px; }
.mk-x:hover { color: var(--crit); }
.mk-count { font: var(--text-small); color: var(--ink-3); white-space: nowrap; min-width: 84px; }
.mk-foot { margin: 0; font: var(--text-micro); color: var(--ink-3); }
</style>
