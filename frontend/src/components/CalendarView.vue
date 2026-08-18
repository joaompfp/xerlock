<template>
  <div class="cal-wrap">
    <div class="cal-strip">
      <div class="strip-title">
        <h2>Calendars</h2>
        <span class="strip-sub">{{ calendars.length }} in file &middot; work patterns and exceptions exactly as exported — check for stripped holidays or invented workdays</span>
      </div>
    </div>

    <div v-if="calendars.length === 0" class="empty-state">This file carries no CALENDAR table.</div>

    <div v-else class="cal-body">
      <!-- Calendar register -->
      <div class="cal-list">
        <button
          v-for="c in calendars"
          :key="c.clndr_id"
          class="cal-card"
          :class="{ active: c.clndr_id === selectedId }"
          @click="selectedId = c.clndr_id"
        >
          <div class="cal-card-top">
            <span class="cal-name">{{ c.clndr_name || '(unnamed)' }}</span>
            <span v-if="c.default_flag" class="cal-badge cal-default">default</span>
          </div>
          <div class="cal-card-meta">
            <span class="cal-badge">{{ typeLabel(c.clndr_type) }}</span>
            <span class="cal-meta-item">{{ c.day_hr_cnt }}h/day</span>
            <span class="cal-meta-item">{{ workdaysPerWeek(c) }}d/wk</span>
            <span class="cal-meta-item" :class="{ 'cal-unused': !c.assigned_count }">
              {{ c.assigned_count ? c.assigned_count + ' activities' : 'unused' }}
            </span>
          </div>
        </button>
      </div>

      <!-- Month browser -->
      <div v-if="selected" class="cal-detail">
        <div class="cal-nav">
          <button class="cal-nav-btn" @click="shiftMonth(-1)" title="Previous month">&lsaquo;</button>
          <span class="cal-month-label">{{ monthLabel }}</span>
          <button class="cal-nav-btn" @click="shiftMonth(1)" title="Next month">&rsaquo;</button>
          <button v-if="dataDate" class="cal-jump" @click="goToDataDate">Data date</button>
          <span class="cal-pattern-sum">{{ patternSummary }}</span>
        </div>

        <div class="cal-grid">
          <div v-for="d in dayHeaders" :key="d" class="cal-head-cell">{{ d }}</div>
          <div
            v-for="cell in monthCells"
            :key="cell.key"
            class="cal-cell"
            :class="[cell.cls, { 'cal-other': !cell.inMonth, 'cal-datadate': cell.isDataDate }]"
            :title="cell.tip"
          >
            <span class="cal-day-num">{{ cell.day }}</span>
            <span v-if="cell.hours" class="cal-day-hrs">{{ cell.hours }}</span>
            <span v-if="cell.cls === 'cal-workexc'" class="cal-flag">!</span>
          </div>
        </div>

        <div class="cal-legend">
          <span><i class="lg lg-work"></i> Working day</span>
          <span><i class="lg lg-nonwork"></i> Non-working</span>
          <span><i class="lg lg-holiday"></i> Holiday exception</span>
          <span><i class="lg lg-workexc"></i> Working exception <em>(works a normally non-working day — verify!)</em></span>
        </div>

        <!-- Exception register -->
        <div class="cal-exceptions">
          <h3>Exceptions <em>({{ selected.exceptions.length }})</em></h3>
          <div v-if="selected.exceptions.length === 0" class="empty-state">✓ No exceptions — the weekly pattern applies year-round (also worth questioning: no public holidays modelled?).</div>
          <table v-else class="data-table exc-table">
            <thead><tr><th>Date</th><th>Weekday</th><th>Type</th><th>Hours</th></tr></thead>
            <tbody>
              <tr v-for="e in selected.exceptions" :key="e.date" :class="{ 'exc-unusual': isWorkingException(e) }">
                <td class="num-cell mono">{{ formatDate(e.date) }}</td>
                <td>{{ weekdayName(e.date) }}</td>
                <td>
                  <span class="issue-badge" :class="isWorkingException(e) ? 'issue-severe' : 'issue-warn'">
                    {{ isWorkingException(e) ? 'Working exception' : 'Non-working (holiday)' }}
                  </span>
                </td>
                <td class="mono">{{ periodsText(e.periods) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { formatDate } from '../utils/format'

// P6 weekday keys are 1..7 = Sunday..Saturday; the grid displays Monday-first.
const P6_KEY_BY_JSDAY = { 0: '1', 1: '2', 2: '3', 3: '4', 4: '5', 5: '6', 6: '7' }
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
const WEEKDAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']

export default {
  name: 'CalendarView',
  props: {
    data: { type: Object, required: true },
  },
  data() {
    const dd = this.data.project.data_date ? new Date(this.data.project.data_date) : new Date(2000, 0, 1)
    return {
      selectedId: this.data.calendars?.[0]?.clndr_id ?? null,
      viewYear: dd.getFullYear(),
      viewMonth: dd.getMonth(),
      dayHeaders: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
    }
  },
  computed: {
    calendars() {
      return this.data.calendars || []
    },
    selected() {
      return this.calendars.find(c => c.clndr_id === this.selectedId) || null
    },
    dataDate() {
      return this.data.project.data_date ? this.data.project.data_date.slice(0, 10) : null
    },
    excByDate() {
      const m = new Map()
      for (const e of this.selected?.exceptions || []) m.set(e.date, e)
      return m
    },
    monthLabel() {
      return `${MONTHS[this.viewMonth]} ${this.viewYear}`
    },
    patternSummary() {
      if (!this.selected) return ''
      const days = this.workdaysPerWeek(this.selected)
      return `${days}-day week · ${this.selected.day_hr_cnt}h/day · ${this.selected.exceptions.length} exception${this.selected.exceptions.length === 1 ? '' : 's'}`
    },
    monthCells() {
      if (!this.selected) return []
      const first = new Date(this.viewYear, this.viewMonth, 1)
      // Monday-first offset: JS getDay() 0=Sun..6=Sat → Mon=0 … Sun=6
      const lead = (first.getDay() + 6) % 7
      const start = new Date(this.viewYear, this.viewMonth, 1 - lead)
      const cells = []
      for (let i = 0; i < 42; i++) {
        const d = new Date(start.getFullYear(), start.getMonth(), start.getDate() + i)
        const iso = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
        const exc = this.excByDate.get(iso)
        const weekPeriods = this.selected.weekdays[P6_KEY_BY_JSDAY[d.getDay()]] || []
        let cls, periods
        if (exc) {
          periods = exc.periods
          // A working exception on a day the weekly pattern already works is just an
          // hours override; on a pattern non-working day it's the suspicious case.
          if (periods.length > 0) cls = weekPeriods.length > 0 ? 'cal-work' : 'cal-workexc'
          else cls = 'cal-holiday'
        } else {
          periods = weekPeriods
          cls = periods.length > 0 ? 'cal-work' : 'cal-nonwork'
        }
        const hours = periods.length ? this.periodHours(periods) : ''
        cells.push({
          key: iso,
          day: d.getDate(),
          inMonth: d.getMonth() === this.viewMonth,
          isDataDate: iso === this.dataDate,
          cls,
          hours,
          tip: periods.length ? periods.map(p => `${p.start}–${p.finish}`).join(', ') : (exc ? 'Exception: non-working' : 'Non-working'),
        })
      }
      return cells
    },
  },
  methods: {
    formatDate,
    typeLabel(t) {
      return { CA_Base: 'Global', CA_Project: 'Project', CA_Rsrc: 'Resource' }[t] || t
    },
    workdaysPerWeek(c) {
      return Object.values(c.weekdays).filter(p => p.length > 0).length
    },
    periodHours(periods) {
      let mins = 0
      for (const p of periods) {
        const [sh, sm] = p.start.split(':').map(Number)
        const [fh, fm] = p.finish.split(':').map(Number)
        mins += fh * 60 + fm - (sh * 60 + sm)
      }
      const h = mins / 60
      return h === Math.round(h) ? `${h}h` : `${h.toFixed(1)}h`
    },
    weekdayName(iso) {
      return WEEKDAYS[new Date(iso + 'T12:00:00').getDay()]
    },
    isWorkingException(e) {
      return e.periods.length > 0
    },
    periodsText(periods) {
      return periods.length ? periods.map(p => `${p.start}–${p.finish}`).join(', ') : '—'
    },
    shiftMonth(dir) {
      const d = new Date(this.viewYear, this.viewMonth + dir, 1)
      this.viewYear = d.getFullYear()
      this.viewMonth = d.getMonth()
    },
    goToDataDate() {
      if (!this.dataDate) return
      const d = new Date(this.dataDate + 'T12:00:00')
      this.viewYear = d.getFullYear()
      this.viewMonth = d.getMonth()
    },
  },
}
</script>

<style scoped>
.cal-wrap { display: flex; flex-direction: column; background: var(--white); border: 1px solid var(--gray-300); border-radius: var(--radius-md); overflow: hidden; }
.cal-strip { background: var(--ink); color: var(--white); padding: var(--space-3) var(--space-4); }
.strip-title { display: flex; align-items: baseline; gap: var(--space-3); flex-wrap: wrap; }
.strip-title h2 { font: var(--text-h2); margin: 0; }
.strip-sub { font: var(--text-small); color: var(--gray-300); }

.cal-body { display: grid; grid-template-columns: 300px 1fr; gap: 0; }
.empty-state { font: var(--text-small); color: var(--gray-700); padding: var(--space-4); }

.cal-list { border-right: 1px solid var(--gray-300); padding: var(--space-3); display: flex; flex-direction: column; gap: var(--space-2); align-content: start; }
.cal-card { text-align: left; background: var(--gray-100); border: 1px solid var(--gray-300); border-radius: var(--radius-sm); padding: var(--space-2) var(--space-3); cursor: pointer; }
.cal-card:hover { background: var(--gray-150); }
.cal-card.active { background: var(--active-soft); border-color: var(--active); }
.cal-card-top { display: flex; align-items: center; gap: var(--space-2); justify-content: space-between; }
.cal-name { font: var(--text-body); font-weight: 600; color: var(--ink); }
.cal-card-meta { display: flex; align-items: center; gap: var(--space-2); margin-top: 3px; flex-wrap: wrap; }
.cal-meta-item { font: var(--text-micro); color: var(--gray-700); font-family: var(--font-mono); }
.cal-unused { color: var(--near); font-style: italic; }
.cal-badge { font: var(--text-micro); padding: 0 6px; border-radius: var(--radius-sm); background: var(--gray-150); color: var(--gray-700); border: 1px solid var(--gray-300); }
.cal-default { background: var(--active-soft); color: var(--active); border-color: var(--active); }

.cal-detail { padding: var(--space-4); min-width: 0; }
.cal-nav { display: flex; align-items: center; gap: var(--space-3); margin-bottom: var(--space-3); flex-wrap: wrap; }
.cal-nav-btn { width: 30px; height: 30px; border: 1px solid var(--gray-300); background: var(--white); border-radius: var(--radius-sm); cursor: pointer; font-size: 17px; line-height: 1; color: var(--ink); }
.cal-nav-btn:hover { background: var(--gray-100); }
.cal-month-label { font: var(--text-h3); color: var(--ink); min-width: 150px; text-align: center; }
.cal-jump { font: var(--text-micro); border: 1px solid var(--gray-300); background: var(--gray-100); padding: 4px 10px; border-radius: var(--radius-sm); cursor: pointer; color: var(--gray-700); }
.cal-jump:hover { background: var(--gray-150); }
.cal-pattern-sum { font: var(--text-small); color: var(--gray-700); margin-left: auto; }

.cal-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 3px; max-width: 640px; }
.cal-head-cell { font: var(--text-micro); text-transform: uppercase; color: var(--gray-700); text-align: center; padding: 2px 0; }
.cal-cell { position: relative; min-height: 52px; border-radius: var(--radius-sm); border: 1px solid var(--gray-300); padding: 4px 6px; display: flex; flex-direction: column; justify-content: space-between; }
.cal-day-num { font: var(--text-small); font-family: var(--font-mono); color: var(--ink); }
.cal-day-hrs { font: var(--text-micro); font-family: var(--font-mono); color: var(--gray-700); align-self: flex-end; }
.cal-work { background: var(--white); }
.cal-nonwork { background: var(--gray-150); }
.cal-nonwork .cal-day-num { color: var(--gray-500); }
.cal-holiday { background: var(--near-tint); border-color: var(--near); }
.cal-holiday .cal-day-num { color: var(--near); font-weight: 700; }
.cal-workexc { background: var(--crit); border-color: var(--crit-deep); }
.cal-workexc .cal-day-num, .cal-workexc .cal-day-hrs { color: var(--white); font-weight: 700; }
.cal-flag { position: absolute; top: 2px; right: 5px; color: var(--white); font-weight: 800; }
.cal-other { opacity: 0.35; }
.cal-datadate { outline: 2px solid var(--active); outline-offset: -2px; }

.cal-legend { display: flex; gap: var(--space-4); flex-wrap: wrap; font: var(--text-micro); color: var(--gray-700); margin: var(--space-3) 0 var(--space-5); }
.cal-legend em { font-style: italic; color: var(--near); }
.lg { display: inline-block; width: 12px; height: 12px; border-radius: 2px; border: 1px solid var(--gray-300); vertical-align: -2px; margin-right: 4px; }
.lg-work { background: var(--white); }
.lg-nonwork { background: var(--gray-150); }
.lg-holiday { background: var(--near-tint); border-color: var(--near); }
.lg-workexc { background: var(--crit); border-color: var(--crit-deep); }

.cal-exceptions h3 { font: var(--text-h3); color: var(--ink); margin: 0 0 var(--space-2); }
.cal-exceptions h3 em { font-style: normal; color: var(--accent); font-family: var(--font-mono); }
.exc-table { width: 100%; border-collapse: collapse; font: var(--text-small); }
.exc-table th { text-align: left; font: var(--text-micro); text-transform: uppercase; color: var(--gray-700); background: var(--gray-100); border-bottom: 2px solid var(--gray-300); padding: var(--space-2) var(--space-3); }
.exc-table td { padding: 5px var(--space-3); border-bottom: 1px solid var(--gray-150); }
.exc-unusual td { background: var(--crit-tint, rgba(165,41,29,0.07)); }
.mono { font-family: var(--font-mono); }
.num-cell { white-space: nowrap; }
.issue-badge { font: var(--text-micro); padding: 1px 7px; border-radius: var(--radius-sm); font-weight: 600; }
.issue-severe { background: var(--crit); color: var(--white); }
.issue-warn { background: var(--near-tint); color: var(--near); }

@media (max-width: 900px) {
  .cal-body { grid-template-columns: 1fr; }
  .cal-list { border-right: none; border-bottom: 1px solid var(--gray-300); }
}
</style>
