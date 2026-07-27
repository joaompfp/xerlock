<template>
  <div class="wbs-node">
    <div class="wbs-row" :style="{ paddingLeft: (level * 20) + 'px' }" @click="toggle">
      <span class="wbs-toggle">{{ expanded ? '\u25BC' : '\u25B6' }}</span>
      <span class="wbs-name">{{ node.wbs_short_name }}</span>
      <span class="wbs-full">{{ node.wbs_name }}</span>
      <span class="wbs-count">{{ node.activity_count }} activities</span>
    </div>
    <div v-if="expanded" class="wbs-children">
      <WBSNode
        v-for="child in node.children"
        :key="child.wbs_id"
        :node="child"
        :level="level + 1"
      />
    </div>
  </div>
</template>

<script>
export default {
  name: 'WBSNode',
  props: {
    node: Object,
    level: { type: Number, default: 0 },
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
  padding: 6px 12px;
  border-bottom: 1px solid #f0f0f0;
  cursor: pointer;
  font-size: 13px;
  transition: background 0.1s;
}
.wbs-row:hover { background: #f5f6f8; }
.wbs-toggle { width: 14px; text-align: center; font-size: 10px; color: #888; flex-shrink: 0; }
.wbs-name { font-weight: 600; color: #1a1a2e; }
.wbs-full { color: #888; font-size: 12px; }
.wbs-count { margin-left: auto; font-size: 11px; color: #aaa; }
</style>
