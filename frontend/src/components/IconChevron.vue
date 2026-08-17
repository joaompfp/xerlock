<template>
  <svg class="icon-chevron" :class="{ expanded }" width="10" height="10" viewBox="0 0 12 12" fill="none">
    <path d="M4 2.5L8 6L4 9.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
  </svg>
</template>

<script>
export default {
  name: 'IconChevron',
  props: {
    expanded: { type: Boolean, default: false },
  },
}
</script>

<style scoped>
.icon-chevron { flex-shrink: 0; transition: transform 0.15s; }
.icon-chevron.expanded { transform: rotate(90deg); }
</style>
