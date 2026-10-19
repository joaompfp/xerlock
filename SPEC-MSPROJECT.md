# SPEC: Microsoft Project files

Status: **phases 0-2 shipped in 1.2.0** (PR #17, 2026-10-19). **Phase 3 specified in §7**
(2026-10-19, target release 1.3.0); no engine code yet. Written 2026-10-18. Read `docs/METHODOLOGY.md`
and `SPEC.md` first: this builds on the same principles.

## 1. Objective

XERlock reviews Primavera P6 `.xer` files. Add Microsoft Project files, so the same
review works on programmes contractors deliver from Project. **P6 stays the core:** no
P6 behaviour, figure or API field changes meaning.

| Format | Phase | Server | Standalone (browser) |
|---|---|---|---|
| Project XML (MSPDI: File > Save As > XML) | 1 | yes | yes |
| `.mpp` (Project 98 to current) | 2 | yes, converted to MSPDI by MPXJ, then the phase 1 reader | no: the page tells the user to save as XML |
| CPM recalculation and Critical Path Test for Project files | 3 | yes | yes |

**Users:** project controls professionals. They need findings they can defend, so every
figure on a Project file is either Project's own stored value or recomputed and
cross-checked against it, exactly as for P6. Where a P6 concept has no Project
equivalent, the check says "not checkable for Microsoft Project files" and why. It is
never approximated silently.

### Acceptance criteria (phases 0-2)

1. **Refactor first, no behaviour change.** The `.xer` result is byte-identical before
   and after, on the sample and on every local P6 corpus file. Commit this separately,
   before any Project code.
2. **Project XML reader.** It produces the same `Schedule` contract the `.xer` path
   produces. Every view works on it: Gantt, network, progress, calendars, WBS, raw tables,
   compare, Health Check and Excel export.
3. **Stored values, not recomputed ones.** Project's own early/late dates, total and free
   slack, critical flag, actuals, baseline (Baseline 0, as planned dates), constraints
   and calendars are read from the file.
4. **Project-specific checks** (source "XERlock"; their definitions go in METHODOLOGY):
   - manually scheduled tasks (`Manual`);
   - logic on summary tasks;
   - elapsed and percentage lags;
   - inactive tasks (excluded from all populations, counted).
5. **Format-honest UI.** Labels that say "P6" name the file's own tool, from a new
   optional `project.source_format` field (`xer` | `mspdi` | `mpp`). Checks that need a
   P6-only concept (e.g. the stored Longest Path flag) show "not checkable" with the
   reason. Recalculation and the Critical Path Test report
   `supported: false, reason: "not yet available for Microsoft Project files"` until
   phase 3.
6. **`.mpp` on the server.** Read via MPXJ, which converts it to MSPDI in memory; the
   phase 1 reader then reads that. The container gains a headless JRE. The read-only and
   no-storage promises hold.
7. **Validated against the corpus (§6).** Every MPXJ test file that has an MSPDI twin
   gives the same result through both paths (`.mpp` → MPXJ → reader, and `.xml` →
   reader). The reader handles every file in the corpus with no crash; any file it
   refuses gets a stated reason.
8. **Docs.** README, METHODOLOGY (a "Microsoft Project files" section mapping every
   field and check), CHANGELOG 1.2.0, and the frontend/backend version set to 1.2.0.

## 2. Commands

```bash
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/pytest
cd frontend && npm run test:run && npm run build && npm run build:standalone
scripts/fetch_msp_corpus.sh                # NEW: MPXJ test files at a pinned commit -> .corpus/mpxj (gitignored)
.venv/bin/python scripts/msp_corpus.py .corpus/mpxj   # NEW: aggregate report, not in CI
```

## 3. Design

**The contract is the neutral model.** `Schedule` (frontend/src/types/schedule.ts) and
the pydantic models stay as they are. The Project reader maps into the existing
vocabulary where the meaning genuinely matches. Snapshots already saved in users'
browsers depend on that vocabulary, so it must not change.

| Project | Contract |
|---|---|
| link Type 0/1/2/3 | PR_FF / PR_FS / PR_SF / PR_SS |
| ConstraintType 0-7 | none / CS_ALAP / CS_MSO or CS_MANDSTART / CS_MEO or CS_MANDFIN / CS_MSOA / CS_MSOB / CS_MEOA / CS_MEOB. Which P6 type matches Project's "Must Start/Finish On" depends on how Project honours constraint dates; decide that from the corpus and document it |
| zero-duration milestone | TT_FinMile (reasoning goes in METHODOLOGY) |
| summary task | WBS node, not an activity |
| status | derived from ActualStart / ActualFinish |
| data date | StatusDate. If missing, data_date is null, a warning says why, and the date-based checks report "not checkable" |

Treat this table as a starting point. Verify every code and unit against MPXJ's
MSPDI reader source and Microsoft's MSPDI schema documentation, not memory. Durations
are ISO 8601 (`PT8H0M0S`), and link lags are in tenths of a minute with a `LagFormat`.
Where the mapping loses meaning, add an optional field rather than overloading an
existing one.

**Backend split** (the phase 0 refactor):

```
backend/xer.py        .xer -> neutral intermediate (activities, links, calendars, WBS, project, options, raw tables)
backend/mspdi.py      NEW: MSPDI XML -> the same intermediate; stdlib xml.etree only
backend/mpp.py        NEW (server only): .mpp -> MSPDI bytes via MPXJ; imported lazily, so the
                      standalone build and plain tests never need Java
backend/analysis.py   NEW: what both formats share, moved out of xer.py: driving links (working-time
                      free float), Longest Path, CPLI, summary counts, the recalc call
```

- The standalone build ships `mspdi.py` and `analysis.py` too (prepare-standalone's
  `pythonFiles`).
- The upload endpoint accepts `.xer`, `.xml`, `.mpp`. Choose the reader by content (XML
  root namespace, OLE2 signature for `.mpp`), not by file extension alone.
- The size cap still applies.
- The frontend's file inputs accept the same types. The standalone build answers `.mpp`
  with "save it from Project as XML (File > Save As > XML)".

**Raw tables for Project files:** the XML's own records as tables. Each record type is a
table (Project, Tasks, PredecessorLinks, Calendars, Resources, Assignments), with field
names exactly as the XML element names. Values are verbatim, not interpreted.

**Driving rule on Project files:** keep the working-time free-float rule. The calendar a
lag counts on is Project's rule, not P6's. Find it from the corpus and document it.

## 4. Testing

- Test-driven, one rule per test, synthetic minimal MSPDI documents in
  `tests/test_mspdi.py`.
- A committed demo sample, `examples/sample-schedule.xml`, hand-written MSPDI for the
  same demo project as the `.xer` sample. It is our own content, not third-party.
  - Add a fixture-drift guard like `test_fixture.py`.
  - Add a second landing-page sample button only if it stays uncluttered.
- Phase 2 tests that need Java are skipped when no JVM is present. CI installs a JRE, so
  they run there.
- The corpus is not in CI. `scripts/msp_corpus.py` reports per-file aggregates: parsed /
  refused (with reason), activity and link counts, and differences between the `.mpp` and
  `.xml` paths.

## 5. Boundaries

**Always**
- Refactor before behaviour, in separate commits (AGENTS.md).
- Keep P6 output byte-identical, proved on the sample and on the local P6 corpus. That
  corpus is client-confidential: report aggregates only, and never copy, quote or
  commit it.
- Update METHODOLOGY in the same commit as each rule.

**Ask first (the supervisor decides)**
- Any new dependency beyond `mpxj` and its JPype bridge (phase 2), and the JRE in the image.
- Any change to an existing contract field's meaning.

**Never**
- Commit MPXJ corpus files or the downloaded templates. Fetch them at a pinned commit
  into gitignored `.corpus/`.
- Approximate Project scheduling with P6 rules and present the result as a recalculation.
- Push, deploy, or open PRs. The supervisor does that.

## 6. Corpus

- **MPXJ test data**: https://github.com/joniles/mpxj `junit/data/` (LGPL-2.1). About 609
  `.mpp` files and about 150 MSPDI `.xml` files, saved by real Microsoft Project 98-2019.
  Pin a commit SHA in the fetch script.
- **One local `.mpp`** under `/XD/JLL` (client-confidential, same rules as the P6
  corpus). Use it only for aggregate checks.

## 7. Phase 3: a scheduling engine for Project files (target 1.3.0)

Status: **specified, not built.** Stage 1 (this section) measured what the oracle can
prove and fixed the rules and their sources; the engine, its tests and the docs are
stage 2. Read `SPEC.md` first: the principle, the comparison method and the Critical
Path Test are the same, with Microsoft Project as the oracle instead of P6.

### 7.1 Objective

On a Project file today, recalculation and the Critical Path Test report
`supported: false, reason: "not yet available for Microsoft Project files"`. Build a
scheduling engine that recomputes a Project file's schedule from its own logic,
durations, calendars, constraints and progress, **the way Project computes it**, and
compare the result with the dates and slack Project stored. Only when the two agree on
every task is the recalculation shown as matching and the Critical Path Test (DCMA 12)
offered. A difference is a review finding (the file was edited and not recalculated, or
uses a feature the engine does not model), never a tolerance.

**The governing rule: Project is the oracle.** A rule is trusted only when it is
documented (Microsoft, or MPXJ's scheduler source, which reproduces Project on real
files) *and* the per-file comparison confirms it on the file under review. Where no rule
is known, the file is refused with a reason. Where a rule is known but the corpus holds
no example of it, the recalculation still runs (the comparison validates the rule on
that file) but the Critical Path Test, which extrapolates the rules to a schedule the
file never stored, is withheld (§7.5, "uncovered features").

### 7.2 What the oracle can prove: coverage (stage 1 measurement)

`scripts/msp_oracle_coverage.py` reads every corpus file through MPXJ (the same reader
for `.mpp` and `.xml`), counts the scheduling features each uses, and sets aside the
files the refusals of §7.5 would reject. Figures at MPXJ commit `71304af` (the pinned
corpus), run 2026-10-19:

| | MPXJ corpus | confidential `.mpp` |
|---|---|---|
| Project files read | 749 (606 `.mpp`, 143 `.xml`); 3 unreadable (MPXJ exception), 5 are P6 PMXML | 1 |
| Scheduled tasks (active, non-summary) | 10,687 | 51 |
| Relationships between scheduled tasks | 327: 225 FS, 34 SS, 34 FF, 34 SF; 178 with lag (130 in days, 46 in weeks, 2 in hours; 6 leads); **no elapsed or percentage lag anywhere** (`LagFormat` 5/7/9 only) | 50, all FS, no lag |
| Files with at least one relationship | **54** of 749 | 1 |
| Tasks whose `Start` differs from the project start | 1,937 of 10,687 (most fixtures sit at the project start) | 51 of 51 |
| Files with progress (an actual start or finish) | 86; 13 of them have logic | 0 |
| Files with a `StatusDate` | 7; **none of them has both logic and progress** | 0 |
| Links across two calendars | 0 (every link has both ends on the same working time) | 0 |
| Manual tasks | 2,784 in 107 files (99 with links) | 0 |
| Resource-driven tasks (a work resource assigned, units > 0) | 1,835; 645 of them on other working time than the task, with a levelling delay or with assignment dates off the task's | 0 |
| Levelling delay / split in-progress tasks / recurring tasks | 30 / 142 / 214 tasks | 0 |
| Subprojects or external tasks | 12 tasks in 6 files | 0 |
| Constraints | SNET 1,012; MSO 7; FNET 8; MFO 3; ALAP 6; **SNLT, FNLT: none** | SNET 3 |
| Deadlines / elapsed durations | 25 / 44 tasks, none in an in-scope file | 0 |
| `MultipleCriticalPaths` on / scheduled from finish | 6 / 6 files, none with logic | off / from start |
| `HonorConstraints` | 0 in **all 143** files Project saved as XML, 1 in all 606 `.mpp` as MPXJ reads them: the element carries no information | 1 |
| Summary-task logic | 1 link (in a file refused for other reasons) | **1 link** (a summary predecessor) |

**In scope** (refusal-free files with logic), under the resource rule §7.5 proposes:
**33 files, 397 tasks, 237 links** (135 FS, 24 SS, 24 FF, 24 SF; 126 lagged links, 92 in
days and 34 in weeks; 129 SNET and 3 MFO constraints; 8 milestones; 5 tasks on a task
calendar; **5 progressed files**, each with one in-progress and two complete tasks; 5
MSPDI files, 28 `.mpp` saved by Project 98, 2000, 2003, 2007, 2010, 2013, 2016 and 2019).
Under the strict rule (refuse any work assignment) it is 26 files, 335 tasks, 192 links
and no progressed file. The confidential file enters scope only if summary-task logic is
modelled (§7.12 Q2).

**What the corpus can validate:** the four link types with and without working-time
lag (days, weeks, leads), SNET and MFO constraints including a constraint held against
logic with negative slack (`slack9.mpp`), milestones at a period's end, late dates from
the project finish, total and free slack, task calendars (5 tasks), unprogressed
Project 98-2019 files in both formats, and completed and in-progress tasks on 5 small
files.

**What it cannot validate** (no in-scope example): deadlines, ALAP, SNLT, FNLT, FNET,
MSO, elapsed durations, elapsed and percentage lags, lags or links across two
calendars, the multiple-critical-paths option, summary-task logic (the confidential
file is the only evidence: one link), progress beyond three tasks per file, and any
file with both progress and a status date. **The corpus is a thin oracle for logic-driven
scheduling**: 54 of 749 files have any logic at all, and the in-scope tasks are mostly
MPXJ's own small relationship fixtures. §7.5 and §7.12 say how each gap is handled.

**MPXJ's own scheduler on the same files** (`--mpxj-scheduler`; see §7.3): it reproduces
679 of 749 files overall, 38 of the 54 with logic, and **31 of the 33 in-scope files**.
The two it misses are `slack9.mpp` (free slack only: Project caps a task's free slack at
its total slack, MPXJ does not, §7.4 rule F3) and `bug1.mpp` (a Project 2003 file where
two tasks' stored late dates sit three days later than any rule gives; §7.12 Q6). Of the
files refused only for manual tasks it reproduces 0 of 6; only for resource calendars 0
of 7; only for recurring tasks 3 of 3. That is the evidence behind the refusals.

### 7.3 Sources

**MPXJ 16.10.0 ships a Project-compatible CPM scheduler.** The `mpxj.jar` the server
already installs (`.venv`, package `mpxj` 16.10.0) contains `org.mpxj.cpm`:
`MicrosoftScheduler` (1,467 lines, 2025-04), `MicrosoftSlackCalculator` (2025-12) and
`MicrosoftSchedulerComparator`, plus a P6 counterpart. LGPL-2.1; its author describes it
as "implemented by observing and attempting to replicate the behavior of Microsoft
Project ... not guaranteed" (`mkdocs/docs/howto-use-cpm.md` at tag v16.10.0). It does
not perform resource levelling, does not schedule from the finish date, and "will not
correctly schedule split tasks, recurring tasks, or summary tasks which have constraints
applied to them" (same page). It never reads the status date (no reference in the
class). The rules below cite it by file and line at tag v16.10.0
(`src/main/java/org/mpxj/cpm/…`; the source was read from the MPXJ repository at that
tag, since the jar carries only class files). **Rules are taken from it, not code:**
XERlock is AGPL-3.0 and stays a Python reimplementation; nothing is copied.

It is **not adopted as a runtime component** (§7.12 Q5): the standalone build has no
Java, the product would carry two engines, and the point of phase 3 is a rule set the
reviewer can read in METHODOLOGY. It is used as a measurement tool (the coverage
script) and as a second reference when our engine and Project disagree.

Microsoft's own pages, cited by title (support.microsoft.com and learn.microsoft.com,
read 2026-10-19):

