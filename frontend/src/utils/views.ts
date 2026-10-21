// Saved Gantt views: a named snapshot of how the chart is looked at (zoom, scroll, WBS
// expansion, filters, chain trace, overlays, highlight groups), replayed like slides in a
// review meeting. Kept per project in this browser, like the notes and the markup.

const PREFIX = 'schedule-app:views:'

export type WbsKey = number | '__unassigned'

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
