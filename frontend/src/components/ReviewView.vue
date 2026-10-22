<template>
  <div class="review" ref="root">
    <div class="rv-actions no-export">
      <span class="rv-actions-note">One page to forward: what the file is, what is wrong with it, what to ask.</span>
      <button class="btn-outline" @click="printPage">Print or save as PDF</button>
      <button class="btn-outline" @click="saveHtml">Download as HTML</button>
    </div>

    <header class="rv-head">
      <h2>{{ data.project.proj_short_name }}</h2>
      <p class="rv-sub">{{ r.kind }}<template v-if="filename"> &middot; {{ filename }}</template> &middot; data date {{ r.dataDate ? formatDate(r.dataDate) : 'not set' }}</p>
      <div class="rv-figures">
        <div><b>{{ r.activities }}</b><span>activities</span></div>
        <div><b>{{ r.finish ? formatDate(r.finish) : '—' }}</b><span>forecast finish</span></div>
        <div><b>{{ r.longestPath }}</b><span>on the longest path</span></div>
        <div><b>{{ r.complete }}/{{ r.activities }}</b><span>complete</span></div>
      </div>
    </header>

    <section class="rv-section">
      <h3>Verdict</h3>
      <div class="rv-verdict">
        <div class="rv-score" :class="scoreClass">{{ r.score }}%</div>
        <div>
          <p class="rv-score-text">{{ r.checksPassing }} of {{ r.checksIncluded }} schedule-quality checks pass: 100 − {{ fmt(r.pointsLost) }} points lost, each check weighted as configured in the Health check.</p>
          <p v-if="!r.findings.length" class="rv-ok">Every included check passes.</p>
        </div>
      </div>
      <ol v-if="r.findings.length" class="rv-findings">
        <li v-for="f in r.findings.slice(0, 5)" :key="f.key">
          <span class="rv-f-name">{{ f.label }}</span>
          <span class="rv-f-measure">{{ f.measure }}</span>
          <span class="rv-f-pts">−{{ fmt(f.pointsLost) }} pts</span>
        </li>
      </ol>
      <p v-if="r.findings.length > 5" class="rv-more">and {{ r.findings.length - 5 }} more failing {{ r.findings.length - 5 === 1 ? 'check' : 'checks' }}.</p>
      <button class="rv-link no-export" @click="$emit('open', 'health')">Open the Health check for the offending activities &rarr;</button>
    </section>

    <section class="rv-section">
      <h3>Schedule risk</h3>
      <ul class="rv-risks">
        <li :class="{ bad: r.negativeFloat > 0 }"><b>{{ r.negativeFloat }}</b> {{ r.negativeFloat === 1 ? 'activity has' : 'activities have' }} negative float: already behind a date imposed on them.</li>
        <li><b>{{ r.nearCritical }}</b> incomplete {{ r.nearCritical === 1 ? 'activity is' : 'activities are' }} near-critical (total float of 10 working days or less).</li>
        <li v-if="r.cpli" :class="{ bad: r.cpli.value < 0.95 }">CPLI <b>{{ r.cpli.value.toFixed(2) }}</b>: a {{ r.cpli.pathDays }}-day path to the finish with {{ r.cpli.finishFloatDays }} days of float on it (below 0.95, the finish needs the path compressed).</li>
      </ul>
    </section>

    <section v-if="r.milestonesAhead.length" class="rv-section">
      <h3>Milestones ahead <em>{{ r.milestonesAchieved }} achieved</em></h3>
      <table class="rv-table">
        <thead><tr><th>Milestone</th><th class="num">Target</th><th class="num">Forecast</th><th class="num">Variance</th><th>Status</th></tr></thead>
        <tbody>
          <tr v-for="m in r.milestonesAhead.slice(0, 8)" :key="m.task_id">
            <td><span class="code">{{ m.task_code }}</span> {{ m.task_name }}</td>
            <td class="num">{{ m.target ? formatDate(m.target) : '—' }}</td>
            <td class="num">{{ m.forecast ? formatDate(m.forecast) : '—' }}</td>
            <td class="num" :class="{ bad: (m.varianceDays ?? 0) > 0 }">{{ m.varianceDays == null ? '—' : (m.varianceDays > 0 ? '+' : '') + m.varianceDays + 'd' }}</td>
            <td><span class="rv-chip" :class="'st-' + m.status">{{ statusLabels[m.status] }}</span></td>
          </tr>
        </tbody>
      </table>
      <p v-if="r.milestonesAhead.length > 8" class="rv-more">and {{ r.milestonesAhead.length - 8 }} more.</p>
    </section>

    <section v-if="r.compare" class="rv-section">
      <h3>Against the earlier file <em>{{ compareFilename }}</em></h3>
      <p class="rv-compare">
        Finish {{ r.compare.earlierFinish ? formatDate(r.compare.earlierFinish) : '—' }} &rarr; {{ r.finish ? formatDate(r.finish) : '—' }}:
        <b :class="r.compare.verdict.cls">{{ r.compare.finishDeltaDays > 0 ? '+' : '' }}{{ r.compare.finishDeltaDays }}d {{ r.compare.finishDeltaDays > 0 ? 'later' : r.compare.finishDeltaDays < 0 ? 'earlier' : 'unchanged' }}</b>
        &middot; longest path kept {{ r.compare.longestPathKept }}
        <span v-for="c in r.compare.verdict.chips" :key="c" class="rv-chip">{{ c }}</span>
      </p>
    </section>

    <section v-if="r.notes.length" class="rv-section">
      <h3>Review notes <em>{{ r.notes.length }}</em></h3>
      <ul class="rv-notes">
        <li v-for="n in r.notes" :key="n.code">
          <span class="code">{{ n.code }}</span> <b>{{ n.name }}</b>
          <span v-if="n.severity" class="rv-chip" :class="'sev-' + n.severity">{{ severityLabels[n.severity] }}</span>
          <div class="rv-note">{{ n.note }}</div>
        </li>
      </ul>
    </section>

    <footer class="rv-foot">Read from the file as exported, by XERlock (read-only) on {{ formatDate(new Date().toISOString()) }}. Every figure is defined in the methodology; the checks' targets and weights are as configured in the Health check.</footer>
  </div>
