// Where a .xer file is parsed. One function for every caller (main upload, Compare's
// baseline), so the choice lives in one place and both behave identically.
//
// 'server': POST /api/upload; the FastAPI backend parses it in memory and discards it.
// 'local':  the same Python parsing core (backend/xer.py) runs in this browser under
//           Pyodide, in a Web Worker. The file never leaves the machine.
// Chosen at build time (VITE_PARSER=local, npm run build:local), so each build carries
// only the code for its own mode.

import type { Schedule } from '../types/schedule'

export type ParserMode = 'server' | 'local'
export const PARSER_MODE: ParserMode = import.meta.env.VITE_PARSER === 'local' ? 'local' : 'server'

/** Progress text for the loading state, when the parser can report it. */
export type OnStage = (message: string) => void

export async function parseSchedule(file: File, onStage?: OnStage): Promise<Schedule> {
  if (PARSER_MODE === 'local') {
    const { parseLocally } = await import('./localParser')
    return parseLocally(file, onStage)
  }
  return parseOnServer(file)
}

/** In standalone mode, begin loading the in-browser parser before a file is chosen. */
export function prepareParser(): void {
  if (PARSER_MODE === 'local') void import('./localParser').then(m => m.warmUp())
}

async function parseOnServer(file: File): Promise<Schedule> {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch('/api/upload', { method: 'POST', body: form })
  if (!res.ok) {
    let msg = 'Could not parse this file.'
    try { msg = ((await res.json()) as { detail?: string }).detail || msg } catch { /* non-JSON error body */ }
    throw new Error(msg)
  }
  return (await res.json()) as Schedule
}
