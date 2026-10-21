// Reviewer markup drawn on the Gantt: key dates (a thin line) and periods (a faint band).
// Kept per project in this browser, like the review notes, and never sent anywhere.

const PREFIX = 'schedule-app:markup:'

/** A small muted palette, so markup reads as annotation and never competes with the
 *  bars' critical/near-critical colours. Each name maps to a --mk-<name> CSS token. */
export const MARK_COLORS = ['slate', 'teal', 'amber', 'rose', 'violet'] as const
export type MarkColor = typeof MARK_COLORS[number]

export interface KeyDate { id: string; date: string; label: string; color: MarkColor }
/** `to` is inclusive: a period from 3 Aug to 14 Aug shades both days. */
export interface Period { id: string; from: string; to: string; label: string; color: MarkColor }

export interface Markup {
  keyDates: KeyDate[]
  periods: Period[]
}

export const emptyMarkup = (): Markup => ({ keyDates: [], periods: [] })

function keyFor(projectKey: string | null | undefined): string {
  return PREFIX + (projectKey || 'default')
}

const isColor = (c: unknown): c is MarkColor => MARK_COLORS.includes(c as MarkColor)
const isDay = (d: unknown): d is string => typeof d === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(d)

/** Reads what this browser stored, dropping any entry that doesn't have the expected
 *  shape rather than failing the whole chart over one bad row. */
export function loadMarkup(projectKey: string | null | undefined): Markup {
  try {
    const raw = localStorage.getItem(keyFor(projectKey))
    if (!raw) return emptyMarkup()
    const m = JSON.parse(raw) as Partial<Markup>
    return {
      keyDates: (m.keyDates || []).filter(k => k && isDay(k.date) && isColor(k.color) && typeof k.label === 'string'),
      periods: (m.periods || []).filter(p => p && isDay(p.from) && isDay(p.to) && isColor(p.color) && typeof p.label === 'string'),
    }
  } catch {
    return emptyMarkup()
  }
}

export function saveMarkup(projectKey: string | null | undefined, m: Markup): void {
  try {
    localStorage.setItem(keyFor(projectKey), JSON.stringify(m))
  } catch {
    // Storage full or unavailable: the markup just won't survive a reload.
  }
}

export function newMarkId(): string {
  return Math.random().toString(36).slice(2, 10)
}

/** The next colour after `c`, wrapping: a click on a swatch steps through the palette. */
export function nextColor(c: MarkColor): MarkColor {
  return MARK_COLORS[(MARK_COLORS.indexOf(c) + 1) % MARK_COLORS.length]
}

/** A period typed backwards (to before from) is read the right way round. */
export function periodSpan(p: Pick<Period, 'from' | 'to'>): { from: string; to: string } {
  return p.from <= p.to ? { from: p.from, to: p.to } : { from: p.to, to: p.from }
}
