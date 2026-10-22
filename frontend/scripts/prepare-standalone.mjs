// Assembles the public directory for the standalone build (npm run build:standalone):
// everything in public/, plus py/ with what the in-browser parser needs, all served from
// the app's own origin.
//   py/pyodide.*, python_stdlib.zip   the Python runtime, from the pinned npm package
//   py/backend/{schedule,xer,mspdi,analysis,worktime,cpm,recalc}.py  XERlock's readers, analysis and CPM engine, the same files the server runs (mpp.py needs Java and stays on the server)
//   py/manifest.json                   tells the worker what to load
//   LICENSE, NOTICE, THIRD-PARTY-NOTICES.txt   the terms everything above is distributed under
import { cpSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { STANDALONE_PYTHON_FILES } from './standalone-files.mjs'

const here = dirname(fileURLToPath(import.meta.url))
const frontend = join(here, '..')
const repo = join(frontend, '..')
const out = join(frontend, '.standalone-public')
const py = join(out, 'py')

rmSync(out, { recursive: true, force: true })
cpSync(join(frontend, 'public'), out, { recursive: true })
mkdirSync(join(py, 'backend'), { recursive: true })

const pyodide = join(frontend, 'node_modules', 'pyodide')
for (const f of ['pyodide.mjs', 'pyodide.asm.mjs', 'pyodide.asm.wasm', 'python_stdlib.zip', 'pyodide-lock.json']) {
  cpSync(join(pyodide, f), join(py, f))
}

const pythonFiles = STANDALONE_PYTHON_FILES
for (const f of pythonFiles) cpSync(join(repo, 'backend', f), join(py, 'backend', f))

writeFileSync(join(py, 'manifest.json'), JSON.stringify({ python: pythonFiles }, null, 2))

// The build redistributes Pyodide, so it carries its terms with it.
const pyodideVersion = JSON.parse(readFileSync(join(pyodide, 'package.json'), 'utf8')).version
for (const f of ['LICENSE', 'NOTICE']) cpSync(join(repo, f), join(out, f))
writeFileSync(join(out, 'THIRD-PARTY-NOTICES.txt'), `XERlock's standalone build includes:

Pyodide ${pyodideVersion} (py/pyodide.*, py/python_stdlib.zip, py/pyodide-lock.json)
  Mozilla Public License 2.0. Source: https://github.com/pyodide/pyodide
  It bundles CPython (Python Software Foundation License) and its standard library.
`)
console.log(`standalone assets ready: Pyodide ${pyodideVersion}`)
