export function formatDate(d) {
  if (!d) return '--'
  const dt = new Date(d)
  return dt.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
}

export function formatHours(h) {
  if (!h) return '0d'
  const days = Math.round(h / 8)
  return days + 'd'
}

export function statusLabel(s) {
  const map = { TK_Complete: 'Done', TK_Active: 'Active', TK_NotStart: 'Not started' }
  return map[s] || s
}
