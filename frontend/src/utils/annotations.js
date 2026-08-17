const PREFIX = 'schedule-app:annotations:'

export const SEVERITIES = ['query', 'risk', 'logic', 'resolved']
export const SEVERITY_LABELS = { query: 'Query', risk: 'Risk', logic: 'Logic Issue', resolved: 'Resolved' }

function keyFor(projectKey) {
  return PREFIX + (projectKey || 'default')
}

export function loadAnnotations(projectKey) {
  try {
    const raw = localStorage.getItem(keyFor(projectKey))
    return raw ? JSON.parse(raw) : {}
  } catch {
    return {}
  }
}

function persist(projectKey, annotations) {
  try {
    localStorage.setItem(keyFor(projectKey), JSON.stringify(annotations))
  } catch {
    // Quota exceeded or storage unavailable — annotations just won't persist across reloads.
  }
}

export function saveAnnotation(projectKey, taskId, { severity, note }) {
  const all = loadAnnotations(projectKey)
  all[taskId] = { severity, note, updatedAt: Date.now() }
  persist(projectKey, all)
  return all
}

export function removeAnnotation(projectKey, taskId) {
  const all = loadAnnotations(projectKey)
  delete all[taskId]
  persist(projectKey, all)
  return all
}
