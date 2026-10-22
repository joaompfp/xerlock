// Saved Gantt views: a named snapshot of how the chart is looked at (zoom, scroll, WBS
// expansion, filters, chain trace, overlays, highlight groups), replayed like slides in a
// review meeting. Kept per project in this browser, like the notes and the markup.

import type { WbsKey } from './ganttRows'
import type { GanttFilter } from './ganttFilter'
import type { NoteFilter } from './annotations'

const PREFIX = 'schedule-app:views:'

export interface ViewState {
  zoom: string
  dayWidthOverride: number | null
  criticalBasis: string
  showLinks: boolean
  linksScope: string
  showProgressLine: boolean
  showBaseline: boolean
  showMarkup: boolean
  showSlipArrows: boolean
  filterText: string
  filterStatus: string
  filterConstraint: string
  filterNotes: string
  filterCriticalOnly: boolean
  filterFrom: string
  filterTo: string
  filterCodes: Record<string, string>
  /** The chain trace by activity code (codes survive a file update; task ids may not). */
  isolatedCodes: string[] | null
  expandedWbs: WbsKey[]
  filterCollapsed: WbsKey[]
  /** Ids of the highlight groups switched on. */
  groupsOn: string[]
  /** The date at the left edge of the timeline, so the window holds through a zoom change. */
  leftDate: string | null
  /** The first row in view. */
  topRowKey: string | null
}

export interface SavedView { id: string; name: string; savedAt: number; state: ViewState }

function keyFor(projectKey: string | null | undefined): string {
  return PREFIX + (projectKey || 'default')
}

export function loadViews(projectKey: string | null | undefined): SavedView[] {
  try {
    const raw = localStorage.getItem(keyFor(projectKey))
    if (!raw) return []
    const list = JSON.parse(raw) as SavedView[]
    return Array.isArray(list)
      ? list.filter(v => v && typeof v.id === 'string' && typeof v.name === 'string' && v.state && typeof v.state === 'object')
      : []
  } catch {
    return []
  }
}

export function saveViews(projectKey: string | null | undefined, views: SavedView[]): void {
  try {
    localStorage.setItem(keyFor(projectKey), JSON.stringify(views))
  } catch {
    // Storage full or unavailable: the views just won't survive a reload.
  }
}

/** Fills what an older or partial snapshot lacks from the chart's current state, so a
 *  view saved before a setting existed still applies cleanly. */
export function completeState(saved: Partial<ViewState>, current: ViewState): ViewState {
  const out = { ...current }
  for (const k of Object.keys(current) as (keyof ViewState)[]) {
    if (saved[k] !== undefined) (out as Record<string, unknown>)[k] = saved[k]
  }
  return out
}

/** The neighbour of `currentId` one step in `dir`, or null at either end (no wrap: the
 *  last slide stays the last). With no current view, stepping starts at the first. */
export function stepView(views: SavedView[], currentId: string | null, dir: 1 | -1): SavedView | null {
  if (!views.length) return null
  const i = views.findIndex(v => v.id === currentId)
  if (i < 0) return views[0]
  return views[i + dir] ?? null
}

/** The filter as a view stores it (flat fields, kept as they were first saved). */
export function filterToView(f: GanttFilter): Pick<ViewState, 'filterText' | 'filterStatus' | 'filterConstraint' | 'filterNotes' | 'filterCriticalOnly' | 'filterFrom' | 'filterTo' | 'filterCodes'> {
  return {
    filterText: f.text, filterStatus: f.status, filterConstraint: f.constraint, filterNotes: f.notes,
    filterCriticalOnly: f.criticalOnly, filterFrom: f.from, filterTo: f.to, filterCodes: { ...f.codes },
  }
}

/** A view's filter on this file: only its code categories, so one the file no longer
 *  has is dropped and every category it does have gets an entry. */
export function filterFromView(s: ViewState, codeTypes: string[] | null | undefined): GanttFilter {
  return {
    text: s.filterText, status: s.filterStatus, constraint: s.filterConstraint, notes: s.filterNotes as NoteFilter,
    criticalOnly: s.filterCriticalOnly, from: s.filterFrom, to: s.filterTo,
    codes: Object.fromEntries((codeTypes || []).map(t => [t, s.filterCodes[t] || ''])),
  }
}

// ── The zoom a project was last looked at ───────────────────────────────────

const ZOOM_PREFIX = 'schedule-app:gantt-zoom:'

export interface ProjectZoom { zoom: string; dayWidthOverride: number | null }

/** The zoom this project was last shown at, or null for a project not seen before (the
 *  chart then fits the whole programme to the width). */
export function loadProjectZoom(projectKey: string | null | undefined): ProjectZoom | null {
  try {
    const raw = localStorage.getItem(ZOOM_PREFIX + (projectKey || 'default'))
    const z = raw ? JSON.parse(raw) : null
    return z && typeof z.zoom === 'string' && (z.dayWidthOverride === null || typeof z.dayWidthOverride === 'number') ? z : null
  } catch {
    return null
  }
}

export function saveProjectZoom(projectKey: string | null | undefined, z: ProjectZoom): void {
  try {
    localStorage.setItem(ZOOM_PREFIX + (projectKey || 'default'), JSON.stringify(z))
  } catch {
    // Not remembered: the next open fits the programme again.
  }
}
