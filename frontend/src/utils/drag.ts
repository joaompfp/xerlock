// Mouse drags that keep tracking outside the element they started on: the move and
// release are followed on the window until the button comes up. One place for the
// listener bookkeeping that every draggable thing on the chart needs.

/** Follows a drag begun by `start`. `onMove` gets the pointer's offset from where the
 *  drag began; `onEnd` runs once on release. Returns a function that ends the drag
 *  early without calling `onEnd` (for a component unmounting mid-drag). */
export function trackDrag(
  start: MouseEvent,
  onMove: (dx: number, dy: number) => void,
  onEnd: () => void,
): () => void {
  const x0 = start.clientX
  const y0 = start.clientY
  const move = (e: MouseEvent) => onMove(e.clientX - x0, e.clientY - y0)
  const stop = () => {
    window.removeEventListener('mousemove', move)
    window.removeEventListener('mouseup', up)
  }
  const up = () => {
    stop()
    onEnd()
  }
  window.addEventListener('mousemove', move)
  window.addEventListener('mouseup', up)
  return stop
}
