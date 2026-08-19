<template>
  <div class="health-wrap">
    <div class="health-strip">
      <div class="strip-title">
        <h2>Health Check</h2>
        <span class="strip-sub">{{ data.activities.length }} activities &middot; DCMA-14-inspired logic &amp; quality checks</span>
      </div>
      <div class="strip-score">
        <span class="score-num" :class="scoreClass">{{ weightedScore }}%</span>
        <span class="score-detail">{{ passCount }}/{{ includedCount }} checks pass &middot; weighted</span>
        <button class="cfg-btn" :class="{ active: showConfig }" @click="showConfig = !showConfig">⚙ Configure</button>
      </div>
    </div>

    <!-- Check configuration -->
    <div v-if="showConfig" class="cfg-panel">
      <table class="cfg-table">
        <thead>
          <tr><th>Include</th><th>Check</th><th>Threshold</th><th>Target</th><th>Weight</th></tr>
        </thead>
        <tbody>
          <tr v-for="def in checkDefs" :key="def.key" :class="{ 'cfg-off': !cfg[def.key].enabled || !availability[def.key] }">
            <td>
              <input type="checkbox" v-model="cfg[def.key].enabled" :disabled="!availability[def.key]" />
            </td>
            <td>
              {{ def.label }}
              <span v-if="!availability[def.key]" class="cfg-na">— not checkable in this file</span>
            </td>
            <td>
              <template v-if="def.paramLabel">
                {{ def.paramLabel }}
                <input type="number" min="0" v-model.number="cfg[def.key].param" class="cfg-num" />
              </template>
              <span v-else class="cfg-na">—</span>
            </td>
            <td class="cfg-target">
              {{ def.cmp === 'gte' ? '≥' : '≤' }}
              <input type="number" min="0" v-model.number="cfg[def.key].target" class="cfg-num" />
              {{ def.unit === 'pct' ? '%' : '' }}
            </td>
            <td>
              <input type="number" min="0" max="10" v-model.number="cfg[def.key].weight" class="cfg-num" />
            </td>
          </tr>
        </tbody>
      </table>
      <div class="cfg-actions">
        <span class="cfg-note">Targets and weights are yours to set — contracts differ. The score is the weighted share of passing checks; excluded or un-checkable items never count toward it.</span>
        <button class="cfg-reset" @click="resetConfig">Reset to defaults</button>
      </div>
    </div>

    <div class="scorecard">
      <div
        v-for="item in scorecard"
        :key="item.key"
        class="score-item"
        :class="[item.state, { clickable: item.section }]"
        @click="item.section && openSection(item.section)"
        :title="item.tip"
      >
        <div class="score-count">{{ item.display }}</div>
        <div class="score-label">{{ item.label }}</div>
        <div class="score-target">{{ item.targetText }}</div>
      </div>
    </div>

    <!-- Open Ends -->
    <section class="health-section" ref="sec-openEnds">
      <button class="section-head" @click="toggle('openEnds')">
        <span class="section-title">Open Ends <em :class="{ pass: openEnds.length === 0 }">({{ openEnds.length }})</em></span>
        <span class="section-hint">Activities missing a driving predecessor or successor — can float freely with no network effect</span>
        <span class="chevron" :class="{ open: expanded.openEnds }">&rsaquo;</span>
      </button>
      <div v-if="expanded.openEnds" class="section-body">
        <div v-if="openEnds.length === 0" class="empty-state">✓ Every activity is tied into the network at both ends.</div>
        <table v-else class="health-table">
          <thead><tr><th>Code</th><th>Activity</th><th>Issue</th><th>WBS</th><th class="tg-th"></th></tr></thead>
          <tbody>
            <tr v-for="a in openEnds" :key="a.task_id" class="jump-row" title="Show details" @click="openDetail(a.task_id)">
              <td class="code">{{ a.task_code }}</td>
              <td class="name-cell">{{ a.task_name }}</td>
              <td><span class="issue-badge" :class="a.bothOpen ? 'issue-severe' : 'issue-warn'">{{ a.bothOpen ? 'Fully dangling' : (a.openStart ? 'Open start' : 'Open finish') }}</span></td>
              <td class="wbs-cell">{{ a.wbs_path }}</td>
            <td class="tg-cell"><button class="to-gantt" title="Show in Gantt" @click.stop="$emit('jump', a.task_id)">↗</button></td></tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- Relationship type mix & lag/lead audit -->
    <section class="health-section" ref="sec-rel">
      <button class="section-head" @click="toggle('rel')">
        <span class="section-title">Relationship &amp; Lag Audit <em>({{ relationshipStats.leads.length + relationshipStats.bigLags.length }})</em></span>
        <span class="section-hint">FS/SS/FF/SF mix, negative lags ("leads"), and lags over {{ cfg.lags.param }} working days</span>
        <span class="chevron" :class="{ open: expanded.rel }">&rsaquo;</span>
      </button>
      <div v-if="expanded.rel" class="section-body">
        <div class="rel-mix">
          <div v-for="t in relTypeOrder" :key="t" class="rel-mix-item">
            <strong>{{ relationshipStats.counts[t] || 0 }}</strong>
            <span>{{ relTypeLabels[t] }} ({{ relationshipStats.total ? Math.round(100 * (relationshipStats.counts[t] || 0) / relationshipStats.total) : 0 }}%)</span>
          </div>
        </div>
        <p class="section-note" v-if="relationshipStats.total">Industry rule of thumb: &ge;90% of relationships should be Finish-to-Start. This schedule is {{ relationshipStats.pctFs }}% FS.</p>

        <h4 v-if="relationshipStats.leads.length">Negative lag ("leads") — {{ relationshipStats.leads.length }}</h4>
        <table v-if="relationshipStats.leads.length" class="health-table">
          <thead><tr><th>Predecessor</th><th class="num">Finish</th><th class="num">Dur</th><th>Type</th><th class="num">Lag</th><th>Successor</th><th class="num">Start</th><th class="num">Dur</th><th class="tg-th"></th></tr></thead>
          <tbody>
            <tr v-for="(r, i) in relationshipStats.leads" :key="'lead' + i" class="jump-row" title="Show details" @click="openDetail(r.succ.task_id)">
              <td><span class="code">{{ codeOf(r.predId) }}</span><span class="tbl-name">{{ predOf(r.predId)?.task_name }}</span></td>
              <td class="num-cell">{{ predOf(r.predId) ? formatDate(displayEnd(predOf(r.predId))) : '—' }}</td>
              <td class="num-cell">{{ predOf(r.predId) ? formatHours(predOf(r.predId).duration_hrs, predOf(r.predId).calendar_hrs_per_day) : '—' }}</td>
              <td>{{ relTypeLabels[r.type] || r.type }}</td>
              <td class="num-cell lag-neg">{{ formatLag(r.lag, r.succ.calendar_hrs_per_day) }}</td>
              <td><span class="code">{{ r.succ.task_code }}</span><span class="tbl-name">{{ r.succ.task_name }}</span></td>
              <td class="num-cell">{{ formatDate(displayStart(r.succ)) }}</td>
              <td class="num-cell">{{ formatHours(r.succ.duration_hrs, r.succ.calendar_hrs_per_day) }}</td>
              <td class="tg-cell"><button class="to-gantt" title="Show in Gantt" @click.stop="$emit('jump', r.succ.task_id)">↗</button></td>
            </tr>
          </tbody>
        </table>

        <h4 v-if="relationshipStats.bigLags.length">Large lag (&gt;{{ cfg.lags.param }} working days) — {{ relationshipStats.bigLags.length }}</h4>
        <table v-if="relationshipStats.bigLags.length" class="health-table">
          <thead><tr><th>Predecessor</th><th class="num">Finish</th><th class="num">Dur</th><th>Type</th><th class="num">Lag</th><th>Successor</th><th class="num">Start</th><th class="num">Dur</th><th class="tg-th"></th></tr></thead>
          <tbody>
            <tr v-for="(r, i) in relationshipStats.bigLags" :key="'lag' + i" class="jump-row" title="Show details" @click="openDetail(r.succ.task_id)">
              <td><span class="code">{{ codeOf(r.predId) }}</span><span class="tbl-name">{{ predOf(r.predId)?.task_name }}</span></td>
              <td class="num-cell">{{ predOf(r.predId) ? formatDate(displayEnd(predOf(r.predId))) : '—' }}</td>
              <td class="num-cell">{{ predOf(r.predId) ? formatHours(predOf(r.predId).duration_hrs, predOf(r.predId).calendar_hrs_per_day) : '—' }}</td>
              <td>{{ relTypeLabels[r.type] || r.type }}</td>
              <td class="num-cell ">{{ formatLag(r.lag, r.succ.calendar_hrs_per_day) }}</td>
              <td><span class="code">{{ r.succ.task_code }}</span><span class="tbl-name">{{ r.succ.task_name }}</span></td>
              <td class="num-cell">{{ formatDate(displayStart(r.succ)) }}</td>
              <td class="num-cell">{{ formatHours(r.succ.duration_hrs, r.succ.calendar_hrs_per_day) }}</td>
              <td class="tg-cell"><button class="to-gantt" title="Show in Gantt" @click.stop="$emit('jump', r.succ.task_id)">↗</button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- Constraint register -->
    <section class="health-section" ref="sec-constraints">
      <button class="section-head" @click="toggle('constraints')">
        <span class="section-title">Constraint Register <em>({{ constraintList.length }})</em></span>
        <span class="section-hint">Imposed dates that can override network logic — hard constraints can produce negative float</span>
        <span class="chevron" :class="{ open: expanded.constraints }">&rsaquo;</span>
      </button>
      <div v-if="expanded.constraints" class="section-body">
        <div v-if="constraintList.length === 0" class="empty-state">✓ No imposed dates — the network logic alone drives every date.</div>
        <table v-else class="health-table">
          <thead><tr><th>Code</th><th>Activity</th><th>Constraint</th><th class="num">Date</th><th>Severity</th><th>Note</th><th class="tg-th"></th></tr></thead>
          <tbody>
            <tr v-for="a in constraintList" :key="a.task_id" class="jump-row" title="Show details" @click="openDetail(a.task_id)">
              <td class="code">{{ a.task_code }}</td>
              <td class="name-cell">{{ a.task_name }}</td>
              <td>{{ cstrLabels[a.cstr_type] || a.cstr_type }}</td>
              <td class="num-cell">{{ formatDate(a.cstr_date) }}</td>
              <td><span class="issue-badge" :class="a.hard ? 'issue-severe' : 'issue-warn'">{{ a.hard ? 'Hard' : 'Soft' }}</span></td>
              <td class="section-note-cell">{{ a.criticalOnlyByConstraint ? 'Critical only due to this constraint, not network logic' : '' }}</td>
            <td class="tg-cell"><button class="to-gantt" title="Show in Gantt" @click.stop="$emit('jump', a.task_id)">↗</button></td></tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- Negative float -->
    <section class="health-section" ref="sec-negfloat">
      <button class="section-head" @click="toggle('negfloat')">
        <span class="section-title">Negative Float <em :class="{ pass: negativeFloatList.length === 0 }">({{ negativeFloatList.length }})</em></span>
        <span class="section-hint">Activities already behind an imposed date — the schedule is telling you it can't hit its own constraints</span>
        <span class="chevron" :class="{ open: expanded.negfloat }">&rsaquo;</span>
      </button>
      <div v-if="expanded.negfloat" class="section-body">
        <div v-if="negativeFloatList.length === 0" class="empty-state">✓ No activity is behind its constraints.</div>
        <table v-else class="health-table">
          <thead><tr><th>Code</th><th>Activity</th><th class="num">Float</th><th class="num">Finish</th><th class="tg-th"></th></tr></thead>
          <tbody>
            <tr v-for="a in negativeFloatList" :key="a.task_id" class="jump-row" title="Show details" @click="openDetail(a.task_id)">
              <td class="code">{{ a.task_code }}</td>
              <td class="name-cell">{{ a.task_name }}</td>
              <td class="num-cell lag-neg">{{ formatFloat(a.total_float_hrs, a.calendar_hrs_per_day) }}</td>
              <td class="num-cell">{{ formatDate(a.early_end) }}</td>
            <td class="tg-cell"><button class="to-gantt" title="Show in Gantt" @click.stop="$emit('jump', a.task_id)">↗</button></td></tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- High float -->
    <section class="health-section" ref="sec-highfloat">
      <button class="section-head" @click="toggle('highfloat')">
        <span class="section-title">High Float <em>({{ highFloatList.length }})</em></span>
        <span class="section-hint">Incomplete activities with more than {{ cfg.highfloat.param }} working days of float — usually missing logic, not genuine slack</span>
        <span class="chevron" :class="{ open: expanded.highfloat }">&rsaquo;</span>
      </button>
      <div v-if="expanded.highfloat" class="section-body">
        <div v-if="highFloatList.length === 0" class="empty-state">✓ No suspiciously slack activities.</div>
        <table v-else class="health-table">
          <thead><tr><th>Code</th><th>Activity</th><th class="num">Float</th><th>WBS</th><th class="tg-th"></th></tr></thead>
          <tbody>
            <tr v-for="a in highFloatList" :key="a.task_id" class="jump-row" title="Show details" @click="openDetail(a.task_id)">
              <td class="code">{{ a.task_code }}</td>
              <td class="name-cell">{{ a.task_name }}</td>
              <td class="num-cell">{{ formatFloat(a.total_float_hrs, a.calendar_hrs_per_day) }}</td>
              <td class="wbs-cell">{{ a.wbs_path }}</td>
            <td class="tg-cell"><button class="to-gantt" title="Show in Gantt" @click.stop="$emit('jump', a.task_id)">↗</button></td></tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- Invalid dates -->
    <section class="health-section" v-if="availability.invdates" ref="sec-invdates">
      <button class="section-head" @click="toggle('invdates')">
        <span class="section-title">Invalid Dates <em :class="{ pass: invalidDatesList.length === 0 }">({{ invalidDatesList.length }})</em></span>
        <span class="section-hint">Actual dates after the data date, or forecast dates before it — signs the schedule wasn't properly progressed</span>
        <span class="chevron" :class="{ open: expanded.invdates }">&rsaquo;</span>
      </button>
      <div v-if="expanded.invdates" class="section-body">
        <div v-if="invalidDatesList.length === 0" class="empty-state">✓ All actuals sit before the data date, all forecasts after it.</div>
        <table v-else class="health-table">
          <thead><tr><th>Code</th><th>Activity</th><th>Issue</th><th class="tg-th"></th></tr></thead>
          <tbody>
            <tr v-for="a in invalidDatesList" :key="a.task_id" class="jump-row" title="Show details" @click="openDetail(a.task_id)">
              <td class="code">{{ a.task_code }}</td>
              <td class="name-cell">{{ a.task_name }}</td>
              <td><span class="issue-badge issue-warn">{{ a.issues.join(' · ') }}</span></td>
            <td class="tg-cell"><button class="to-gantt" title="Show in Gantt" @click.stop="$emit('jump', a.task_id)">↗</button></td></tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- Missed tasks -->
    <section class="health-section" v-if="availability.missed" ref="sec-missed">
      <button class="section-head" @click="toggle('missed')">
        <span class="section-title">Missed Tasks <em>({{ missedTasksList.length }})</em></span>
        <span class="section-hint">Should have finished by the data date (per the schedule's own planned dates) but haven't — no baseline in a .xer, so this is BEI against the current plan</span>
        <span class="chevron" :class="{ open: expanded.missed }">&rsaquo;</span>
      </button>
      <div v-if="expanded.missed" class="section-body">
        <div v-if="missedTasksList.length === 0" class="empty-state">✓ Everything planned to be finished by the data date is finished.</div>
        <table v-else class="health-table">
          <thead><tr><th>Code</th><th>Activity</th><th class="num">Planned finish</th><th class="num">Forecast finish</th><th>Status</th><th class="tg-th"></th></tr></thead>
          <tbody>
            <tr v-for="a in missedTasksList" :key="a.task_id" class="jump-row" title="Show details" @click="openDetail(a.task_id)">
              <td class="code">{{ a.task_code }}</td>
              <td class="name-cell">{{ a.task_name }}</td>
              <td class="num-cell">{{ formatDate(a.target_end) }}</td>
              <td class="num-cell">{{ formatDate(a.act_end || a.early_end) }}</td>
              <td>{{ a.status === 'TK_Active' ? 'In progress' : 'Not started' }}</td>
            <td class="tg-cell"><button class="to-gantt" title="Show in Gantt" @click.stop="$emit('jump', a.task_id)">↗</button></td></tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- High duration -->
    <section class="health-section" ref="sec-highdur">
      <button class="section-head" @click="toggle('highdur')">
        <span class="section-title">High Duration <em>({{ highDurationList.length }})</em></span>
        <span class="section-hint">Task activities over {{ cfg.highdur.param }} working days — usually should be broken into smaller steps for meaningful progress tracking</span>
        <span class="chevron" :class="{ open: expanded.highdur }">&rsaquo;</span>
      </button>
      <div v-if="expanded.highdur" class="section-body">
        <div v-if="highDurationList.length === 0" class="empty-state">✓ No task runs long enough to need breaking down.</div>
        <table v-else class="health-table">
          <thead><tr><th>Code</th><th>Activity</th><th class="num">Duration</th><th class="num">Start</th><th class="num">Finish</th><th class="tg-th"></th></tr></thead>
          <tbody>
            <tr v-for="a in highDurationList" :key="a.task_id" class="jump-row" title="Show details" @click="openDetail(a.task_id)">
              <td class="code">{{ a.task_code }}</td>
              <td class="name-cell">{{ a.task_name }}</td>
              <td class="num-cell">{{ formatHours(a.duration_hrs, a.calendar_hrs_per_day) }}</td>
              <td class="num-cell">{{ formatDate(displayStart(a)) }}</td>
              <td class="num-cell">{{ formatDate(displayEnd(a)) }}</td>
              <td class="tg-cell"><button class="to-gantt" title="Show in Gantt" @click.stop="$emit('jump', a.task_id)">↗</button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- LOE on critical path -->
    <section class="health-section" ref="sec-loe">
      <button class="section-head" @click="toggle('loe')">
        <span class="section-title">LOE on Critical Path <em>({{ loeOnCriticalList.length }})</em></span>
        <span class="section-hint">Level-of-Effort/hammock activities shouldn't normally drive the critical path — usually a sign of inverted logic</span>
        <span class="chevron" :class="{ open: expanded.loe }">&rsaquo;</span>
      </button>
      <div v-if="expanded.loe" class="section-body">
        <div v-if="loeOnCriticalList.length === 0" class="empty-state">✓ No level-of-effort activity drives the critical path.</div>
        <table v-else class="health-table">
          <thead><tr><th>Code</th><th>Activity</th><th class="num">Start</th><th class="num">Finish</th><th class="num">Dur</th><th class="tg-th"></th></tr></thead>
          <tbody>
            <tr v-for="a in loeOnCriticalList" :key="a.task_id" class="jump-row" title="Show details" @click="openDetail(a.task_id)">
              <td class="code">{{ a.task_code }}</td>
              <td class="name-cell">{{ a.task_name }}</td>
              <td class="num-cell">{{ formatDate(displayStart(a)) }}</td>
              <td class="num-cell">{{ formatDate(displayEnd(a)) }}</td>
              <td class="num-cell">{{ formatHours(a.duration_hrs, a.calendar_hrs_per_day) }}</td>
              <td class="tg-cell"><button class="to-gantt" title="Show in Gantt" @click.stop="$emit('jump', a.task_id)">↗</button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- Driving path cross-check -->
    <section class="health-section" v-if="drivingPathAvailable" ref="sec-driving">
      <button class="section-head" @click="toggle('driving')">
        <span class="section-title">Driving Path Cross-Check <em>({{ drivingMismatchList.length }})</em></span>
        <span class="section-hint">Where P6's own driving-path flag disagrees with this app's computed longest path</span>
        <span class="chevron" :class="{ open: expanded.driving }">&rsaquo;</span>
      </button>
      <div v-if="expanded.driving" class="section-body">
        <div v-if="drivingMismatchList.length === 0" class="empty-state">No discrepancies — computed longest path matches P6's driving path flag.</div>
        <table v-else class="health-table">
          <thead><tr><th>Code</th><th>Activity</th><th>P6 driving?</th><th>App longest path?</th><th class="tg-th"></th></tr></thead>
          <tbody>
            <tr v-for="a in drivingMismatchList" :key="a.task_id" class="jump-row" title="Show details" @click="openDetail(a.task_id)">
              <td class="code">{{ a.task_code }}</td>
              <td class="name-cell">{{ a.task_name }}</td>
              <td>{{ a.driving_path_flag ? 'Yes' : 'No' }}</td>
              <td>{{ a.is_longest_path ? 'Yes' : 'No' }}</td>
            <td class="tg-cell"><button class="to-gantt" title="Show in Gantt" @click.stop="$emit('jump', a.task_id)">↗</button></td></tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- Out-of-sequence progress -->
    <section class="health-section" ref="sec-oos">
      <button class="section-head" @click="toggle('oos')">
        <span class="section-title">Out-of-Sequence Progress <em>({{ outOfSequenceList.length }})</em></span>
        <span class="section-hint">Activities progressed before their Finish-to-Start predecessor actually finished</span>
        <span class="chevron" :class="{ open: expanded.oos }">&rsaquo;</span>
      </button>
      <div v-if="expanded.oos" class="section-body">
        <div v-if="outOfSequenceList.length === 0" class="empty-state">✓ All recorded progress respects the network logic.</div>
        <table v-else class="health-table">
          <thead><tr><th>Activity</th><th class="num">Started</th><th>Predecessor</th><th class="num">Predecessor finished</th><th class="tg-th"></th></tr></thead>
          <tbody>
            <tr v-for="(r, i) in outOfSequenceList" :key="i" class="jump-row" title="Show details" @click="openDetail(r.activity.task_id)">
              <td><span class="code">{{ r.activity.task_code }}</span><span class="tbl-name">{{ r.activity.task_name }}</span></td>
              <td class="num-cell">{{ formatDate(r.activity.act_start) }}</td>
              <td><span class="code">{{ r.predecessor.task_code }}</span><span class="tbl-name">{{ r.predecessor.task_name }}</span></td>
              <td class="num-cell">{{ r.predecessor.act_end ? formatDate(r.predecessor.act_end) : 'Not finished' }}</td>
              <td class="tg-cell"><button class="to-gantt" title="Show in Gantt" @click.stop="$emit('jump', r.activity.task_id)">↗</button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- Resource coverage -->
    <section class="health-section" v-if="data.project.has_resources" ref="sec-resources">
      <button class="section-head" @click="toggle('resources')">
        <span class="section-title">Missing Resources <em>({{ noResourceList.length }})</em></span>
        <span class="section-hint">Incomplete task activities with no resource assigned</span>
        <span class="chevron" :class="{ open: expanded.resources }">&rsaquo;</span>
      </button>
      <div v-if="expanded.resources" class="section-body">
        <div v-if="noResourceList.length === 0" class="empty-state">Every incomplete activity has a resource assigned.</div>
        <table v-else class="health-table">
          <thead><tr><th>Code</th><th>Activity</th><th class="tg-th"></th></tr></thead>
          <tbody>
            <tr v-for="a in noResourceList" :key="a.task_id" class="jump-row" title="Show details" @click="openDetail(a.task_id)">
              <td class="code">{{ a.task_code }}</td>
              <td class="name-cell">{{ a.task_name }}</td>
            <td class="tg-cell"><button class="to-gantt" title="Show in Gantt" @click.stop="$emit('jump', a.task_id)">↗</button></td></tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- Shared drawer: audit an activity without leaving this tab; the ↗ controls
         (row icon or drawer button) are the intentional jump to the Gantt. -->
    <ActivityDetailDrawer
      :activity="selectedActivity"
      :lookup="activitiesById"
      :annotations="annotations"
      :project-name="data.project.proj_short_name"
      show-jump
      @close="selectedTaskId = null"
      @select="openDetail"
      @jump="id => $emit('jump', id)"
      @annotate="(id, patch) => $emit('annotate', id, patch)"
      @unannotate="id => $emit('unannotate', id)"
    />
  </div>
</template>

<script>
import { formatDate, formatHours, formatFloat, formatLag } from '../utils/format'
import { REL_TYPE_LABELS, CSTR_LABELS, HARD_CONSTRAINT_TYPES, displayStart, displayEnd } from '../utils/p6'
import ActivityDetailDrawer from './ActivityDetailDrawer.vue'

const CFG_KEY = 'schedule-app:health-config'
const CFG_VERSION = 1

// One row per check: unit 'pct' evaluates the percentage against target, 'count' the raw
// count. cmp 'lte' = at most, 'gte' = at least. param is the check's own threshold (days).
// Defaults follow DCMA-14 conventions where one exists; targets/weights are user-editable
// because contracts specify their own.
const CHECK_DEFS = [
  { key: 'openends', label: 'Open Ends', section: 'openEnds', unit: 'pct', cmp: 'lte', target: 5, weight: 2 },
  { key: 'leads', label: 'Leads', section: 'rel', unit: 'count', cmp: 'lte', target: 0, weight: 1 },
  { key: 'lags', label: 'Large Lags', section: 'rel', unit: 'pct', cmp: 'lte', target: 5, weight: 1, param: 10, paramLabel: 'Lag over (days)' },
  { key: 'fs', label: 'FS Relationships', section: 'rel', unit: 'pct', cmp: 'gte', target: 90, weight: 1 },
  { key: 'hardcstr', label: 'Hard Constraints', section: 'constraints', unit: 'pct', cmp: 'lte', target: 5, weight: 1 },
  { key: 'negfloat', label: 'Negative Float', section: 'negfloat', unit: 'count', cmp: 'lte', target: 0, weight: 2 },
  { key: 'highfloat', label: 'High Float', section: 'highfloat', unit: 'pct', cmp: 'lte', target: 5, weight: 1, param: 44, paramLabel: 'Float over (days)' },
  { key: 'invdates', label: 'Invalid Dates', section: 'invdates', unit: 'count', cmp: 'lte', target: 0, weight: 1 },
  { key: 'missed', label: 'Missed Tasks', section: 'missed', unit: 'pct', cmp: 'lte', target: 5, weight: 1 },
  { key: 'highdur', label: 'High Duration', section: 'highdur', unit: 'pct', cmp: 'lte', target: 5, weight: 1, param: 44, paramLabel: 'Duration over (days)' },
  { key: 'oos', label: 'Out-of-Sequence', section: 'oos', unit: 'count', cmp: 'lte', target: 0, weight: 1 },
  { key: 'loe', label: 'LOE on Critical', section: 'loe', unit: 'count', cmp: 'lte', target: 0, weight: 1 },
  { key: 'driving', label: 'Driving Mismatches', section: 'driving', unit: 'count', cmp: 'lte', target: 0, weight: 1 },
  { key: 'noresource', label: 'Missing Resources', section: 'resources', unit: 'pct', cmp: 'lte', target: 5, weight: 1 },
]

function defaultConfig() {
  const cfg = {}
  for (const d of CHECK_DEFS) {
    cfg[d.key] = { enabled: true, target: d.target, weight: d.weight }
    if (d.param !== undefined) cfg[d.key].param = d.param
  }
  return cfg
}

function loadConfig() {
  const cfg = defaultConfig()
  try {
    const raw = localStorage.getItem(CFG_KEY)
    if (!raw) return cfg
    const saved = JSON.parse(raw)
    if (saved.version !== CFG_VERSION) return cfg
    for (const key of Object.keys(cfg)) {
      if (saved.cfg?.[key]) Object.assign(cfg[key], saved.cfg[key])
    }
  } catch { /* corrupted config — fall back to defaults */ }
  return cfg
}

export default {
  name: 'HealthCheck',
  components: { ActivityDetailDrawer },
  props: {
    data: { type: Object, required: true },
    annotations: { type: Object, default: () => ({}) },
  },
  emits: ['jump', 'annotate', 'unannotate'],
  data() {
    return {
      expanded: {
        openEnds: true,
        rel: true,
        constraints: false,
        negfloat: true,
        highfloat: false,
        invdates: true,
        missed: true,
        highdur: false,
        loe: false,
        driving: false,
        oos: false,
        resources: false,
      },
      showConfig: false,
      selectedTaskId: null,
      cfg: loadConfig(),
      checkDefs: CHECK_DEFS,
      cstrLabels: CSTR_LABELS,
      relTypeLabels: REL_TYPE_LABELS,
      relTypeOrder: ['PR_FS', 'PR_SS', 'PR_FF', 'PR_SF'],
    }
  },
  watch: {
    cfg: {
      deep: true,
      handler(v) {
        try {
          localStorage.setItem(CFG_KEY, JSON.stringify({ version: CFG_VERSION, cfg: v }))
        } catch { /* storage unavailable */ }
      },
    },
  },
  computed: {
    selectedActivity() {
      return this.selectedTaskId != null ? this.activitiesById.get(this.selectedTaskId) || null : null
    },
    activitiesById() {
      const m = new Map()
      for (const a of this.data.activities) m.set(a.task_id, a)
      return m
    },
    dataDateObj() {
      return this.data.project.data_date ? new Date(this.data.project.data_date) : null
    },
    openEnds() {
      const list = []
      for (const a of this.data.activities) {
        const noPred = a.predecessors.length === 0
        const noSucc = a.successors.length === 0
        const flagStart = noPred && a.task_type !== 'TT_StartMile'
        const flagFinish = noSucc && a.task_type !== 'TT_FinMile'
        if (flagStart || flagFinish) {
          list.push({ ...a, openStart: flagStart, openFinish: flagFinish, bothOpen: flagStart && flagFinish })
        }
      }
      return list
    },
    relationshipStats() {
      const counts = {}
      const leads = []
      const bigLags = []
      const largeLagHrs = (this.cfg.lags.param || 10) * 8
      let total = 0
      for (const a of this.data.activities) {
        for (const p of a.predecessors) {
          total++
          counts[p.type] = (counts[p.type] || 0) + 1
          if (p.lag_hrs < 0) leads.push({ succ: a, predId: p.task_id, type: p.type, lag: p.lag_hrs })
          else if (p.lag_hrs > largeLagHrs) bigLags.push({ succ: a, predId: p.task_id, type: p.type, lag: p.lag_hrs })
        }
      }
      leads.sort((x, y) => x.lag - y.lag)
      bigLags.sort((x, y) => y.lag - x.lag)
      const pctFs = total ? Math.round((100 * (counts.PR_FS || 0)) / total) : 100
      return { total, counts, leads, bigLags, pctFs }
    },
    constraintList() {
      return this.data.activities
        .filter(a => a.cstr_type)
        .map(a => ({
          ...a,
          hard: HARD_CONSTRAINT_TYPES.has(a.cstr_type),
          criticalOnlyByConstraint: a.is_critical && !a.is_longest_path,
        }))
        .sort((a, b) => (b.hard === a.hard ? 0 : b.hard ? 1 : -1))
    },
    negativeFloatList() {
      return this.data.activities
        .filter(a => a.is_negative_float)
        .sort((a, b) => a.total_float_hrs - b.total_float_hrs)
    },
    highFloatList() {
      const th = this.cfg.highfloat.param ?? 44
      return this.data.activities
        .filter(a => a.status !== 'TK_Complete' && a.total_float_hrs !== null
          && a.total_float_hrs / (a.calendar_hrs_per_day || 8) > th)
        .sort((a, b) => b.total_float_hrs - a.total_float_hrs)
    },
    invalidDatesList() {
      const dd = this.dataDateObj
      if (!dd) return []
      const list = []
      for (const a of this.data.activities) {
        const issues = []
        if (a.act_start && new Date(a.act_start) > dd) issues.push('Actual start after data date')
        if (a.act_end && new Date(a.act_end) > dd) issues.push('Actual finish after data date')
        if (!a.act_start && a.early_start && new Date(a.early_start) < dd) issues.push('Forecast start before data date')
        if (!a.act_end && a.early_end && new Date(a.early_end) < dd) issues.push('Forecast finish before data date')
        if (issues.length) list.push({ ...a, issues })
      }
      return list
    },
    // Denominator for the missed-tasks percentage: everything the schedule's own planned
    // dates said would be finished by now (BEI-style, but against the current plan — a
    // .xer carries no separate baseline).
    plannedDoneCount() {
      const dd = this.dataDateObj
      if (!dd) return 0
      return this.data.activities.filter(a => a.target_end && new Date(a.target_end) < dd).length
    },
    missedTasksList() {
      const dd = this.dataDateObj
      if (!dd) return []
      return this.data.activities
        .filter(a => a.status !== 'TK_Complete' && a.target_end && new Date(a.target_end) < dd)
        .sort((a, b) => (a.target_end < b.target_end ? -1 : 1))
    },
    highDurationList() {
      const th = this.cfg.highdur.param ?? 44
      return this.data.activities
        .filter(a => a.task_type === 'TT_Task' && a.duration_hrs / (a.calendar_hrs_per_day || 8) > th)
        .sort((a, b) => b.duration_hrs - a.duration_hrs)
    },
    loeOnCriticalList() {
      return this.data.activities.filter(a => a.task_type === 'TT_LOE' && (a.is_critical || a.is_longest_path))
    },
    drivingPathAvailable() {
      return this.data.activities.some(a => a.driving_path_flag)
    },
    drivingMismatchList() {
      if (!this.drivingPathAvailable) return []
      return this.data.activities.filter(a => a.driving_path_flag !== a.is_longest_path)
    },
    outOfSequenceList() {
      const byId = this.activitiesById
      const list = []
      for (const a of this.data.activities) {
        if (!a.act_start) continue
        for (const p of a.predecessors) {
          if (p.type !== 'PR_FS') continue
          const pred = byId.get(p.task_id)
          if (!pred) continue
          if (!pred.act_end || new Date(pred.act_end) > new Date(a.act_start)) {
            list.push({ activity: a, predecessor: pred })
          }
        }
      }
      return list
    },
    noResourceList() {
      if (!this.data.project.has_resources) return []
      return this.data.activities.filter(
        a => a.task_type === 'TT_Task' && a.status !== 'TK_Complete' && a.resource_names.length === 0
      )
    },
    availability() {
      return {
        openends: true, leads: true, lags: true, fs: true, hardcstr: true, negfloat: true,
        highfloat: true, highdur: true, oos: true, loe: true,
        invdates: !!this.dataDateObj,
        missed: !!this.dataDateObj,
        driving: this.drivingPathAvailable,
        noresource: this.data.project.has_resources,
      }
    },
    // Per-check measurement: count of findings, the value the target is compared
    // against (a % of the check's own denominator, or the raw count), and pass/fail.
    checkResults() {
      const nAct = this.data.activities.length || 1
      const nRel = this.relationshipStats.total || 1
      const raw = {
        openends: { count: this.openEnds.length, denom: nAct },
        leads: { count: this.relationshipStats.leads.length, denom: nRel },
        lags: { count: this.relationshipStats.bigLags.length, denom: nRel },
        fs: { count: this.relationshipStats.pctFs, denom: 100, valueOverride: this.relationshipStats.pctFs, displayOverride: this.relationshipStats.pctFs + '%' },
        hardcstr: { count: this.constraintList.filter(c => c.hard).length, denom: nAct },
        negfloat: { count: this.negativeFloatList.length, denom: nAct },
        highfloat: { count: this.highFloatList.length, denom: nAct },
        invdates: { count: this.invalidDatesList.length, denom: nAct },
        missed: { count: this.missedTasksList.length, denom: this.plannedDoneCount || 1 },
        highdur: { count: this.highDurationList.length, denom: nAct },
        oos: { count: this.outOfSequenceList.length, denom: nAct },
        loe: { count: this.loeOnCriticalList.length, denom: nAct },
        driving: { count: this.drivingMismatchList.length, denom: nAct },
        noresource: { count: this.noResourceList.length, denom: nAct },
      }
      const results = {}
      for (const def of CHECK_DEFS) {
        const r = raw[def.key]
        const c = this.cfg[def.key]
        const value = r.valueOverride !== undefined
          ? r.valueOverride
          : def.unit === 'pct' ? (100 * r.count) / r.denom : r.count
        const pass = def.cmp === 'gte' ? value >= c.target : value <= c.target
        results[def.key] = {
          count: r.count,
          value,
          pass,
          display: r.displayOverride !== undefined ? r.displayOverride : r.count,
          included: c.enabled && this.availability[def.key],
        }
      }
      return results
    },
    includedDefs() {
      return CHECK_DEFS.filter(d => this.checkResults[d.key].included)
    },
    includedCount() {
      return this.includedDefs.length
    },
    passCount() {
      return this.includedDefs.filter(d => this.checkResults[d.key].pass).length
    },
    weightedScore() {
      let wTotal = 0
      let wPass = 0
      for (const d of this.includedDefs) {
        const w = Math.max(0, this.cfg[d.key].weight || 0)
        wTotal += w
        if (this.checkResults[d.key].pass) wPass += w
      }
      return wTotal ? Math.round((100 * wPass) / wTotal) : 100
    },
    scoreClass() {
      return this.weightedScore >= 80 ? 'score-good' : this.weightedScore >= 60 ? 'score-mid' : 'score-bad'
    },
    scorecard() {
      return CHECK_DEFS.filter(d => this.availability[d.key]).map(d => {
        const r = this.checkResults[d.key]
        const c = this.cfg[d.key]
        const targetText = `${d.cmp === 'gte' ? '≥' : '≤'} ${c.target}${d.unit === 'pct' ? '%' : ''}`
        return {
          key: d.key,
          label: d.label,
          display: r.display,
          section: d.section,
          state: !r.included ? 'excluded' : r.pass ? 'pass' : 'fail',
          targetText: r.included ? targetText : 'excluded',
          tip: r.included
            ? `${d.label}: ${r.count} finding${r.count === 1 ? '' : 's'} · target ${targetText} · weight ${c.weight}`
            : `${d.label} is excluded from the score`,
        }
      })
    },
  },
  mounted() {
    window.addEventListener('keydown', this._onKeydown = e => {
      if (e.key === 'Escape' && this.selectedTaskId != null && this.$el.offsetParent !== null) this.selectedTaskId = null
    })
    document.addEventListener('mousedown', this._onDocMousedown = e => {
      if (this.selectedTaskId != null && this.$el.offsetParent !== null && !this.$el.contains(e.target)) this.selectedTaskId = null
    })
  },
  beforeUnmount() {
    window.removeEventListener('keydown', this._onKeydown)
    document.removeEventListener('mousedown', this._onDocMousedown)
  },
  methods: {
    formatDate,
    formatHours,
    formatFloat,
    formatLag,
    displayStart,
    displayEnd,
    openDetail(taskId) {
      this.selectedTaskId = taskId
    },
    predOf(taskId) {
      return this.activitiesById.get(taskId) || null
    },
    codeOf(taskId) {
      const a = this.activitiesById.get(taskId)
      return a ? a.task_code : '?' + taskId
    },
    toggle(key) {
      this.expanded[key] = !this.expanded[key]
    },
    openSection(key) {
      this.expanded[key] = true
      this.$nextTick(() => {
        this.$refs['sec-' + key]?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      })
    },
    resetConfig() {
      this.cfg = defaultConfig()
    },
  },
}
</script>

<style scoped>
.health-wrap { display: flex; flex-direction: column; background: var(--white); border: 1px solid var(--gray-300); border-radius: var(--radius-md); overflow: hidden; }
.health-strip { background: var(--ink); color: var(--white); padding: var(--space-3) var(--space-4); display: flex; align-items: center; justify-content: space-between; gap: var(--space-4); flex-wrap: wrap; }
.strip-title { display: flex; align-items: baseline; gap: var(--space-3); flex-wrap: wrap; }
.strip-title h2 { font: var(--text-h2); margin: 0; }
.strip-sub { font: var(--text-small); color: var(--gray-300); }
.strip-score { display: flex; align-items: center; gap: var(--space-3); }
.score-num { font-family: var(--font-mono); font-size: 27px; font-weight: 800; }
.score-good { color: var(--ok-bright); }
.score-mid { color: var(--near-bright); }
.score-bad { color: var(--crit-bright); }
.score-detail { font: var(--text-micro); color: var(--gray-300); max-width: 120px; }
.cfg-btn { font: var(--text-small); background: transparent; color: var(--gray-300); border: 1px solid var(--gray-500); border-radius: var(--radius-sm); padding: 4px 10px; cursor: pointer; }
.cfg-btn:hover, .cfg-btn.active { color: var(--white); border-color: var(--white); }

.cfg-panel { border-bottom: 1px solid var(--gray-300); background: var(--gray-100); padding: var(--space-3) var(--space-4); }
.cfg-table { border-collapse: collapse; font: var(--text-small); }
.cfg-table th { text-align: left; font: var(--text-micro); text-transform: uppercase; color: var(--gray-700); padding: var(--space-1) var(--space-4) var(--space-1) 0; border-bottom: 1px solid var(--gray-300); }
.cfg-table td { padding: 3px var(--space-4) 3px 0; color: var(--ink); }
.cfg-off td { opacity: 0.5; }
.cfg-num { width: 58px; border: 1px solid var(--gray-300); border-radius: var(--radius-sm); padding: 2px 6px; background: var(--white); font-family: var(--font-mono); }
.cfg-na { color: var(--gray-500); font: var(--text-micro); }
.cfg-target { white-space: nowrap; font-family: var(--font-mono); }
.cfg-actions { display: flex; align-items: center; justify-content: space-between; gap: var(--space-4); margin-top: var(--space-3); flex-wrap: wrap; }
.cfg-note { font: var(--text-micro); color: var(--gray-700); max-width: 640px; }
.cfg-reset { font: var(--text-micro); border: 1px solid var(--gray-300); background: var(--white); padding: 4px 10px; border-radius: var(--radius-sm); cursor: pointer; color: var(--gray-700); }
.cfg-reset:hover { background: var(--gray-150); }

.scorecard { display: flex; flex-wrap: wrap; gap: 1px; background: var(--gray-300); border-bottom: 1px solid var(--gray-300); }
.score-item { flex: 1; min-width: 110px; background: var(--white); padding: var(--space-3); text-align: center; }
.score-item.clickable { cursor: pointer; }
.score-item.clickable:hover { background: var(--gray-100); }
.score-item.pass .score-count { color: var(--ok); }
.score-item.fail .score-count { color: var(--crit); }
.score-item.excluded { opacity: 0.55; }
.score-item.excluded .score-count { color: var(--gray-500); }
.score-count { font-family: var(--font-mono); font-size: 23px; font-weight: 700; }
.score-label { font: var(--text-micro); color: var(--gray-700); text-transform: uppercase; letter-spacing: 0.03em; }
.score-target { font: var(--text-micro); color: var(--gray-500); font-family: var(--font-mono); margin-top: 1px; }

.health-section { border-bottom: 1px solid var(--gray-300); }
.health-section:last-child { border-bottom: none; }
.section-title { font: 600 15px/1.4 var(--font-ui); }
.section-head { width: 100%; display: flex; align-items: center; gap: var(--space-4); padding: var(--space-3) var(--space-4); background: var(--gray-100); border: none; cursor: pointer; text-align: left; }
.section-head:hover { background: var(--gray-150); }
.section-title { font-weight: 600; color: var(--ink); white-space: nowrap; }
.section-title em { font-style: normal; color: var(--accent); font-family: var(--font-mono); }
.section-title em.pass { color: var(--ok); }
.section-hint { font: var(--text-small); color: var(--gray-700); flex: 1; }
.chevron { transition: transform 0.15s; color: var(--gray-500); font-size: 19px; }
.chevron.open { transform: rotate(90deg); }
.section-body { padding: var(--space-4); }
.section-note { font: var(--text-small); color: var(--gray-700); margin: var(--space-2) 0 var(--space-4); }
.section-body h4 { font: var(--text-small); font-weight: 700; color: var(--ink); margin: var(--space-4) 0 var(--space-2); }
.section-body h4:first-child { margin-top: 0; }
.empty-state { font: var(--text-small); color: var(--ok); }

.rel-mix { display: flex; gap: var(--space-6); flex-wrap: wrap; }
.rel-mix-item { display: flex; flex-direction: column; gap: 2px; }
.rel-mix-item strong { font-family: var(--font-mono); font-size: 19px; color: var(--ink); }
.rel-mix-item span { font: var(--text-micro); color: var(--gray-700); }

.health-table { width: 100%; border-collapse: collapse; font: var(--text-small); }
.health-table th { text-align: left; font: var(--text-micro); text-transform: uppercase; color: var(--gray-700); background: var(--gray-100); border-bottom: 2px solid var(--gray-300); padding: var(--space-2) var(--space-3); }
.health-table td { padding: 6px var(--space-3); border-bottom: 1px solid var(--gray-150); }
.jump-row { cursor: pointer; }
.jump-row:hover td { background: var(--accent-soft); }
.code { font-family: var(--font-mono); font-weight: 600; color: var(--accent); white-space: nowrap; }
.name-cell { color: var(--ink-soft); }
.wbs-cell { color: var(--gray-700); font: var(--text-micro); font-family: var(--font-mono); }
.num-cell { font-family: var(--font-mono); text-align: right; white-space: nowrap; }
.section-note-cell { color: var(--near); font: var(--text-micro); font-style: italic; }
.lag-neg { color: var(--crit); font-weight: 700; }

.tbl-name { display: block; color: var(--ink-soft); font: var(--text-micro); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 260px; }
.tg-th { width: 30px; }
.tg-cell { text-align: center; width: 30px; }
.to-gantt { border: 1px solid var(--gray-300); background: var(--white); color: var(--gray-700); border-radius: var(--radius-sm); width: 22px; height: 22px; line-height: 1; cursor: pointer; font-size: 12px; padding: 0; }
.to-gantt:hover { background: var(--active-soft); color: var(--active); border-color: var(--active); }
.issue-badge { font: var(--text-micro); padding: 1px 7px; border-radius: var(--radius-sm); font-weight: 600; }
.issue-severe { background: var(--crit); color: var(--white); }
.issue-warn { background: var(--near-tint); color: var(--near); }
</style>
