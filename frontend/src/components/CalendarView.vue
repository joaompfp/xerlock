<template>
  <div class="cal-wrap">
    <div class="view-bar">
      <div class="strip-title">
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
          @click="selectedId = c.clndr_id; showAllActs = false"
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

        <div class="cal-main">
          <div class="cal-grid-col">
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

            <!-- Which months hold exceptions, and month navigation in one strip.
                 Replaces the register table: exceptions belong to the calendar. -->
            <div class="cal-year">
              <span class="cal-year-label">EXCEPTIONS {{ viewYear }}</span>
              <button
                v-for="m in yearMonths"
                :key="m.i"
                class="cal-year-month"
                :class="{ active: m.i === viewMonth }"
                :title="m.tip"
                @click="viewMonth = m.i"
              >
                <i :class="m.cls"></i><span>{{ m.label }}</span>
              </button>
              <span class="cal-year-sum">{{ yearSummary }}</span>
            </div>

            <div class="cal-legend">
              <span><i class="lg lg-work"></i> Working day</span>
              <span><i class="lg lg-nonwork"></i> Non-working</span>
              <span><i class="lg lg-holiday"></i> Holiday</span>
              <span><i class="lg lg-workexc"></i> Working exception</span>
            </div>
          </div>

          <!-- Exceptions live beside the calendar they belong to -->
          <aside class="cal-exc-panel">
            <div v-if="workingExceptions.length" class="cal-callout">
              <div class="cal-callout-head">WORKING EXCEPTIONS ({{ workingExceptions.length }})</div>
              <button v-for="e in workingExceptions" :key="e.date" class="cal-exc-row cal-exc-work" @click="goToDate(e.date)">
                <b>{{ formatDate(e.date) }}</b>
                <span>{{ periodsText(e.periods) }}</span>
              </button>
              <p class="cal-callout-note">date deliberately marked to work — often a worked holiday, verify</p>
            </div>

            <div class="cal-holidays">
              <div class="cal-panel-head">HOLIDAYS ({{ holidays.length }})</div>
              <div v-if="holidays.length === 0" class="cal-panel-empty">None modelled in this calendar.</div>
              <button v-for="e in holidays" :key="e.date" class="cal-exc-row" @click="goToDate(e.date)">
                <b>{{ formatDate(e.date) }}</b>
                <span>{{ weekdayName(e.date) }}</span>
              </button>
            </div>
          </aside>
        </div>

        <!-- Which activities actually run on this calendar -->
        <div class="cal-activities">
          <div class="cal-act-head">
            <h3>Activities on this calendar <em>({{ activitiesOnCalendar.length }})</em></h3>
            <button v-if="activitiesOnCalendar.length > ACT_PAGE" class="btn-tiny-light" @click="showAllActs = !showAllActs">
              {{ showAllActs ? 'Show fewer' : `Showing ${ACT_PAGE} of ${activitiesOnCalendar.length}` }}
            </button>
          </div>
          <div v-if="activitiesOnCalendar.length === 0" class="cal-panel-empty">No activity uses this calendar.</div>
          <div v-else class="cal-act-scroll">
          <table class="data-table act-table">
            <thead><tr>
              <th>Code</th><th>Activity</th><th>WBS</th>
              <th class="num">Dur</th><th class="num">Start</th><th class="num">Finish</th><th class="num">Float</th>
              <th>Exception in span</th>
            </tr></thead>
            <tbody>
              <tr v-for="a in visibleActivities" :key="a.task_id" class="jump-row" title="Show in Gantt" @click="$emit('jump', a.task_id)">
                <td class="code">{{ a.task_code }}</td>
                <td class="name-cell">{{ a.task_name }}</td>
                <td class="wbs-cell">{{ a.wbs_path }}</td>
                <td class="num-cell mono">{{ formatHours(a.duration_hrs, a.calendar_hrs_per_day) }}</td>
                <td class="num-cell mono">{{ formatDate(displayStart(a)) }}</td>
                <td class="num-cell mono">{{ formatDate(displayEnd(a)) }}</td>
                <td class="num-cell mono">{{ formatFloat(a.total_float_hrs, a.calendar_hrs_per_day) }}</td>
                <td class="mono cal-exc-span">
                  <span v-if="a.excInSpan" class="exc-hit">{{ formatDate(a.excInSpan) }}</span>
                  <span v-else class="cal-dash">—</span>
                </td>
              </tr>
            </tbody>
          </table>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { formatDate, formatHours, formatFloat } from '../utils/format'
import { displayStart, displayEnd } from '../utils/p6'

// P6 weekday keys are 1..7 = Sunday..Saturday; the grid displays Monday-first.
const P6_KEY_BY_JSDAY = { 0: '1', 1: '2', 2: '3', 3: '4', 4: '5', 5: '6', 6: '7' }
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
const WEEKDAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']

