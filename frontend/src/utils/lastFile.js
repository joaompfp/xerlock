const STORAGE_KEY = 'schedule-app:last-file'

// Bump whenever the parsed-payload shape changes (new fields on activities/project).
// A cached payload from an older schema silently lacks the new fields — features
// depending on them would just not render, with no error — so a version mismatch
// invalidates the cache and the user re-uploads instead.
const SCHEMA_VERSION = 3

export function loadLastFile() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (parsed.schemaVersion !== SCHEMA_VERSION) {
      localStorage.removeItem(STORAGE_KEY)
      return null
    }
    return parsed
  } catch {
    return null
  }
}

export function saveLastFile(filename, data) {
  const payload = d => JSON.stringify({ filename, data: d, savedAt: Date.now(), schemaVersion: SCHEMA_VERSION })
  try {
    localStorage.setItem(STORAGE_KEY, payload(data))
  } catch {
    // Quota exceeded — raw tables are by far the largest part of the payload, so retry
    // without them (flagged, so the Tables tab can explain) before giving up entirely.
    try {
      localStorage.setItem(STORAGE_KEY, payload({ ...data, raw_tables: {}, raw_tables_omitted: true }))
    } catch {
      // Storage unavailable or still too large — the app works, just no "reopen last file".
    }
  }
}

export function clearLastFile() {
  try {
    localStorage.removeItem(STORAGE_KEY)
  } catch {
    // ignore
  }
}