</template>

<script lang="ts">
import { defineComponent, type PropType } from 'vue'
import type { Schedule } from '../types/schedule'
import { SEVERITY_LABELS, type Annotations } from '../utils/annotations'
import { loadHealthConfig } from '../utils/healthChecks'
import { MILESTONE_STATUS_LABELS } from '../utils/milestones'
import { buildReview, type Review } from '../utils/review'
import { formatDate } from '../utils/format'
import { downloadFile, standaloneHtml } from '../utils/exportHtml'

export default defineComponent({
  name: 'ReviewView',
  props: {
    data: { type: Object as PropType<Schedule>, required: true },
    annotations: { type: Object as PropType<Annotations>, default: () => ({}) },
    filename: { type: String, default: '' },
    compareData: { type: Object as PropType<Schedule | null>, default: null },
    compareFilename: { type: String, default: '' },
    /** Changes when the Health check's targets or weights do (its score), so the
     *  verdict is rebuilt with them. */
    refreshKey: { type: [Number, null] as PropType<number | null>, default: null },
  },
  emits: ['open'],
  data() {
    return { statusLabels: MILESTONE_STATUS_LABELS, severityLabels: SEVERITY_LABELS as Record<string, string> }
  },
  computed: {
    r(): Review {
      void this.refreshKey
      return buildReview(this.data, loadHealthConfig(), this.annotations, this.compareData)
    },
    scoreClass(): string {
      return this.r.score >= 80 ? 'good' : this.r.score >= 60 ? 'mid' : 'bad'
    },
  },
  methods: {
    formatDate,
    fmt(p: number): string {
      return p >= 10 || Number.isInteger(p) ? String(Math.round(p)) : p.toFixed(1)
    },
    printPage() {
      window.print()
    },
    saveHtml() {
      const name = `${this.data.project.proj_short_name || 'schedule'}-review.html`.replace(/[^\w.-]+/g, '_')
      downloadFile(name, standaloneHtml(this.$refs.root as HTMLElement, `${this.data.project.proj_short_name} — schedule review`))
    },
  },
})
</script>

