// Assembles the public directory for the standalone build (npm run build:standalone):
// everything in public/, plus py/ with what the in-browser parser needs, all served from
// the app's own origin.
//   py/pyodide.*, python_stdlib.zip   the Python runtime, from the pinned npm package
//   py/<PyP6XER wheel>                 the version requirements.txt pins, SHA-256 checked
//   py/backend/{schedule,xer,mspdi,analysis,worktime,cpm,recalc}.py  XERlock's readers, analysis and CPM engine, the same files the server runs (mpp.py needs Java and stays on the server)
//   py/manifest.json                   tells the worker what to load
//   LICENSE, NOTICE, THIRD-PARTY-NOTICES.txt   the terms everything above is distributed under
import { createHash } from 'node:crypto'
import { cpSync, existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

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

const pythonFiles = ['schedule.py', 'xer.py', 'mspdi.py', 'analysis.py', 'worktime.py', 'cpm_core.py', 'cpm.py', 'recalc.py', 'cpm_msp.py', 'recalc_msp.py']
for (const f of pythonFiles) cpSync(join(repo, 'backend', f), join(py, 'backend', f))

// One source of truth for the parser library's version: the server's requirements.txt.
const pin = readFileSync(join(repo, 'requirements.txt'), 'utf8').match(/^PyP6XER==(\S+)/m)
if (!pin) throw new Error('requirements.txt must pin PyP6XER==<version>')
const version = pin[1]
const meta = await (await fetch(`https://pypi.org/pypi/PyP6XER/${version}/json`)).json()
const wheel = meta.urls.find(u => u.packagetype === 'bdist_wheel' && u.filename.endsWith('-none-any.whl'))
if (!wheel) throw new Error(`No pure-Python wheel for PyP6XER ${version}`)
const cache = join(frontend, 'node_modules', '.cache', 'xerlock', wheel.filename)
if (!existsSync(cache)) {
  mkdirSync(dirname(cache), { recursive: true })
  writeFileSync(cache, Buffer.from(await (await fetch(wheel.url)).arrayBuffer()))
}
const bytes = readFileSync(cache)
const sha = createHash('sha256').update(bytes).digest('hex')
if (sha !== wheel.digests.sha256) {
  rmSync(cache)
  throw new Error(`PyP6XER wheel checksum mismatch (got ${sha}, PyPI says ${wheel.digests.sha256})`)
}
writeFileSync(join(py, wheel.filename), bytes)

writeFileSync(join(py, 'manifest.json'), JSON.stringify({ wheel: wheel.filename, python: pythonFiles }, null, 2))

// The build redistributes Pyodide and PyP6XER, so it carries their terms with it (the
// wheel holds PyP6XER's full licence text in its dist-info).
const pyodideVersion = JSON.parse(readFileSync(join(pyodide, 'package.json'), 'utf8')).version
for (const f of ['LICENSE', 'NOTICE']) cpSync(join(repo, f), join(out, f))
writeFileSync(join(out, 'THIRD-PARTY-NOTICES.txt'), `XERlock's standalone build includes:

Pyodide ${pyodideVersion} (py/pyodide.*, py/python_stdlib.zip, py/pyodide-lock.json)
  Mozilla Public License 2.0. Source: https://github.com/pyodide/pyodide
  It bundles CPython (Python Software Foundation License) and its standard library.

PyP6XER ${version} (py/${wheel.filename})
  GNU Lesser General Public License v2.1; full text inside the wheel at
  pyp6xer-${version}.dist-info/licenses/LICENSE. Source: https://github.com/HassanEmam/PyP6Xer
`)
console.log(`standalone assets ready: Pyodide ${pyodideVersion}, ${wheel.filename}`)
