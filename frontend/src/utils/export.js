import { statusLabel, formatDate } from './format'
import { SEVERITY_LABELS } from './annotations'
import { relTypeLabel, displayStart, displayEnd } from './p6'

const REPORT_SEVERITY_ORDER = ['logic', 'risk', 'query', 'resolved']
const SEVERITY_FILL = { logic: 'FFF8E3E1', risk: 'FFF6ECD2', query: 'FFDCE6F0', resolved: 'FFE1EBE4' }

const HEADER_FILL = 'FF2F5496'
const CRITICAL_FONT = 'FFC0392B'

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

// total_float_hrs is null when P6 didn't compute a float (typically completed
// activities) — must not export as "0", which reads as zero float / critical.
function floatDays(hrs, hrsPerDay = 8) {
  return hrs == null ? '' : round1(hrs / (hrsPerDay || 8))
}

/**
 * XER timestamps are wall-clock strings ("2026-08-09 08:00") with no timezone. Parsing
 * them with `new Date(str)` interprets them in the browser's LOCAL zone, and ExcelJS then
 * serializes via UTC — so any date on the other side of a DST change from "now" shifts by
 * an hour (and a midnight timestamp shifts to the previous day). Building the Date from
 * UTC components keeps the wall-clock time intact end-to-end.
 */
function toDate(d) {
  if (!d) return null
  const m = /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/.exec(d)
  if (m) return new Date(Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5]))
  const dt = new Date(d)
  return isNaN(dt) ? null : dt
}

function slug(s) {
  return (s || 'schedule').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '')
}

/**
 * wbs_id -> [level1Label, level2Label, ...], built from the nested wbs_tree.
 * The root node (the project itself) is excluded since it's identical for every
 * activity and just adds noise; it still gets its own fallback entry (its own
 * label as a single-element array) in case an activity is assigned directly to it.
 */
function buildWbsLevelsMap(wbsTree) {
  const map = new Map()
  function walk(node, trail, isRoot) {
    const label = node.wbs_short_name ? `${node.wbs_short_name} ${node.wbs_name}` : node.wbs_name
    const levels = isRoot ? [] : [...trail, label]
    map.set(node.wbs_id, levels.length ? levels : [label])
    for (const child of node.children || []) walk(child, levels, false)
  }
  for (const root of wbsTree || []) walk(root, [], true)
  return map
}

function maxWbsDepth(wbsLevelsMap) {
  let max = 1
  for (const levels of wbsLevelsMap.values()) {
    if (levels.length > max) max = levels.length
  }
  return max
}

function wbsLevelColumns(maxDepth, widthPerLevel = 22) {
  return Array.from({ length: maxDepth }, (_, i) => ({
    header: `WBS Level ${i + 1}`,
    key: `wbs_l${i + 1}`,
    width: widthPerLevel,
  }))
}