<style scoped>
.review { max-width: 980px; margin: 0 auto; font: var(--text-body); background: var(--panel); border: 1px solid var(--gray-300); border-radius: var(--radius-md); padding: var(--space-5) var(--space-6); color: var(--ink); }
.rv-actions { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; margin-bottom: var(--space-4); }
.rv-actions-note { margin-right: auto; font: var(--text-small); color: var(--ink-3); }
.rv-head h2 { margin: 0; font-size: 22px; }
.rv-sub { margin: 4px 0 var(--space-3); font: var(--text-small); color: var(--ink-3); }
.rv-figures { display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--space-3); padding: var(--space-3) 0; border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); }
.rv-figures div { display: flex; flex-direction: column; }
.rv-figures b { font-family: var(--font-mono); font-size: 18px; }
.rv-figures span { font: var(--text-micro); text-transform: uppercase; letter-spacing: 0.04em; color: var(--ink-3); }
.rv-section { margin-top: var(--space-5); break-inside: avoid; }
.rv-section h3 { margin: 0 0 var(--space-2); font-size: 15px; }
.rv-section h3 em { font-style: normal; font-weight: 400; color: var(--ink-3); margin-left: 6px; font-size: 13px; }
.rv-verdict { display: flex; align-items: center; gap: var(--space-4); }
.rv-score { font-family: var(--font-mono); font-size: 40px; font-weight: 800; }
.rv-score.good { color: var(--ok); } .rv-score.mid { color: var(--near); } .rv-score.bad { color: var(--crit); }
.rv-score-text { margin: 0; font: var(--text-small); color: var(--ink-2); max-width: 640px; }
.rv-ok { margin: 4px 0 0; color: var(--ok); font-weight: 600; }
.rv-findings { margin: var(--space-3) 0 0; padding-left: 20px; }
.rv-findings li { padding: 5px 0; border-bottom: 1px solid var(--line-soft); display: flex; gap: var(--space-3); align-items: baseline; flex-wrap: wrap; }
.rv-f-name { font-weight: 600; min-width: 220px; font-size: 14px; }
.rv-f-measure { color: var(--ink-2); font: var(--text-small); flex: 1; }
.rv-f-pts { font-family: var(--font-mono); font-size: 12px; font-weight: 700; color: var(--crit); }
.rv-more { margin: 6px 0 0; font: var(--text-small); color: var(--ink-3); }
.rv-link { margin-top: var(--space-2); border: none; background: none; padding: 0; color: var(--accent); font: var(--text-small); font-weight: 600; cursor: pointer; }
.rv-risks { margin: 0; padding-left: 20px; }
.rv-risks li { padding: 3px 0; font: var(--text-small); }
.rv-risks li.bad b, td.bad, .rv-compare .v-slip { color: var(--crit); }
.rv-compare .v-gain { color: var(--ok); }
.rv-table { width: 100%; border-collapse: collapse; font: var(--text-small); }
.rv-table th { text-align: left; font: var(--text-micro); text-transform: uppercase; color: var(--ink-3); border-bottom: 1px solid var(--gray-300); padding: 4px 6px; }
.rv-table td { padding: 5px 6px; border-bottom: 1px solid var(--line-soft); }
.rv-table .num { text-align: right; font-family: var(--font-mono); white-space: nowrap; }
.code { font-family: var(--font-mono); color: var(--accent); font-weight: 600; }
.rv-chip { display: inline-block; font: var(--text-micro); font-weight: 600; border: 1px solid var(--gray-300); border-radius: 10px; padding: 0 7px; margin-left: 6px; }
.st-at-risk, .sev-risk { color: var(--crit); border-color: var(--crit); }
.st-watch, .sev-query { color: var(--near); border-color: var(--near); }
.st-on-track, .sev-resolved { color: var(--ok); border-color: var(--ok); }
.rv-notes { list-style: none; margin: 0; padding: 0; }
.rv-notes li { padding: 6px 0; border-bottom: 1px solid var(--line-soft); font: var(--text-small); }
.rv-note { margin-top: 2px; font: var(--text-small); color: var(--ink-2); white-space: pre-wrap; }
.rv-foot { margin-top: var(--space-6); font: var(--text-micro); color: var(--ink-3); }
@media (max-width: 700px) {
  .review { padding: var(--space-4); }
  .rv-figures { grid-template-columns: 1fr 1fr; }
}
@media print {
  .no-export { display: none !important; }
  .review { border: none; padding: 0; max-width: none; }
}
</style>
