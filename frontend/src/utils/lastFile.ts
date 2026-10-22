// The last file opened, kept in this browser (IndexedDB) so it can be reopened without
// the file, and so a reload of the page comes back to it. IndexedDB holds hundreds of
// megabytes where localStorage held about five: a large programme, raw tables and
// all, fits. Nothing leaves the browser.

import type { Schedule } from '../types/schedule'
import { openDb, tx } from './idb'

const STORE = 'last-file'
const KEY = 'last'
// The pre-IndexedDB copy: read once, moved across, then removed to free its quota.
const LEGACY_KEY = 'schedule-app:last-file'

// Bump whenever the parsed-payload shape changes (new fields on activities/project).
// A cached payload from an older schema silently lacks the new fields — features
// depending on them would just not render, with no error — so a version mismatch
// invalidates the cache and the user re-uploads instead.
const SCHEMA_VERSION = 3

/** A schedule as cached in the browser: raw tables may have been dropped to fit quota. */
export type StoredSchedule = Schedule & { raw_tables_omitted?: boolean }

export interface LastFile {
  filename: string
  data: StoredSchedule
  savedAt: number
  schemaVersion: number
}

interface Record { id: string; file: LastFile }

function legacy(): LastFile | null {
  try {
    const raw = localStorage.getItem(LEGACY_KEY)
    if (!raw) return null
    localStorage.removeItem(LEGACY_KEY)
    return JSON.parse(raw) as LastFile
  } catch {
    return null
  }
}

export async function loadLastFile(): Promise<LastFile | null> {
  try {
    const old = legacy()
    if (old && old.schemaVersion === SCHEMA_VERSION) await put(old)
    const db = await openDb()
    const rec = await tx<Record>(db, STORE, 'readonly', s => s.get(KEY))
    db.close()
    const f = rec?.file
    if (!f) return null
    if (f.schemaVersion !== SCHEMA_VERSION) {
      await clearLastFile()
      return null
    }
    return f
  } catch {
    return null
  }
}

async function put(file: LastFile): Promise<void> {
  const db = await openDb()
  try {
    await tx(db, STORE, 'readwrite', s => s.put({ id: KEY, file }))
  } finally {
    db.close()
  }
}

/** Keeps the file and returns what was kept; null when the browser would not store it
 *  (private window, storage full or blocked), so the page can say so instead of
 *  promising a reopen. */
export async function saveLastFile(filename: string, data: StoredSchedule): Promise<LastFile | null> {
  const file = { filename, data, savedAt: Date.now(), schemaVersion: SCHEMA_VERSION }
  try {
    await put(file)
    return file
  } catch {
    return null
  }
}

export async function clearLastFile(): Promise<void> {
  try {
    const db = await openDb()
    await tx(db, STORE, 'readwrite', s => s.delete(KEY))
    db.close()
  } catch {
    // Nothing kept, or storage unavailable: either way there is nothing to reopen.
  }
}
