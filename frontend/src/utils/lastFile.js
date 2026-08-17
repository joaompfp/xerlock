const STORAGE_KEY = 'schedule-app:last-file'

export function loadLastFile() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export function saveLastFile(filename, data) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ filename, data, savedAt: Date.now() }))
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
