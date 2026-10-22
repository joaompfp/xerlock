// The Python files the standalone build ships under py/backend/: the readers, the analysis
// and the CPM engine, exactly the files the server runs (mpp.py needs Java and isolate.py
// is the server's process wrapper, so both stay on the server). One list, read by
// prepare-standalone.mjs and by the test that parses the sample through Pyodide.
export const STANDALONE_PYTHON_FILES = [
  'schedule.py', 'xer.py', 'pmxml.py', 'mspdi.py', 'analysis.py', 'worktime.py',
  'cpm_core.py', 'cpm.py', 'recalc.py', 'cpm_msp.py', 'recalc_msp.py',
]
