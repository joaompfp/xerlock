const STORAGE_KEY = 'schedule-app:last-file'

// Bump whenever the parsed-payload shape changes (new fields on activities/project).
// A cached payload from an older schema silently lacks the new fields — features
// depending on them would just not render, with no error — so a version mismatch
// invalidates the cache and the user re-uploads instead.
const SCHEMA_VERSION = 2

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
  try {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ filename, data, savedAt: Date.now(), schemaVersion: SCHEMA_VERSION })
    )
  } catch {
    // Quota exceeded (a very large schedule) or storage unavailable — the app still
    // works fine, it just won't offer a "reopen last file" shortcut next time.
  }
}

export function clearLastFile() {
  try {
    localStorage.removeItem(STORAGE_KEY)
  } catch {
    // ignore
  }
}
