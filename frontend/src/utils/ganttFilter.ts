// The Gantt's filter: what a reviewer narrows the chart to (search, status, constraint,
// notes, critical only, a date window, activity codes), how an activity is tested
// against it, and how an active filter is described back to them. Pure functions, so
// the component holds one filter object and the rules live here, tested.

import type { Activity } from '../types/schedule'
import { displayStart, displayEnd, CONSTRAINT_FILTER_GROUPS, CSTR_LABELS, constraintTypesOf, matchesConstraintFilter, constraintFilterLabel, cstrLabel } from './p6'
import { matchesNoteFilter, NOTE_FILTER_LABELS, type Annotations, type NoteFilter } from './annotations'
import { formatDateShort } from './format'

export interface GanttFilter {
  text: string
  status: string
  constraint: string
  notes: NoteFilter
  criticalOnly: boolean
  /** Date window, ISO days, inclusive; either end may be open. */
  from: string
  to: string
  /** Activity code type → chosen code ('' for none), one entry per type in the file. */
  codes: Record<string, string>
}

export const STATUS_LABELS: Record<string, string> = { TK_NotStart: 'Not started', TK_Active: 'Active', TK_Complete: 'Complete' }

/** No filter, with one empty entry per code type: an undefined v-model renders a select blank. */
export function emptyFilter(codeTypes: string[] | null | undefined): GanttFilter {
  return {
    text: '', status: '', constraint: '', notes: '', criticalOnly: false, from: '', to: '',
    codes: Object.fromEntries<string>((codeTypes || []).map(t => [t, ''])),
  }
}

export function activeCodes(f: GanttFilter): [string, string][] {
  return Object.entries(f.codes).filter(([, v]) => v)
}

export function isFilterSet(f: GanttFilter): boolean {
  return !!(f.text.trim() || f.status || f.constraint || f.notes || f.criticalOnly || f.from || f.to || activeCodes(f).length)
}

export interface MatchContext {
  annotations: Annotations
  isCritical: (a: Activity) => boolean
}

export function matchesFilter(a: Activity, f: GanttFilter, ctx: MatchContext): boolean {
  const q = f.text.trim().toLowerCase()
  if (q && !(a.task_code.toLowerCase().includes(q) || a.task_name.toLowerCase().includes(q) || (a.wbs_path && a.wbs_path.toLowerCase().includes(q)))) return false
  if (f.status && a.status !== f.status) return false
  if (f.from || f.to) {
    // Window-intersection on the display dates (actual once started, else early):
    // an activity is shown if any part of it touches [from, to]. ISO date-prefix
    // string comparison is deliberate — no timezone surprises.
    const aStart = (displayStart(a) || '').slice(0, 10)
    const aEnd = (displayEnd(a) || aStart || '').slice(0, 10)
    if (!aStart) return false
    if (f.from && aEnd < f.from) return false
    if (f.to && aStart > f.to) return false
  }
  if (!matchesConstraintFilter(a, f.constraint)) return false
  if (!matchesNoteFilter(ctx.annotations[a.task_id], f.notes)) return false
  if (f.criticalOnly && !ctx.isCritical(a)) return false
  const codes = activeCodes(f)
  if (codes.length && !codes.every(([type, code]) => a.activity_codes.some(c => c.type === type && c.code === code))) return false
  return true
}

/** The filter with one chip's condition removed (ids as `filterChips` gives them). */
export function withoutChip(f: GanttFilter, id: string): GanttFilter {
  if (id === 'text') return { ...f, text: '' }
  if (id === 'status') return { ...f, status: '' }
  if (id === 'cstr') return { ...f, constraint: '' }
  if (id === 'notes') return { ...f, notes: '' }
  if (id === 'crit') return { ...f, criticalOnly: false }
  if (id === 'dates') return { ...f, from: '', to: '' }
  if (id.startsWith('code:')) return { ...f, codes: { ...f.codes, [id.slice(5)]: '' } }
  return f
}

// ── Look-ahead: the window every site meeting asks for — data date + N days ──

export const LOOK_AHEAD_DAYS = [28, 56]

export function lookAheadWindow(dataDate: string | null | undefined, days: number): { from: string; to: string } | null {
  if (!dataDate) return null
  const from = dataDate.slice(0, 10)
  const end = new Date(from + 'T12:00:00')
  end.setDate(end.getDate() + days)
  const to = `${end.getFullYear()}-${String(end.getMonth() + 1).padStart(2, '0')}-${String(end.getDate()).padStart(2, '0')}`
  return { from, to }
}

