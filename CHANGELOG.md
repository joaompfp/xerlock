# Changelog

All notable changes to XERlock. Versions follow [Semantic Versioning](https://semver.org/):
a change to what an existing figure means, or to the API contract the frontend and saved
snapshots rely on, is a major version.

## [1.1.0] - 2026-10-14

### Added
- Standalone build: the same Python parsing core and CPM engine the server runs, executed in
  the browser under Pyodide in a Web Worker. No server; the `.xer` never leaves the user's
  computer. Published at https://joaompfp.github.io/xerlock/ and attached to this release
  as `xerlock-standalone-1.1.0.zip` for hosting on any static web server.

### Changed
- The parsing core moved from `backend/main.py` to `backend/xer.py` so that both builds run
  the same code; the server's API and results are unchanged.

## [1.0.0] - 2026-10-13

First release. XERlock reviews a Primavera P6 `.xer` export read-only, in memory, and shows
its working: every figure is either P6's own value or recomputed and checked against it
(see [docs/METHODOLOGY.md](docs/METHODOLOGY.md)).

### Review views
- Gantt chart with WBS grid, critical-path link overlay, float tails, driving-chain panel,
  look-ahead filters and baseline ghost bars.
- Critical-path network diagram (activity-on-node), scoped to the critical, near-critical
  or full network.
- Progress: milestone variance, look-ahead, duration-weighted S-curve.
- Calendars: work patterns, holidays and working exceptions per calendar.
- Raw tables: every table in the file exactly as exported.
- WBS tree with roll-ups.
- Compare two snapshots, including forensic checks on changed actual dates and
  constraints; snapshots can be kept in the browser.
- Excel review report export.

### Schedule analysis
- Health Check to the DCMA 14-Point Assessment definitions and populations (DCMA 01-13;
  BEI is not computed without a baseline), plus out-of-sequence progress, ALAP and LOE on
  the critical path. Configurable targets and weights.
- Longest Path traced through driving links, using relationship free float in working
  time on the file's own calendars, and cross-checked against P6's stored flag.
- CPLI in working time.
- CPM engine: reschedules the programme in memory from its own logic, calendars,
  constraints, progress and scheduling options, and reports every activity where its
  dates or float differ from P6's.
- DCMA 12 Critical Path Test, run only when the recalculation reproduces P6 exactly.

### Project
- Licensed AGPL-3.0-or-later with an attribution term (see NOTICE); contributions under
  the CLA. Versions published before 12 October 2026 remain available under MIT.

[1.1.0]: https://github.com/joaompfp/xerlock/releases/tag/v1.1.0
[1.0.0]: https://github.com/joaompfp/xerlock/releases/tag/v1.0.0
