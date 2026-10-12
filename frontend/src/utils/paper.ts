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

export interface PaperSize {
  label: string
  /** CSS @page size keyword. */
  pageCss: string
  wMm: number
  hMm: number
}

export type PaperKey = 'a4' | 'a3' | 'letter'

export const PAPER_SIZES: Record<PaperKey, PaperSize> = {
  a4: { label: 'A4', pageCss: 'A4', wMm: 297, hMm: 210 },
  a3: { label: 'A3', pageCss: 'A3', wMm: 420, hMm: 297 },
  letter: { label: 'Letter', pageCss: 'letter', wMm: 279.4, hMm: 215.9 },
}

const PAGE_MARGIN_MM = 20 // 10mm each side
const PX_PER_MM = 96 / 25.4 // CSS px at 96dpi

// Takes any string: the key comes from a saved view in localStorage and may be stale.
export function paperOrDefault(key: string): PaperSize {
  return PAPER_SIZES[key as PaperKey] || PAPER_SIZES.a4
}

/** Usable width in CSS px for a landscape sheet, less margins and a safety buffer
 *  (font antialiasing and sub-pixel rounding otherwise push content onto page 2). */
export function usableWidthPx(key: string, bufferPx: number): number {
  return Math.round((paperOrDefault(key).wMm - PAGE_MARGIN_MM) * PX_PER_MM) - bufferPx
}

/** Usable height in CSS px — only the network diagram fits vertically as well. */
export function usableHeightPx(key: string, bufferPx: number): number {
  return Math.round((paperOrDefault(key).hMm - PAGE_MARGIN_MM) * PX_PER_MM) - bufferPx
}