export function lookAheadActive(f: GanttFilter, dataDate: string | null | undefined, days: number): boolean {
  const w = lookAheadWindow(dataDate, days)
  return !!w && f.from === w.from && f.to === w.to
}

/** Sets the look-ahead window, or clears it when that window is already the one set. */
export function toggleLookAhead(f: GanttFilter, dataDate: string | null | undefined, days: number): GanttFilter {
  const w = lookAheadWindow(dataDate, days)
  if (!w) return f
  return lookAheadActive(f, dataDate, days) ? { ...f, from: '', to: '' } : { ...f, from: w.from, to: w.to }
}

// ── Describing the filter back ──────────────────────────────────────────────

/** One label per active condition — the printout's title line states exactly what is
 *  narrowing the view, so a filtered chart can't be read as the whole programme. */
export function filterChips(f: GanttFilter, dataDate: string | null | undefined): { id: string; label: string }[] {
  const out: { id: string; label: string }[] = []
  const q = f.text.trim()
  if (q) out.push({ id: 'text', label: `Search: ${q}` })
  if (f.status) out.push({ id: 'status', label: `Status: ${STATUS_LABELS[f.status] || f.status}` })
  if (f.constraint) out.push({ id: 'cstr', label: `Constraint: ${constraintFilterLabel(f.constraint)}` })
  if (f.notes) out.push({ id: 'notes', label: `Notes: ${NOTE_FILTER_LABELS[f.notes]}` })
  if (f.criticalOnly) out.push({ id: 'crit', label: 'Critical only' })
  if (f.from || f.to) {
    const la = LOOK_AHEAD_DAYS.find(d => lookAheadActive(f, dataDate, d))
    out.push({ id: 'dates', label: la
      ? `${la / 7}-week look-ahead`
      : `Window: ${f.from ? formatDateShort(f.from) : '…'} – ${f.to ? formatDateShort(f.to) : '…'}` })
  }
  for (const [type, code] of activeCodes(f)) out.push({ id: 'code:' + type, label: `${type}: ${code}` })
  return out
}

export function emptyFilterHint(f: GanttFilter): string {
  const bits: string[] = []
  if (f.text.trim()) bits.push(`text “${f.text.trim()}”`)
  if (f.status) bits.push('a status')
  if (f.constraint) bits.push('a constraint')
  if (f.notes) bits.push('notes')
  if (f.criticalOnly) bits.push('critical only')
  if (f.from || f.to) bits.push('a date window')
  if (activeCodes(f).length) bits.push('an activity code')
  return bits.length
    ? `Filtering by ${bits.join(', ')}.`
    : 'This schedule has no activities to show.'
}

// ── Choices offered, counted on this file ───────────────────────────────────

export interface CountedOption<T extends string = string> { value: T; label: string; count: number }

/** The groups first, then each P6 type in its usual order, counted on this file so an
 *  empty choice is visibly empty rather than a surprise blank chart. */
export function constraintOptions(activities: Activity[]): CountedOption[] {
  const counts = new Map<string, number>()
  const bump = (k: string) => counts.set(k, (counts.get(k) || 0) + 1)
  for (const a of activities) {
    for (const t of new Set(constraintTypesOf(a))) bump(t)
    for (const g of Object.keys(CONSTRAINT_FILTER_GROUPS)) if (matchesConstraintFilter(a, g)) bump(g)
  }
  const groups = Object.entries(CONSTRAINT_FILTER_GROUPS).map(([value, label]) => ({ value, label, count: counts.get(value) || 0 }))
  const types = Object.keys(CSTR_LABELS).filter(t => counts.has(t))
    .map(t => ({ value: t, label: cstrLabel(t), count: counts.get(t)! }))
  return [...groups, ...types]
}

/** Counted over this file's activities, so a note left on an activity the file no
 *  longer has doesn't promise a match. */
export function noteOptions(activities: Activity[], annotations: Annotations): CountedOption<NoteFilter>[] {
  const notes = activities.map(a => annotations[a.task_id]).filter(Boolean)
  return (Object.entries(NOTE_FILTER_LABELS) as [NoteFilter, string][])
    .map(([value, label]) => ({ value, label, count: notes.filter(n => matchesNoteFilter(n, value)).length }))
}

/** Each code type's values in this file, sorted. */
export function codeValuesByType(activities: Activity[], types: string[]): Map<string, string[]> {
  const sets = new Map<string, Set<string>>()
  for (const t of types) sets.set(t, new Set())
  for (const a of activities) for (const c of a.activity_codes) sets.get(c.type)?.add(c.code)
  const m = new Map<string, string[]>()
  for (const [t, set] of sets) m.set(t, [...set].sort())
  return m
}
