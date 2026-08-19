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

      <!-- The driving chain, not two flat lists: what actually controls this
           activity's dates, in sequence, with the link type and lag per hop. -->
      <div class="detail-logic">
        <h4 class="logic-head">Driving chain</h4>
        <div class="chain">
          <template v-for="p in drivingPreds" :key="'dp' + p.task_id">
            <button class="chain-node" @click="$emit('select', p.task_id)">
              <span class="chain-code">{{ p.activity ? p.activity.task_code : '?' + p.task_id }}</span>
              <span class="chain-name">{{ p.activity ? p.activity.task_name : '' }}</span>
              <span v-if="p.activity" class="chain-float" :class="floatCellClass(p.activity)">{{ formatFloat(p.activity.total_float_hrs, p.activity.calendar_hrs_per_day) }}</span>
              <span v-if="visibleIds && !visibleIds.has(p.task_id)" class="rel-hidden">not shown</span>
            </button>
            <div class="chain-hop">
              <span class="hop-type">{{ relTypeLabel(p.type) }}</span>
              <span v-if="p.lag_hrs" class="hop-lag">{{ formatLag(p.lag_hrs, activity.calendar_hrs_per_day) }} lag</span>
            </div>
          </template>

          <div class="chain-node chain-current">
            <span class="chain-code">{{ activity.task_code }}</span>
            <span class="chain-name">{{ activity.task_name }}</span>
            <span class="chain-float" :class="floatCellClass(activity)">{{ formatFloat(activity.total_float_hrs, activity.calendar_hrs_per_day) }}</span>
          </div>

          <template v-for="sx in drivingSuccs" :key="'ds' + sx.task_id">
            <div class="chain-hop">
              <span class="hop-type">{{ relTypeLabel(sx.type) }}</span>
              <span v-if="sx.lag_hrs" class="hop-lag">{{ formatLag(sx.lag_hrs, activity.calendar_hrs_per_day) }} lag</span>
            </div>
            <button class="chain-node" @click="$emit('select', sx.task_id)">
              <span class="chain-code">{{ sx.activity ? sx.activity.task_code : '?' + sx.task_id }}</span>
              <span class="chain-name">{{ sx.activity ? sx.activity.task_name : '' }}</span>
              <span v-if="sx.activity" class="chain-float" :class="floatCellClass(sx.activity)">{{ formatFloat(sx.activity.total_float_hrs, sx.activity.calendar_hrs_per_day) }}</span>
              <span v-if="visibleIds && !visibleIds.has(sx.task_id)" class="rel-hidden">not shown</span>
            </button>
          </template>
        </div>
        <p v-if="!drivingPreds.length && !drivingSuccs.length" class="chain-none">
          No relationship explains this activity's dates. Progress recorded out of sequence
          leaves nothing driving it.
        </p>

        <div v-for="side in otherSides" :key="side.label" class="rel-section">
          <button class="rel-more" @click="open[side.key] = !open[side.key]" :aria-expanded="String(open[side.key])">
            <span class="chev" :class="{ open: open[side.key] }">&rsaquo;</span>
            {{ side.label }} <em>{{ side.items.length }}</em>
          </button>
          <template v-if="open[side.key]">
            <div v-if="side.items.length === 0" class="rel-empty">None</div>
            <button v-for="p in side.items" :key="side.key + p.task_id" class="rel-item-btn" @click="$emit('select', p.task_id)">
              <div class="rel-item-row">
                <span class="rel-code">{{ p.activity ? p.activity.task_code : '?' + p.task_id }}</span>
                <span class="rel-item-name">{{ p.activity ? p.activity.task_name : '' }}</span>
                <span v-if="visibleIds && !visibleIds.has(p.task_id)" class="rel-hidden">not shown</span>
              </div>
              <div class="rel-item-row rel-item-sub">
                <span class="rel-type">{{ relTypeLabel(p.type) }}</span>
                <template v-if="p.activity">
                  <span class="rel-dates">{{ formatDate(displayStart(p.activity)) }} → {{ formatDate(displayEnd(p.activity)) }}</span>
                </template>
                <span v-if="p.lag_hrs" class="rel-lag">{{ formatLag(p.lag_hrs, activity.calendar_hrs_per_day) }} lag</span>
              </div>
            </button>
          </template>
        </div>
      </div>

      <AnnotationEditor
        :key="activity.task_id"
        :annotation="annotations[activity.task_id] || null"
        :activity="activity"
        :project-name="projectName"
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
    projectName: { type: String, default: '' },
  },
  emits: ['close', 'select', 'jump', 'annotate', 'unannotate'],
  data() {
    return { open: { preds: false, succs: false } }
  },
  computed: {
    enrichedPreds() {
      return (this.activity?.predecessors || []).map(p => ({ ...p, activity: this.lookup.get(p.task_id) }))
    },
    enrichedSuccs() {
      return (this.activity?.successors || []).map(p => ({ ...p, activity: this.lookup.get(p.task_id) }))
    },
    drivingPreds() { return this.enrichedPreds.filter(p => p.driving) },
    drivingSuccs() { return this.enrichedSuccs.filter(p => p.driving) },
    otherSides() {
      return [
        { key: 'preds', label: 'Other predecessors', items: this.enrichedPreds.filter(p => !p.driving) },
        { key: 'succs', label: 'Other successors', items: this.enrichedSuccs.filter(p => !p.driving) },
      ]
    },
  },
  watch: {
    activity() { this.open = { preds: false, succs: false } },
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
    floatCellClass(a) {
      if (a.total_float_hrs == null) return ''
      if (a.total_float_hrs <= 0) return 'fl-crit'
      if (a.total_float_hrs <= 80) return 'fl-near'
      return ''
    },
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
.rel-hidden { color: var(--ink-3); font: var(--text-micro); font-style: italic; }
.drawer-gantt { margin-top: var(--space-2); }

.logic-head { font: var(--text-micro); text-transform: uppercase; letter-spacing: 0.06em; color: var(--ink-3); margin: 0 0 var(--space-2); }
.chain { display: flex; flex-direction: column; }
.chain-node { display: flex; align-items: baseline; gap: 7px; width: 100%; text-align: left; background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius-sm); padding: 6px 9px; cursor: pointer; }
.chain-node:hover { border-color: var(--accent); background: var(--accent-soft); }
/* The activity you are looking at, in place in its own chain. */
.chain-current { border-color: var(--crit); background: var(--crit-soft); cursor: default; }
.chain-current:hover { border-color: var(--crit); background: var(--crit-soft); }
.chain-code { font-family: var(--font-mono); font-size: 11px; font-weight: 700; color: var(--accent); flex: none; }
.chain-current .chain-code { color: var(--crit); }
.chain-name { flex: 1; font-size: 12px; color: var(--ink-2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.chain-current .chain-name { color: var(--ink); font-weight: 600; }
.chain-float { font-family: var(--font-mono); font-size: 11px; color: var(--ink-3); flex: none; }
.chain-float.fl-crit { color: var(--crit); font-weight: 700; }
.chain-float.fl-near { color: var(--near); font-weight: 600; }
/* The hop carries the link type and lag, so the chain reads as a sequence. */
.chain-hop { display: flex; align-items: center; gap: 6px; padding: 2px 0 2px 14px; position: relative; min-height: 20px; }
.chain-hop::before { content: ''; position: absolute; left: 6px; top: 0; bottom: 0; border-left: 1px solid var(--line); }
.hop-type { font-family: var(--font-mono); font-size: 10px; font-weight: 700; color: var(--ink-3); }
.hop-lag { font-family: var(--font-mono); font-size: 10px; color: var(--near); background: var(--near-soft); border-radius: 3px; padding: 0 5px; }
.chain-none { font: var(--text-small); color: var(--ink-3); margin: var(--space-2) 0 0; }

.rel-more { display: flex; align-items: center; gap: 6px; width: 100%; text-align: left; background: none; border: none; padding: 7px 0; cursor: pointer; font: var(--text-small); font-weight: 600; color: var(--ink-2); }
.rel-more em { font-style: normal; font-family: var(--font-mono); color: var(--ink-3); }
.rel-more .chev { transition: transform 0.15s; color: var(--ink-3); }
.rel-more .chev.open { transform: rotate(90deg); }
</style>
