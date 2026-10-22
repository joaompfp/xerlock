// Windowed rendering for long lists: which rows a scrolled viewport needs drawn, so a
// table or chart of thousands of rows puts only a few dozen on the page.

/** Rows drawn beyond the viewport's top and bottom edges, so a quick scroll or a small
 *  drag never shows an empty band before the next render. */
export const ROW_OVERSCAN = 20

/** The rows `[from, to)` a viewport scrolled to `scrollTop` shows, widened by the
 *  overscan and clamped to the rows that exist. */
export function visibleRowRange(scrollTop: number, viewportH: number, rowHeight: number, count: number, overscan = ROW_OVERSCAN): { from: number; to: number } {
  const from = Math.max(0, Math.floor(scrollTop / rowHeight) - overscan)
  const to = Math.min(count, Math.ceil((scrollTop + viewportH) / rowHeight) + overscan)
  return { from: Math.min(from, to), to }
}
