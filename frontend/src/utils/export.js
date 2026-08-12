import { statusLabel } from './format'

const REL_TYPE_LABELS = { PR_FS: 'FS', PR_SS: 'SS', PR_FF: 'FF', PR_SF: 'SF' }

const HEADER_FILL = 'FF2F5496'
const CRITICAL_FONT = 'FFC0392B'

const ACTIVITY_COLUMNS = [
  { header: 'Activity ID', key: 'task_code', width: 14 },
  { header: 'Activity Name', key: 'task_name', width: 44 },
  { header: 'WBS', key: 'wbs_path', width: 26 },
  { header: 'Status', key: 'status_label', width: 12 },
  { header: '% Complete', key: 'pct_complete', width: 10 },
  { header: 'Orig. Duration (d)', key: 'duration_d', width: 10 },
  { header: 'Start', key: 'early_start', width: 12, style: { numFmt: 'dd-mmm-yy' } },
  { header: 'Finish', key: 'early_end', width: 12, style: { numFmt: 'dd-mmm-yy' } },
  { header: 'Total Float (d)', key: 'total_float_d', width: 11 },
  { header: 'Free Float (d)', key: 'free_float_d', width: 11 },
  { header: 'Calendar', key: 'calendar', width: 16 },
  { header: 'Critical', key: 'critical_label', width: 9 },
]

const RELATIONSHIP_COLUMNS = [
  { header: 'Predecessor ID', key: 'pred_code', width: 14 },
  { header: 'Predecessor Name', key: 'pred_name', width: 38 },
  { header: 'Type', key: 'type', width: 8 },
  { header: 'Lag (d)', key: 'lag_d', width: 8 },
  { header: 'Successor ID', key: 'succ_code', width: 14 },
  { header: 'Successor Name', key: 'succ_name', width: 38 },
]

function round1(n) {
  if (n == null) return 0
  return Math.round(n * 10) / 10
}

function toDate(d) {
  if (!d) return null
  const dt = new Date(d)
  return isNaN(dt) ? null : dt
}

function relTypeLabel(t) {
  return REL_TYPE_LABELS[t] || t || ''
}

function slug(s) {
  return (s || 'schedule').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '')
}

/**
 * wbs_id -> "Level 1 > Level 2 > ..." breadcrumb, built from the nested wbs_tree.
 * The root node (the project itself) is excluded from the breadcrumb since it's
 * identical on every row and just adds noise; it still gets its own fallback entry
 * in case an activity is assigned directly to it.
 */
function buildWbsPathMap(wbsTree) {
  const map = new Map()
  function walk(node, trail, isRoot) {
    const label = node.wbs_short_name ? `${node.wbs_short_name} ${node.wbs_name}` : node.wbs_name
    const path = isRoot ? [] : [...trail, label]
    map.set(node.wbs_id, path.length ? path.join(' > ') : label)
    for (const child of node.children || []) walk(child, path, false)
  }
  for (const root of wbsTree || []) walk(root, [], true)
  return map
}

function styleHeaderRow(ws) {
  const row = ws.getRow(1)
  row.eachCell(cell => {
    cell.font = { bold: true, color: { argb: 'FFFFFFFF' } }
    cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: HEADER_FILL } }
    cell.alignment = { vertical: 'middle' }
  })
  ws.views = [{ state: 'frozen', ySplit: 1 }]
  ws.autoFilter = { from: { row: 1, column: 1 }, to: { row: 1, column: ws.columns.length } }
}

function addActivitiesSheet(wb, activities, wbsPathMap, sheetName) {
  const ws = wb.addWorksheet(sheetName)
  ws.columns = ACTIVITY_COLUMNS
  activities.forEach(a => {
    ws.addRow({
      task_code: a.task_code,
      task_name: a.task_name,
      wbs_path: wbsPathMap.get(a.wbs_id) || '',
      status_label: statusLabel(a.status),
      pct_complete: a.pct_complete,
      duration_d: round1(a.duration_hrs / 8),
      early_start: toDate(a.early_start),
      early_end: toDate(a.early_end),
      total_float_d: round1(a.total_float_hrs / 8),
      free_float_d: round1(a.free_float_hrs / 8),
      calendar: a.calendar || '',
      critical_label: a.is_critical ? 'Yes' : '',
    })
  })
  styleHeaderRow(ws)
  activities.forEach((a, i) => {
    if (!a.is_critical) return
    ws.getRow(i + 2).eachCell(cell => {
      cell.font = { ...(cell.font || {}), color: { argb: CRITICAL_FONT } }
    })
  })
  return ws
}

