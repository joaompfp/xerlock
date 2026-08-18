// Snapshot register: parsed schedules saved in IndexedDB so a reviewer can diff this
// month's submission against last month's without carrying the old .xer around.
// Two stores — meta (listed every visit) and data (loaded only when a compare starts) —
// so listing a year of monthly snapshots doesn't pull ~50MB of payloads into memory.
// Everything stays browser-local: saving a snapshot never sends anything anywhere,
// consistent with the XERlock lock promise.

const DB_NAME = 'xerlock'
const DB_VERSION = 1
const META = 'snapshot-meta'
const DATA = 'snapshot-data'

function openDb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION)
    req.onupgradeneeded = () => {
      const db = req.result
      if (!db.objectStoreNames.contains(META)) db.createObjectStore(META, { keyPath: 'id' })
      if (!db.objectStoreNames.contains(DATA)) db.createObjectStore(DATA, { keyPath: 'id' })
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

function tx(db, store, mode, fn) {
  return new Promise((resolve, reject) => {
    const t = db.transaction(store, mode)
    const req = fn(t.objectStore(store))
    t.oncomplete = () => resolve(req?.result)
    t.onerror = () => reject(t.error)
  })
}

export async function listSnapshots() {
  try {
    const db = await openDb()
    const metas = (await tx(db, META, 'readonly', s => s.getAll())) || []
    db.close()
    return metas.sort((a, b) => b.savedAt - a.savedAt)
  } catch {
    return []
  }
}

export async function saveSnapshot(filename, data) {
  const id = `snap-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
  const meta = {
    id,
    filename,
    proj: data.project.proj_short_name,
    dataDate: data.project.data_date,
    activities: data.project.total_activities,
    savedAt: Date.now(),
  }
  // Raw tables are the bulk of the payload and Compare never reads them. The JSON
  // round-trip also strips Vue's reactive Proxy — IndexedDB's structured clone
  // throws DataCloneError on proxied objects.
  const slim = JSON.parse(JSON.stringify({ ...data, raw_tables: {}, raw_tables_omitted: true }))
  const db = await openDb()
  await tx(db, META, 'readwrite', s => s.put(meta))
  await tx(db, DATA, 'readwrite', s => s.put({ id, data: slim }))
  db.close()
  return meta
}

export async function getSnapshotData(id) {
  const db = await openDb()
  const rec = await tx(db, DATA, 'readonly', s => s.get(id))
  db.close()
  return rec ? rec.data : null
}

export async function deleteSnapshot(id) {
  const db = await openDb()
  await tx(db, META, 'readwrite', s => s.delete(id))
  await tx(db, DATA, 'readwrite', s => s.delete(id))
  db.close()
}
