<template>
  <div class="health-wrap">
    <div class="view-bar">
      <div class="strip-title">
        <span class="strip-sub">{{ data.activities.length }} activities &middot; DCMA 14-Point Assessment checks, plus XERlock's own &middot; see the methodology for every definition</span>
      </div>
      <div class="strip-score">
        <span class="score-num" :class="scoreClass">{{ weightedScore }}%</span>
        <span class="score-detail" title="Weighted share of included checks that pass. This roll-up is XERlock's; DCMA defines pass/fail per metric, not a composite score.">{{ passCount }}/{{ includedCount }} checks pass &middot; weighted</span>
        <button class="cfg-btn" :class="{ active: showConfig }" @click="showConfig = !showConfig">⚙ Configure</button>
      </div>
    </div>

    <!-- Check configuration — below the results, not above them -->
    <div v-if="showConfig" class="cfg-panel">
      <table class="cfg-table">
        <thead>
          <tr><th>Include</th><th>Source</th><th>Check</th><th>Threshold</th><th>Target</th><th>Weight</th></tr>
        </thead>
        <tbody>
          <tr v-for="def in checkDefs" :key="def.key" :class="{ 'cfg-off': !cfg[def.key].enabled || !availability[def.key] }">
            <td>
              <input type="checkbox" v-model="cfg[def.key].enabled" :disabled="!availability[def.key]" />
            </td>
            <td class="cfg-source">{{ def.source }}</td>
            <td>
              {{ def.label }}
              <span v-if="!availability[def.key]" class="cfg-na">— {{ def.naReason || 'not checkable in this file' }}</span>
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
        <span class="cfg-note">Targets and weights are yours to set — contracts differ. Defaults are DCMA's. The score is the weighted share of passing checks — XERlock's roll-up, not a DCMA figure; excluded or un-checkable items never count toward it.</span>
        <button class="cfg-reset" @click="resetConfig">Reset to defaults</button>
      </div>
    </div>

    <!-- Unequal weight for unequal news: the failures are cards in the state colour,
         the passes collapse to a quiet strip, and what can't be checked is a footnote.
         Colour covers a small fraction of the view, so failures are pre-attentive. -->
    <!-- The settings every computed date depends on. Read before trusting any of them. -->
    <div v-if="schedOpts.present" class="hc-options">
      <span class="hc-group-label">P6 scheduling options</span>
      <span v-for="o in schedOptionRows" :key="o.label" class="hc-opt" :class="{ warn: o.warn }" :title="o.warn || ''">
        {{ o.label }} <b>{{ o.value }}</b>
      </span>
    </div>
    <div v-else class="hc-options">
      <span class="hc-group-label">P6 scheduling options</span>
      <span class="hc-opt">Not in this export (no SCHEDOPTIONS table) — P6 defaults assumed: lag on the predecessor's calendar, critical at TF ≤ {{ formatFloat(schedOpts.critical_float_hrs || 0, 8) }}</span>
    </div>

    <div class="hc-results">
      <template v-if="failingChecks.length">
        <div class="hc-group-label">Failing ({{ failingChecks.length }})</div>
        <div class="hc-fail-grid">
          <button
            v-for="item in failingChecks"
            :key="item.key"
            class="hc-fail-card"
            :class="{ clickable: item.section }"
            @click="item.section && openSection(item.section)"
            :title="item.tip"
          >
            <div class="hc-fail-value">{{ item.display }}</div>
            <div class="hc-fail-name">{{ item.label }}</div>
            <div class="hc-fail-target">target {{ item.targetText }}</div>
          </button>
        </div>
      </template>

      <div v-if="passingChecks.length" class="hc-pass-row">
        <span class="hc-group-label">Passing</span>
        <button
          v-for="item in passingChecks"
          :key="item.key"
          class="hc-pass-pill"
          :class="{ clickable: item.section }"
          @click="item.section && openSection(item.section)"
          :title="item.tip"
        >
          <b>{{ item.display }}</b>{{ item.label }}
        </button>
      </div>

      <p v-for="c in excludedChecks" :key="c.key" class="hc-footnote">
        {{ c.source }} {{ c.label }} — {{ c.naReason || 'not checkable in this file' }}
      </p>
    </div>

    <!-- Open Ends -->
    <section class="health-section" ref="sec-openEnds">
      <button class="section-head" @click="toggle('openEnds')">
        <span class="section-title">Open Ends <em :class="{ pass: openEnds.length === 0 }">({{ openEnds.length }})</em></span>
        <span class="section-hint">Incomplete activities whose start or finish is not tied into the logic — they can move without moving anything (DCMA 01; dangling ends per GAO). The project start and finish milestones are exempt</span>
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
              <td><span class="issue-badge" :class="a.bothOpen ? 'issue-severe' : 'issue-warn'">{{ a.bothOpen ? 'Both ends open' : (a.openStart ? (a.dangling ? 'Dangling start (FF/SF only)' : 'No predecessor') : (a.dangling ? 'Dangling finish (SS/SF only)' : 'No successor')) }}</span></td>
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
        <span class="section-hint">FS/SS/FF/SF mix, negative lags ("leads"), and lags{{ cfg.lags.param ? ' over ' + cfg.lags.param + ' working days' : '' }} — on links into incomplete work (DCMA 02–04)</span>
        <span class="chevron" :class="{ open: expanded.rel }">&rsaquo;</span>
      </button>
      <div v-if="expanded.rel" class="section-body">
        <div class="rel-mix">
          <div v-for="t in relTypeOrder" :key="t" class="rel-mix-item">
            <strong>{{ relationshipStats.counts[t] || 0 }}</strong>
            <span>{{ relTypeLabels[t] }} ({{ relationshipStats.total ? Math.round(100 * (relationshipStats.counts[t] || 0) / relationshipStats.total) : 0 }}%)</span>
          </div>
        </div>
        <p class="section-note" v-if="relationshipStats.total">DCMA 04: &ge;90% of relationships should be Finish-to-Start. This schedule is {{ relationshipStats.pctFs }}% FS.</p>

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

        <h4 v-if="relationshipStats.bigLags.length">Lags{{ cfg.lags.param ? ' over ' + cfg.lags.param + ' working days' : '' }} — {{ relationshipStats.bigLags.length }}</h4>
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

    <!-- ALAP constraints -->
    <section class="health-section" ref="sec-alap">
      <button class="section-head" @click="toggle('alap')">
        <span class="section-title">ALAP Constraints <em :class="{ pass: alapList.length === 0 }">({{ alapList.length }})</em></span>
        <span class="section-hint">Scheduled As Late As Possible, against late dates — it consumes the activity's float, and on the critical path it may be the constraint driving criticality rather than the logic</span>
        <span class="chevron" :class="{ open: expanded.alap }">&rsaquo;</span>
      </button>
      <div v-if="expanded.alap" class="section-body">
        <div v-if="alapList.length === 0" class="empty-state">✓ No activity is scheduled As Late As Possible.</div>
        <template v-else>
          <p class="section-note">
            {{ alapOnCriticalPath.length }} of {{ alapList.length }} sit on the critical path.
          </p>
          <table class="health-table">
            <thead><tr><th>Code</th><th>Activity</th><th>On critical path</th><th class="num">Float</th><th class="num">Finish</th><th>WBS</th></tr></thead>
            <tbody>
              <tr v-for="a in alapList" :key="a.task_id" class="jump-row" title="Show in Gantt" @click="$emit('jump', a.task_id)">
                <td class="code">{{ a.task_code }}</td>
                <td class="name-cell">{{ a.task_name }}</td>
                <td>
                  <span v-if="a.onCriticalPath" class="issue-badge issue-severe">On critical path</span>
                  <span v-else class="alap-off">—</span>
                </td>
                <td class="num-cell">{{ formatFloat(a.total_float_hrs, a.calendar_hrs_per_day) }}</td>
                <td class="num-cell">{{ formatDate(displayEnd(a)) }}</td>
                <td class="wbs-cell">{{ a.wbs_path }}</td>
              </tr>
            </tbody>
          </table>
        </template>
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
        <span class="section-hint">Planned to finish by the data date but still open, or finished late (DCMA 11). Measured against P6's Planned Finish, not a baseline — a single .xer carries none</span>
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
              <td>{{ a.status === 'TK_Complete' ? 'Finished late' : a.status === 'TK_Active' ? 'In progress' : 'Not started' }}</td>
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
        <span class="section-hint">Where P6's stored Longest Path flag disagrees with the path recomputed from the file's own dates — a sign the schedule was not recalculated after its last edit</span>
        <span class="chevron" :class="{ open: expanded.driving }">&rsaquo;</span>
      </button>
      <div v-if="expanded.driving" class="section-body">
        <div v-if="drivingMismatchList.length === 0" class="empty-state">✓ The recomputed Longest Path matches P6's own flag on every activity.</div>
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
        <span class="section-hint">Progress the logic says could not have happened yet: started before an FS predecessor finished or an SS predecessor started, or finished before an FF predecessor finished</span>
        <span class="chevron" :class="{ open: expanded.oos }">&rsaquo;</span>
      </button>
      <div v-if="expanded.oos" class="section-body">
        <div v-if="outOfSequenceList.length === 0" class="empty-state">✓ All recorded progress respects the network logic.</div>
        <table v-else class="health-table">
          <thead><tr><th>Activity</th><th>Link</th><th>What happened</th><th>Predecessor</th><th class="num">Predecessor date</th><th class="tg-th"></th></tr></thead>
          <tbody>
            <tr v-for="(r, i) in outOfSequenceList" :key="i" class="jump-row" title="Show details" @click="openDetail(r.activity.task_id)">
              <td><span class="code">{{ r.activity.task_code }}</span><span class="tbl-name">{{ r.activity.task_name }}</span></td>
              <td>{{ relTypeLabels[r.type] }}</td>
              <td>{{ r.what }}</td>
              <td><span class="code">{{ r.predecessor.task_code }}</span><span class="tbl-name">{{ r.predecessor.task_name }}</span></td>
              <td class="num-cell">{{ r.predDate ? formatDate(r.predDate) : 'Not yet' }}</td>
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
import { REL_TYPE_LABELS, CSTR_LABELS, displayStart, displayEnd } from '../utils/p6'
import { CHECK_DEFS, CFG_VERSION, defaultConfig, runChecks, weightedScore } from '../utils/healthChecks'
import ActivityDetailDrawer from './ActivityDetailDrawer.vue'

