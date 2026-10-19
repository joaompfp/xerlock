# Changelog

All notable changes to XERlock. Versions follow [Semantic Versioning](https://semver.org/):
a change to what an existing figure means, or to the API contract the frontend and saved
snapshots rely on, is a major version.

## [1.4.0] - 2026-10-19

### Added
- Gantt: a **Slip** column beside Float whenever the compared schedule's bars are drawn,
  giving each activity's finish movement in calendar days (+ later, − earlier, "new" when
  the compared file lacks it), the same measure as Compare's date changes.

## [1.3.1] - 2026-10-19

### Fixed
- Project free slack counts only the links written on the task: a link inherited through
  its parent summary's logic schedules the task but leaves its free slack at its total
  slack, and a link to a summary task is measured against the summary's rolled-up date.
  Evidence: Microsoft's "Project 2003 deployment" template (250 tasks) now reproduces with 0
  differences; it stored 78 free-slack values the old rule got wrong.

### Added
- A task's levelling delay is honoured: elapsed time added to the early start its logic
  gives, and taken off its late start for its predecessors (Microsoft's Leveling Delay,
  Early Start and Late Finish field pages). A coursework schedule with progress, a status
  date and a levelled task reproduces exactly. The rule is validated for an unstarted,
  unconstrained task with FS predecessors without lag, delayed onto a working start; any
  other levelled task is listed in `uncovered` and keeps the Critical Path Test withheld.
  An assignment's levelling delay, in regular duration units, is still refused.
- `tests/test_msp_examples.py`: local oracle `.mpp` files under `examples/` (gitignored,
  never committed) must reproduce and pass the Critical Path Test; skipped when absent.

## [1.3.0] - 2026-10-19

### Added
- Recalculation and the Critical Path Test (DCMA 12) for Microsoft Project files. A second
  CPM engine (`backend/cpm_msp.py`) reschedules the file with Project's rules, each taken
  from MPXJ 16.10.0's `MicrosoftScheduler` (LGPL; rules, not code) or Microsoft's own pages
  and cited in `docs/METHODOLOGY.md`, and `backend/recalc_msp.py` compares Start/Finish,
  late dates and slack with what Project stored. Validated on MPXJ's corpus: 32 of the 33
  files with logic the engine accepts reproduce with 0 differences (the exception, a Project
  2003 file, is documented), and the one real-world `.mpp` available reproduces and passes
  the test.
- Refusals with their reasons: scheduling from the finish date, incomplete manually
  scheduled tasks, levelling delays, split or contoured tasks, recurring tasks, inserted or
  external projects, summary-task constraints, the multiple-critical-paths option, and
  resource assignments on other working time than the task's.
- `recalculation.uncovered`: the rules a Project file rests on that the oracle corpus has
  not validated (deadlines, ALAP and late-side constraints, elapsed durations and lags,
  percentage lags, cross-calendar links). The file is still compared; the Critical Path Test
  is withheld and the Health Check names the rules.
- `scripts/msp_oracle_coverage.py`: what the corpus can prove, feature by feature, with
  MPXJ's own scheduler as a second reference; `scripts/msp_corpus.py` reports the
  recalculation's result per file.

### Changed
- `backend/cpm_core.py` holds what both engines share (result and link types, ordering,
  comparison, Critical Path Test); P6 results are unchanged, proved on the sample and on 12
  real exports.
- `Recalculation.options` carries Project's settings on a Project file (`schedule_from`,
  `lag_calendar`, `critical_slack_limit_days`, `multiple_critical_paths`); the P6 keys are
  unchanged.

## [1.2.0] - 2026-10-19

### Added
- Microsoft Project files. Project XML (File > Save As > XML) is read by both builds;
  `.mpp` (Project 98 to current) on the server, converted in memory by MPXJ (LGPL-2.1,
  Java; the container carries a headless JRE). Every view and check works on them. Project's
  own stored dates, slack, critical flags, actuals, Baseline 0, constraints and calendars are
  read, never recomputed; the recalculation and the Critical Path Test are not yet available
  for Project files and say so. `docs/METHODOLOGY.md` maps every field and check.
- Project-specific checks: manually scheduled tasks, logic on summary tasks, elapsed and
  percentage lags, inactive tasks (left out of every population and counted).
- `project.source_format` (`xer` | `mspdi` | `mpp`) in the API, and the UI names the file's
  own tool. Checks that need a P6-only concept report "not checkable" with the reason.
- `examples/sample-schedule.xml`: the demo project as Project would save it, on the upload
  screen beside the `.xer` sample.
- `scripts/fetch_msp_corpus.sh` and `scripts/msp_corpus.py`: MPXJ's test corpus at a pinned
  commit, and an aggregate report of what parses and whether `.mpp` and XML twins agree.

### Changed
- The parsing core is split into readers (`backend/xer.py`, `backend/mspdi.py`,
  `backend/mpp.py`) and shared analysis (`backend/analysis.py`); `backend/schedule.py` picks
  the reader from the file's content. `.xer` results are unchanged apart from four new optional
  project fields (`source_format`, and `inactive_activities`, `summary_links` and
  `msp_options`, which are null for P6), verified on the sample and on 12 real exports.
- The upload endpoint accepts `.xer`, `.xml` and `.mpp`.

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

[1.2.0]: https://github.com/joaompfp/xerlock/compare/v1.1.0...main
[1.1.0]: https://github.com/joaompfp/xerlock/releases/tag/v1.1.0
[1.0.0]: https://github.com/joaompfp/xerlock/releases/tag/v1.0.0
