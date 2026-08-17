<template>
  <div class="wbs-node">
    <div
      class="wbs-row"
      :class="{ stripe: index % 2 === 1, indented: level > 0 }"
      :style="{ paddingLeft: (level * 20 + 10) + 'px' }"
      @click="toggle"
    >
      <IconChevron v-if="node.children.length > 0" class="wbs-toggle" :expanded="expanded" />
      <span v-else class="wbs-toggle-spacer"></span>
      <span class="wbs-code">{{ node.wbs_short_name }}</span>
      <span class="wbs-full">{{ node.wbs_name }}</span>
      <span class="wbs-count">{{ node.activity_count }}</span>
    </div>
    <div v-if="expanded" class="wbs-children">
      <WBSNode
        v-for="(child, i) in node.children"
        :key="child.wbs_id"
        :node="child"
        :level="level + 1"
        :index="i"
      />
    </div>
  </div>
</template>

<script>
import IconChevron from './IconChevron.vue'

export default {
  name: 'WBSNode',
  components: { IconChevron },
  props: {
    node: Object,
    level: { type: Number, default: 0 },
    index: { type: Number, default: 0 },
  },
  data() {
    return { expanded: this.level < 2 }
  },
  methods: {
    toggle() {
      if (this.node.children.length > 0) this.expanded = !this.expanded
    },
  },
}
</script>

<style scoped>
.wbs-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 12px;
  border-bottom: 1px solid var(--gray-150);
  cursor: pointer;
  font: var(--text-body);
  transition: background 0.1s;
}
.wbs-row.stripe { background: var(--gray-100); }
.wbs-row.indented { border-left: 2px solid var(--gray-300); }
.wbs-row:hover { background: var(--accent-soft); }
.wbs-toggle { color: var(--gray-500); flex-shrink: 0; }
.wbs-toggle-spacer { width: 10px; flex-shrink: 0; }
.wbs-code { font-family: var(--font-mono); font-size: 12px; font-weight: 600; color: var(--ink); background: var(--gray-150); border-radius: var(--radius-sm); padding: 1px 6px; flex-shrink: 0; }
.wbs-full { color: var(--gray-700); flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.wbs-count { font: var(--text-micro); color: var(--gray-700); background: var(--gray-150); border-radius: var(--radius-sm); padding: 2px 6px; flex-shrink: 0; }
</style>
