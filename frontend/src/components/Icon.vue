<template>
  <svg class="icon" :width="size" :height="size" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <path :d="paths[name]" />
  </svg>
</template>

<script lang="ts">
import { defineComponent, type PropType } from 'vue'

// A handful of line icons for the Gantt toolbar, drawn on a 24-unit grid in the stroke
// of the surrounding text. Kept to one path each, so an icon is a single line here.
const PATHS = {
  'zoom-in': 'M10.5 4a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13zM20 20l-4.9-4.9M10.5 7.5v6M7.5 10.5h6',
  'zoom-out': 'M10.5 4a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13zM20 20l-4.9-4.9M7.5 10.5h6',
  fit: 'M3 12h18M7 8l-4 4 4 4M17 8l4 4-4 4',
  'expand-all': 'M7 5l5 5 5-5M7 13l5 5 5-5',
  'collapse-all': 'M7 11l5-5 5 5M7 19l5-5 5 5',
  'level-down': 'M7 9l5 5 5-5',
  'level-up': 'M7 15l5-5 5 5',
  link: 'M10 14a4.5 4.5 0 0 0 6.4 0l3-3a4.5 4.5 0 0 0-6.4-6.4l-1.2 1.2M14 10a4.5 4.5 0 0 0-6.4 0l-3 3a4.5 4.5 0 0 0 6.4 6.4l1.2-1.2',
  progress: 'M12 3v4l-5 4 7 3-2 3v4',
  baseline: 'M4 6h11v4H4zM9 14h11v4H9z',
  slip: 'M4 8v8M4 12h15M15 8l4 4-4 4',
  flag: 'M5 21V4M5 4h12l-2.5 4L17 12H5',
  pencil: 'M4 20h4L19 9l-4-4L4 16zM13 7l4 4',
  text: 'M5 7V5h14v2M12 5v14M9 19h6',
  today: 'M12 4a8 8 0 1 0 0 16 8 8 0 0 0 0-16zM12 2v4M12 18v4M2 12h4M18 12h4',
  fullscreen: 'M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5',
  print: 'M7 9V3h10v6M7 17H4v-7h16v7h-3M7 14h10v7H7z',
  bookmark: 'M6 3h12v18l-6-4-6 4z',
} as const

export type IconName = keyof typeof PATHS

export default defineComponent({
  name: 'Icon',
  props: {
    name: { type: String as PropType<IconName>, required: true },
    size: { type: Number, default: 15 },
  },
  data() {
    return { paths: PATHS as Record<string, string> }
  },
})
</script>

<style scoped>
.icon { flex-shrink: 0; display: block; }
</style>
