<template>
  <!-- The XERlock mark: a magnifying glass whose lens is a padlock (read-only), with the
       schedule under review inside it; the last bar is the critical path. The one in-app
       definition: public/favicon.svg and docs/logo.svg are the same drawing as files.
       Strokes take currentColor, so the caller sets the ink; the lens is filled with the
       surface it sits on, so the bars read on light and dark backgrounds alike. Colours
       are set through CSS properties, not SVG attributes, so every engine resolves the
       theme variables the same way. -->
  <svg class="xl-mark" :width="size" :height="size" viewBox="0 0 32 32" fill="none" aria-hidden="true">
    <path class="ink" d="M9.6 10V6.6a4.4 4.4 0 0 1 8.8 0V10" stroke-width="2.4" stroke-linecap="round" />
    <circle class="ink" cx="14" cy="17" r="8.4" stroke-width="2.6" :style="{ fill: surface }" />
    <path class="ink" d="M20.2 23.2l7 7" stroke-width="3.2" stroke-linecap="round" />
    <rect class="bar" x="8.4" y="12.6" width="6.4" height="2.4" rx="1.2" />
    <rect class="bar" x="11" y="15.8" width="6.4" height="2.4" rx="1.2" />
    <rect class="bar crit" x="13.6" y="19" width="5.6" height="2.4" rx="1.2" />
  </svg>
</template>

<script lang="ts">
import { defineComponent } from 'vue'

export default defineComponent({
  name: 'XerlockMark',
  props: {
    size: { type: Number, default: 24 },
    /** CSS colour of the background behind the mark; fills the lens. */
    surface: { type: String, default: 'var(--bg)' },
  },
})
</script>

<style scoped>
.xl-mark { flex: none; }
.ink { stroke: currentColor; }
.bar { fill: var(--accent); }
.bar.crit { fill: var(--crit); }
</style>
