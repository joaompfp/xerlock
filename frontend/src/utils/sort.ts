// Table sorting.
//
// The important rule: a value P6 never supplied is *unknown*, not zero. Total
// float is blank on completed activities, and the previous comparator coerced
// null to '' — which JavaScript then compares as 0, dropping every completed
// activity into the middle of the critical band on a float-ascending sort.
// Unknown values now sort last in both directions, matching the em-dash the
// table renders for them.

/** What a sort column can yield; null/undefined/'' mean unknown. */
export type SortValue = string | number | boolean | null | undefined

export type SortDir = 'asc' | 'desc'

function isMissing(v: SortValue): v is null | undefined | '' {
  return v == null || v === ''
}

/** Comparator for one field. `get` extracts the value (some columns are derived,
 *  e.g. display dates). Returns a function suitable for Array.prototype.sort. */
export function compareBy<T>(get: (row: T) => SortValue, dir: SortDir = 'asc'): (a: T, b: T) => number {
  const sign = dir === 'asc' ? 1 : -1
  return (a: T, b: T) => {
    let va = get(a)
    let vb = get(b)
    const ma = isMissing(va)
    const mb = isMissing(vb)
    // Unknown sinks to the bottom whichever way the column is sorted — flipping
    // the direction should reorder the data, not parade the blanks.
    if (ma && mb) return 0
    if (ma) return 1
    if (mb) return -1
    if (typeof va === 'string') va = va.toLowerCase()
    if (typeof vb === 'string') vb = vb.toLowerCase()
    // Both are known here: the isMissing checks above returned on null/undefined.
    if (va! < vb!) return -sign
    if (va! > vb!) return sign
    return 0
  }
}

export function sortRows<T>(rows: readonly T[], get: (row: T) => SortValue, dir: SortDir = 'asc'): T[] {
  return [...rows].sort(compareBy(get, dir))
}
