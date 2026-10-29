<template>
  <div class="compare-wrap">
    <div class="view-bar">
      <div class="strip-title">
        <span class="strip-sub">{{ current.project.proj_short_name }} vs "{{ baselineFilename }}"</span>
      </div>
      <button class="btn-tiny-light" @click="$emit('reset')">Compare a different file</button>
    </div>

    <!-- Headline verdict: the so-what before any table -->
    <!-- Activities are matched by code: when few codes match, the two files are not two
         versions of one programme, and every figure below would mislead. -->
    <div v-if="mismatched" class="cmp-mismatch">
      Only {{ matched.length }} of {{ Math.max(current.activities.length, baseline.activities.length) }} activity codes appear in both files:
      these look like different projects, so the comparison below says little.
    </div>

    <!-- Neutral words for the move; green only when the finish came in AND the logic that
         drove it largely survived. When the programme was re-sequenced, an earlier finish
         is a re-plan, not recovered time, and the banner says so beside the number. -->
    <div v-if="finishDelta !== null" class="cmp-verdict" :class="verdictClass">
      <div class="verdict-main">
        <span class="verdict-label">Project finish</span>
        <span class="verdict-dates">{{ formatDate(baseline.project.latest_end) }} <span class="verdict-arrow">→</span> {{ formatDate(current.project.latest_end) }}</span>
        <span class="verdict-delta">{{ finishDelta > 0 ? '+' : '' }}{{ finishDelta }}d</span>
        <span class="verdict-word">{{ finishDelta > 0 ? 'later' : finishDelta < 0 ? 'earlier' : 'unchanged' }}</span>
        <span v-for="c in replanChips" :key="c" class="verdict-chip">{{ c }}</span>
      </div>
      <div class="verdict-sub">
        <template v-if="ddAdvance === 0">Data date unchanged ({{ formatDate(current.project.data_date) }}) &middot; </template>
        <template v-else-if="ddAdvance !== null">Data date {{ ddAdvance > 0 ? 'advanced' : 'moved back' }} {{ Math.abs(ddAdvance) }}d ({{ formatDate(baseline.project.data_date) }} → {{ formatDate(current.project.data_date) }}) &middot; </template>
        {{ dateChanges.length }} finish date{{ dateChanges.length === 1 ? '' : 's' }} moved &middot; {{ durationChanges.length }} duration edit{{ durationChanges.length === 1 ? '' : 's' }}
      </div>
    </div>

    <!-- Counts read in a neutral ink; only the longest-path figure carries colour, so the
         alarm, when there is one, has one place to point. Each card states its rule. -->
    <div class="scorecard">
      <div class="score-item" title="Activities present in both files, by activity code"><div class="score-count">{{ matched.length }}</div><div class="score-label">Matched</div></div>
      <div class="score-item" title="Activity codes only in the current file"><div class="score-count">{{ added.length }}</div><div class="score-label">Added</div></div>
      <div class="score-item" title="Activity codes only in the earlier file"><div class="score-count">{{ removed.length }}</div><div class="score-label">Removed</div></div>
      <div class="score-item" :class="stabilityClass" :title="`Of the ${stability.baseCount} activities on the earlier file's longest path, ${stability.retained} are on the current one (both computed the same way, from each file's own flags)`"><div class="score-count">{{ stability.retained }}<small>/{{ stability.baseCount }}</small></div><div class="score-label">Longest path kept</div></div>
      <div class="score-item" title="Matched activities whose original duration was edited"><div class="score-count">{{ durationChanges.length }}</div><div class="score-label">Duration edits</div></div>
      <div class="score-item" title="Matched activities whose total float fell by one working day or more (on the activity's own calendar)"><div class="score-count">{{ floatErosion.length }}</div><div class="score-label">Float down ≥ 1d</div></div>
      <div class="score-item" :title="`Matched activities whose predecessor links changed: ${linkTotals.added} links added, ${linkTotals.removed} removed`"><div class="score-count">{{ logicChanges.length }}</div><div class="score-label">Logic edited <span class="score-sub">+{{ linkTotals.added }} / −{{ linkTotals.removed }} links</span></div></div>
    </div>
    <p class="stability-note">
      {{ stability.retained }} of the {{ stability.baseCount }} activities on the earlier file's longest path are still on it ({{ stability.pct }}%) &middot;
      {{ stability.newlyCritical }} joined it &middot; {{ stability.dropped }} left it
      <span v-if="stability.driverChanged"> &middot; the activity driving the finish changed</span>
    </p>

    <!-- What drives the finish now, against the earlier file: the longest path with
         what changed on each activity, and what left it. Indicative, not forensic. -->
    <section class="compare-section" v-if="drivers.path.length">
      <button class="section-head" @click="toggle('drivers')">
        <span class="section-title">What drives the finish <em>({{ drivers.path.length }})</em></span>
        <span class="section-hint">The current longest path and what changed on it since the earlier file</span>
        <span class="chevron" :class="{ open: expanded.drivers }">&rsaquo;</span>
      </button>
      <div v-if="expanded.drivers" class="section-body">
        <p class="drivers-summary">
          On this path, duration edits add <b>{{ signed(drivers.durationEditDays) }}d</b> and activities new to the file <b>{{ drivers.addedDays }}d</b> of work;
          {{ drivers.path.filter(p => p.joined || p.added).length }} activities joined the path and {{ drivers.left.length }} left it.
          A first reading of the finish move, not a forensic analysis: float, calendars and progress move it too.
        </p>
        <p v-if="!driverRows.length && !showUnchanged" class="drivers-summary">Nothing on the longest path changed. <button class="btn-tiny-light" @click="showUnchanged = true">Show the path</button></p>
        <table v-else class="compare-table">
          <thead><tr><th>Code</th><th>Activity</th><th>What changed</th></tr></thead>
          <tbody>
            <tr v-for="p in driverRows.slice(0, rowLimit('drivers'))" :key="p.code" class="jump-row" title="Show in Gantt" @click="jumpTo(p.code)">
              <td class="code">{{ p.code }}</td>
              <td class="name-cell">{{ p.name }}</td>
              <td><div class="drv-tags">
                <span v-if="p.added" class="drv-tag drv-bad">new activity</span>
                <span v-else-if="p.joined" class="drv-tag">joined the path</span>
                <span v-if="p.durationDays" class="drv-tag" :class="{ 'drv-bad': p.durationDays > 0 }">duration {{ signed(p.durationDays) }}d</span>
                <span v-if="p.startDays" class="drv-tag">start {{ signed(p.startDays) }}d</span>
                <span v-if="p.logicEdited" class="drv-tag">logic edited</span>
                <span v-if="p.constraintChanged" class="drv-tag">constraint changed</span>
                <span v-if="!changed(p)" class="drv-none">unchanged</span>
              </div></td>
            </tr>
            <tr v-if="driverRows.length > rowLimit('drivers')" class="more-row"><td colspan="3"><button class="btn-tiny-light" @click.stop="showAllRows('drivers')">Show all {{ driverRows.length }}</button></td></tr>
            <tr v-if="unchangedOnPath && !showUnchanged" class="more-row"><td colspan="3"><button class="btn-tiny-light" @click.stop="showUnchanged = true">Show the {{ unchangedOnPath }} unchanged {{ unchangedOnPath === 1 ? 'activity' : 'activities' }} too</button></td></tr>
          </tbody>
        </table>
        <p v-if="drivers.left.length" class="drivers-left">
          Left the longest path:
          <span v-for="l in drivers.left.slice(0, 30)" :key="l.code" class="drv-left" :title="l.name">{{ l.code }}<template v-if="l.removed"> (removed)</template></span>
          <template v-if="drivers.left.length > 30">and {{ drivers.left.length - 30 }} more</template>
        </p>
      </div>
    </section>

    <div class="cmp-side-by-side">
    <!-- Milestone movement (dumbbells) -->
    <section class="compare-section" v-if="milestoneMoves.length">
      <button class="section-head" @click="toggle('milestones')">
        <span class="section-title">Milestone Movement <em>({{ milestoneMoves.filter(m => m.delta !== 0).length }})</em></span>
        <span class="section-hint">Earlier &rarr; current date per milestone — the exhibit that goes in front of the client</span>
        <span class="chevron" :class="{ open: expanded.milestones }">&rsaquo;</span>
      </button>
      <div v-if="expanded.milestones" class="section-body">
        <div class="dumbbell-chart">
          <div v-for="m in milestoneMoves" :key="m.code" class="db-row jump-row" title="Show in Gantt" @click="$emit('jump', m.cur.task_id)">
            <span class="db-label"><span class="code">{{ m.code }}</span> {{ m.cur.task_name }}</span>
            <div class="db-track">
              <div v-if="m.delta !== 0" class="db-join" :class="m.delta > 0 ? 'db-slip' : 'db-gain'" :style="{ left: Math.min(m.baseX, m.curX) + '%', width: Math.abs(m.curX - m.baseX) + '%' }"></div>
              <span class="db-dot db-base" :style="{ left: m.baseX + '%' }" :title="'Earlier file: ' + formatDate(m.baseDate)"></span>
              <span class="db-dot db-cur" :class="m.delta > 0 ? 'db-slip' : m.delta < 0 ? 'db-gain' : 'db-hold'" :style="{ left: m.curX + '%' }" :title="'Current: ' + formatDate(m.curDate)"></span>
            </div>
            <span class="db-delta" :class="m.delta > 0 ? 'lag-neg' : m.delta < 0 ? 'lag-pos' : 'db-zero'">{{ m.delta > 0 ? '+' : '' }}{{ m.delta }}d</span>
          </div>
          <div class="db-axis">
            <span>{{ formatDate(msDomain.min) }}</span>
            <span class="db-axis-legend"><span class="db-dot db-base db-inline"></span> earlier &nbsp; <span class="db-dot db-cur db-slip db-inline"></span> current</span>
            <span>{{ formatDate(msDomain.max) }}</span>
          </div>
        </div>
      </div>
    </section>

    <!-- Slip tornado -->
    <section class="compare-section" v-if="tornadoRows.length">
      <button class="section-head" @click="toggle('tornado')">
        <span class="section-title">Biggest Movers <em>({{ dateChanges.length }})</em></span>
        <span class="section-hint">Finish-date change per activity — slips grow right, gains grow left</span>
        <span class="chevron" :class="{ open: expanded.tornado }">&rsaquo;</span>
      </button>
      <div v-if="expanded.tornado" class="section-body">
        <div class="tornado">
          <div v-for="d in tornadoRows" :key="d.code" class="tor-row jump-row" title="Show in Gantt" @click="$emit('jump', d.cur.task_id)">
            <span class="tor-label"><span class="code">{{ d.code }}</span> {{ d.cur.task_name }}</span>
            <div class="tor-track">
              <div class="tor-half tor-left">
                <div v-if="d.deltaDays < 0" class="tor-bar tor-gain" :style="{ width: (100 * -d.deltaDays / tornadoMax) + '%' }"></div>
              </div>
              <div class="tor-half tor-right">
                <div v-if="d.deltaDays > 0" class="tor-bar tor-slip" :style="{ width: (100 * d.deltaDays / tornadoMax) + '%' }"></div>
              </div>
            </div>
            <span class="tor-delta" :class="d.deltaDays > 0 ? 'lag-neg' : 'lag-pos'">{{ d.deltaDays > 0 ? '+' : '' }}{{ d.deltaDays }}d</span>
          </div>
          <p v-if="dateChanges.length > tornadoRows.length" class="tor-note">Showing the {{ tornadoRows.length }} biggest of {{ dateChanges.length }} moved activities — the full list is in Date Changes below.</p>
        </div>
      </div>
    </section>
    </div>

    <!-- Slipped / pulled ahead -->
    <section class="compare-section">
      <button class="section-head" @click="toggle('dates')">
        <span class="section-title">Date Changes <em>({{ dateChanges.length }})</em></span>
        <span class="section-hint">Activities whose finish date moved since the earlier file</span>
        <span class="chevron" :class="{ open: expanded.dates }">&rsaquo;</span>
      </button>
      <div v-if="expanded.dates" class="section-body">
        <div v-if="dateChanges.length === 0" class="empty-state">No finish-date changes.</div>
        <table v-else class="compare-table">
          <thead><tr><th>Code</th><th>Activity</th><th class="num">Earlier Finish</th><th class="num">Current Finish</th><th class="num">Change</th></tr></thead>
          <tbody>
            <tr v-for="d in dateChanges" :key="d.code" class="jump-row" title="Show in Gantt" @click="$emit('jump', d.cur.task_id)">
              <td class="code">{{ d.code }}</td>
              <td class="name-cell">{{ d.cur.task_name }}</td>
              <td class="num-cell">{{ formatDate(displayEnd(d.base)) }}</td>
              <td class="num-cell">{{ formatDate(displayEnd(d.cur)) }}</td>
              <td class="num-cell" :class="d.deltaDays > 0 ? 'lag-neg' : 'lag-pos'">{{ d.deltaDays > 0 ? '+' : '' }}{{ d.deltaDays }}d</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- Duration changes -->
    <section class="compare-section">
      <button class="section-head" @click="toggle('durations')">
        <span class="section-title">Duration Changes <em>({{ durationChanges.length }})</em></span>
        <span class="section-hint">Activities whose original duration was edited since the earlier file</span>
        <span class="chevron" :class="{ open: expanded.durations }">&rsaquo;</span>
      </button>
      <div v-if="expanded.durations" class="section-body">
        <div v-if="durationChanges.length === 0" class="empty-state">No duration changes.</div>
        <table v-else class="compare-table">
          <thead><tr><th>Code</th><th>Activity</th><th class="num">Earlier Dur</th><th class="num">Current Dur</th><th class="num">Change</th></tr></thead>
          <tbody>
            <tr v-for="d in durationChanges" :key="d.code" class="jump-row" title="Show in Gantt" @click="$emit('jump', d.cur.task_id)">
              <td class="code">{{ d.code }}</td>
              <td class="name-cell">{{ d.cur.task_name }}</td>
              <td class="num-cell">{{ formatHours(d.base.duration_hrs, d.base.calendar_hrs_per_day) }}</td>
              <td class="num-cell">{{ formatHours(d.cur.duration_hrs, d.cur.calendar_hrs_per_day) }}</td>
              <td class="num-cell" :class="d.deltaDays > 0 ? 'lag-neg' : 'lag-pos'">{{ d.deltaDays > 0 ? '+' : '' }}{{ d.deltaDays }}d</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- Actual dates rewritten -->
    <section class="compare-section">
      <button class="section-head" @click="toggle('actuals')">
        <span class="section-title">Actual Dates Changed <em>({{ actualChanges.length }})</em></span>
        <span class="section-hint">Actuals reported in the earlier file that moved or disappeared — recorded history should not change between updates</span>
        <span class="chevron" :class="{ open: expanded.actuals }">&rsaquo;</span>
      </button>
      <div v-if="expanded.actuals" class="section-body">
        <div v-if="actualChanges.length === 0" class="empty-state">✓ Every actual date in the earlier file is unchanged.</div>
        <table v-else class="compare-table">
          <thead><tr><th>Code</th><th>Activity</th><th>Field</th><th class="num">Earlier</th><th class="num">Current</th></tr></thead>
          <tbody>
            <template v-for="d in actualChanges" :key="d.code">
              <tr v-for="c in d.changes" :key="d.code + c.label" class="jump-row" title="Show in Gantt" @click="$emit('jump', d.cur.task_id)">
                <td class="code">{{ d.code }}</td>
                <td class="name-cell">{{ d.cur.task_name }}</td>
                <td>{{ c.label }}</td>
                <td class="num-cell">{{ formatDate(c.was) }}</td>
                <td class="num-cell lag-neg">{{ c.now ? formatDate(c.now) : 'Removed' }}</td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </section>

    <!-- Constraint changes -->
    <section class="compare-section">
      <button class="section-head" @click="toggle('constraints')">
        <span class="section-title">Constraint Changes <em>({{ constraintChanges.length }})</em></span>
        <span class="section-hint">Imposed dates added, removed or moved — they change what drives the dates without touching the logic</span>
        <span class="chevron" :class="{ open: expanded.constraints }">&rsaquo;</span>
      </button>
      <div v-if="expanded.constraints" class="section-body">
        <div v-if="constraintChanges.length === 0" class="empty-state">✓ No constraint changed.</div>
        <table v-else class="compare-table">
          <thead><tr><th>Code</th><th>Activity</th><th>Earlier</th><th>Current</th></tr></thead>
          <tbody>
            <tr v-for="d in constraintChanges" :key="d.code" class="jump-row" title="Show in Gantt" @click="$emit('jump', d.cur.task_id)">
              <td class="code">{{ d.code }}</td>
              <td class="name-cell">{{ d.cur.task_name }}</td>
              <td>{{ d.base.cstr_type ? cstrLabel(d.base.cstr_type) + ' ' + formatDate(d.base.cstr_date) : '—' }}</td>
              <td>{{ d.cur.cstr_type ? cstrLabel(d.cur.cstr_type) + ' ' + formatDate(d.cur.cstr_date) : '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- Float erosion -->
    <section class="compare-section">
      <button class="section-head" @click="toggle('float')">
        <span class="section-title">Float Erosion <em>({{ floatErosion.length }})</em></span>
        <span class="section-hint">Activities whose total float fell by one working day or more since the earlier file</span>
        <span class="chevron" :class="{ open: expanded.float }">&rsaquo;</span>
      </button>
      <div v-if="expanded.float" class="section-body">
        <div v-if="floatErosion.length === 0" class="empty-state">No float erosion.</div>
        <table v-else class="compare-table">
          <thead><tr><th>Code</th><th>Activity</th><th class="num">Earlier Float</th><th class="num">Current Float</th><th class="num">Change</th></tr></thead>
          <tbody>
            <tr v-for="d in floatErosion" :key="d.code" class="jump-row" title="Show in Gantt" @click="$emit('jump', d.cur.task_id)">
              <td class="code">{{ d.code }}</td>
              <td class="name-cell">{{ d.cur.task_name }}</td>
              <td class="num-cell">{{ formatFloat(d.base.total_float_hrs, d.base.calendar_hrs_per_day) }}</td>
              <td class="num-cell" :class="d.cur.is_negative_float ? 'lag-neg' : ''">{{ formatFloat(d.cur.total_float_hrs, d.cur.calendar_hrs_per_day) }}</td>
              <td class="num-cell lag-neg">{{ formatFloat(d.delta, d.cur.calendar_hrs_per_day) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- Critical path changes -->
    <section class="compare-section">
      <button class="section-head" @click="toggle('critical')">
        <span class="section-title">Critical Path Changes <em>({{ criticalEntered.length + criticalLeft.length }})</em></span>
        <span class="section-hint">Activities that entered or left the critical set (TF&le;0)</span>
        <span class="chevron" :class="{ open: expanded.critical }">&rsaquo;</span>
      </button>
      <div v-if="expanded.critical" class="section-body">
        <div v-if="criticalEntered.length === 0 && criticalLeft.length === 0" class="empty-state">No change in the critical set.</div>
        <template v-else>
          <h4 v-if="criticalEntered.length">Newly critical ({{ criticalEntered.length }})</h4>
          <table v-if="criticalEntered.length" class="compare-table">
            <thead><tr><th>Code</th><th>Activity</th><th class="num">Current Float</th></tr></thead>
            <tbody>
              <tr v-for="d in criticalEntered" :key="d.code" class="jump-row" title="Show in Gantt" @click="$emit('jump', d.cur.task_id)">
                <td class="code">{{ d.code }}</td>
                <td class="name-cell">{{ d.cur.task_name }}</td>
                <td class="num-cell lag-neg">{{ formatFloat(d.cur.total_float_hrs, d.cur.calendar_hrs_per_day) }}</td>
              </tr>
            </tbody>
          </table>
          <h4 v-if="criticalLeft.length">Dropped from critical ({{ criticalLeft.length }})</h4>
          <table v-if="criticalLeft.length" class="compare-table">
            <thead><tr><th>Code</th><th>Activity</th><th class="num">Current Float</th></tr></thead>
            <tbody>
              <tr v-for="d in criticalLeft" :key="d.code" class="jump-row" title="Show in Gantt" @click="$emit('jump', d.cur.task_id)">
                <td class="code">{{ d.code }}</td>
                <td class="name-cell">{{ d.cur.task_name }}</td>
                <td class="num-cell">{{ formatFloat(d.cur.total_float_hrs, d.cur.calendar_hrs_per_day) }}</td>
              </tr>
            </tbody>
          </table>
        </template>
      </div>
    </section>

    <!-- Logic changes -->
    <section class="compare-section">
      <button class="section-head" @click="toggle('logic')">
        <span class="section-title">Logic Changes <em>({{ logicChanges.length }})</em></span>
        <span class="section-hint">Activities with added or removed predecessor links since the earlier file</span>
        <span class="chevron" :class="{ open: expanded.logic }">&rsaquo;</span>
      </button>
      <div v-if="expanded.logic" class="section-body">
        <div v-if="logicChanges.length === 0" class="empty-state">No logic changes.</div>
        <table v-else class="compare-table">
          <thead><tr><th>Code</th><th>Activity</th><th>Added links</th><th>Removed links</th></tr></thead>
          <tbody>
            <tr v-for="d in logicChanges" :key="d.code" class="jump-row" title="Show in Gantt" @click="$emit('jump', d.cur.task_id)">
              <td class="code">{{ d.code }}</td>
              <td class="name-cell">{{ d.cur.task_name }}</td>
              <td class="links-cell added">{{ d.added.join(', ') || '—' }}</td>
              <td class="links-cell removed">{{ d.removed.join(', ') || '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- Added / removed activities -->
    <section class="compare-section">
      <button class="section-head" @click="toggle('addrem')">
        <span class="section-title">Added / Removed Activities <em>({{ added.length + removed.length }})</em></span>
        <span class="section-hint">Activities present in only one of the two files</span>
        <span class="chevron" :class="{ open: expanded.addrem }">&rsaquo;</span>
      </button>
      <div v-if="expanded.addrem" class="section-body">
        <div v-if="added.length === 0 && removed.length === 0" class="empty-state">No activities added or removed.</div>
        <template v-else>
          <h4 v-if="added.length">Added ({{ added.length }})</h4>
          <table v-if="added.length" class="compare-table">
            <thead><tr><th>Code</th><th>Activity</th><th class="num">Start</th><th class="num">Finish</th></tr></thead>
            <tbody>
              <tr v-for="a in added" :key="a.task_id" class="jump-row" title="Show in Gantt" @click="$emit('jump', a.task_id)">
                <td class="code">{{ a.task_code }}</td>
                <td class="name-cell">{{ a.task_name }}</td>
                <td class="num-cell">{{ formatDate(displayStart(a)) }}</td>
                <td class="num-cell">{{ formatDate(displayEnd(a)) }}</td>
              </tr>
            </tbody>
          </table>
          <h4 v-if="removed.length">Removed ({{ removed.length }})</h4>
          <table v-if="removed.length" class="compare-table">
            <thead><tr><th>Code</th><th>Activity</th><th class="num">Start</th><th class="num">Finish</th></tr></thead>
            <tbody>
              <tr v-for="a in removed" :key="a.task_id">
                <td class="code">{{ a.task_code }}</td>
                <td class="name-cell">{{ a.task_name }}</td>
                <td class="num-cell">{{ formatDate(displayStart(a)) }}</td>
                <td class="num-cell">{{ formatDate(displayEnd(a)) }}</td>
              </tr>
            </tbody>
          </table>
        </template>
      </div>
    </section>
  </div>
</template>

<script lang="ts">
import { defineComponent, type PropType } from 'vue'
import rowLimitMixin from '../mixins/rowLimit'
import { formatDate, formatFloat, formatHours, formatLag } from '../utils/format'
import { REL_TYPE_LABELS, cstrLabel, displayStart, displayEnd } from '../utils/p6'
import { actualDateChanges, constraintChanges, finishSlipDays, finishVerdict, finishDrivers, longestPathStability, type ActualChange, type FinishDrivers, type PathChange, type FinishVerdict, type MatchedPair, type Stability } from '../utils/compareChecks'
import type { Activity, Schedule } from '../types/schedule'

type SectionKey = 'drivers' | 'milestones' | 'tornado' | 'dates' | 'durations' | 'actuals' | 'constraints' | 'float' | 'critical' | 'logic' | 'addrem'
type Delta = MatchedPair & { deltaDays: number }
interface MilestoneMove extends MatchedPair {
  curDate: string | null
  baseDate: string | null
  delta: number
  baseX: number
  curX: number
}

const days = (a: string | number | Date, b: string | number | Date) => new Date(a).getTime() - new Date(b).getTime()

export default defineComponent({
  name: 'CompareView',
  mixins: [rowLimitMixin],
  props: {
    // Either side may be a snapshot saved by an older version; see types/schedule.ts.
    current: { type: Object as PropType<Schedule>, required: true },
    baseline: { type: Object as PropType<Schedule>, required: true },
    baselineFilename: { type: String, default: '' },
  },
  emits: ['jump', 'reset'],
  data() {
    return {
      showUnchanged: false,
      expanded: { drivers: true, milestones: true, tornado: true, dates: false, durations: true, actuals: true, constraints: true, float: true, critical: true, logic: false, addrem: false } as Record<SectionKey, boolean>,
    }
  },
  computed: {
    curByCode(): Map<string, Activity> {
      const m = new Map<string, Activity>()
      for (const a of this.current.activities) m.set(a.task_code, a)
      return m
    },
    baseByCode(): Map<string, Activity> {
      const m = new Map<string, Activity>()
      for (const a of this.baseline.activities) m.set(a.task_code, a)
      return m
    },
    matched(): MatchedPair[] {
      const out: MatchedPair[] = []
      for (const [code, cur] of this.curByCode) {
        const base = this.baseByCode.get(code)
        if (base) out.push({ code, cur, base })
      }
      return out
    },
    added(): Activity[] {
      return this.current.activities.filter(a => !this.baseByCode.has(a.task_code))
    },
    removed(): Activity[] {
      return this.baseline.activities.filter(a => !this.curByCode.has(a.task_code))
    },
    dateChanges(): Delta[] {
      return this.matched
        .map(d => ({ ...d, deltaDays: finishSlipDays(d.cur, d.base) }))
        .filter((d): d is Delta => d.deltaDays !== null && d.deltaDays !== 0)
        .sort((a, b) => b.deltaDays - a.deltaDays)
    },
    finishDelta(): number | null {
      const c = this.current.project.latest_end
      const b = this.baseline.project.latest_end
      if (!c || !b) return null
      return Math.round(days(c, b) / 86400000)
    },
    ddAdvance(): number | null {
      const c = this.current.project.data_date
      const b = this.baseline.project.data_date
      if (!c || !b) return null
      return Math.round(days(c, b) / 86400000)
    },
    milestoneMoves(): MilestoneMove[] {
      // baseX/curX are filled in by the loop below, once the domain is known.
      const rows = this.matched
        .filter(d => (d.cur.task_type || '').includes('Mile'))
        .map(d => {
          const curDate = displayEnd(d.cur) || displayStart(d.cur)
          const baseDate = displayEnd(d.base) || displayStart(d.base)
          return { ...d, curDate, baseDate, delta: curDate && baseDate ? Math.round(days(curDate, baseDate) / 86400000) : 0 }
        })
        .filter(m => m.curDate && m.baseDate)
        .sort((a, b) => days(a.curDate!, b.curDate!))
      const dom = this.msDomain
      const span = Math.max(1, days(dom.max ?? 0, dom.min ?? 0))
      for (const m of rows as MilestoneMove[]) {
        m.baseX = (100 * days(m.baseDate!, dom.min ?? 0)) / span
        m.curX = (100 * days(m.curDate!, dom.min ?? 0)) / span
      }
      return rows as MilestoneMove[]
    },
    msDomain(): { min: string | null; max: string | null } {
      const dates: Date[] = []
      for (const d of this.matched) {
        if (!(d.cur.task_type || '').includes('Mile')) continue
        const c = displayEnd(d.cur) || displayStart(d.cur)
        const b = displayEnd(d.base) || displayStart(d.base)
        if (c) dates.push(new Date(c))
        if (b) dates.push(new Date(b))
      }
      if (!dates.length) return { min: null, max: null }
      const min = new Date(Math.min(...dates.map(Number)))
      const max = new Date(Math.max(...dates.map(Number)))
      // 4% padding each side so edge dots don't clip
      const pad = Math.max(86400000, days(max, min) * 0.04)
      return { min: new Date(+min - pad).toISOString(), max: new Date(+max + pad).toISOString() }
    },
    tornadoRows(): Delta[] {
      return [...this.dateChanges].sort((a, b) => Math.abs(b.deltaDays) - Math.abs(a.deltaDays)).slice(0, 30)
    },
    tornadoMax(): number {
      return Math.max(1, ...this.tornadoRows.map(d => Math.abs(d.deltaDays)))
    },
    durationChanges(): Delta[] {
      // The forensic reviewer proved this gap with a hand-perturbed file: a quiet
      // duration edit between submissions is exactly the kind of change a diff must
      // surface. Compares original (target) durations, in the activity's own calendar.
      return this.matched
        .filter(d => d.cur.duration_hrs !== d.base.duration_hrs)
        .map(d => ({ ...d, deltaDays: Math.round(((d.cur.duration_hrs - d.base.duration_hrs) / (d.cur.calendar_hrs_per_day || 8)) * 10) / 10 }))
        .sort((a, b) => Math.abs(b.deltaDays) - Math.abs(a.deltaDays))
    },
    actualChanges(): (MatchedPair & { changes: ActualChange[] })[] {
      return actualDateChanges(this.matched)
    },
    constraintChanges(): MatchedPair[] {
      return constraintChanges(this.matched)
    },
    floatErosion(): (MatchedPair & { delta: number })[] {
      return this.matched
        // A loss of at least one working day on the activity's calendar: smaller moves are
        // rounding in the export, not erosion anyone would act on.
        .filter(d => d.cur.total_float_hrs != null && d.base.total_float_hrs != null
          && d.base.total_float_hrs - d.cur.total_float_hrs >= (d.cur.calendar_hrs_per_day || 8))
        .map(d => ({ ...d, delta: Math.round((d.cur.total_float_hrs! - d.base.total_float_hrs!) * 10) / 10 }))
        .sort((a, b) => a.delta - b.delta)
    },
    criticalEntered(): MatchedPair[] {
      return this.matched.filter(d => !d.base.is_critical && d.cur.is_critical)
    },
    criticalLeft(): MatchedPair[] {
      return this.matched.filter(d => d.base.is_critical && !d.cur.is_critical)
    },
    logicChanges(): (MatchedPair & { added: string[]; removed: string[] })[] {
      const linkSet = (activity: Activity, lookupById: Map<number, Activity>) => {
        const set = new Set<string>()
        for (const p of activity.predecessors) {
          const predActivity = lookupById.get(p.task_id)
          const code = predActivity ? predActivity.task_code : '?' + p.task_id
          set.add(`${code} (${REL_TYPE_LABELS[p.type] || p.type}${p.lag_hrs ? ' ' + formatLag(p.lag_hrs) : ''})`)
        }
        return set
      }
      const curById = new Map(this.current.activities.map(a => [a.task_id, a]))
      const baseById = new Map(this.baseline.activities.map(a => [a.task_id, a]))
      const out: (MatchedPair & { added: string[]; removed: string[] })[] = []
      for (const d of this.matched) {
        const curLinks = linkSet(d.cur, curById)
        const baseLinks = linkSet(d.base, baseById)
        const added = [...curLinks].filter(l => !baseLinks.has(l))
        const removed = [...baseLinks].filter(l => !curLinks.has(l))
        if (added.length || removed.length) out.push({ ...d, added, removed })
      }
      return out
    },
    linkTotals(): { added: number; removed: number } {
      let added = 0, removed = 0
      for (const d of this.logicChanges) { added += d.added.length; removed += d.removed.length }
      return { added, removed }
    },
    // Under a fifth of the larger file's codes in common.
    mismatched(): boolean {
      const n = Math.max(this.current.activities.length, this.baseline.activities.length)
      return n > 0 && this.matched.length < 0.2 * n
    },
    verdict(): FinishVerdict {
      return finishVerdict(this.finishDelta ?? 0, this.stability, this.ddAdvance)
    },
    replanChips(): string[] {
      return this.verdict.chips
    },
    verdictClass(): string {
      return this.verdict.cls
    },
    stabilityClass(): string {
      if (!this.stability.baseCount) return ''
      return this.stability.pct < 50 ? 'fail' : this.stability.pct < 90 ? 'warn' : 'pass'
    },
    drivers(): FinishDrivers {
      return finishDrivers(this.baseline, this.current)
    },
    // The changed activities on the path first-class; the unchanged ones on request.
    driverRows(): PathChange[] {
      return this.showUnchanged ? this.drivers.path : this.drivers.path.filter(this.changed)
    },
    unchangedOnPath(): number {
      return this.drivers.path.filter(p => !this.changed(p)).length
    },
    stability(): Stability {
      return longestPathStability(this.baseline, this.current)
    },
  },
  methods: {
    changed(p: PathChange): boolean {
      return p.added || p.joined || !!p.durationDays || !!p.startDays || p.logicEdited || p.constraintChanged
    },
    signed(n: number): string {
      return (n > 0 ? '+' : '') + n
    },
    jumpTo(code: string) {
      const a = this.current.activities.find(x => x.task_code === code)
      if (a) this.$emit('jump', a.task_id)
    },
    formatDate,
    formatFloat,
    formatHours,
    cstrLabel,
    displayStart,
    displayEnd,
    toggle(key: SectionKey) {
      this.expanded[key] = !this.expanded[key]
    },
  },
})
</script>

<style scoped>
.compare-wrap { display: flex; flex-direction: column; background: var(--white); border: 1px solid var(--gray-300); border-radius: var(--radius-md); overflow: hidden; }

.scorecard { display: flex; flex-wrap: wrap; gap: 1px; background: var(--gray-300); border-bottom: 1px solid var(--gray-300); }
.score-item { flex: 1; min-width: 110px; background: var(--white); padding: var(--space-3); text-align: center; }
.score-item.pass .score-count { color: var(--ok); }
.score-item.fail .score-count { color: var(--crit); }
.score-item.warn .score-count { color: var(--near); }
.score-count small { font-size: 14px; font-weight: 600; color: var(--ink-3); }
.score-sub { display: block; text-transform: none; letter-spacing: 0; font-family: var(--font-mono); color: var(--ink-3); margin-top: 2px; }
.score-count { font-family: var(--font-mono); font-size: 23px; font-weight: 700; }
.score-label { font: var(--text-micro); color: var(--gray-700); text-transform: uppercase; letter-spacing: 0.03em; }
.stability-note { font: var(--text-small); color: var(--gray-700); padding: var(--space-2) var(--space-4); margin: 0; background: var(--gray-100); border-bottom: 1px solid var(--gray-300); }

.compare-section { border-bottom: 1px solid var(--gray-300); }
.compare-section:last-child { border-bottom: none; }
.empty-state { font: var(--text-small); color: var(--ok); }

.compare-table { width: 100%; border-collapse: collapse; font: var(--text-small); }
.compare-table th { text-align: left; font: var(--text-micro); text-transform: uppercase; color: var(--gray-700); background: var(--gray-100); border-bottom: 2px solid var(--gray-300); padding: var(--space-2) var(--space-3); }
.compare-table td { padding: 6px var(--space-3); border-bottom: 1px solid var(--gray-150); }
.jump-row { cursor: pointer; }
.jump-row:hover td { background: var(--accent-soft); }
.code { font-family: var(--font-mono); font-weight: 600; color: var(--accent); white-space: nowrap; }
.name-cell { color: var(--ink-soft); }
.num-cell { font-family: var(--font-mono); text-align: right; white-space: nowrap; }
/* Verdict banner */
.drivers-summary { margin: 0 0 var(--space-3); font: var(--text-small); color: var(--ink-2); }
.drv-tags { display: flex; flex-wrap: wrap; gap: 4px; }
.drv-tag { font: var(--text-micro); font-weight: 600; border: 1px solid var(--gray-300); border-radius: 10px; padding: 0 7px; color: var(--ink-2); white-space: nowrap; }
.drv-tag.drv-bad { color: var(--crit); border-color: var(--crit); }
.drv-none { font: var(--text-micro); color: var(--ink-3); }
.drivers-left { margin: var(--space-3) 0 0; font: var(--text-small); color: var(--ink-2); display: flex; flex-wrap: wrap; gap: 4px 8px; align-items: baseline; }
.drv-left { font-family: var(--font-mono); font-size: 12px; color: var(--ink-3); }
.cmp-mismatch { padding: var(--space-3) var(--space-4); background: var(--near-tint); color: var(--ink); border-bottom: 1px solid var(--near); font: var(--text-small); font-weight: 600; }
.cmp-verdict { padding: var(--space-4); border-bottom: 1px solid var(--gray-300); }
.cmp-verdict.v-slip { background: var(--crit-tint); }
.cmp-verdict.v-gain { background: var(--ok-tint); }
.cmp-verdict.v-hold { background: var(--gray-100); }
.verdict-main { display: flex; align-items: baseline; gap: var(--space-3); flex-wrap: wrap; }
.verdict-label { font: var(--text-micro); text-transform: uppercase; letter-spacing: 0.05em; color: var(--gray-700); }
.verdict-dates { font-family: var(--font-mono); font-size: 19px; font-weight: 600; color: var(--ink); }
.verdict-arrow { color: var(--gray-500); }
.verdict-delta { font-family: var(--font-mono); font-size: 27px; font-weight: 800; }
.v-slip .verdict-delta, .v-slip .verdict-word { color: var(--crit); }
.v-gain .verdict-delta, .v-gain .verdict-word { color: var(--ok); }
.v-hold .verdict-delta, .v-hold .verdict-word { color: var(--gray-700); }
.verdict-word { font-weight: 700; }
.verdict-chip { font: var(--text-small); font-weight: 600; color: var(--ink); background: var(--panel); border: 1px solid var(--gray-300); border-radius: 12px; padding: 1px 9px; }
.verdict-sub { font: var(--text-small); color: var(--gray-700); margin-top: 2px; }

/* Milestone dumbbells */
.dumbbell-chart { display: flex; flex-direction: column; gap: 2px; }
.db-row { display: grid; grid-template-columns: minmax(180px, 320px) 1fr 52px; align-items: center; gap: var(--space-3); padding: 3px var(--space-2); border-radius: var(--radius-sm); cursor: pointer; }
.db-row:hover { background: var(--accent-soft); }
.db-label { font: var(--text-small); color: var(--ink-soft); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.db-track { position: relative; height: 18px; background: linear-gradient(to bottom, transparent 8px, var(--gray-150) 8px, var(--gray-150) 10px, transparent 10px); }
.db-join { position: absolute; top: 7px; height: 4px; border-radius: 2px; }
.db-join.db-slip { background: var(--crit); opacity: 0.45; }
.db-join.db-gain { background: var(--ok); opacity: 0.45; }
.db-dot { position: absolute; top: 4px; width: 10px; height: 10px; border-radius: 50%; transform: translateX(-5px); box-sizing: border-box; }
.db-base { background: var(--white); border: 2px solid var(--gray-500); }
.db-cur { border: 2px solid transparent; }
.db-cur.db-slip { background: var(--crit); }
.db-cur.db-gain { background: var(--ok); }
.db-cur.db-hold { background: var(--gray-500); }
.db-delta { font-family: var(--font-mono); font-size: 13px; text-align: right; white-space: nowrap; }
.db-zero { color: var(--gray-500); }
.db-axis { display: flex; justify-content: space-between; font: var(--text-micro); color: var(--gray-700); font-family: var(--font-mono); margin-top: var(--space-2); padding: 0 var(--space-2); }
.db-axis-legend { font-family: var(--font-ui); }
.db-inline { position: static; display: inline-block; transform: none; vertical-align: -1px; }

/* Slip tornado */
.tornado { display: flex; flex-direction: column; gap: 1px; }
.tor-row { display: grid; grid-template-columns: minmax(180px, 320px) 1fr 52px; align-items: center; gap: var(--space-3); padding: 2px var(--space-2); border-radius: var(--radius-sm); cursor: pointer; }
.tor-row:hover { background: var(--accent-soft); }
.tor-label { font: var(--text-small); color: var(--ink-soft); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.tor-track { display: flex; height: 14px; }
.tor-half { flex: 1; position: relative; }
.tor-left { border-right: 2px solid var(--gray-500); }
.tor-left .tor-bar { position: absolute; right: 0; top: 2px; bottom: 2px; border-radius: 3px 0 0 3px; }
.tor-right .tor-bar { position: absolute; left: 0; top: 2px; bottom: 2px; border-radius: 0 3px 3px 0; }
.tor-bar.tor-slip { background: var(--crit); }
.tor-bar.tor-gain { background: var(--ok); }
.tor-delta { font-family: var(--font-mono); font-size: 13px; text-align: right; white-space: nowrap; }
.tor-note { font: var(--text-micro); color: var(--gray-700); margin-top: var(--space-2); }

/* Milestone movement and the biggest movers answer the same question at two
   scales; side by side they are read together instead of scrolled between. */
.cmp-side-by-side { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 1px; background: var(--line); }
.cmp-side-by-side > .compare-section { background: var(--panel); border-bottom: none; }
@media (max-width: 1200px) { .cmp-side-by-side { grid-template-columns: 1fr; } }

.lag-neg { color: var(--crit); font-weight: 700; }
.lag-pos { color: var(--ok); font-weight: 700; }
.links-cell { font: var(--text-micro); font-family: var(--font-mono); }
.links-cell.added { color: var(--ok); }
.links-cell.removed { color: var(--crit); }
</style>