export default {
  name: 'CalendarView',
  props: {
    data: { type: Object, required: true },
  },
  emits: ['jump'],
  data() {
    const dd = this.data.project.data_date ? new Date(this.data.project.data_date) : new Date(2000, 0, 1)
    return {
      selectedId: this.data.calendars?.[0]?.clndr_id ?? null,
      viewYear: dd.getFullYear(),
      viewMonth: dd.getMonth(),
      dayHeaders: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
      showAllActs: false,
      ACT_PAGE: 10,
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
    workingExceptions() {
      return (this.selected?.exceptions || []).filter(e => e.periods.length > 0)
    },
    holidays() {
      return (this.selected?.exceptions || []).filter(e => e.periods.length === 0)
    },
    yearSummary() {
      const h = this.holidays.length
      const w = this.workingExceptions.length
      return `${h} holiday${h === 1 ? '' : 's'} · ${w} working exception${w === 1 ? '' : 's'}`
    },
    yearMonths() {
      const MON = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
      return MON.map((label, i) => {
        const inMonth = (this.selected?.exceptions || []).filter(
          e => +e.date.slice(0, 4) === this.viewYear && +e.date.slice(5, 7) - 1 === i)
        const work = inMonth.some(e => e.periods.length > 0)
        return {
          i, label,
          cls: work ? 'ym-work' : inMonth.length ? 'ym-holiday' : 'ym-none',
          tip: inMonth.length ? `${inMonth.length} exception${inMonth.length === 1 ? '' : 's'}` : 'No exceptions',
        }
      })
    },
    // The activities-per-calendar list is a client-side group-by on clndr_id, which
    // the parse already puts on every activity — no backend change.
    activitiesOnCalendar() {
      if (!this.selected) return []
      const excDates = (this.selected.exceptions || []).map(e => e.date)
      return this.data.activities
        .filter(a => a.clndr_id === this.selected.clndr_id)
        .map(a => {
          const s = (displayStart(a) || '').slice(0, 10)
          const e = (displayEnd(a) || s).slice(0, 10)
          // Flags an activity whose date range covers one of this calendar's
          // exceptions — where a stripped or worked holiday actually bites.
          const hit = s ? excDates.find(d => d >= s && d <= e) : null
          return { ...a, excInSpan: hit || null }
        })
        .sort((a, b) => (displayStart(a) || '').localeCompare(displayStart(b) || ''))
    },
    visibleActivities() {
      return this.showAllActs ? this.activitiesOnCalendar : this.activitiesOnCalendar.slice(0, this.ACT_PAGE)
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
          // Any dated exception that works is a deliberate author decision — often a
          // public holiday marked to be worked through — so it always gets the loud
          // treatment, matching the exception register below.
          cls = periods.length > 0 ? 'cal-workexc' : 'cal-holiday'
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
    formatHours,
    formatFloat,
    displayStart,
    displayEnd,
    goToDate(iso) {
      const d = new Date(iso + 'T12:00:00')
      this.viewYear = d.getFullYear()
      this.viewMonth = d.getMonth()
    },
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

.cal-detail { padding: var(--space-4); min-width: 0; overflow: hidden; }
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
.cal-workexc .cal-day-num, .cal-workexc .cal-day-hrs { color: var(--on-solid); font-weight: 700; }
.cal-flag { position: absolute; top: 2px; right: 5px; color: var(--on-solid); font-weight: 800; }
.cal-other { opacity: 0.35; }
.cal-datadate { outline: 2px solid var(--active); outline-offset: -2px; }

.cal-legend { display: flex; gap: var(--space-4); flex-wrap: wrap; font: var(--text-micro); color: var(--gray-700); margin: var(--space-3) 0 var(--space-5); }
.cal-legend em { font-style: italic; color: var(--near); }
.lg { display: inline-block; width: 12px; height: 12px; border-radius: 2px; border: 1px solid var(--gray-300); vertical-align: -2px; margin-right: 4px; }
.lg-work { background: var(--white); }
.lg-nonwork { background: var(--gray-150); }
.lg-holiday { background: var(--near-tint); border-color: var(--near); }
.lg-workexc { background: var(--crit); border-color: var(--crit-deep); }

/* ── Calendar detail: grid + exceptions beside it, activities below ───────── */
.cal-main { display: grid; grid-template-columns: minmax(0, 1fr) 236px; gap: var(--space-4); align-items: start; }
.cal-grid-col { min-width: 0; }

.cal-year { display: flex; align-items: center; gap: 3px; margin-top: var(--space-3); flex-wrap: wrap; }
.cal-year-label { font-family: var(--font-mono); font-size: 9px; font-weight: 600; letter-spacing: 0.1em; color: var(--ink-3); margin-right: var(--space-2); }
.cal-year-month { display: flex; flex-direction: column; align-items: center; gap: 3px; flex: 1; min-width: 34px; background: none; border: none; border-radius: var(--radius-sm); padding: 4px 2px; cursor: pointer; }
.cal-year-month:hover { background: var(--chip); }
.cal-year-month.active { background: var(--chip); }
.cal-year-month i { display: block; width: 100%; height: 4px; border-radius: 2px; }
.cal-year-month span { font-family: var(--font-mono); font-size: 10px; color: var(--ink-3); }
.cal-year-month.active span { color: var(--ink); font-weight: 600; }
.ym-none { background: var(--line); }
.ym-holiday { background: var(--near); }
.ym-work { background: var(--crit); }
.cal-year-sum { margin-left: auto; font-family: var(--font-mono); font-size: 10px; color: var(--ink-3); }

.cal-exc-panel { display: flex; flex-direction: column; gap: var(--space-3); }
.cal-callout { border: 1px solid var(--crit); background: var(--crit-soft); border-radius: var(--radius-md); padding: var(--space-2) var(--space-3); }
.cal-callout-head, .cal-panel-head { font-family: var(--font-mono); font-size: 9px; font-weight: 600; letter-spacing: 0.1em; color: var(--crit); margin-bottom: 4px; }
.cal-panel-head { color: var(--ink-3); }
.cal-callout-note { font: var(--text-micro); color: var(--crit); font-style: italic; margin-top: 4px; }
.cal-holidays { border: 1px solid var(--line); border-radius: var(--radius-md); padding: var(--space-2) var(--space-3); }
.cal-exc-row { display: flex; align-items: baseline; justify-content: space-between; gap: var(--space-2); width: 100%; background: none; border: none; border-radius: 4px; padding: 3px 4px; cursor: pointer; text-align: left; }
.cal-exc-row:hover { background: var(--panel); }
.cal-exc-row b { font-family: var(--font-mono); font-size: 11px; font-weight: 600; color: var(--ink); }
.cal-exc-row span { font-family: var(--font-mono); font-size: 10px; color: var(--ink-3); }
.cal-exc-work b { color: var(--crit); }
.cal-panel-empty { font: var(--text-small); color: var(--ink-3); }

/* The table is wider than the column on a real schedule. Without its own scroll
   container it overflows .cal-wrap (overflow:hidden), and clicking anything inside
   makes the browser scroll the whole card sideways — taking the calendar list
   off-screen. */
.cal-activities { margin-top: var(--space-5); min-width: 0; }
.cal-act-scroll { overflow-x: auto; }
.cal-act-head { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); margin-bottom: var(--space-2); }
.cal-act-head h3 { font: var(--text-h3); color: var(--ink); margin: 0; }
.cal-act-head h3 em { font-style: normal; color: var(--accent); font-family: var(--font-mono); }
.act-table { width: 100%; min-width: 880px; border-collapse: collapse; font: var(--text-small); }
.act-table th { text-align: left; font: var(--text-micro); text-transform: uppercase; color: var(--ink-3); background: var(--panel-2); border-bottom: 2px solid var(--line); padding: var(--space-2) var(--space-3); }
.act-table th.num { text-align: right; }
.act-table td { padding: 5px var(--space-3); border-bottom: 1px solid var(--line-soft); }
.act-table .jump-row { cursor: pointer; }
.act-table .jump-row:hover td { background: var(--accent-soft); }
.act-table .code { font-family: var(--font-mono); font-weight: 600; color: var(--accent); white-space: nowrap; }
.act-table .name-cell { color: var(--ink-2); max-width: 320px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.act-table .wbs-cell { font-family: var(--font-mono); font: var(--text-micro); color: var(--ink-3); max-width: 240px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cal-exc-span .exc-hit { font-family: var(--font-mono); font-size: 11px; font-weight: 600; color: var(--crit); }
.cal-dash { color: var(--ink-3); }

@media (max-width: 1000px) {
  .cal-main { grid-template-columns: 1fr; }
}

.cal-exceptions h3 { font: var(--text-h3); color: var(--ink); margin: 0 0 var(--space-2); }
.cal-exceptions h3 em { font-style: normal; color: var(--accent); font-family: var(--font-mono); }
.exc-table { width: 100%; border-collapse: collapse; font: var(--text-small); }
.exc-table th { text-align: left; font: var(--text-micro); text-transform: uppercase; color: var(--gray-700); background: var(--gray-100); border-bottom: 2px solid var(--gray-300); padding: var(--space-2) var(--space-3); }
.exc-table td { padding: 5px var(--space-3); border-bottom: 1px solid var(--gray-150); }
.exc-unusual td { background: var(--crit-tint); }
.mono { font-family: var(--font-mono); }
.num-cell { white-space: nowrap; }
.issue-badge { font: var(--text-micro); padding: 1px 7px; border-radius: var(--radius-sm); font-weight: 600; }
.issue-severe { background: var(--crit); color: var(--on-solid); }
.issue-warn { background: var(--near-tint); color: var(--near); }

@media (max-width: 900px) {
  .cal-body { grid-template-columns: 1fr; }
  .cal-list { border-right: none; border-bottom: 1px solid var(--gray-300); }
}
</style>
