const PREFIX = 'schedule-app:annotations:'

export type Severity = 'query' | 'risk' | 'logic' | 'resolved'

export interface Annotation {
  /** null for a note saved without a severity flag. */
  severity: Severity | null
  note: string
  updatedAt: number
  /** Present while the note's callout is shown on the Gantt: its offset in pixels from
   *  the bar's finish end, so it follows the bar through zoom and scroll. */
  callout?: CalloutOffset
}

export interface CalloutOffset { dx: number; dy: number }

/** Where a newly opened callout sits: just right of the bar end, a little below it. */
export const DEFAULT_CALLOUT: CalloutOffset = { dx: 18, dy: 10 }

/** task_id -> annotation. Keys are strings once round-tripped through JSON. */
export type Annotations = Record<string, Annotation>

export const SEVERITIES: readonly Severity[] = ['query', 'risk', 'logic', 'resolved']
export const SEVERITY_LABELS: Record<string, string> = { query: 'Query', risk: 'Risk', logic: 'Logic Issue', resolved: 'Resolved' }

// The Gantt's notes filter: every noted activity, one severity, or notes saved without one.
export type NoteFilter = '' | 'any' | 'unflagged' | Severity

export const NOTE_FILTER_LABELS: Record<Exclude<NoteFilter, ''>, string> = {
  any: 'Any note', ...SEVERITY_LABELS, unflagged: 'No severity',
} as Record<Exclude<NoteFilter, ''>, string>

export function matchesNoteFilter(a: Annotation | undefined, f: NoteFilter): boolean {
  if (!f) return true
  if (!a) return false
  if (f === 'any') return true
  if (f === 'unflagged') return a.severity === null
  return a.severity === f
}

function keyFor(projectKey: string | null | undefined): string {
  return PREFIX + (projectKey || 'default')
}

export function loadAnnotations(projectKey: string | null | undefined): Annotations {
  try {
    const raw = localStorage.getItem(keyFor(projectKey))
    return raw ? (JSON.parse(raw) as Annotations) : {}
  } catch {
    return {}
  }
}

function persist(projectKey: string | null | undefined, annotations: Annotations): void {
  try {
    localStorage.setItem(keyFor(projectKey), JSON.stringify(annotations))
  } catch {
    // Quota exceeded or storage unavailable — annotations just won't persist across reloads.
  }
}

export function saveAnnotation(
  projectKey: string | null | undefined,
  taskId: number | string,
  { severity, note }: { severity: Severity | null; note: string },
): Annotations {
  const all = loadAnnotations(projectKey)
  // Editing the text keeps the callout where the reviewer put it.
  all[taskId] = { ...all[taskId], severity, note, updatedAt: Date.now() }
  persist(projectKey, all)
  return all
}

export function removeAnnotation(projectKey: string | null | undefined, taskId: number | string): Annotations {
  const all = loadAnnotations(projectKey)
  delete all[taskId]
  persist(projectKey, all)
  return all
}

/** Show (with an offset) or hide (null) a note's callout. No-op for an unannotated task. */
export function setCallout(
  projectKey: string | null | undefined,
  taskId: number | string,
  callout: CalloutOffset | null,
): Annotations {
  const all = loadAnnotations(projectKey)
  const a = all[taskId]
  if (!a) return all
  if (callout) a.callout = { dx: Math.round(callout.dx), dy: Math.round(callout.dy) }
  else delete a.callout
  persist(projectKey, all)
  return all
}