- *Total Slack (task field)*: "Total slack is calculated as the smaller value of the
  Late Finish minus the Early Finish field, and the Late Start minus the Early Start
  field"; negative slack "is usually caused by constraint dates"; for SS links "the total
  slack can change when you enter progress on the predecessor task".
- *Start Slack (task field)*: "Start Slack = Late Start - Early Start"; "If a task has
  an actual start date and a deadline, the start slack is 0 and the finish slack is the
  difference between the task's finish date and deadline date"; "The smaller of the
  start slack and finish slack amounts determines the amount of free slack available".
- *Free Slack (task field)*: "If the task has no successor tasks, free slack is the same
  as total slack."
- *Late Finish (task field)*: "When you first create a task, its late finish date is the
  same as the project finish date"; "If there is a leveling delay on the successor task,
  this delay is also figured into the date in the Late Finish field."
- *Deadline (task field)*: "deadlines can affect how Total Slack is calculated"; a
  deadline does not constrain scheduling.
- *Task Information dialog box, Predecessors tab* (article 7480b3c4): "If a successor
  uses a task calendar, lag time duration is based on that calendar; otherwise the
  duration is based on the project calendar" (and the same sentence for lead time).
- *Task Calendar (task field)*: "the working times in the applied task calendar
  supersede those in the project calendar. If resources are assigned, the task is
  scheduled based on the intersection of the working times of the task and resource
  calendar. If you turn on the Ignore Resource Calendar field, only the task calendar
  is used."
