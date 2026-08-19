// Table sorting.
//
// The important rule: a value P6 never supplied is *unknown*, not zero. Total
// float is blank on completed activities, and the previous comparator coerced
// null to '' — which JavaScript then compares as 0, dropping every completed
// activity into the middle of the critical band on a float-ascending sort.
// Unknown values now sort last in both directions, matching the em-dash the
// table renders for them.

function isMissing(v) {
  return v == null || v === ''
}

/** Comparator for one field. `get` extracts the value (some columns are derived,
 *  e.g. display dates). Returns a function suitable for Array.prototype.sort. */
export function compareBy(get, dir = 'asc') {
  const sign = dir === 'asc' ? 1 : -1
  return (a, b) => {
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
    if (va < vb) return -sign
    if (va > vb) return sign
    return 0
  }
}

export function sortRows(rows, get, dir = 'asc') {
  return [...rows].sort(compareBy(get, dir))
}
