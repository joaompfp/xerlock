// Client for the in-browser parser worker (workers/localParser.worker.ts). One worker for
// the page's lifetime: Python loads once, then every later file parses immediately.

import type { Schedule } from '../types/schedule'
import type { OnStage } from './parseSchedule'
import type { ParseRequest, ParseResponse } from '../workers/localParser.worker'

interface Pending { resolve: (s: Schedule) => void; reject: (e: Error) => void; onStage?: OnStage }

let worker: Worker | null = null
let nextId = 1
const pending = new Map<number, Pending>()

function getWorker(): Worker {
  if (worker) return worker
  worker = new Worker(new URL('../workers/localParser.worker.ts', import.meta.url), { type: 'module' })
  worker.onmessage = (e: MessageEvent<ParseResponse>) => {
    const msg = e.data
    const p = pending.get(msg.id)
    if (!p) return
    if ('stage' in msg) { p.onStage?.(msg.stage); return }
    pending.delete(msg.id)
    if (msg.ok) p.resolve(JSON.parse(msg.json) as Schedule)
    else p.reject(new Error(msg.error))
  }
  // A worker that fails to start (e.g. a blocked asset) fails every request in flight,
  // and is recreated on the next attempt.
  worker.onerror = e => {
    for (const p of pending.values()) p.reject(new Error('The in-browser parser failed to start: ' + e.message))
    pending.clear()
    worker = null
  }
  return worker
}

/** Start loading Python in the background, so the first file parses without the wait. */
export function warmUp(): void {
  const id = nextId++
  pending.set(id, { resolve: () => {}, reject: () => {} })
  getWorker().postMessage({ id } satisfies ParseRequest)
}

export async function parseLocally(file: File, onStage?: OnStage, project?: number): Promise<Schedule> {
  const bytes = await file.arrayBuffer()
  const id = nextId++
  return new Promise<Schedule>((resolve, reject) => {
    pending.set(id, { resolve, reject, onStage })
    const req: ParseRequest = { id, bytes, project }
    getWorker().postMessage(req, [bytes])
  })
}