- *Tasks aren't scheduled as expected in Microsoft Project* (learn.microsoft.com,
  previous-versions troubleshooting): "the Tasks will always honor their constraint dates
  setting overrides the task relationship links"; "If you entered a percent complete on
  a task, and the task has already started, you can't change the Start Date
  automatically"; "If a Summary task (at any level) has a predecessor or a constraint,
  the subtask can't be scheduled any earlier than the summary task"; "Automatic resource
  leveling adds delay to a task"; "a task that has the constraint of As Late As Possible
  (ALAP) in a project is scheduled from the project's Finish Date".
- *Set the status date for project reporting*: the four "Calculation options for this
  project" (move end of completed parts / start of remaining parts to the status date)
  act on actuals as they are entered; changing the settings alone "doesn't move the
  actual or remaining work at all".
- VBA *Application.OptionsSchedule*: `AutoSplit` "True if tasks in progress are
  automatically split"; `HonorConstraints` "True if tasks honor their constraint dates".
  *Application.OptionsCalculation*: `CalcMultipleCriticalPaths`, `MoveCompleted`,
  `MoveRemaining` and their partners, as above.
- *Show the critical path of your project in Project*: "Calculate multiple critical
  paths" is a checkbox under Advanced options; the page does not say what it changes.
  No Microsoft page found describes its effect on late dates (third-party sources say
  tasks without successors get late finish = early finish); MPXJ does not implement it.

