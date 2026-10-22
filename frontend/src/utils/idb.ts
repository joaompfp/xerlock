// XERlock's IndexedDB database: everything the app keeps in this browser that is too
// large for localStorage (snapshots for Compare). Opened per call; the browser keeps the
// connection cheap, and the stores are created on first use.

const DB_NAME = 'xerlock'
const DB_VERSION = 1
const STORES = ['snapshot-meta', 'snapshot-data']

export function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION)
    req.onupgradeneeded = () => {
      const db = req.result
      for (const name of STORES) {
        if (!db.objectStoreNames.contains(name)) db.createObjectStore(name, { keyPath: 'id' })
      }
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

// T is what the store holds; callers name it, since IndexedDB values are untyped.
export function tx<T>(
  db: IDBDatabase,
  store: string,
  mode: IDBTransactionMode,
  fn: (s: IDBObjectStore) => IDBRequest | undefined,
): Promise<T | undefined> {
  return new Promise((resolve, reject) => {
    const t = db.transaction(store, mode)
    const req = fn(t.objectStore(store))
    t.oncomplete = () => resolve(req?.result as T | undefined)
    t.onerror = () => reject(t.error)
  })
}
