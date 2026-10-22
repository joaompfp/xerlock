// The standalone build parses files in the browser with Pyodide (localParser.worker.ts).
// This runs that same path under Node: the Python files the build ships, loaded into
// Pyodide the way the worker loads them, parsing the sample. A file the readers import
// but the build leaves out, or Python the runtime can't run, fails here, not on a
// user's machine.
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { loadPyodide } from 'pyodide'
import { STANDALONE_PYTHON_FILES } from '../../scripts/standalone-files.mjs'

const repo = fileURLToPath(new URL('../../../', import.meta.url))

describe('standalone parser (Pyodide)', () => {
  it('parses the sample with the files the build ships', async () => {
    const py = await loadPyodide()
    py.FS.mkdirTree('/xerlock/backend')
    for (const name of STANDALONE_PYTHON_FILES) {
      py.FS.writeFile(`/xerlock/backend/${name}`, readFileSync(`${repo}backend/${name}`, 'utf8'))
    }
    py.runPython("import sys; sys.path.insert(0, '/xerlock')")
    py.FS.writeFile('/tmp/upload.bin', readFileSync(`${repo}examples/sample-schedule.xer`))
    const json = py.runPython(
      "import json\nfrom backend.schedule import parse_schedule\njson.dumps(parse_schedule('/tmp/upload.bin'))",
    ) as string
    const data = JSON.parse(json)
    expect(data.activities).toHaveLength(24)
    expect(data.project.proj_short_name).toBe('DEMO-DC-01')
    expect(data.project.recalculation.supported).toBe(true)
    expect(data.project.recalculation.differing).toBe(0)
  }, 120_000)
})