const CFG_KEY = 'schedule-app:health-config'

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
  emits: ['jump', 'annotate', 'unannotate', 'score'],
  data() {
    return {
      expanded: {
        openEnds: true,
        rel: true,
        constraints: false,
        alap: true,
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
    // The sidebar shows the score on the Health check nav item, so the state is
    // visible from any view without opening this one.
    weightedScore: { immediate: true, handler(v) { this.$emit('score', v) } },
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
    schedOpts() {
      return this.data.project.schedule_options || {}
    },
    // Each option with the reason it deserves a second look, where it does.
    schedOptionRows() {
      const o = this.schedOpts
      const yn = v => (v == null ? '—' : v ? 'Yes' : 'No')
      const critical = o.critical_type === 'CT_DrivPath'
        ? 'Longest Path'
        : `TF ≤ ${formatFloat(o.critical_float_hrs, 8)}`
      return [
        { label: 'Out-of-sequence progress', value: o.progress_override ? 'Progress Override' : o.retained_logic ? 'Retained Logic' : 'Actual Dates',
          warn: o.progress_override ? 'Progress Override lets out-of-sequence work ignore its predecessors; Retained Logic is the conservative setting' : '' },
        { label: 'Critical', value: critical },
        { label: 'Total float as', value: { FT_FF: 'Finish float', FT_SF: 'Start float', FT_SmallestFloat: 'Smallest' }[o.float_type] || o.float_type || '—' },
        { label: 'Lag calendar', value: { rcal_Predecessor: 'Predecessor', rcal_Successor: 'Successor', rcal_24Hour: '24-hour', rcal_ProjDefault: 'Project default' }[o.lag_calendar] || o.lag_calendar },
        { label: 'Open ends critical', value: yn(o.open_ends_critical) },
        { label: 'Expected finish dates', value: yn(o.use_expected_finish),
          warn: o.use_expected_finish ? 'Expected Finish lets an entered date set remaining duration instead of the estimate' : '' },
      ]
    },
    // All check logic lives in utils/healthChecks.js; these are views onto one run.
    checks() {
      return runChecks(this.data, this.cfg)
    },
    openEnds() { return this.checks.openEnds },
    relationshipStats() { return this.checks.relationshipStats },
    constraintList() { return this.checks.constraintList },
    alapList() { return this.checks.alapList },
    alapOnCriticalPath() { return this.checks.alapOnCriticalPath },
    negativeFloatList() { return this.checks.negativeFloatList },
    highFloatList() { return this.checks.highFloatList },
    invalidDatesList() { return this.checks.invalidDatesList },
    plannedDoneCount() { return this.checks.plannedDoneCount },
    missedTasksList() { return this.checks.missedTasksList },
    highDurationList() { return this.checks.highDurationList },
    loeOnCriticalList() { return this.checks.loeOnCriticalList },
    drivingPathAvailable() { return this.checks.drivingPathAvailable },
    drivingMismatchList() { return this.checks.drivingMismatchList },
    outOfSequenceList() { return this.checks.outOfSequenceList },
    noResourceList() { return this.checks.noResourceList },
    availability() { return this.checks.availability },
    checkResults() { return this.checks.results },
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
      return weightedScore(this.checkResults, this.cfg)
    },
    scoreClass() {
      return this.weightedScore >= 80 ? 'score-good' : this.weightedScore >= 60 ? 'score-mid' : 'score-bad'
    },
    failingChecks() {
      return this.scorecard.filter(c => c.state === 'fail')
    },
    passingChecks() {
      return this.scorecard.filter(c => c.state === 'pass')
    },
    excludedChecks() {
      return CHECK_DEFS.filter(d => !this.availability[d.key])
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
.strip-score { display: flex; align-items: center; gap: var(--space-3); }
.score-num { font-family: var(--font-mono); font-size: 27px; font-weight: 800; }
.score-good { color: var(--ok); }
.score-mid { color: var(--near); }
.score-bad { color: var(--crit); }
.score-detail { font: var(--text-micro); color: var(--ink-2); max-width: 120px; }
.cfg-btn { font: var(--text-small); background: transparent; color: var(--ink-2); border: 1px solid var(--ink-3); border-radius: var(--radius-sm); padding: 4px 10px; cursor: pointer; }
.cfg-btn:hover, .cfg-btn.active { color: var(--ink); border-color: var(--ink); }

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

.hc-results { padding: var(--space-3) var(--space-4); border-bottom: 1px solid var(--line); }
.hc-group-label { font-family: var(--font-mono); font-size: 9px; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: var(--ink-3); margin-bottom: var(--space-2); }
.hc-fail-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: var(--space-2); margin-bottom: var(--space-4); }
.hc-fail-card { text-align: left; border: 1px solid var(--crit); background: var(--crit-soft); border-radius: var(--radius-md); padding: var(--space-3); cursor: pointer; }
.hc-fail-card:hover { background: var(--panel); }
.hc-fail-value { font-family: var(--font-mono); font-size: 26px; font-weight: 700; color: var(--crit); line-height: 1.1; }
.hc-fail-name { font: var(--text-small); font-weight: 600; color: var(--ink); margin-top: 2px; }
.hc-fail-target { font-family: var(--font-mono); font-size: 10px; color: var(--ink-3); margin-top: 2px; }
.hc-pass-row { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.hc-pass-row .hc-group-label { margin-bottom: 0; margin-right: 2px; }
.hc-pass-pill { display: inline-flex; align-items: baseline; gap: 5px; border: 1px solid var(--line); background: var(--panel); border-radius: 14px; padding: 2px 10px; cursor: pointer; font-size: 11px; color: var(--ink-3); }
.hc-pass-pill:hover { border-color: var(--ok); color: var(--ink-2); }
.hc-pass-pill b { font-family: var(--font-mono); font-size: 11px; font-weight: 700; color: var(--ok); }
.hc-footnote { font-family: var(--font-mono); font-size: 10px; color: var(--ink-3); margin-top: var(--space-3); }
.hc-footnote + .hc-footnote { margin-top: 2px; }
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
.alap-off { color: var(--ink-3); }
.lag-neg { color: var(--crit); font-weight: 700; }

.tbl-name { display: block; color: var(--ink-soft); font: var(--text-micro); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 260px; }
.tg-th { width: 30px; }
.tg-cell { text-align: center; width: 30px; }
.to-gantt { border: 1px solid var(--gray-300); background: var(--white); color: var(--gray-700); border-radius: var(--radius-sm); width: 22px; height: 22px; line-height: 1; cursor: pointer; font-size: 12px; padding: 0; }
.to-gantt:hover { background: var(--active-soft); color: var(--active); border-color: var(--active); }
.issue-badge { font: var(--text-micro); padding: 1px 7px; border-radius: var(--radius-sm); font-weight: 600; }
.issue-severe { background: var(--crit); color: var(--on-solid); }
.issue-warn { background: var(--near-tint); color: var(--near); }
.cfg-source { font-family: var(--font-mono); font-size: 10px; color: var(--ink-3); white-space: nowrap; }
.hc-options { display: flex; flex-wrap: wrap; align-items: baseline; gap: var(--space-1) var(--space-4); padding: var(--space-3) var(--space-4); border-bottom: 1px solid var(--line-soft); font: var(--text-small); }
.hc-options .hc-group-label { margin-bottom: 0; }
.hc-opt { color: var(--ink-3); }
.hc-opt b { color: var(--ink); font-weight: 600; }
.hc-opt.warn b { color: var(--near); }
</style>