### 7.4 Rules

Each rule names its source and what the corpus says. "MS" = `MicrosoftScheduler.java`,
"SC" = `MicrosoftSlackCalculator.java`, both at v16.10.0; "validated" means in-scope
corpus files exercise it and MPXJ reproduces them; "uncovered" means no in-scope file
exercises it (§7.5 says what that implies).

**Population and order**

- P1. Scheduled tasks are the active, non-null, non-summary tasks (MS `isTask` L943-946).
  Summary tasks roll up their children (MS L1056-1142) and are not compared (they are
  WBS nodes in XERlock). Inactive tasks and their links are ignored. Validated.
- P2. Order: a depth-first topological sort over the links; a cycle is refused (MS L62,
  `CycleException`). Validated.
- P3. Logic on a summary task is expanded to its leaf descendants: a summary
  *predecessor* of an SS or SF link stands for its earliest-starting leaf, of an FS or
  FF link for every leaf; a summary *successor* stands for every leaf (MS L1001-1049;
  Microsoft: "the subtask can't be scheduled any earlier than the summary task"). The
  expanded links take part in ordering and both passes. Evidence: the confidential file
  only (1 link; MPXJ reproduces that file). §7.12 Q2 decides whether to model or refuse.

**Forward pass** (MS L203-357)

- F1. An unstarted task with no predecessors starts at the first working moment on its
  calendar at or after the project `StartDate` (MS L251); SNET puts it at its constraint
  date, FNET at constraint date minus duration (MS L236-247). With predecessors, its early
  start is the latest instant any link allows (F2), moved to the next working start on
  the task's calendar, except that a milestone may sit at the end of a working period
  (MS L260, L1403-1412: this is the Friday 17:00 rule METHODOLOGY already documents).
  Validated.
- F2. What a link allows (MS L538-667): FS, predecessor early finish + lag; SS,
  predecessor early start + lag (a finished predecessor: its actual start + lag); SF,
  predecessor early start minus the successor's **full** duration, + lag; FF,
  predecessor early finish minus the successor's **remaining** duration, + lag, never
  before the project start. Lag is added on the **successor's** effective calendar
  (task calendar, else project calendar: MS L969, Microsoft *Predecessors tab*); an
  elapsed lag adds clock time (`ProjectCalendar.getDate` L643-651); a percentage lag is
  that share of the predecessor's duration in the predecessor's duration units (MS
  L963-967). Validated for FS/SS/FF/SF with working-time lags in days and weeks and for
  leads; **uncovered** for elapsed and percentage lags and for lags across two calendars
  (every corpus link has both ends on the same working time, so the corpus confirms
  only that lags are working time, not the choice of calendar; Microsoft's sentence is
  the source for that choice).
