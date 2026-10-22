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

/** `project`: which project of a multi-project .xer to read (by default the largest). */
export async function parseSchedule(file: File, onStage?: OnStage, project?: number): Promise<Schedule> {
  if (PARSER_MODE === 'local') {
    const { parseLocally } = await import('./localParser')
    return parseLocally(file, onStage, project)
  }
  return parseOnServer(file, onStage, project)
}

/** In standalone mode, begin loading the in-browser parser before a file is chosen. */
export function prepareParser(): void {
  if (PARSER_MODE === 'local') void import('./localParser').then(m => m.warmUp())
}

// XMLHttpRequest rather than fetch: it reports upload progress, so a large file on a
// slow link shows how far it has got before the server starts reading it.
function parseOnServer(file: File, onStage?: OnStage, project?: number): Promise<Schedule> {
  return new Promise((resolve, reject) => {
    const form = new FormData()
    form.append('file', file)
    if (project != null) form.append('project', String(project))
    const xhr = new XMLHttpRequest()
    xhr.open('POST', '/api/upload')
    xhr.responseType = 'json'
    xhr.upload.onprogress = e => {
      if (onStage && e.lengthComputable) onStage(`Uploading… ${Math.round((100 * e.loaded) / e.total)}%`)
    }
    xhr.upload.onload = () => onStage?.('Reading the schedule on the server…')
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300 && xhr.response) return resolve(xhr.response as Schedule)
      const detail = (xhr.response as { detail?: string } | null)?.detail
      reject(new Error(typeof detail === 'string' ? detail : 'Could not parse this file.'))
    }
    xhr.onerror = () => reject(new Error('The server could not be reached.'))
    xhr.send(form)
  })
}
