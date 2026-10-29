<template>
  <div class="vw" ref="root">
    <template v-if="views.length">
      <button aria-label="Previous view" class="vw-step" title="Previous view" :disabled="!canStep(-1)" @click="$emit('step', -1)">&lsaquo;</button>
      <select class="vw-select" :value="currentId || ''" title="Saved views" @change="pick">
        <option value="" disabled>Views ({{ views.length }})</option>
        <option v-for="(v, i) in views" :key="v.id" :value="v.id">{{ i + 1 }}. {{ v.name }}</option>
      </select>
      <button aria-label="Next view" class="vw-step" title="Next view" :disabled="!canStep(1)" @click="$emit('step', 1)">&rsaquo;</button>
    </template>
    <div class="vw-pop">
      <button class="vw-open" :class="{ active: open }" :title="views.length ? 'Save or manage views' : 'Save this chart as a view'" @click="open = !open"><Icon name="bookmark" :size="14" /><span v-if="!views.length">Save view</span></button>
      <div v-if="open" class="vw-panel popover popover-below popover-end">
        <form class="vw-row" @submit.prevent="save">
          <input v-model="draft" class="vw-name" placeholder="Name the current chart, e.g. Roof delay" maxlength="50" />
          <button class="btn-tiny-light" type="submit" :disabled="!draft.trim()">Save</button>
        </form>
        <p v-if="!views.length" class="vw-hint">A view keeps the zoom, scroll, expanded WBS, filters, chain trace, overlays and highlights. Step through saved views with ‹ › like slides.</p>
        <div v-for="(v, i) in views" :key="v.id" class="vw-row">
          <span class="vw-n">{{ i + 1 }}</span>
          <input class="vw-name" :value="v.name" maxlength="50" @change="$emit('rename', v.id, ($event.target as HTMLInputElement).value)" />
          <button class="btn-tiny-light" title="Replace this view with the chart as it is now" @click="$emit('update', v.id)">Update</button>
          <button aria-label="Remove" class="vw-x" title="Remove" @click="$emit('remove', v.id)">&times;</button>
        </div>
        <p class="vw-hint">Saved in this browser for this project.</p>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, type PropType } from 'vue'
import { stepView, type SavedView } from '../utils/views'
import Icon from './Icon.vue'

export default defineComponent({
  name: 'GanttViewBar',
  components: { Icon },
  props: {
    views: { type: Array as PropType<SavedView[]>, required: true },
    currentId: { type: String as PropType<string | null>, default: null },
  },
  emits: ['apply', 'step', 'save', 'update', 'rename', 'remove'],
  data() {
    return { open: false, draft: '' }
  },
  mounted() {
    document.addEventListener('mousedown', this.onDocMousedown)
  },
  beforeUnmount() {
    document.removeEventListener('mousedown', this.onDocMousedown)
  },
  methods: {
    canStep(dir: 1 | -1): boolean {
      return !!stepView(this.views, this.currentId, dir)
    },
    pick(e: Event) {
      const id = (e.target as HTMLSelectElement).value
      if (id) this.$emit('apply', id)
    },
    save() {
      const name = this.draft.trim()
      if (!name) return
      this.$emit('save', name)
      this.draft = ''
    },
    onDocMousedown(e: MouseEvent) {
      if (this.open && !(this.$refs.root as HTMLElement).contains(e.target as Node)) this.open = false
    },
  },
})
</script>

<style scoped>
.vw { margin-left: auto; display: flex; align-items: center; gap: 4px; }
.vw-step { border: 1px solid var(--gray-300); background: var(--panel); color: var(--ink-2); border-radius: var(--radius-sm); width: 24px; height: 24px; font-size: 16px; line-height: 1; cursor: pointer; }
.vw-step:disabled { opacity: 0.35; cursor: default; }
.vw-step:hover:not(:disabled) { border-color: var(--accent); color: var(--accent); }
.vw-select { height: 24px; max-width: 132px; padding: 0 4px; border: 1px solid var(--gray-300); border-radius: var(--radius-sm); font: var(--text-small); background: var(--white); color: var(--ink); }
.vw-pop { position: relative; }
.vw-open { height: 26px; min-width: 26px; display: inline-flex; align-items: center; gap: 5px; padding: 0 6px; border: 1px solid transparent; border-radius: var(--radius-sm); background: none; color: var(--ink-2); cursor: pointer; font: var(--text-small); }
.vw-open:hover { border-color: var(--gray-300); background: var(--panel); color: var(--ink); }
.vw-open.active { border-color: var(--accent); color: var(--accent); background: var(--accent-soft); }
.vw-panel { --pop-min: 380px; display: flex; flex-direction: column; gap: 6px; }
.vw-row { display: flex; align-items: center; gap: 5px; margin: 0; }
.vw-n { font-family: var(--font-mono); font-size: 11px; color: var(--ink-3); width: 16px; text-align: right; }
.vw-name { flex: 1; min-width: 0; padding: 3px 6px; border: 1px solid var(--gray-300); border-radius: var(--radius-sm); font: var(--text-small); background: var(--white); color: var(--ink); }
.vw-x { border: none; background: none; cursor: pointer; color: var(--ink-3); font-size: 15px; line-height: 1; padding: 0 3px; }
.vw-x:hover { color: var(--crit); }
.vw-hint { margin: 0; font: var(--text-small); color: var(--ink-3); max-width: 380px; }
</style>
