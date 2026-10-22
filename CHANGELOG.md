# Changelog

All notable changes to XERlock. Versions follow [Semantic Versioning](https://semver.org/):
a change to what an existing figure means, or to the API contract the frontend and saved
snapshots rely on, is a major version.

## [1.13.0] - 2026-10-22

### Added
- Primavera P6 XML exports are read, in both builds. The XML is mapped onto the same
  tables a .xer carries, so every view and check, the recalculation and the Critical
  Path Test work identically: a P6 XML twin of the sample reads exactly as the .xer.
  Embedded baselines open or compare like any other project of the file; the raw-table
  inspector shows the XML's own elements; an export without total float gets it from
  each activity's early and late finish, and says so.

### Fixed
- Start milestones stored as TT_Mile (older P6 versions) were treated as ordinary
  activities by the open-ends check: flagged for a missing successor-side tie, and the
  project start milestone was not exempted.

## [1.12.0] - 2026-10-22

### Added
- A .xer holding several projects shows them above the chart: any of them opens from
  the same file, and Compare offers the others as the earlier file, so a baseline the
  export carries as a second project can be compared directly. The largest project is
  still the one opened first. The upload API takes an optional `project` id.

## [1.11.0] - 2026-10-22

States, keyboard and phone (council review, batch B).

### Added
- Keyboard: arrows pan and + / − zoom the Gantt (↑ ↓ still move the selection) and
  the network diagram; every icon-only button has an accessible name.
- On a phone the Gantt shows its timeline: the activity column narrows to code and
  name beside it (at 390 px the timeline used to be blank).
- Uploads report their progress, then that the server is reading the file.

### Changed
- Compare warns when few activity codes match: the files look like different
  projects. Deleting a snapshot asks first.

### Fixed
- Compare's upload note said nothing was uploaded on the server build; it now says
  what happens in each build. The snapshot list's Saved column no longer truncates.

## [1.10.0] - 2026-10-22

The numbers read first, made defensible (council review, batch A).

### Changed
- Compare's headline reads the finish move as later, earlier or unchanged, and is
  green only when the finish came in and the logic that drove it largely survived.
  A new finish driver, less than half the longest path kept, or a data date that did
  not move show beside the number. The cards are neutral except "Longest path kept"
  (e.g. 13/96), each card states its rule, float erosion counts losses of a working
  day or more, and logic edits show links added and removed. The earlier file is no
  longer called a baseline; the Gantt's chip for its bars reads "Compared".
- Health check: each failing card shows its rate and what it is of, the target, its
  weight and the points it costs, sorted by points lost, under a line naming the
  biggest losses; the score reads "100 − N points lost". CPLI shows the path length
  and finish float it comes from.
- The sidebar leads with the longest path; TF ≤ 0 follows, with what inflates it
  (negative float, ALAP, open ends) in its tooltip; progress reads "3/24 complete".
- A project opened for the first time fits the width, then keeps its zoom; the header
  labels follow any zoom; the data-date badge no longer covers a month label; WBS
  rows read "24 act."; the filter chip reads "Critical only"; the legend lists only
  the bar states shown.
- Progress states the basis of each figure; the planned line reads "Planned (this file)".

### Fixed
- The last file is kept in IndexedDB, so large files are kept too, and a reload comes
  back to it; when the browser will not keep it, the landing page says so.
- Dark mode: search boxes and native controls were white.
- Critical and milestone rows drew their marker on every cell.

## [1.9.0] - 2026-10-22

Large programmes. Measured on a 5,040-activity schedule, before and after:
parsing 6.4 s -> 2.1 s; opening the file 8.2 s -> 3.7 s; expanding the whole Gantt
2.6 s -> 0.2 s; the critical path view 7.5 s -> 0.6 s; the activity table 4.1 s ->
0.2 s. A 2,000-activity Gantt used to run a browser out of memory when scrolled.

### Changed
- Views are built the first time they are opened, not all at once on load.
- The Gantt and the activity table draw only the rows in view; the network diagram
  draws only what is on screen, and plain boxes when zoomed far out. Printing still
  draws everything.
- The network diagram is laid out by XERlock's own linear-time layered layout instead
  of dagre: hundreds of times faster, and fewer crossing links on most real networks.
- Health check and Progress lists show 100 rows, then "Show all N" (the Excel export
  keeps every row).
- Calendar arithmetic and date formatting no longer walk day by day or rebuild a
  formatter per date.
- The server parses each upload in its own process with a time limit, at most two at
  a time: a file that hangs or crashes a reader gets an error instead of holding or
  stopping the server. A crash names the step that failed.

### Fixed
- .xer files from older P6 versions whose WBS table lacks the tmpl_guid column no
  longer fail to open.
- Activity names in Windows-1252 files keep their accented characters (they were
  dropped); the warning now says which encoding was used.
- Activities list the resources assigned to them; on files with resources, the
  "no resource assigned" check counted every activity.
- Asta Powerproject (.pp) files get a clear message: export them as Microsoft Project
  XML.

### Removed
- The PyP6XER and dagre dependencies: every .xer table is read in one pass, and the
  standalone build no longer downloads a parser wheel.

## [1.8.5] - 2026-10-22

### Changed
- Tighter sidebar spacing, so the figures, navigation, legend and footer fit a 900 px
  tall window without scrolling.

## [1.8.4] - 2026-10-22

### Changed
- The headline figures (critical, milestones, longest path, negative float, % done)
  sit in the sidebar under the data date, and Review notes and Export sit in its footer.
  On wide screens the top bar is gone: the highlighted sidebar item names the page.
- The Gantt legend sits at the bottom of the sidebar while the Gantt is open (back
  above the toolbar in fullscreen), and saved views sit at the end of the filter row:
  the Gantt's controls take two rows instead of three. Both rows fit at 1500 px.
- The sidebar can be hidden (« in its header) to an 18 px rail, and the choice is
  remembered. Narrow screens keep the slide-over sidebar and the top bar.

## [1.8.3] - 2026-10-22

### Changed
- The Gantt toolbar is one compact row with every control on it; the ⋯ menu is gone.
  Scale is D W M Q, zoom, fit and the WBS controls are icons, the basis reads
  "TF ≤ 0 | Longest", and Links, Progress, Baseline, Slip and Key dates are chips.
  Key dates has an edit button (the key dates, periods and highlights editor) and an add
  text box button beside it. Today, fullscreen, print and the paper size sit at the
  right. Every icon has a tooltip. It fits on one row at 1500 px with a baseline loaded,
  and at 1366 px without one.

## [1.8.2] - 2026-10-22

### Added
- Gantt text boxes (⋯ → Add text box): a free remark on the chart, not tied to an
  activity. Type straight away; double-click to edit, drag to move, the dot changes its
  colour, × removes it (so does leaving it empty). Pinned to a date and a height, so it
  follows the timeline through zoom and scroll. Saved with the key dates and highlights,
  switched off with them, and screen-only like callouts.

## [1.8.1] - 2026-10-22

### Added
- Gantt slip arrows (⋯ → Slip arrows, off by default, offered while the compared
  schedule's bars are drawn): under each activity whose finish moved by a calendar day or
  more, an arrow from the compared finish to the current one, red when later and green
  when earlier. The figure stays in the Slip column. Saved views keep the setting.

## [1.8.0] - 2026-10-22

### Added
- Saved Gantt views. "Save view" (top right of the Gantt) keeps the chart as it is: zoom,
  the date window and first row in view, expanded WBS, every filter, the chain trace,
  overlays and which highlight groups are on. Pick a view from the list, or step through
  them with ‹ › like slides; Manage renames, updates or removes them. Saved per project
  in this browser; a chain trace is kept by activity code, so it survives a file update.

## [1.7.0] - 2026-10-22

### Added
- Gantt highlight groups: named sets of activities in one of the markup colours. While a
  group is on, its activities carry a coloured edge and ring and everything else is
  dimmed. Add or remove an activity from its details (Highlight…), or keep a chain trace
  with "Save as highlight". Groups are listed with the key dates (⋯ → Key dates &
  highlights…) to rename, recolour, switch on/off or remove; members are kept by
  activity code, so they survive the next update of the file.

## [1.6.1] - 2026-10-22

### Changed
- On the Gantt printout each review note is a numbered marker, on its bar and before
  its name, and the notes are listed in full after the chart (number, activity,
  severity, text). Callouts are screen-only: they no longer print.

## [1.6.0] - 2026-10-22

### Added
- Gantt key dates and periods (⋯ → Key dates & periods…). A key date is a thin line
  with its label in the timeline header; a period is a faint band behind the bars with
  a coloured rule and label in the header. Each takes a label, its date(s) and one of
  five muted colours (click the swatch to change it). Saved per project in this
  browser, shown on screen and on the printout, and switched off from the same menu.

## [1.5.1] - 2026-10-22

### Changed
- The Gantt activity column can be dragged up to 80% of the window (was 700 px), and a
  saved width is no longer cut back to 55% of the window on reload.

### Added
- Double-click the activity column's edge to fit it to the longest name on screen.

## [1.5.0] - 2026-10-21

### Added
- Gantt note callouts. Clicking a note's dot (after the activity name, or the new one
  at the bar's end) shows the note as a callout on the chart; clicking it again or the
  callout's × hides it. Drag a callout to move it: a dashed leader keeps it tied to its
  bar, and it follows the bar through zoom and scroll. Shown callouts and their
  positions are saved with the notes in this browser, and print on their bar's sheet.
  Clicking a bar still opens the activity's details.

## [1.4.3] - 2026-10-21

### Added
- Gantt notes filter: activities with any review note, one severity (Query, Risk, Logic
  Issue, Resolved), or notes saved without a severity, each with its count.

### Changed
- The Gantt filters sit on one compact row under the toolbar instead of in a dialog:
  search, status, constraint, notes, critical, date window with 4/8-week look-ahead, and
  an activity-code picker. A control that is narrowing the view is drawn in the accent
  colour; the match count sits at the end of the row.

## [1.4.2] - 2026-10-21

### Added
- Gantt constraint filter: any constraint, hard constraints only, no constraint, or one
  type (As Late As Possible, Finish On or Before, …). The primary and secondary
  constraints both count, and each choice shows how many activities it matches.

## [1.4.1] - 2026-10-19

### Added
- Gantt Slip column on WBS rows: the WBS finish against the latest compared finish of the
  same activities.

### Changed
- The Gantt printout is the screen's Gantt, not a table. It has the same columns
  (Slip included), bars, compared-schedule outlines, links and data-date line, and is
  fitted to the paper width. It is drawn one sheet at a time, each sheet with a title
  line (project, data date, filters, compared file, page number) and the column header.
  The header's tick scale follows the fitted width.

### Fixed
- The printout no longer includes the app header, toolbar, legend or filter strip, and no
  longer prints the tinted page background.

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
