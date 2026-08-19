// Paper sizes for print fitting, shared by the Gantt and the network diagram.
//
// Both charts fit their content to the usable area of a sheet. They previously
// carried separate copies of this table that had already drifted apart (different
// property names, and only one knew page heights). The safety buffer stays a
// per-caller argument: each chart's value was tuned against its own printed
// output, and they are not interchangeable.
//
// @page `size` needs these exact CSS keywords — Chromium does not accept custom
// page dimensions through a CSS variable there.

export const PAPER_SIZES = {
  a4: { label: 'A4', pageCss: 'A4', wMm: 297, hMm: 210 },
  a3: { label: 'A3', pageCss: 'A3', wMm: 420, hMm: 297 },
  letter: { label: 'Letter', pageCss: 'letter', wMm: 279.4, hMm: 215.9 },
}

const PAGE_MARGIN_MM = 20 // 10mm each side
const PX_PER_MM = 96 / 25.4 // CSS px at 96dpi

export function paperOrDefault(key) {
  return PAPER_SIZES[key] || PAPER_SIZES.a4
}

/** Usable width in CSS px for a landscape sheet, less margins and a safety buffer
 *  (font antialiasing and sub-pixel rounding otherwise push content onto page 2). */
export function usableWidthPx(key, bufferPx) {
  return Math.round((paperOrDefault(key).wMm - PAGE_MARGIN_MM) * PX_PER_MM) - bufferPx
}

/** Usable height in CSS px — only the network diagram fits vertically as well. */
export function usableHeightPx(key, bufferPx) {
  return Math.round((paperOrDefault(key).hMm - PAGE_MARGIN_MM) * PX_PER_MM) - bufferPx
}
