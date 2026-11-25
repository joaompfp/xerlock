<template>
  <!-- A date input that always reads dd-mmm-yy. A native <input type="date"> prints its
       value in the browser's own locale (mm/dd/yyyy on an en-US machine), and no CSS can
       change that. So the visible text is ours and a transparent native input sits on top
       of it: a click still opens the browser's calendar, but the field never shows a
       locale-ordered date. The button carries the keyboard and screen-reader name. -->
  <span class="date-field" :class="{ empty: !modelValue }">
    <button
      type="button"
      class="df-display"
      :aria-label="label"
      :title="title || label"
      @keydown.enter.prevent="openPicker"
      @keydown.space.prevent="openPicker"
    >{{ modelValue ? formatDate(modelValue) : placeholder }}</button>
    <input
      ref="native"
      class="df-native"
      type="date"
      :value="modelValue || ''"
      tabindex="-1"
      aria-hidden="true"
      @input="emitValue"
    />
  </span>
</template>

<script lang="ts">
import { defineComponent } from 'vue'
import { formatDate } from '../utils/format'

export default defineComponent({
  name: 'DateField',
  props: {
    /** ISO day, 'YYYY-MM-DD', as the native input and the schedule store it. */
    modelValue: { type: String, default: '' },
    label: { type: String, required: true },
    title: { type: String, default: '' },
    /** Shown while empty; writes the shape the field prints once filled. */
    placeholder: { type: String, default: 'dd-mmm-yy' },
  },
  emits: ['update:modelValue', 'input', 'change'],
  methods: {
    formatDate,
    emitValue(e: Event) {
      const v = (e.target as HTMLInputElement).value
      this.$emit('update:modelValue', v)
      this.$emit('input', v)
      this.$emit('change', v)
    },
    openPicker() {
      const el = this.$refs.native as HTMLInputElement | undefined
      if (!el) return
      if (typeof el.showPicker === 'function') {
        try { el.showPicker(); return } catch { /* not allowed here; focus instead */ }
      }
      el.focus()
    },
  },
})
</script>

<style scoped>
.date-field { position: relative; display: inline-flex; align-items: center; box-sizing: border-box; }
.df-display {
  all: unset;
  box-sizing: border-box;
  width: 100%;
  height: 100%;
  display: inline-flex;
  align-items: center;
  font: inherit;
  color: inherit;
  cursor: pointer;
  white-space: nowrap;
}
.date-field.empty .df-display { color: var(--ink-3); }
.date-field:focus-within { outline: 2px solid var(--accent); outline-offset: 1px; }
.df-native { position: absolute; inset: 0; width: 100%; height: 100%; opacity: 0; border: 0; padding: 0; margin: 0; cursor: pointer; }
</style>
