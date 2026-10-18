/// <reference lib="webworker" />
// Runs XERlock's Python parsing core (backend/schedule.py and the readers it dispatches
// to) in the browser under Pyodide.
// Lives in a worker so a large file never freezes the page. Every asset (the Python
// runtime, the PyP6XER wheel, the parser source) is served from this app's own origin
// under py/, prepared by scripts/prepare-local-parser.mjs: no CDN, nothing for a
// corporate proxy to block, and no request leaves the site once it is loaded.

import type { PyodideInterface } from 'pyodide'

/** Without bytes, the request only boots the runtime (warm-up). */
export interface ParseRequest { id: number; bytes?: ArrayBuffer }
export type ParseResponse =
  | { id: number; stage: string }
  | { id: number; ok: true; json: string }
  | { id: number; ok: false; error: string }

interface Manifest { wheel: string; python: string[] }

const ASSETS = new URL(import.meta.env.BASE_URL + 'py/', self.location.origin).href
const post = (msg: ParseResponse) => self.postMessage(msg)

let ready: Promise<PyodideInterface> | null = null

async function boot(stage: (s: string) => void): Promise<PyodideInterface> {
  stage('Loading the parser (first time only)…')
  const manifest = (await (await fetch(ASSETS + 'manifest.json')).json()) as Manifest
  const { loadPyodide } = (await import(/* @vite-ignore */ ASSETS + 'pyodide.mjs')) as typeof import('pyodide')
  const py = await loadPyodide({ indexURL: ASSETS })
  // PyP6XER is pure Python with no dependencies: unpacking its wheel installs it.
  py.unpackArchive(await (await fetch(ASSETS + manifest.wheel)).arrayBuffer(), 'wheel')
  py.FS.mkdirTree('/xerlock/backend')
  for (const name of manifest.python) {
    py.FS.writeFile(`/xerlock/backend/${name}`, await (await fetch(ASSETS + 'backend/' + name)).text())
  }
  py.runPython("import sys; sys.path.insert(0, '/xerlock')")
  return py
}

// The parser's own messages for files it rejects (ValueError and its subclasses) are
// written for users and shown verbatim, as the server does; anything else is a crash,
// reported generically. A .mpp always lands here: this build has no Java, so
// backend/schedule.py says to save it as XML.
function userMessage(err: unknown): string {
  const text = String((err as Error)?.message ?? err)
  const valueError = text.match(/(?:ValueError|UnsupportedFile): (.+)\s*$/)
  if (valueError) return valueError[1].trim()
  console.error('XERlock local parser:', text)
  return 'Could not parse this file as a P6 .xer export or a Microsoft Project file'
}

self.onmessage = async (e: MessageEvent<ParseRequest>) => {
  const { id, bytes } = e.data
  const stage = (s: string) => post({ id, stage: s })
  try {
    ready ??= boot(stage)
    const py = await ready.catch(err => { ready = null; throw err })
    if (!bytes) { post({ id, ok: true, json: 'null' }); return }
    stage('Parsing on this computer — nothing is uploaded…')
    py.FS.writeFile('/tmp/upload.bin', new Uint8Array(bytes))
    try {
      const json = py.runPython(
        "import json\nfrom backend.schedule import parse_schedule\njson.dumps(parse_schedule('/tmp/upload.bin'))",
      ) as string
      post({ id, ok: true, json })
    } finally {
      py.FS.unlink('/tmp/upload.bin')
    }
  } catch (err) {
    post({ id, ok: false, error: userMessage(err) })
  }
}