function addRelationshipsSheet(wb, activities, actLookup, sheetName) {
  const ws = wb.addWorksheet(sheetName)
  ws.columns = RELATIONSHIP_COLUMNS
  const seen = new Set()
  activities.forEach(a => {
    ;(a.predecessors || []).forEach(p => {
      const key = `${p.task_id}->${a.task_id}:${p.type}`
      if (seen.has(key)) return
      seen.add(key)
      const pa = actLookup.get(p.task_id)
      ws.addRow({
        pred_code: pa ? pa.task_code : String(p.task_id),
        pred_name: pa ? pa.task_name : '',
        type: relTypeLabel(p.type),
        lag_d: round1(p.lag_hrs / 8),
        succ_code: a.task_code,
        succ_name: a.task_name,
      })
    })
  })
  styleHeaderRow(ws)
  return ws
}

function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

async function downloadWorkbook(wb, filename) {
  const buf = await wb.xlsx.writeBuffer()
  const blob = new Blob([buf], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  })
  triggerDownload(blob, filename)
}

async function newWorkbook() {
  // Lazy-loaded: ExcelJS is only needed when an .xlsx export is actually triggered,
  // so it shouldn't bloat the initial page bundle.
  const { default: ExcelJS } = await import('exceljs')
  const wb = new ExcelJS.Workbook()
  wb.creator = 'Schedule App'
  wb.created = new Date()
  return wb
}

/** Full programme export: all activities + all relationships, P6-style two-sheet workbook. */
export async function exportProgrammeXlsx(data) {
  const wb = await newWorkbook()
  const wbsPathMap = buildWbsPathMap(data.wbs_tree)
  const actLookup = new Map(data.activities.map(a => [a.task_id, a]))
  addActivitiesSheet(wb, data.activities, wbsPathMap, 'Activities')
  addRelationshipsSheet(wb, data.activities, actLookup, 'Relationships')
  await downloadWorkbook(wb, `${slug(data.project.proj_short_name)}-programme.xlsx`)
}

/** Critical-path-only export: critical activities + the relationships that chain them. */
export async function exportCriticalPathXlsx(data) {
  const wb = await newWorkbook()
  const wbsPathMap = buildWbsPathMap(data.wbs_tree)
  const critical = data.activities.filter(a => a.is_critical)
  const criticalIds = new Set(critical.map(a => a.task_id))
  const actLookup = new Map(data.activities.map(a => [a.task_id, a]))
  addActivitiesSheet(wb, critical, wbsPathMap, 'Critical Path')
  const criticalWithCriticalPreds = critical.filter(a =>
    (a.predecessors || []).some(p => criticalIds.has(p.task_id))
  )
  addRelationshipsSheet(wb, criticalWithCriticalPreds, actLookup, 'Relationships')
  await downloadWorkbook(wb, `${slug(data.project.proj_short_name)}-critical-path.xlsx`)
}

function csvEscape(v) {
  const s = String(v ?? '')
  if (/[",\n]/.test(s)) return '"' + s.replace(/"/g, '""') + '"'
  return s
}

function downloadCsv(rows, filename) {
  const csv = rows.map(r => r.map(csvEscape).join(',')).join('\r\n')
  const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' })
  triggerDownload(blob, filename)
}

/** CSV export of an activity list (used for both "all activities" and any filtered view). */
export function exportActivitiesCsv(data, activities, filename) {
  const wbsPathMap = buildWbsPathMap(data.wbs_tree)
  const headers = [
    'Activity ID', 'Activity Name', 'WBS', 'Status', '% Complete',
    'Orig. Duration (d)', 'Start', 'Finish', 'Total Float (d)', 'Free Float (d)',
    'Calendar', 'Critical',
  ]
  const rows = activities.map(a => [
    a.task_code,
    a.task_name,
    wbsPathMap.get(a.wbs_id) || '',
    statusLabel(a.status),
    a.pct_complete,
    round1(a.duration_hrs / 8),
    a.early_start ? a.early_start.slice(0, 10) : '',
    a.early_end ? a.early_end.slice(0, 10) : '',
    round1(a.total_float_hrs / 8),
    round1(a.free_float_hrs / 8),
    a.calendar || '',
    a.is_critical ? 'Yes' : '',
  ])
  downloadCsv([headers, ...rows], filename || `${slug(data.project.proj_short_name)}-activities.csv`)
}
