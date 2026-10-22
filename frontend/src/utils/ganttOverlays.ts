// Where the Gantt's overlays land: the reviewer's key dates, periods and text boxes,
// the slip arrows against a compared schedule, and the note callouts. Pure functions of
// the rows and a date→x mapping, so the component only draws what these return.

import type { Activity } from '../types/schedule'
import type { Annotations, Severity } from './annotations'
import { periodSpan, type Markup, type MarkColor, type TextBox } from './markup'
import { displayEnd } from './p6'
import { finishSlipDays } from './compareChecks'
import { formatDate } from './format'
import type { ActivityRow, Row, ToX } from './ganttRows'

export interface KeyDateMark { id: string; x: number; label: string; color: MarkColor; title: string }
export interface PeriodBand { id: string; x: number; w: number; label: string; color: MarkColor; title: string }

// Days are local midnights: a key date's line sits at the start of its day, and a
// period's band runs to the end of its last day.
const day = (d: string) => d + 'T00:00:00'

/** Key dates inside the drawn timeline. */
export function keyDateMarks(markup: Markup, toX: ToX, totalWidth: number): KeyDateMark[] {
  const out = []
  for (const k of markup.keyDates) {
    const x = toX(day(k.date))
    if (x === null || x < 0 || x > totalWidth) continue
    out.push({ id: k.id, x, label: k.label, color: k.color, title: `${k.label || 'Key date'} — ${formatDate(day(k.date))}` })
  }
  return out
}

/** Periods clipped to the drawn timeline; one entirely outside it is left out. */
export function periodBands(markup: Markup, toX: ToX, dayWidth: number, totalWidth: number): PeriodBand[] {
  const out = []
  for (const p of markup.periods) {
    const { from, to } = periodSpan(p)
    const x0 = toX(day(from))
    const xTo = toX(day(to))
    if (x0 === null || xTo === null) continue
    const x1 = xTo + dayWidth
    const x = Math.max(0, x0)
    const w = Math.min(totalWidth, x1) - x
    if (w <= 0) continue
    out.push({ id: p.id, x, w, label: p.label, color: p.color,
      title: `${p.label || 'Period'} — ${formatDate(day(from))} to ${formatDate(day(to))}` })
  }
  return out
}

/** A text box being dragged: its live position until the drop saves it. */
export interface TextDrag { id: string; x0: number; y0: number; x: number; y: number }

export function placedTextBoxes(texts: TextBox[], toX: ToX, drag: TextDrag | null): (TextBox & { x: number })[] {
  const out = []
  for (const t of texts) {
    const live = drag?.id === t.id ? drag : null
    const x = live ? live.x : toX(t.at)
    if (x === null) continue
    out.push({ ...t, x, y: live ? live.y : t.y })
  }
  return out
}

/** Where a note attaches to its row: the bar's finish end, or the milestone. */
export function calloutAnchorX(row: ActivityRow): number {
  return row.milestone ? row.x + 7 : row.x + row.w
}

export interface SlipArrow { id: number; x1: number; x2: number; y: number; late: boolean }

/** Finish movement against the compared schedule, drawn just under the bar. Only rows
 *  that moved by at least a calendar day, so a steady programme draws nothing. */
export function slipArrows(rows: Row[], baselineByCode: Map<string, Activity>, toX: ToX, rowHeight: number): SlipArrow[] {
  const out = []
  for (const row of rows) {
    if (row.type !== 'activity') continue
    const b = baselineByCode.get(row.activity.task_code)
    const d = b ? finishSlipDays(row.activity, b) : null
    if (!b || !d) continue
    const x1 = toX(displayEnd(b))
    const x2 = toX(displayEnd(row.activity))
    if (x1 === null || x2 === null) continue
    out.push({ id: row.activity.task_id, x1, x2, y: row.index * rowHeight + rowHeight - 2, late: d > 0 })
  }
  return out
}

export interface Callout {
  id: number
  code: string
  note: string
  severity: Severity | null
  /** The bar's finish end, in timeline coordinates (row centre). */
  ax: number
  ay: number
  dx: number
  dy: number
}

/** A callout being dragged: its offset live until the drop saves it. */
export interface CalloutDrag { id: number; dx0: number; dy0: number; dx: number; dy: number }

/** The open note callouts on these rows. */
export function callouts(rows: Row[], annotations: Annotations, drag: CalloutDrag | null, rowHeight: number): Callout[] {
  const out: Callout[] = []
  for (const row of rows) {
    if (row.type !== 'activity') continue
    const a = annotations[row.activity.task_id]
    if (!a?.callout) continue
    const live = drag?.id === row.activity.task_id ? drag : a.callout
    out.push({
      id: row.activity.task_id, code: row.activity.task_code, note: a.note, severity: a.severity,
      ax: calloutAnchorX(row) + 7, ay: row.index * rowHeight + rowHeight / 2,
      dx: live.dx, dy: live.dy,
    })
  }
  return out
}
