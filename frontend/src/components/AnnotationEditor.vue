<template>
  <div class="annotation-editor">
    <div class="annotation-head">
      <h4>Review Note</h4>
      <span v-if="annotation" class="annotation-time">{{ timeAgo(annotation.updatedAt) }}</span>
    </div>
    <div class="severity-picker">
      <button
        v-for="s in severities"
        :key="s"
        type="button"
        class="severity-chip"
        :class="['sev-' + s, { active: draftSeverity === s }]"
        @click="draftSeverity = draftSeverity === s ? null : s"
      >{{ severityLabels[s] }}</button>
    </div>
    <textarea
      v-model="draftNote"
      class="annotation-note"
      rows="2"
      placeholder="Notes for this activity (query, risk, logic issue)…"
      title="Ctrl+Enter saves"
      @keydown.ctrl.enter.prevent="save"
    ></textarea>
    <div class="annotation-actions">
      <button class="btn-tiny-light" :class="{ saved: justSaved }" @click="save" :disabled="!draftSeverity && !draftNote.trim()">{{ justSaved ? 'Saved ✓' : 'Save' }}</button>
      <button v-if="annotation" class="btn-tiny-light btn-remove" @click="$emit('remove')">Remove</button>
      <span v-if="annotation" class="annotation-share">
        <button class="btn-tiny-light" title="Copy this note as plain text" @click="copy">{{ justCopied ? 'Copied ✓' : 'Copy' }}</button>
        <button class="btn-tiny-light" title="Download this note as a .txt file" @click="exportTxt">Export .txt</button>
      </span>
    </div>
  </div>
</template>

<script>
import { SEVERITIES, SEVERITY_LABELS } from '../utils/annotations'
import { timeAgo } from '../utils/format'
import { copyNoteToClipboard, exportNoteTxt } from '../utils/export'

export default {
  name: 'AnnotationEditor',
  props: {
    annotation: { type: Object, default: null },
    // Minimal context needed to label a shared note (code/name/wbs/dates/float) — the
    // full activity object works fine here.
    activity: { type: Object, default: null },
    projectName: { type: String, default: '' },
  },
  emits: ['save', 'remove'],
  data() {
    return {
      justSaved: false,
      justCopied: false,
      draftSeverity: this.annotation ? this.annotation.severity : null,
      draftNote: this.annotation ? this.annotation.note : '',
      severities: SEVERITIES,
      severityLabels: SEVERITY_LABELS,
    }
  },
  watch: {
    annotation(a) {
      this.draftSeverity = a ? a.severity : null
      this.draftNote = a ? a.note : ''
    },
  },
  methods: {
    timeAgo,
    save() {
      this.$emit('save', { severity: this.draftSeverity, note: this.draftNote.trim() })
      this.justSaved = true
      setTimeout(() => { this.justSaved = false }, 1500)
    },
    async copy() {
      const ok = await copyNoteToClipboard(this.projectName, this.activity, this.annotation)
      if (!ok) {
        alert('Could not copy to the clipboard — try Export .txt instead.')
        return
      }
      this.justCopied = true
      setTimeout(() => { this.justCopied = false }, 1500)
    },
    exportTxt() {
      exportNoteTxt(this.projectName, this.activity, this.annotation)
    },
  },
}
</script>

<style scoped>
.annotation-editor { border-top: 1px dashed var(--gray-300); margin-top: var(--space-4); padding-top: var(--space-3); }
.annotation-head { display: flex; align-items: baseline; gap: var(--space-2); margin-bottom: var(--space-2); }
.annotation-head h4 { margin: 0; font: 700 13px/1.3 var(--font-ui); text-transform: uppercase; letter-spacing: 0.04em; color: var(--gray-700); }
.annotation-time { font: var(--text-micro); color: var(--gray-500); }
.severity-picker { display: flex; gap: 6px; margin-bottom: var(--space-2); flex-wrap: wrap; }
.severity-chip { font: var(--text-micro); padding: 3px 10px; border-radius: 12px; border: 1px solid var(--gray-300); background: var(--white); color: var(--gray-700); cursor: pointer; font-weight: 600; }
.severity-chip.sev-query.active { background: var(--active-soft); border-color: var(--active); color: var(--active); }
.severity-chip.sev-risk.active { background: var(--near-tint); border-color: var(--near); color: var(--near); }
.severity-chip.sev-logic.active { background: var(--crit-tint); border-color: var(--crit); color: var(--crit); }
.severity-chip.sev-resolved.active { background: var(--ok-tint); border-color: var(--ok); color: var(--ok); }
.annotation-note { width: 100%; box-sizing: border-box; font: var(--text-small); font-family: var(--font-ui); padding: 6px 8px; border: 1px solid var(--gray-300); border-radius: var(--radius-sm); resize: vertical; }
.annotation-actions { display: flex; gap: var(--space-2); margin-top: var(--space-2); align-items: center; flex-wrap: wrap; }
.annotation-share { display: flex; gap: var(--space-2); margin-left: auto; }
.btn-remove { color: var(--crit); }
.btn-tiny-light.saved { color: var(--ok); border-color: var(--ok); }
</style>