- F3. Constraints are honoured over logic (Microsoft: the setting "overrides the task
  relationship links"; MS L262-321 applies them unconditionally): SNET, early start no
  earlier than the date; FNET, no earlier than date minus duration; SNLT, **no later**
  than the date; FNLT, no later than date minus duration; MSO, early start = date;
  MFO, early finish = date and early start = date minus duration. The constraint date is
  taken as it is (no snapping). `HonorConstraints` is not read: Project writes 0 in
  every XML it saves and the behaviour is the honouring one (`slack9.mpp`, where MFO
  milestones hold their dates against later predecessors with negative slack).
  Validated: SNET, MFO. Uncovered: FNET, SNLT, FNLT, MSO.
- F4. Duration: the task's `Duration` in working time on the task's effective calendar
  (MS L1198-1206); an elapsed duration (`DurationFormat` in elapsed units) is clock time
  (`getDate` L643-651). Uncovered: elapsed durations.
- F5. Progress: a started task keeps its actual start as early start, and its early
  finish is the actual finish when complete, else actual start plus **full** duration
  (MS L323-353; Microsoft: a started task's start "can't change ... automatically").
  There is no data date in the forward pass: the status date plays no part (MS never
  reads it; Microsoft's calculation options act when actuals are entered), there is no
  retained-logic / progress-override switch, and remaining work is not moved to the
  status date. An FNET constraint on a started task raises its early finish to the date
  (MS L332-338); other constraints on started tasks are not applied (MS L341-344 is a
  TODO in MPXJ; treated as uncovered). Validated on 5 files (one in-progress and two
  complete tasks each): thin, see §7.12 Q4.
- F6. ALAP: after the backward pass a second forward pass runs in which a link from an
  ALAP predecessor to a non-ALAP successor uses the predecessor's **late** dates (MS
  L106-109, L1431-1434); an ALAP task's displayed Start/Finish are its late dates (MS
  L118-119). Uncovered.
- F7. Manual tasks keep their typed dates and feed their successors as they are (MS
  L205-211). MPXJ reproduces none of the 6 files refused only for this, so the rule is
  not trusted: refused (§7.5).

**Backward pass** (MS L380-493)

- B1. Project finish = the latest early finish of any scheduled task (MS L101). A task
  with no unfinished successors has late finish = project finish (MS L400-403;
  Microsoft *Late Finish*). Finished successors are left out (MS L388). No open-ends
  option, no must-finish date, no multiple-critical-paths variant (§7.5). Validated.
- B2. What a successor allows (MS L675-904): FS, the successor's calculated late start
  (late finish minus remaining duration, B4) minus lag; FF, successor late finish minus
  lag; SF, successor late finish plus the predecessor's duration, minus lag; SS, the
  successor's late start taken as a next-work-start on the predecessor's calendar, minus
  lag, plus the predecessor's duration. Lag is removed on the successor's calendar (MS
  L980-996). Results are capped at the project finish (MS L711-714). The SS rule has
  further cases for started tasks (MS L757-786: project finish when the predecessor has
  started) that no corpus file exercises. Validated: FS, FF, SF, SS unprogressed.
- B3. Constraints and deadlines on the late side: MSO, late finish = date plus duration;
  MFO, late finish = date; SNLT, late finish no later than date plus duration; FNLT, no
  later than the date; a **deadline** caps the late finish (MS L416-459; Microsoft
  *Start Slack*: with an actual start and a deadline "the finish slack is the difference
  between the task's finish date and deadline date"). SNET/FNET do not touch late
  dates. A late finish that lands on a period's start is moved back to the previous
  period's end when no working time lies between (MS L462, L1364-1372). A zero-duration
  milestone with an actual start has late finish = actual start (MS L406-409).
  Validated: MFO. Uncovered: MSO, SNLT, FNLT, deadlines.
- B4. Late start = late finish minus the **remaining** duration (MS L487). A finished
  task has late finish = actual finish and late start = actual start (MS L464-467,
  L490); a started task shows late start = actual start but its calculated late start
  is what FS predecessors read (MS L487-491, L847). Validated on the 5 progressed files.

**Slack** (SC; measured as working time on the task's effective calendar, in the
task's duration units, which the file stores in tenths of a minute)

- S1. Start slack = late start minus early start; finish slack = late finish minus
  early finish (SC L43-89; Microsoft *Start Slack*). Validated.
- S2. Total slack = the smaller of the two (Microsoft *Total Slack*; SC L189-196:
  `TotalSlackCalculationType` is always "smallest" for Project files,
  `ProjectProperties` L3968); for a started task it is the finish slack (SC L154-157;
  Microsoft *Start Slack* remark); an ALAP task has 0 (SC L51-54). Validated (started:
  5 files; ALAP: uncovered).
- S3. Free slack: 0 for a finished task; else the smallest, over unfinished successors,
  of the working time from the predecessor's date to the successor's date (FS finish to
  start, SS start to start, FF finish to finish, SF start to finish), measured on the
  **predecessor's** calendar, minus the lag; with no unfinished successor it equals the
  total slack; a negative value is 0 (SC L92-133, L224-312; Microsoft *Free Slack*).
  **Corpus addendum:** Project also caps free slack at total slack: in `slack9.mpp` two
  tasks whose only successor allows one day of movement have total slack 0 and free
  slack 0, where MPXJ (no cap) gives 1 day. One file, two tasks; consistent with
  Microsoft's "the smaller of the start slack and finish slack amounts determines the
  amount of free slack available". Adopted (§7.12 Q7).
- S4. Critical = not finished, total slack ≤ `CriticalSlackLimit`, not 100% complete,
  auto-scheduled (`Task.calculateCritical` L6820-6839). XERlock keeps showing the
  **stored** `Critical` flag; the engine's flag is compared as part of the self-check
  only if that proves useful.

**Resource-driven tasks** (MS L1264-1334, `ResourceAssignment.getEffectiveCalendar`
L686-716): a task with a work-resource assignment (units > 0) is scheduled by work on
the assignment's calendar: the resource calendar, the task calendar when the task
ignores resource calendars, or their intersection when both apply (Microsoft *Task
Calendar*); fixed-duration tasks keep the task calendar. The stored `Duration` already
embodies work and units, so a duration-based pass on the task's calendar reproduces the
task whenever the assignment calendar defines the same working time as the task's and
the assignment has not been delayed or contoured off the task's dates. That is the
narrow refusal of §7.5; MPXJ reproduces 0 of the 7 files it alone refuses, and all 7
extra files the narrow rule admits over the strict one except `bug1.mpp` (Q6).

### 7.5 Refusals

A refused file reports `supported: false` with the reason below (counts filled in);
nothing is approximated. Detection is from the MSPDI elements named.

| Refusal | User-facing reason | Elements | Corpus |
|---|---|---|---|
| Scheduled from finish | "the project is scheduled from its finish date; only start-date scheduling is modelled" | `ScheduleFromStart` 0 | 6 files, none with logic (MPXJ: unsupported) |
| Manual tasks | "N manually scheduled tasks are incomplete: their dates are typed, not computed, so the schedule cannot be recalculated" | `Manual` 1 and no `ActualFinish` | 107 files; MPXJ reproduces 0 of 6 with logic |
| Levelling delay | "N tasks or assignments carry a levelling delay: resource levelling is not reproducible" | `LevelingDelay` > 0 (task or assignment) | 30 tasks, 6 files |
| Split tasks | "N in-progress tasks are split: their remaining work resumes after a gap" | `Resume` after `Stop` with working time between, on an incomplete task | 1 file with logic (MPXJ: unsupported) |
| Recurring tasks | "N recurring tasks: Project generates and constrains their occurrences itself" | `Recurring` 1 | 17 files (MPXJ: unsupported, though it reproduces 3 of 3) |
| Inserted or external projects | "N tasks belong to inserted or external projects: their dates come from another file" | `IsSubproject`, `ExternalTask`, `ExternalProject`, `CrossProject` links | 6 files |
| Summary-task constraints | "N summary tasks carry a constraint" | summary with `ConstraintType` ≠ 0 | none (MPXJ: unsupported) |
| Summary-task logic | "N relationships are on summary tasks" — **unless Q2 adopts rule P3** | `PredecessorLink` with a summary at either end | confidential file |
| Multiple critical paths | "the project calculates multiple critical paths, a rule the oracle has not validated" | `MultipleCriticalPaths` 1 | 6 files, none with logic |
| Resource-driven tasks (narrow rule) | "N tasks are scheduled by resource assignments on other working time than the task's, or with delayed or contoured assignments" | an assignment with a work resource (`Resources/Resource/Type` 1), `Units` > 0, whose calendar (resource `CalendarUID`, or the task's when `IgnoreResourceCalendar`) does not define the task calendar's working time (same base, no own exceptions, work weeks or weekday overrides), or with `LevelingDelay` > 0, or whose `Start`/`Finish` differ from the task's | 645 tasks; 12 files with logic |
| Logic loop | "logic loop through N tasks" | — | none |

Not refusals: `HonorConstraints` (uninformative, F3); the absence of a `StatusDate`
(Project's passes do not use it; the DCMA checks that need it stay "not checkable");
inactive tasks (ignored, as Project ignores them); summary tasks (rolled up).

**Uncovered features** (rule known, no corpus example: deadlines; ALAP; SNLT, FNLT,
FNET, MSO; elapsed durations; elapsed or percentage lags; lags or links across two
calendars; constraints on started tasks): the recalculation runs and is compared, the
report lists them under a new optional field `uncovered: [...]`, and the **Critical
Path Test is withheld** with the reason "the file uses features whose scheduling rules
the oracle corpus has not validated: …". The reviewer sees exactly which rule the file
rests on. When an oracle file for a feature arrives (§7.12 Q4) and reproduces, the
feature leaves the list. (§7.12 Q3 confirms this policy.)

### 7.6 Oracle comparison

Per scheduled task, the engine's values against the file's: `Start` and `Finish`
(Project's scheduled dates; `EarlyStart`/`EarlyFinish` equal them on every corpus task,
and for an ALAP task they are the late dates, rule F6), `LateStart`, `LateFinish`,
`TotalSlack`, `FreeSlack`. Completed tasks are compared too (actual dates, slack 0).
Summary tasks are not (not activities). Manual tasks never reach the comparison
(refused).

- Dates: exact to the minute, as for P6. MSPDI writes seconds; `.mpp` dates are
  minutes. (MPXJ's comparator allows 0.29 working minutes for its own arithmetic; the
  engine is held to the minute, and a sub-minute drift is a bug in `worktime.py`.)
- Slack: stored in tenths of a minute (`TotalSlack` 4800 = 8 h), compared in hours of
  working time on the task's calendar to 0.01 h, the existing `cpm.differences`
  tolerance (the resolution of the stored value is 0.0017 h, so this is one decimal of
  a minute, not a hidden rounding). Project computes slack in the task's duration units
  on its calendar; whether it writes those units out via `MinutesPerDay` rather than
  via the task calendar's hours is exactly what the 5 task-calendar cases in scope will
  tell; a systematic difference there is a finding to document, not to absorb.
- A `.mpp` conversion omits zero slack (METHODOLOGY): absent means 0 after a
  conversion, unknown in Project's own XML (an unknown stored value is not compared and
  is counted as such).
- Report shape: the same dict as `recalc.run` (supported, reason, options, compared,
  excluded, differing, by_field, differences, truncated), so the frontend and saved
  snapshots need no new field for the comparison; `options` carries Project's settings
  (`schedule_from`, `lag_calendar: "successor"`, `critical_slack_limit_days`,
  `multiple_critical_paths`, `delay_days`) and the new optional `uncovered` list.

### 7.7 Acceptance criteria

1. **Refactor first.** The engine-agnostic parts of `cpm.py` (§7.9) are extracted in a
   commit of its own; `.venv/bin/pytest` is green and `scripts/cpm_oracle.py` on the 12
   P6 files reports the same per-file counts before and after (0 differences, same CPT
   results). The sample `.xer` result is byte-identical.
2. **Reproduction.** On every in-scope corpus file (33 under the narrow rule) the
   engine reports 0 differences on dates and slack, with two files that may carry a
   documented exception: `slack9.mpp` must match (rule S3's cap is required), and
   `bug1.mpp` must either match or be explained in METHODOLOGY as Project-stored values
   no rule produces (Q6). The confidential file reports 0 differences if P3 is adopted.
   Every other corpus file is refused with the stated reason, never approximated, and
   nothing crashes (`scripts/msp_corpus.py` exit 0).
3. **Self-check.** Every Project parse reports the recalculation the way a P6 parse does
   (count of differing tasks, field and delta each); the Health Check item reads
   "Recalculation matches Project" with the file's own tool named (`source_format`).
4. **Critical Path Test** on Project files, with the same method as `SPEC.md` §1, criterion 4
   (first incomplete Longest Path task with duration, 600 working days, finish must move
   by the delay on the delayed task's calendar, absorbing task named on failure),
   offered only when criterion 3 reports 0 differences and the file has no uncovered
   feature. It passes on `examples/sample-schedule.xml`.
5. **Refusals and uncovered features** appear with their reasons (§7.5) in the API and
   the Health Check.
6. **Docs.** METHODOLOGY gains "Recalculation of Microsoft Project files" (every rule
   above with its source, the refusals, the coverage table and what the oracle cannot
   prove), the "Not done" list and the Project table lose "not yet available"; README
   and CHANGELOG 1.3.0; frontend and backend version 1.3.0. Claims are made only once
   criteria 1-5 hold.

### 7.8 Commands

```bash
.venv/bin/pytest                                   # includes tests/test_cpm_msp.py (no Java needed)
.venv/bin/pytest tests/test_cpm*.py tests/test_mspdi.py
scripts/fetch_msp_corpus.sh                        # MPXJ test data -> .corpus/mpxj (gitignored)
.venv/bin/python scripts/msp_oracle_coverage.py .corpus/mpxj --mpxj-scheduler \
    --confidential /path/to/file.mpp               # stage 1: coverage; aggregates only
.venv/bin/python scripts/msp_corpus.py .corpus/mpxj   # stage 2: gains per-file recalculation
                                                   # match/refusal counts (no new script)
.venv/bin/python scripts/cpm_oracle.py /path/to/p6/*.xer   # P6 unchanged, before and after the refactor
cd frontend && npm run test:run && npm run build && npm run build:standalone
```

### 7.9 Design

**A separate engine module, `backend/cpm_msp.py`, sharing the data model, the
comparison and the Critical Path Test with `cpm.py`.** The starting preference was one
engine with a per-format rule set; the rules argue against it. Of the rule sites in
`cpm.py`'s two passes and float, Project differs at twelve: the floor (data date vs
project start and actual start, F1/F5), started and completed work (data date vs actual
dates and full duration, F5/B4), what FF and SF links allow (successor duration
arithmetic, F2), the lag calendar and lag kinds (F2), constraints in the forward pass
(SNLT/FNLT cap early dates, F3), milestone placement (F1), the late-finish snap and
the late start from remaining duration (B3/B4), constraints and deadlines on the late
side (B3), ALAP (a second forward pass vs P6's free-float delay, F6), total slack
(fixed "smallest", started → finish slack, S2), free slack (predecessor calendar, lag
removed, capped, no successor → total slack, S3) and summary-logic expansion (P3);
and it has none of P6's progress modes, float types, open-ends option, must-finish
date, expected finish, LOE or external dates. A shared `_Engine` would branch on the
format in nearly every method: two engines interleaved in one class, which fails
cohesion and makes the P6 rules harder to read, for the sake of sharing a few dozen
lines of pass skeleton. Separation also keeps the "byte-identical P6" guarantee
trivially true.

What is genuinely shared and is extracted first (the refactor commit): the `Dates`,
`Link` and `LogicLoop` types, `_clean`, `differences` (already format-free), the
topological order, and `critical_path_test`, which becomes engine-agnostic by taking
the engine's `schedule` callable and its "remaining duration of" and "with remaining
duration" hooks instead of calling `cpm.schedule` and `_Engine.remaining_of` directly.
Whether these live on in `cpm.py` (imported by `cpm_msp.py`) or move to a small
`backend/cpm_core.py` is decided by the diff: the smallest change that leaves `cpm.py`
a pure P6 module wins. `cpm_msp.py` defines its own `Task` and `Options` (the fields
differ: full and remaining duration, elapsed flag, deadline, milestone, Project's eight
constraint types, project start; no data date or progress mode).

```
backend/cpm_msp.py       NEW: the Project engine (§7.4), pure functions over plain data,
                         stdlib only; runs in the browser build too. Input: tasks, links
                         (summary logic already expanded), calendars, options. Output:
                         {uid: Dates} as cpm.py returns.
backend/recalc_msp.py    NEW: the only module that knows both the MSPDI elements and the
                         engine's types (as recalc.py is for .xer): engine input from the
                         reader's intermediate, refusal detection (§7.5), stored values
                         (§7.6), the report, the CPT call. Reuses recalc's report shape
                         and constants (CPT_DELAY_DAYS, MAX_DIFFERENCES_LISTED).
backend/mspdi.py         reads what the engine needs and the reader does not keep yet:
                         project StartDate; per task DurationFormat (elapsed), Resume/
                         Stop, LevelingDelay, Recurring, IgnoreResourceCalendar, the raw
                         ConstraintType; per assignment Units, LevelingDelay, Start/
                         Finish, the resource's Type and CalendarUID. `recalculate` calls
                         recalc_msp.run instead of returning unsupported.
backend/cpm.py           refactor only: the shared pieces above; P6 behaviour unchanged.
scripts/msp_corpus.py    adds per-file recalculation columns (compared / differing /
                         refused: reason), aggregates only.
tests/test_cpm_msp.py    NEW: one rule per test on minimal networks (§7.10).
tests/test_mspdi.py      the new elements; sample XML reproduces and passes the CPT.
frontend                 HealthCheck: tool name from source_format in the recalculation
                         card and the "Recalculation matches Project" item; Project's
                         options block; uncovered-feature notice; CPT card unchanged.
                         prepare-standalone ships cpm_msp.py and recalc_msp.py.
docs/METHODOLOGY.md      the rules, refusals, coverage and limits (criterion 6).
```

**Units.** Hours as floats and `datetime` instants, every duration on a named
`WorkCalendar`, as in `cpm.py`; elapsed durations and lags use `ALL_HOURS`. A
percentage lag is resolved to hours by the reader (it already does) and carried as a
working-time lag plus the `lag_pct` marker for the uncovered list.

### 7.10 Testing plan

Test-driven, one rule per test, the smallest network that shows it, hand-calculated on
the 8-hour five-day calendar `test_cpm.py` uses. Required cases, each named after the
rule it proves:

- P1-P3: inactive task ignored with its links; summary rolled up and not compared;
  summary logic expanded (SS/SF to the earliest leaf, FS/FF to all leaves; successor
  summary to all leaves); loop refused.
- F1: start at project start; project start in non-working time; SNET and FNET on a
  task without predecessors; milestone kept at Friday 17:00 after an FS link; a task
  pushed to Monday 08:00.
- F2: FS, SS, FF, SF with zero, positive and negative lag; FF uses the successor's
  remaining duration and never starts before the project start; SF subtracts the full
  duration; lag counted on the successor's calendar when the two differ; elapsed lag
  on the clock; percentage lag.
- F3: each of the seven dated constraints as the forward pass applies it, including
  SNLT and FNLT pulling a task earlier than its logic (negative slack), MFO holding a
  milestone (`slack9` shape).
- F4: elapsed duration.
- F5: started task anchored at its actual start with full duration; completed task;
  FNET on a started task; no status-date effect.
- F6: ALAP task takes late dates and feeds its successor from them; slack 0.
- B1-B4: late finish from the project finish; finished successor ignored; FS reads the
  calculated late start of a started successor; SS, FF, SF backward arithmetic; MSO,
  MFO, SNLT, FNLT and deadline on late dates; late finish snapped back from a period
  start; late start from remaining duration; completed task's late dates.
- S1-S3: start, finish and total slack; started → finish slack; free slack on the
  predecessor's calendar minus lag; no successor → total slack; negative → 0; capped
  at total slack.
- Refusals: one test per row of §7.5, asserting the reason text; uncovered features
  listed and the CPT withheld.
- CPT: passes on a clean chain; fails when a constraint or deadline absorbs the delay
  and names the task.
- Sample: `examples/sample-schedule.xml` reproduces exactly and passes the CPT;
  `.xer` sample results byte-identical through the refactor.

Oracle runs (not CI): `scripts/msp_corpus.py` on the corpus (criterion 2) and on the
confidential file (aggregates only), `scripts/cpm_oracle.py` on the P6 files before and
after the refactor commit.

### 7.11 Boundaries

**Always**
- Project's stored values are the reference; a mismatch is a bug or a finding. Minute
  on dates, 0.01 h on slack.
- Refactor before behaviour, in separate commits (AGENTS.md); P6 output byte-identical,
  proved on the sample and the 12 P6 files.
- Every rule cites its source in METHODOLOGY in the same commit.
- Aggregates only from the confidential file; nothing from any `/XD/JLL` file is
  committed, quoted or printed.
- Read-only: recalculation in memory; the upload is never modified or stored.

**Ask first**
- The open questions of §7.12, before stage 2 starts.
- Any new dependency, any change to an existing contract field's meaning, any new
  required field. New fields are optional.
- Running MPXJ's scheduler in the product (not proposed).

**Never**
- Approximate silently; present a recalculation or CPT on a refused file or on one
  with differences; present the CPT on a file with uncovered features.
- Copy MPXJ code (LGPL) into XERlock; rules only, cited.
- Push, PR, deploy or release: the supervisor does that.

### 7.12 Open questions for the supervisor (with recommendations)

1. **Resource rule: narrow or strict?** Narrow (recommended): refuse only assignments on
   other working time, delayed or contoured. It admits 7 more corpus files, 62 more
   tasks and the only progressed in-scope files, and MPXJ's results back the boundary
   (0 of 7 reproduced on the far side of it, all reproduced on the near side except
   `bug1.mpp`, Q6). Strict would refuse most real files, where every task has a
   resource.
2. **Summary-task logic (P3): model or refuse?** Model (recommended), on the condition
   that the confidential file then reproduces with 0 differences; it is the only
   real-world oracle we hold and the rule is MPXJ's, which reproduces that file. If it
   does not reproduce, refuse and say so.
3. **Uncovered-feature policy:** run the comparison, list the features, withhold the CPT
   (recommended), rather than refusing files for deadlines or an ALAP task, which real
   files use. The comparison itself validates the rule on that file; only the CPT
   extrapolates.
4. **Progressed files:** accept on the current evidence (5 files, F5/B4 are simple and
   Microsoft-documented) or refuse until better oracle files exist? Recommended: accept,
   and ask whether you can produce oracle files in Project itself (e.g. a copy of the
   confidential file with progress entered and recalculated, saved as `.mpp` and XML;
   likewise a copy with a deadline, an ALAP task, an SNLT constraint, a second
   calendar on a lagged link). Ten minutes in Project would validate every uncovered
   rule at once; those files stay under `/XD/JLL` and are reported as aggregates.
5. **MPXJ's scheduler:** keep it as a measurement tool and second reference only
   (recommended), not as a runtime engine (no Java in the standalone build; two engines
   in the product; LGPL code must not be copied).
6. **`bug1.mpp`:** a Project 2003 file where two tasks' late dates (and total slack 12 d
   vs 9 d) do not follow the rules and MPXJ also misses them. Recommended: investigate
   in stage 2 for an hour; if no rule explains it, document it as stored values Project
   did not recalculate and let the engine report the differences, which is the product's
   intended behaviour, and exclude it from criterion 2 by name with that note.
7. **Free slack capped at total slack (S3 addendum):** adopt on the strength of one file
   plus Microsoft's sentence (recommended), or leave uncapped like MPXJ and accept a
   known 2-task difference on `slack9.mpp`?
8. **Recurring tasks:** refuse (recommended, MPXJ's author says unsupported) although
   MPXJ reproduces the 3 files refused only for that; revisit when a real file turns up.
9. **Health Check score:** treat a Project recalculation mismatch the way the P6 one is
   treated today (same item, same weight), so the two formats read alike.
