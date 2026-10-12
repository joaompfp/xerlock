const PREFIX = 'schedule-app:annotations:'

export type Severity = 'query' | 'risk' | 'logic' | 'resolved'

export interface Annotation {
  /** null for a note saved without a severity flag. */
  severity: Severity | null
  note: string
  updatedAt: number
}

/** task_id -> annotation. Keys are strings once round-tripped through JSON. */
export type Annotations = Record<string, Annotation>

export const SEVERITIES: readonly Severity[] = ['query', 'risk', 'logic', 'resolved']
export const SEVERITY_LABELS: Record<string, string> = { query: 'Query', risk: 'Risk', logic: 'Logic Issue', resolved: 'Resolved' }

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
  all[taskId] = { severity, note, updatedAt: Date.now() }
  persist(projectKey, all)
  return all
}

export function removeAnnotation(projectKey: string | null | undefined, taskId: number | string): Annotations {
  const all = loadAnnotations(projectKey)
  delete all[taskId]
  persist(projectKey, all)
  return all
}