function wbsLevelValues(wbsLevelsMap, wbsId, maxDepth) {
  const levels = wbsLevelsMap.get(wbsId) || []
  const out = {}
  for (let i = 0; i < maxDepth; i++) out[`wbs_l${i + 1}`] = levels[i] || ''
  return out
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

function addActivitiesSheet(wb, activities, wbsLevelsMap, maxDepth, sheetName) {
  const ws = wb.addWorksheet(sheetName)
  ws.columns = [
    { header: 'Activity ID', key: 'task_code', width: 14 },
    { header: 'Activity Name', key: 'task_name', width: 44 },
    ...wbsLevelColumns(maxDepth),
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
  activities.forEach(a => {
    ws.addRow({
      task_code: a.task_code,
      task_name: a.task_name,
      ...wbsLevelValues(wbsLevelsMap, a.wbs_id, maxDepth),
      status_label: statusLabel(a.status),
      pct_complete: a.pct_complete,
      duration_d: round1(a.duration_hrs / (a.calendar_hrs_per_day || 8)),
      early_start: toDate(displayStart(a)),
      early_end: toDate(displayEnd(a)),
      total_float_d: floatDays(a.total_float_hrs, a.calendar_hrs_per_day),
      free_float_d: round1(a.free_float_hrs / (a.calendar_hrs_per_day || 8)),
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
        lag_d: round1(p.lag_hrs / (a.calendar_hrs_per_day || 8)),
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
  wb.creator = 'XERlock'
  wb.created = new Date()
  return wb
}

/**
 * Single P6-style workbook: Activities (all), Critical Path (subset), Relationships (all).
 * One file covers both the full programme and the critical-path view, since a critical
 * path is just a filtered slice of the same activity/relationship data.
 */
export async function exportWorkbook(data) {
  const wb = await newWorkbook()
  const wbsLevelsMap = buildWbsLevelsMap(data.wbs_tree)
  const maxDepth = maxWbsDepth(wbsLevelsMap)
  const actLookup = new Map(data.activities.map(a => [a.task_id, a]))
  const critical = data.activities.filter(a => a.is_critical)

  addActivitiesSheet(wb, data.activities, wbsLevelsMap, maxDepth, 'Activities')
  addActivitiesSheet(wb, critical, wbsLevelsMap, maxDepth, 'Critical Path')
  addRelationshipsSheet(wb, data.activities, actLookup, 'Relationships')

  await downloadWorkbook(wb, `${slug(data.project.proj_short_name)}-schedule.xlsx`)
}

/**
 * A reviewer's working notes — every annotated activity, grouped by severity
 * (Logic Issue / Risk / Query first, Resolved last), with the underlying
 * schedule data (dates, float, WBS) alongside the note so the report stands
 * on its own without needing the app open.
 */
export async function exportReviewReport(data, annotations) {
  const wb = await newWorkbook()
  const actLookup = new Map(data.activities.map(a => [a.task_id, a]))
  const wbsLevelsMap = buildWbsLevelsMap(data.wbs_tree)

  const ws = wb.addWorksheet('Review Report')
  ws.columns = [
    { header: 'Severity', key: 'severity', width: 13 },
    { header: 'Activity ID', key: 'task_code', width: 14 },
    { header: 'Activity Name', key: 'task_name', width: 42 },
    { header: 'WBS Path', key: 'wbs_path', width: 40 },
    { header: 'Start', key: 'early_start', width: 12, style: { numFmt: 'dd-mmm-yy' } },
    { header: 'Finish', key: 'early_end', width: 12, style: { numFmt: 'dd-mmm-yy' } },
    { header: 'Float (d)', key: 'float_d', width: 9 },
    { header: 'Note', key: 'note', width: 60 },
    { header: 'Last updated', key: 'updated', width: 16, style: { numFmt: 'dd-mmm-yy hh:mm' } },
  ]

  ws.mergeCells('A1:I1')
  ws.getCell('A1').value = `Review Report — ${data.project.proj_short_name}`
  ws.getCell('A1').font = { bold: true, size: 14 }
  ws.mergeCells('A2:I2')
  ws.getCell('A2').value =
    `${data.project.total_activities} activities · data date ${data.project.data_date ? formatDate(data.project.data_date) : 'unknown'} · ` +
    `${Object.keys(annotations).length} annotated activities, generated ${new Date().toLocaleString('en-GB')}`
  ws.getCell('A2').font = { italic: true, color: { argb: 'FF6B7280' } }
  ws.addRow([])

  const headerRowNum = 4
  ws.spliceRows(headerRowNum, 0, ws.columns.map(c => c.header))
  const headerRow = ws.getRow(headerRowNum)
  headerRow.eachCell(cell => {
    cell.font = { bold: true, color: { argb: 'FFFFFFFF' } }
    cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: HEADER_FILL } }
  })
  ws.views = [{ state: 'frozen', ySplit: headerRowNum }]

  const entries = Object.entries(annotations)
    .map(([taskId, ann]) => ({ activity: actLookup.get(Number(taskId)), ann }))
    .filter(e => e.activity)
    .sort((a, b) => {
      const oa = REPORT_SEVERITY_ORDER.indexOf(a.ann.severity)
      const ob = REPORT_SEVERITY_ORDER.indexOf(b.ann.severity)
      if (oa !== ob) return (oa === -1 ? 99 : oa) - (ob === -1 ? 99 : ob)
      return a.activity.task_code.localeCompare(b.activity.task_code)
    })

  entries.forEach(({ activity: a, ann }) => {
    const row = ws.addRow({
      severity: SEVERITY_LABELS[ann.severity] || '—',
      task_code: a.task_code,
      task_name: a.task_name,
      wbs_path: a.wbs_path || (wbsLevelsMap.get(a.wbs_id) || []).join(' / '),
      early_start: toDate(displayStart(a)),
      early_end: toDate(displayEnd(a)),
      float_d: floatDays(a.total_float_hrs, a.calendar_hrs_per_day),
      note: ann.note || '',
      updated: ann.updatedAt ? new Date(ann.updatedAt) : null,
    })
    const fill = SEVERITY_FILL[ann.severity]
    if (fill) {
      row.getCell('severity').fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: fill } }
    }
  })
  ws.autoFilter = { from: { row: headerRowNum, column: 1 }, to: { row: headerRowNum, column: ws.columns.length } }

  await downloadWorkbook(wb, `${slug(data.project.proj_short_name)}-review-report.xlsx`)
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
  const wbsLevelsMap = buildWbsLevelsMap(data.wbs_tree)
  const maxDepth = maxWbsDepth(wbsLevelsMap)
  const wbsHeaders = Array.from({ length: maxDepth }, (_, i) => `WBS Level ${i + 1}`)
  const headers = [
    'Activity ID', 'Activity Name', ...wbsHeaders, 'Status', '% Complete',
    'Orig. Duration (d)', 'Start', 'Finish', 'Total Float (d)', 'Free Float (d)',
    'Calendar', 'Critical',
  ]
  const rows = activities.map(a => {
    const levels = wbsLevelsMap.get(a.wbs_id) || []
    const wbsCells = Array.from({ length: maxDepth }, (_, i) => levels[i] || '')
    return [
      a.task_code,
      a.task_name,
      ...wbsCells,
      statusLabel(a.status),
      a.pct_complete,
      round1(a.duration_hrs / (a.calendar_hrs_per_day || 8)),
      displayStart(a) ? displayStart(a).slice(0, 10) : '',
      displayEnd(a) ? displayEnd(a).slice(0, 10) : '',
      floatDays(a.total_float_hrs, a.calendar_hrs_per_day),
      round1(a.free_float_hrs / (a.calendar_hrs_per_day || 8)),
      a.calendar || '',
      a.is_critical ? 'Yes' : '',
    ]
  })
  downloadCsv([headers, ...rows], filename || `${slug(data.project.proj_short_name)}-activities.csv`)
}
