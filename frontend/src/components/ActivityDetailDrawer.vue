<template>
  <!-- The one activity detail drawer, shared by Gantt, Critical Path, and Health Check.
       Layout/styles come from the global .detail-drawer system in App.vue; per-host
       behavior is props (visibleIds, showJump) and the #actions slot. -->
  <Transition name="detail-slide">
    <aside class="detail-drawer" v-if="activity">
      <div class="detail-header">
        <button class="detail-close" @click="$emit('close')" title="Close" aria-label="Close">&times;</button>
        <span class="detail-code">{{ activity.task_code }}</span>
        <h3 class="detail-name">{{ activity.task_name }}</h3>
        <div v-if="activity.wbs_path" class="detail-wbs-path">{{ activity.wbs_path }}</div>
        <slot name="actions"></slot>
        <button v-if="showJump" class="btn-tiny-light drawer-gantt" @click="$emit('jump', activity.task_id)">Show in Gantt ↗</button>
      </div>

      <div class="detail-stat-grid">
        <div class="stat-tile">
          <div class="stat-value">{{ formatHours(activity.duration_hrs, activity.calendar_hrs_per_day) }}</div>
          <div class="stat-label">Duration</div>
        </div>
        <div class="stat-tile" :class="floatTileClass(activity)">
          <div class="stat-value">{{ formatFloat(activity.total_float_hrs, activity.calendar_hrs_per_day) }}</div>
          <div class="stat-label">Float</div>
        </div>
        <div class="stat-tile">
          <div class="stat-value stat-value-date">{{ formatDate(displayStart(activity)) }}</div>
          <div class="stat-label">Start</div>
        </div>
        <div class="stat-tile">
          <div class="stat-value stat-value-date">{{ formatDate(displayEnd(activity)) }}</div>
          <div class="stat-label">Finish</div>
        </div>
        <div class="stat-tile">
          <div class="stat-value stat-status" :class="'status-' + activity.status">{{ statusLabel(activity.status) }}</div>
          <div class="stat-label">Status</div>
        </div>
        <div class="stat-tile">
          <div class="stat-value">{{ activity.pct_complete }}%</div>
          <div class="stat-progress"><div class="stat-progress-fill" :style="{ width: activity.pct_complete + '%' }"></div></div>
          <div class="stat-label">Complete</div>
        </div>
      </div>

      <!-- An imposed date is often the single fact explaining an activity's float —
           surface it here instead of making the reviewer hunt in the Health Check. -->
      <div v-if="activity.cstr_type" class="detail-constraint">
        <span class="constraint-label">Constraint</span>
        <strong>{{ cstrLabel(activity.cstr_type) }}</strong>
        <span v-if="activity.cstr_date">&middot; {{ formatDate(activity.cstr_date) }}</span>
        <template v-if="activity.cstr_type2">
          <span>&middot; plus {{ cstrLabel(activity.cstr_type2) }}</span>
          <span v-if="activity.cstr_date2">{{ formatDate(activity.cstr_date2) }}</span>
        </template>
      </div>

      <div class="detail-rels">
        <div v-for="side in relSides" :key="side.label" class="rel-section">
          <h4>{{ side.label }} <em>{{ side.items.length }}</em></h4>
          <div v-if="side.items.length === 0" class="rel-empty">None</div>
          <button v-for="p in side.items" :key="p.task_id" class="rel-item-btn" @click="$emit('select', p.task_id)">
            <div class="rel-item-row">
              <span class="rel-code">{{ p.activity ? p.activity.task_code : '?' + p.task_id }}</span>
              <span class="rel-item-name">{{ p.activity ? p.activity.task_name : '' }}</span>
              <span v-if="p.driving" class="rel-driving" title="This link controls the dates — P6's 'driving' relationship flag">Driving</span>
              <span v-if="visibleIds && !visibleIds.has(p.task_id)" class="rel-hidden">not shown</span>
            </div>
            <div class="rel-item-row rel-item-sub">
              <span class="rel-type">{{ relTypeLabel(p.type) }}</span>
              <template v-if="p.activity">
                <span class="rel-dates">{{ formatDate(displayStart(p.activity)) }} → {{ formatDate(displayEnd(p.activity)) }}</span>
                <span class="rel-dur">{{ formatHours(p.activity.duration_hrs, p.activity.calendar_hrs_per_day) }}</span>
              </template>
              <span v-if="p.lag_hrs" class="rel-lag">{{ formatLag(p.lag_hrs, activity.calendar_hrs_per_day) }} lag</span>
            </div>
          </button>
        </div>
      </div>

      <AnnotationEditor
        :key="activity.task_id"
        :annotation="annotations[activity.task_id] || null"
        @save="patch => $emit('annotate', activity.task_id, patch)"
        @remove="$emit('unannotate', activity.task_id)"
      />
    </aside>
  </Transition>
</template>

<script>
import { formatDate, formatHours, formatFloat, formatLag, statusLabel } from '../utils/format'
import { relTypeLabel, cstrLabel, displayStart, displayEnd } from '../utils/p6'
import AnnotationEditor from './AnnotationEditor.vue'

export default {
  name: 'ActivityDetailDrawer',
  components: { AnnotationEditor },
  props: {
    activity: { type: Object, default: null },
    // task_id → activity, for enriching predecessor/successor entries
    lookup: { type: Map, required: true },
    annotations: { type: Object, default: () => ({}) },
    // When set (Critical Path), rel entries absent from this set get a "not shown" badge
    visibleIds: { type: Set, default: null },
    showJump: { type: Boolean, default: false },
  },
  emits: ['close', 'select', 'jump', 'annotate', 'unannotate'],
  computed: {
    relSides() {
      const enrich = list => list.map(p => ({ ...p, activity: this.lookup.get(p.task_id) }))
      return [
        { label: 'Predecessors', items: enrich(this.activity?.predecessors || []) },
        { label: 'Successors', items: enrich(this.activity?.successors || []) },
      ]
    },
  },
  methods: {
    formatDate,
    formatHours,
    formatFloat,
    formatLag,
    statusLabel,
    relTypeLabel,
    cstrLabel,
    displayStart,
    displayEnd,
    // Same severity bands used everywhere else in the app.
    floatTileClass(a) {
      if (a.is_negative_float) return 'stat-tile-neg'
      if (a.total_float_hrs === 0) return 'stat-tile-crit'
      if (a.total_float_hrs != null && a.total_float_hrs <= 80) return 'stat-tile-near'
      return ''
    },
  },
}
</script>

<style scoped>
.rel-hidden { color: var(--gray-500); font: var(--text-micro); font-style: italic; }
.drawer-gantt { margin-top: var(--space-2); }
</style>
