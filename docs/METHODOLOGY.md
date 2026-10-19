# Methodology

How XERlock computes every figure it shows, which standard each one follows, and where it
departs from that standard. Written for a reviewer who has to defend a finding: each
definition names the `.xer` fields it reads, so it can be re-checked by hand in the
**Raw tables** view against the file as exported. Microsoft Project files are mapped into
the same vocabulary; the section *Microsoft Project files* names the MSPDI element behind
each field and the checks that do not apply.

## The principle: read P6's results, recompute to cross-check

Every figure XERlock shows is **P6's own computed value**, read from the `TASK` table
exactly as exported: early/late dates, total float, free float, remaining durations. The
uploaded file is never modified or re-saved.

It does recompute, in memory and independently, so that P6's values can be checked:

| Recomputed | Checked against | Disagreement means |
|---|---|---|
| Driving relationships | (P6 does not export per-link driving flags) | — |
| Longest Path | `TASK.driving_path_flag` | the schedule was edited and not recalculated, or a defect in XERlock |
| CPLI | — (P6 does not compute it) | — |
| The whole schedule: early and late dates, total and free float (see *Recalculation*) | `TASK` early/late/remaining dates and float | the submission was edited and not rescheduled, a scheduling feature the engine does not model, or a defect in XERlock |

On the 12 real contractor submissions used in development (not published), the
recomputed Longest Path matched P6's flag on every activity, and the recalculation
reproduced every stored date and float: 0 differences on each file.

## Standards referenced

| Short name | Document |
|---|---|
| DCMA 14 | DCMA 14-Point Schedule Assessment, as published in the DCMA EVMS Program Analysis Pamphlet (DCMA-EA PAM 200.1, 2012) |
| GAO | GAO Schedule Assessment Guide: Best Practices for Project Schedules (GAO-16-89G) |
| AACE 49R-06 | AACE International Recommended Practice 49R-06, *Identifying the Critical Path* |
| AACE 29R-03 | AACE International Recommended Practice 29R-03, *Forensic Schedule Analysis* |
| AACE 78R-13 | AACE International Recommended Practice 78R-13, *Original Baseline Schedule Review* |
| PMI | PMI *Practice Standard for Scheduling*, 3rd edition |

## Units and dates

- **Data date** is `PROJECT.last_recalc_date` — P6's status date for the last schedule run.
- **Durations, float and lags** are stored in hours. Shown in days, they are divided by the
  activity's own calendar hours per day (`CALENDAR.day_hr_cnt`), as P6 displays them. A
  lag is shown in the successor's calendar days.
- **Displayed start/finish** is the actual date once one exists, else the early date. P6
  resets the early dates of completed work to the data date, so early dates alone would
  collapse finished work onto the data date.
- **Working time.** Every comparison of two dates that stands for a duration, lag or float
  is measured in working hours on a P6 calendar (`backend/worktime.py`), never in clock
  time. Calendars are decoded from `CALENDAR.clndr_data`: weekly work periods plus dated
  exceptions (holidays, and worked days that would otherwise be non-working).

## Critical activities

**Critical** follows the project's own definition in `PROJECT.critical_path_type`
(AACE 49R-06 discusses both):

- `CT_TotFloat`: total float ≤ `PROJECT.critical_drtn_hr_cnt` (P6's default threshold is
  0; a contract may set it higher). Negative float is critical and is also flagged
  separately.
- `CT_DrivPath`: on P6's Longest Path (`driving_path_flag`). If the file carries no flags,
  the recomputed Longest Path is used.

## Driving relationships and the Longest Path

A relationship **drives** its successor when its *relationship free float* is zero: the
successor sits exactly where the link, plus its lag, puts it.

```
implied = predecessor date (EF for FS/FF, ES for SS/SF) + lag, added on the lag calendar
free float = working hours from implied to the successor date (ES for FS/SS, EF for FF/SF),
             measured on the successor's calendar
driving    = |free float| ≤ 1 minute
```

- The **lag calendar** is the one named in `SCHEDOPTIONS.sched_calendar_on_relationship_lag`
  (predecessor, successor, 24-hour or project default). Without the table, P6's default
  (predecessor) is assumed.
- The gap is measured on the **successor's** calendar because P6 places the successor at
  the first working moment on its own calendar after the link allows. A Friday 16:00 →
  Monday 08:00 FS link on a 5-day calendar therefore has zero free float.
- An activity can have **no** driving predecessor. That happens when it is held by a
  constraint, by the data date, or by out-of-sequence progress.
- Two links can both drive (concurrent drivers). Both are marked.

Each link's free float is shown in the activity panel, so any driving flag can be checked
by hand.

**Longest Path** (P6's definition, AACE 49R-06's preferred basis): start from the activity
with no successors that has the latest early finish (all of them, if several tie), and
walk backward through driving links only. The chain ends where nothing drives.

## Percent complete

- **Per activity**, on the basis the activity declares in `TASK.complete_pct_type`, as P6
  computes it:
  - `CP_Phys`: `phys_complete_pct`.
  - `CP_Drtn`: (original − remaining) / original duration, clamped to 0–100. 100 when
    complete.
  - `CP_Units`: actual / (actual + remaining) units summed over the activity's `TASKRSRC`
    rows. Falls back to the physical figure when the file has no resource quantities.
- **Project "Activities done"**: the share of activities with status Complete. A count,
  not weighted by duration, cost or units. It is labelled as a count for that reason.

## Health check

Every rule lives in `frontend/src/utils/healthChecks.ts`, with unit tests beside it.

**Population.** DCMA's percentage metrics are taken over incomplete activities,
excluding level-of-effort (`TT_LOE`) and WBS-summary (`TT_WBS`) activities, which carry
no logic of their own. Milestones are included. Relationship metrics count the links into
incomplete activities.

Targets and weights are editable because contracts set their own. The defaults are
DCMA's. The overall **score** is the weighted share of included checks that pass. That
roll-up is XERlock's: DCMA defines a pass/fail per metric, not a composite score.

| Source | Check | Finding | Measured as | Default target |
|---|---|---|---|---|
| DCMA 01 | Logic | No FS/SS predecessor (start not tied) or no FS/FF successor (finish not tied). Exempt: the earliest start milestone without predecessors, the latest finish milestone without successors | % of population | ≤ 5% |
| DCMA 02 | Leads | Negative lag | count | 0 |
| DCMA 03 | Lags | Positive lag above the threshold (default 0 days, i.e. any lag) | % of relationships | ≤ 5% |
| DCMA 04 | Relationship types | FS share | % of relationships | ≥ 90% |
| DCMA 05 | Hard constraints | Mandatory Start/Finish, Start/Finish On, Start/Finish On or Before (P6's names for DCMA's "no later than"), as primary or secondary constraint | % of population | ≤ 5% |
| DCMA 06 | High float | Total float > 44 working days | % of population | ≤ 5% |
| DCMA 07 | Negative float | Total float < 0 | count | 0 |
| DCMA 08 | High duration | Task or resource-dependent activity with original duration > 44 working days | % of population | ≤ 5% |
| DCMA 09 | Invalid dates | Actual after the data date, or forecast (early) date before it | count | 0 |
| DCMA 10 | Resources | Incomplete task without a resource assignment. Runs only if the file has resources | % of population | ≤ 5% |
| DCMA 11 | Missed tasks | Planned finish on or before the data date, and not finished or finished late | % of those planned to finish | ≤ 5% |
| DCMA 12 | Critical Path Test | The project finish fails to move by the test delay added to the first Longest Path activity (see *Critical Path Test*). Runs only when the recalculation reproduces P6 | count (0 pass, 1 fail) | 0 |
| DCMA 13 | CPLI | (CPL + TF) / CPL | ratio | ≥ 0.95 |
| XERlock | Out-of-sequence | Successor started before an FS predecessor finished, started before an SS predecessor started, or finished before an FF predecessor finished | count | 0 |
| XERlock | ALAP constraints | As Late As Possible, primary or secondary | count | 0 |
| XERlock | LOE on critical | Level of effort that is critical or on the Longest Path | count | 0 |
| XERlock | Driving path cross-check | P6's stored Longest Path flag ≠ recomputed Longest Path | count | 0 |
| XERlock | Recalculation matches P6 | Activities whose recalculated dates or float differ from the stored values. Not checkable when the engine refuses the file | count | 0 |

Deviations from DCMA, stated so they can be weighed:

- **DCMA 01** counts only missing predecessors or successors. XERlock also counts dangling
  ends (a start tied only by FF/SF links, a finish tied only by SS/SF), following GAO's
  guidance on dangling logic. The Open Ends list labels which case each one is.
- **DCMA 11 and 14** measure against the baseline. A single `.xer` carries none, so Missed
  Tasks uses P6's Planned Finish (`target_end_date`). P6 moves planned dates with the
  forecast on work that has not started. Read the result as a check against the current
  plan, not a baseline execution index. **BEI (DCMA 14)** is not computed.
- **DCMA 12 (Critical Path Test)** is withheld on any file the recalculation does not
  reproduce exactly, and on files the engine refuses. A result on a schedule the engine
  cannot be shown to model would not be defensible.

**CPLI.** CPL is the working time on the finish activity's calendar from the data date
to the early finish of the Longest Path's last activity. TF is that activity's total
float. If the project has no finish deadline, TF is 0 and CPLI is 1.00 by construction.
CPLI says something only where a deadline exists.

**Scheduling options.** These are shown above the results, because every computed date
depends on them (AACE 78R-13; GAO best practice 9). XERlock flags two settings that
deserve a second look:
- *Progress Override*, which lets out-of-sequence work ignore its predecessors. *Retained
  Logic* is the conservative setting.
- *Use Expected Finish dates*, which lets a typed-in date set the remaining duration in
  place of the estimate.

## Recalculation

`backend/cpm.py` is a CPM engine that reschedules the project from the file's own logic,
remaining durations, calendars, constraints, progress and scheduling options, the way P6
does. `backend/recalc.py` feeds it the raw tables and compares the result with what P6
stored. **P6 is the oracle**: a rule is in the engine because real exports show P6
behaving that way, and the comparison is reported, never smoothed over. Tolerances are one
minute on dates and 0.01 h on float, as the driving rule uses.

**What is compared.** For every activity that is not complete and not a WBS summary: the
remaining early dates (`restart_date`, `reend_date`; the early dates where a file does
not write those), the remaining late dates (`rem_late_start_date`, `rem_late_end_date`;
else the late dates), `total_float_hr_cnt` and `free_float_hr_cnt`. Completed work has no
remaining dates or float in P6, so it is excluded and the count of exclusions is shown.

**Inputs.** `TASK` (type, status, calendar, remaining duration, actual dates, primary and
secondary constraint, expected finish), `TASKPRED` (type, lag), `CALENDAR` (decoded as in
*Units and dates*), `PROJECT.last_recalc_date` (data date) and `plan_end_date` (must
finish by), and `SCHEDOPTIONS`: progress mode (`sched_retained_logic` /
`sched_progress_override`; neither set is *Actual Dates*), `sched_float_type`,
`sched_calendar_on_relationship_lag`, `sched_open_critical_flag`,
`sched_use_expect_end_flag`, `sched_lag_early_start_flag`. Without the table, P6's
defaults apply: Retained Logic, finish float, predecessor calendar for lags.

**Working time and snapping.** Every duration, lag and float is working time on a named
calendar. A date logic puts in non-working time is moved the way P6 moves it:

- An early *start* goes forward to the next working start; a period's end (Friday 16:00)
  is not a start, so it becomes Monday 08:00. An early *finish* may sit on a period's end,
  and when it falls in non-working time it also moves forward, to the next working start
  (a finish milestone driven from Saturday lands Monday 08:00, not Friday 16:00). A finish
  at a period's start (Monday 08:00) is kept as it is.
- A late *finish* goes back to the previous working end: Monday 08:00 becomes Friday
  16:00. A late *start* imposed by a successor is kept wherever it falls inside a period,
  its end included (a 16:00 start imposed from a calendar whose day ends later). A late
  start set by a constraint date is read like an early start.
- A link's lag is added (forward) or taken off (backward) on the lag calendar named in the
  options. In the backward pass, a lagged result is then read as a date of the
  successor's kind on the successor's calendar; a lag-free link passes the date through.

**Forward pass** (activities in dependency order; a loop is reported and nothing is
computed):

- Remaining work starts no earlier than the data date. FS and SS predecessors bound the
  start, FF and SF the finish; the latest bound wins. Early finish = early start plus
  remaining duration on the activity's calendar. When an FF/SF link or a finish-side
  constraint pushes the finish later than that, the start moves with it (P6 keeps the
  duration; it never stretches an activity).
- *Start milestones* (`TT_Mile`, `TT_StartMile`) have a start only; *finish milestones*
  (`TT_FinMile`) a finish only, which every incoming link bounds: an FS link from a task
  finishing Friday 16:00 puts a finish milestone at Friday 16:00 and a start milestone at
  Monday 08:00. A task with zero remaining duration is placed like a task (its start
  snaps forward).
- *Constraints.* Start On or After, Start On, Mandatory Start bound the early start;
  Finish On or After, Finish On, Mandatory Finish bound the early finish. Mandatory dates
  then override whatever logic gave, in both passes. As Late As Possible is applied after
  the backward pass: the early dates are delayed by the activity's free float, so it
  finishes exactly where its nearest successor needs it (P6 uses free float, not total
  float, for ALAP). Primary and secondary constraints both apply.
- *Progress.* Under **Retained Logic**, the remaining work of a started activity waits
  for its unfinished predecessors. Under **Progress Override** a started activity ignores
  its predecessors and its remaining work starts at the data date. Under **Actual Dates**
  the engine behaves as Retained Logic except that an actual start later than the data
  date is honoured as the start of the remaining work (this mode is not represented in
  the development corpus and is unverified against P6).
- *Completed work* is still placed: at the data date itself (not moved into working
  time), or later when Retained Logic holds it behind an unfinished predecessor. That
  held date is what its successors see, which is how P6 keeps out-of-sequence completion
  from releasing successors early. The lag of a link from completed work counts from the
  activity's actual finish (or start); a lag already spent before the data date holds
  nothing. SS lags from started work count from the early start, which P6 holds at the
  data date, unless `sched_lag_early_start_flag` says to count from the actual start.
- *Expected finish* (`expect_end_date`, when `sched_use_expect_end_flag` is on) replaces
  the early finish when it is later than the early start (unverified on real files).
- *Level of effort* never drives. It starts with the earliest link from its predecessors
  and finishes with the latest link date from its predecessors' finishes or its
  successors' dates. WBS summaries are not placed (their dates come from their children,
  which the engine does not model) and are excluded from the comparison.

**Backward pass** (reverse order):

- The project finish is the latest early finish of any activity, or the must-finish-by
  date when the project has one. An activity with no successor, or only SS/SF ones, gets
  its late finish from there ("open finish"); with "make open-ended activities critical"
  it gets its own early finish instead.
- FS and FF successors bound the late finish, SS and SF the late start; the earliest
  bound wins. Late start = late finish less the remaining duration; when a start-side
  bound pulls the late start earlier, the late finish moves with it. Finish On or Before,
  Finish On and Mandatory Finish bound the late finish; Start On or Before, Start On and
  Mandatory Start the late start.
- A start milestone's late dates are a start: an FS successor's late start of Monday 08:00
  gives Monday 08:00, and an open-ended start milestone sits on the project finish as it
  is. A finish milestone's late dates are a finish, so an SS successor's Monday 08:00 gives
  Friday 16:00. A task with zero remaining duration is read as a finish here.
- Completed work carries late dates for its predecessors' sake: the earliest its
  successors allow, taken as it is. A lag into completed work is not taken off (it was
  spent with the work).

**Float.** Total float is late finish − early finish (`FT_FF`), late start − early start
(`FT_SF`) or the smaller, in working hours on the activity's calendar. Free float is the
least working time, on the activity's own calendar, from each successor link's implied
date to the successor's early date; never negative; for an activity without successors,
the time to the project finish. With a single project, "calculate float based on finish
date of each project" and "opened projects" are the same thing.

**Refused files.** The engine declines to model, and the Critical Path Test is withheld,
when the file has: resource-dependent activities (`TT_Rsrc`, which schedule on resource
calendars); activities with external relationship dates (`external_early_start_date`,
`external_late_end_date`); relationships to activities outside the project; a logic
loop; the multiple float path option (`enable_multiple_longest_path_calc`, or
`float_path` set on activities); or no data date. The reason is shown in place of the
check. Resource levelling leaves no flag in a `.xer`; a levelled schedule shows up as
differences, which is the right outcome: its dates are not reproducible from logic.

**Critical Path Test (DCMA 12).** Only on a file with zero differences. Take the first
incomplete activity on the Longest Path that has a duration to extend (milestones have
none) and whose *finish* carries the path onward: a driving FS or FF link to a later
Longest Path activity, or the project finish itself. Where the path leaves an activity by
its start (an SS or SF link), a longer activity is expected to move nothing, so delaying it
would report a break that is not one; the test is about the continuity of the path, and a
start-driven chain is valid logic (its untied finish is DCMA 01's business). Add the test
delay, **600 working days** on that activity's calendar (a common
DCMA practice value; the backend parameter `CPT_DELAY_DAYS` sets it); reschedule in
memory. The project finish activity is the one without successors that finishes last.
The test **passes** when its early finish moved by the full delay, measured in working
time on the delayed activity's calendar. On failure, the activity named is the first
along the path whose own finish moved less than the delay: a constraint, or a successor
tied only by an SS link, is usually found there. When the activities from the delayed one
to the finish use unlike calendars, the same span of clock time reads differently on each
(holidays, work periods), so the test allows one working week and says so; with one
calendar along the path the match must be exact. All twelve development files pass the test.

## Compare

Activities are matched by activity code (`task_code`), which stays stable across
re-exports. Internal IDs do not. All date movements are in **calendar days**.

| Section | Rule |
|---|---|
| Project finish | Latest displayed finish in each file |
| Date changes | Displayed finish moved |
| Duration changes | Original duration changed, in the current activity's calendar days |
| Actual dates changed | An actual start/finish present in the earlier file moved or disappeared. As-built history should not change between updates; AACE 29R-03 treats validating it as a precondition of any delay analysis |
| Constraint changes | Primary or secondary constraint type or date added, removed or changed |
| Float erosion | Total float decreased |
| Critical path changes | Entered or left the critical set |
| Critical path stability | Share of the earlier Longest Path still on it |
| Logic changes | Predecessor links (code, type, lag) added or removed |

Compare shows what changed. It is not a delay analysis. It allocates no responsibility and
implements none of the AACE 29R-03 methods (observational static or dynamic, modelled
additive or subtractive). It is the evidence-gathering step those methods start from.

## Progress

- **Milestones**: variance is forecast minus planned finish, in calendar days.
  Status bands: on track ≤ 0, watch 1–10, at risk > 10. The bands are XERlock's convention.
- **Look-ahead**: incomplete activities whose early dates overlap the window from the data
  date.
- **S-curve** (`frontend/src/utils/sCurve.ts`): cumulative share of the programme's total
  original duration, in working days (hours / the activity's hours per day, so calendars of
  different lengths weigh the same per day). Task and resource-dependent activities only;
  milestones carry no duration and level of effort would count the work it spans twice.
  - *Planned*: each activity's original duration spread linearly between its P6 planned
    start and finish (`target_start_date`, `target_end_date`). Not a baseline.
  - *Earned*: original less remaining duration (P6's duration % complete basis; the full
    original once complete), spread from actual start to actual finish, or to the data
    date while in progress. Plotted up to the data date.
  - *Forecast*: earned at the data date plus each activity's remaining duration spread
    over its remaining early dates. Ends above 100% when remaining estimates exceed
    original durations, which is growth worth seeing, not an error.
  - Spreading is linear in calendar time, not working time. At monthly resolution the
    difference is small, and the curve does not depend on calendar decoding.

## Microsoft Project files

XERlock reads Microsoft Project files since 1.2.0: Project XML (File > Save As > XML, the
MSPDI format) anywhere, and `.mpp` (Project 98 to current) on the server, where
[MPXJ](https://www.mpxj.org) converts the `.mpp` to MSPDI in memory and the same reader
reads the result. The file is mapped into the P6 vocabulary the rest of XERlock uses
(`backend/mspdi.py`), so every view and check works the same way; this section says what
each field and check means on a Project file and where the meaning differs. Element
names below are the MSPDI ones, as the **Raw tables** view shows them (one table per
record type: Project, Tasks, PredecessorLinks, TaskBaselines, Calendars, CalendarWeekDays,
CalendarExceptions, Resources, Assignments; nested records carry their parent's UID as
the first column; nothing is interpreted).

**The principle holds: Project's own stored values, nothing recomputed.** Each figure is
read from the file; the recomputed figures are the same ones as for P6 (driving links,
Longest Path, CPLI) and, since 1.3.0, the recalculation, which reschedules the file with
**Project's** rules and compares the result with what Project stored (section
*Recalculation of Microsoft Project files*). The mapping was verified against MPXJ's
MSPDI reader source and on MPXJ's test corpus (`scripts/fetch_msp_corpus.sh`, 609 `.mpp`
and 143 MSPDI files saved by Project 98-2019; `scripts/msp_corpus.py` reports the
aggregates).

| Field | Read from | Rule |
|---|---|---|
| Activity id (`task_code`) | Task `UID` | Project's row `ID` renumbers when rows move, so Compare matches on the unique id (shown as the code; Project's Unique ID column) |
| Name, WBS | `Name`, `OutlineLevel`, `WBS` | A task with children, flagged `Summary`, or UID 0 (the project summary) is a WBS node, not an activity; files without a UID 0 task get the project as root |
| Early dates | `Start`, `Finish` | Project's scheduled dates. `EarlyStart`/`EarlyFinish` equal them on every task in the corpus (10,669 of 10,669) |
| Late dates | `LateStart`, `LateFinish` | As stored |
| Total float, free float | `TotalSlack`, `FreeSlack` | Tenths of a minute, shown in hours and days. Absent in Project's own XML means unknown (blank); after a `.mpp` conversion absent means zero, because MPXJ's writer omits zero slack (4,946 of 4,946 absent values in the corpus twins are 0 in Project's XML) |
| Critical | `Critical` | Project's flag, as stored (Project: total slack ≤ `CriticalSlackLimit`, and not manually scheduled) |
| Duration, remaining | `Duration`, `RemainingDuration` | ISO 8601 (`PT40H0M0S`) in hours; days are `MinutesPerDay` per day for every task, as Project converts them |
| Status | `ActualStart`, `ActualFinish` | Not started / in progress / complete from which actuals exist |
| % complete | `PercentComplete` | Project's duration % complete (`CP_Drtn`) |
| Planned dates (`target_start`/`target_end`) | `Baseline` number 0 | Blank when no baseline was saved; Missed Tasks is then not checkable |
| Constraints | `ConstraintType`, `ConstraintDate` | 0 none, 1 ALAP, 2 Must Start On → **Mandatory Start**, 3 Must Finish On → **Mandatory Finish**, 4/5 Start No Earlier/Later Than → Start On or After/Before, 6/7 Finish No Earlier/Later Than → Finish On or After/Before. Must Start/Finish On map to P6's Mandatory constraints because Project holds the date against later logic and shows the conflict as negative slack (corpus file `slack9.mpp`: a Must Finish On milestone kept at its date while its predecessor finishes a day later); P6's Start/Finish On would let logic move the date. `HonorConstraints` cannot refine this: Project writes 0 and MPXJ 1 for the same project, so it is shown but not used |
| Deadline | `Deadline` | Shown on the activity; not a constraint (DCMA 05 does not count it), though it bounds the late finish and so can produce negative slack |
| Milestones | `Milestone` with zero `Duration` | A finish milestone (`TT_FinMile`): Project places a zero-duration milestone at the instant its FS predecessor finishes (Friday 17:00, not Monday 08:00), which is P6's finish-milestone convention. A task flagged milestone with a duration stays a task |
| Relationships | `PredecessorLink` `Type` 0 FF, 1 FS, 2 SF, 3 SS; `LinkLag` in tenths of a minute | Links to tasks in other project files (`CrossProject`) are left out with a warning |
| Lag kinds | `LagFormat` | Elapsed units (em, eh, ed, ew, emo, e%) count on the 24-hour clock: the driving rule uses that calendar for them. Percentage lags are `LinkLag` % of the predecessor's duration, converted to hours. Both are listed by the *Elapsed & percentage lags* check |
| Lag calendar | — | A lag counts on the successor's task calendar, else the project calendar (Microsoft's rule for lead and lag time); XERlock's `lag_calendar` is therefore *successor*. Every lagged link in the corpus has both ends on the same calendar, so the corpus confirms only that lags are working time (the 24-hour reading matched none of the 136 lagged links), not the choice of calendar |
| Calendars | `Calendars`, `WeekDays`, `Exceptions` | Day types 1-7 = Sunday-Saturday, as P6. A derived calendar inherits the days and exceptions of its `BaseCalendarUID` and overrides what it defines. Exceptions are the `Exceptions` list (Project 2007 and later) or, when the list is absent, the legacy `DayType` 0 entries; recurring exceptions (daily, weekly, monthly, yearly, absolute and relative) are expanded to dates the way MPXJ's `RecurringData` expands them. Hours per day are the project's `MinutesPerDay` |
| Task calendar | `CalendarUID` | The task's own calendar, else the project calendar (`CalendarUID` on the project) |
| Data date | `StatusDate` | Blank when the file has none (a warning says so); the checks that compare dates with it, and the CPLI, are then not checkable. `CurrentDate` is the save date, not a status date, and is not used |
| Resources | `Resources`, `Assignments` | Resource names per task; DCMA 10 runs when the file has named resources |
| Inactive tasks | `Active` 0 | Left out of every population, with their relationships; counted (Project 2010 and later) |
| Manual tasks | `Manual` 1 | Kept as activities, flagged `manual`; listed by the *Manually scheduled tasks* check |
| Critical threshold | `CriticalSlackLimit` | Days, converted with `MinutesPerDay` |
| Version | `SaveVersion`, `LastSaved` | Shown in the Raw tables header |

**Not mapped** (visible in the raw tables only): outline codes and custom fields (P6
activity codes stay empty), resource calendars' effect on task dates, timephased data,
subprojects' contents beyond what the file embeds (a warning counts them), alternate
work weeks (`WorkWeeks`: none in the corpus; the base week applies throughout), and
elapsed task durations (`DurationFormat` in elapsed units: the stored hours are shown,
divided by the project day like any other duration, so "3 edays" reads as 72 h).

**Checks on Project files.** The DCMA checks run unchanged on the mapped fields. Those
that need a P6-only concept say so instead of guessing:

| Check | On a Project file |
|---|---|
| Driving path cross-check | Not checkable: Project stores no Longest Path flag. The recomputed Longest Path stands alone |
| LOE on critical | Not applicable: Project has no level-of-effort task type |
| Recalculation, Critical Path Test (DCMA 12) | Run with Project's rules (*Recalculation of Microsoft Project files*). The test is withheld on a refused file, on any difference, and while the file rests on a rule the oracle corpus has not validated |
| Invalid dates (DCMA 09), Missed tasks (DCMA 11), CPLI (DCMA 13) | Not checkable without a `StatusDate`; Missed tasks also needs a Baseline 0 |
| Longest Path | Traced through driving links from Project's stored dates exactly as for P6. Project keeps a completed predecessor's real finish where P6 resets it to the data date, so on a progressed Project file the trace ends at the first activity held by the status date; completed work is not on it |

**Project-specific checks** (source "XERlock"), not applicable to P6 files:

| Check | Finding | Measured as | Default target |
|---|---|---|---|
| Manually scheduled tasks | Incomplete task in Manual task mode (`Manual` 1): its dates are typed, not placed by logic, so the path through it is not a calculation and its float is not a measure | count | 0 |
| Logic on summary tasks | A relationship with a summary task at either end. Project allows it; it moves every task under the summary at once, unseen in the task logic. Reported from the file; such links are not part of the network XERlock traces | count | 0 |
| Elapsed & percentage lags | A lag in elapsed units (24-hour clock) or as a percentage of the predecessor's duration, on a link into incomplete work | count | 0 |
| Inactive tasks | Tasks with `Active` 0, left out of every population. Deactivated scope deserves a look | count | 0 |

**Scheduling settings** shown above the results for a Project file: status date,
schedule from start or finish, critical slack limit, multiple critical paths, honour
constraint dates, new tasks manual, hours per day. They are the file's own values
(`msp_options`), shown so a reviewer reads them before trusting a date.

**`.mpp` files.** MPXJ reads the `.mpp` and writes it as MSPDI; the result is read like
any Project XML and marked `mpp`. On the corpus, every `.mpp` saved alongside an MSPDI
file by the same Project version was read through both paths and compared on dates,
float, flags, constraints and links; the remaining differences come from what MPXJ
reads from the binary format, not from the reader: MPXJ reads a different task mode
(`Manual`) than Project wrote in its XML on some Project 2010-2019 files, and Project's
`Critical` flag and the Start No Earlier Than constraint it keeps on manually scheduled
tasks follow from that. The corpus report lists the counts. Password-protected files are
refused with MPXJ's message.

## Recalculation of Microsoft Project files

`backend/cpm_msp.py` is a second CPM engine, with Microsoft Project's rules, on the same
format-free core as the P6 one (`backend/cpm_core.py`: result and link types, ordering,
the comparison, the Critical Path Test). `backend/recalc_msp.py` builds its input from the
MSPDI elements, decides what must be refused, runs it and compares the result with the
`Start`, `Finish`, `LateStart`, `LateFinish`, `TotalSlack` and `FreeSlack` Project stored,
task by task: dates to the minute, slack to 0.01 h of working time on the task's calendar
(the file stores tenths of a minute). Completed tasks are compared too (their actual
dates, slack 0); summary tasks roll up and are not. **Project is the oracle**: the engine
is trusted on a file only when it reproduces every stored value, and a difference is a
finding (an edit without a recalculation, or a feature the engine does not model), never
a tolerance. `SPEC-MSPROJECT.md` §7 is the design record, with the sources by file and
line.

**Sources.** The rules were taken (rules, not code) from MPXJ 16.10.0's
`org.mpxj.cpm.MicrosoftScheduler` and `MicrosoftSlackCalculator`, read at tag v16.10.0,
which MPXJ's author built by observing Project and which reproduce 31 of the 33 corpus
files in scope; from Microsoft's field pages (*Total Slack*, *Start Slack*, *Free Slack*,
*Late Finish*, *Deadline*, *Task Calendar*, the *Predecessors tab* of the Task Information
dialog, the *Tasks aren't scheduled as expected* troubleshooting page, the *OptionsSchedule*
and *OptionsCalculation* VBA references); and, for three rules MPXJ's working-time
tolerance hides, from the oracle files themselves. Each rule below says which.

**Rules.** Scheduled tasks are the active, non-summary tasks; logic on a summary task is
expanded to its leaf descendants (a summary predecessor of an SS or SF link stands for its
earliest-starting leaf, of an FS or FF link for every leaf; a summary successor for every
leaf). There is no data date: Project's passes never read the status date, and the
"move completed/remaining parts to the status date" options act when actuals are entered.

| Rule | What the engine does | Source |
|---|---|---|
| Start | A task without predecessors starts at the first working moment at or after the project `StartDate` (SNET at its date; FNET a duration before it). With predecessors, at the latest instant any link allows, moved to the next working start on the task's calendar; a milestone may sit at the end of a period (the Friday 17:00 rule) | MPXJ MS L251, L260, L1403-1412 |
| Links | FS: predecessor finish + lag. SS: predecessor start + lag (a finished predecessor: its actual start). FF: predecessor finish minus the successor's remaining duration, + lag, never before the project start. SF: the successor's **finish** is fixed at the predecessor's start + lag, exactly where that lands (a Monday 08:00 finish for a task ending where its predecessor starts), and its start is a full duration earlier | MPXJ MS L538-667; SF finish from mpp9relations.mpp and twins |
| Lag | On the successor's task calendar, else the project calendar; an elapsed lag on the clock; a percentage lag that share of the predecessor's duration | Microsoft, Predecessors tab: "If a successor uses a task calendar, lag time duration is based on that calendar; otherwise ... the project calendar"; MPXJ MS L955-996 |
| Duration | `Duration` in working time on the task's effective calendar; an elapsed duration (`DurationFormat` in elapsed units) on the clock | MPXJ MS L1198-1206, ProjectCalendar.getDate |
| Constraints (forward) | Honoured over logic: SNET and FNET hold the task back, **SNLT and FNLT pull it earlier** than its logic, MSO and MFO set the date; the constraint date is taken as it is. `HonorConstraints` is not read: Project writes 0 in every XML it saves and 1 is read from every `.mpp`, and the behaviour on the corpus is the honouring one (`slack9.mpp`) | Microsoft, "the Tasks will always honor their constraint dates setting overrides the task relationship links"; MPXJ MS L262-321 |
| Progress | A started task keeps its actual start and its **full** duration (actual finish when complete); logic does not move it and no status date does. An FNET constraint raises a started task's finish to its date | Microsoft, "If you entered a percent complete on a task, and the task has already started, you can't change the Start Date automatically"; MPXJ MS L323-353 |
| Late finish | The project finish (the latest early finish) for a task with no unfinished successor; else the earliest a successor allows: FS, the successor's calculated late start minus lag; FF, its late finish minus lag; SF, its late finish plus the predecessor's duration minus lag; SS, its late start read as a next-work-start on the predecessor's calendar minus lag, plus the predecessor's duration; capped at the project finish. MSO: date + duration; MFO: the date; SNLT and FNLT cap it; a **deadline** caps it. A late finish at a period's start becomes the previous period's end, **except for a zero-duration or elapsed task**, which keeps it where its successor's late start is | Microsoft, Late Finish and Start Slack pages; MPXJ MS L380-493; the zero-duration exception from the confidential oracle file, sf259.mpp and every zero-duration task at a project start in the corpus |
| Late start | Late finish minus the **remaining** duration. A finished task has its actual dates as late dates; a started task shows its actual start as late start, while its FS predecessors read the calculated one | MPXJ MS L464-491, L847 |
| ALAP | After the backward pass a second forward pass runs in which an ALAP predecessor feeds a non-ALAP successor from its late dates; an ALAP task shows its late dates as Start/Finish and has slack 0 | MPXJ MS L106-119, L1431-1434; SC L51-54 |
| Total slack | The smaller of start slack (late minus early start) and finish slack (late minus early finish), in working time on the task's calendar (on the clock for an elapsed duration); the finish slack once the task has started. A Must Start/Finish On task shows its constraint date but measures its slack from where logic puts it when that is later: `slack9.mpp` shows a Must Finish On milestone with all four dates on its constraint date and a total slack of -1 day, its predecessor finishing a day after the date | Microsoft, "the smaller value of the Late Finish minus the Early Finish field, and the Late Start minus the Early Start field"; Start Slack page, "If a task has an actual start date and a deadline, the start slack is 0"; MPXJ SC L135-199; the MSO/MFO reading from slack9.mpp |
| Free slack | 0 once finished; else the smallest, over the task's **own** unfinished successors, of the working time from this task's date to the successor's (FS finish to start, SS start to start, FF finish to finish, SF start to finish) on **this** task's calendar, minus the lag; the total slack when no successor is left; never negative, and **never more than the total slack** (slack9.mpp, where MPXJ's uncapped value differs from Project's). Only links written on the task count: a link inherited through its parent summary's logic schedules the task but leaves its free slack at its total slack, and a link the task itself has to a summary task is measured against the summary's rolled-up start (its earliest leaf) or finish | Microsoft, Free Slack page, "If the task has no successor tasks, free slack is the same as total slack"; Start Slack page, "The smaller of the start slack and finish slack amounts determines the amount of free slack available"; MPXJ SC L92-133; the own-link reading from Microsoft's "Project 2003 deployment" template (250 tasks, 75 summary links): 78 tasks whose only successors come through their parent summary store free slack equal to total slack, and 5 tasks linked to a summary store the gap to its earliest leaf, while every date and total slack matches |
| Levelling delay | A task's `LevelingDelay` is elapsed time added to the early start its logic gives (then the next working start); its predecessors' late finish comes from its late start less the delay. Validated only for an unstarted, unconstrained task whose predecessors are FS without lag (or none) and whose delayed start lands on a working start; any other levelled task is an uncovered rule (below). An assignment's levelling delay, in regular duration units, is refused | Microsoft, Leveling Delay fields: "the amount of time that a task or assignment is to be delayed from its early start date", "Task leveling delay is expressed in elapsed duration units, while assignment leveling delay is expressed in regular duration units"; Early Start page, "a task's leveling delay is also figured into the early start date"; Late Finish page, "If there is a leveling delay on the successor task, this delay is also figured into the date in the Late Finish field"; MPXJ MS L913-935 (elapsed conversion). Validated by one oracle file: a coursework schedule with 22 tasks, 4 in progress, a status date and one task delayed 18.7 elapsed days, which reproduces exactly; and five corpus fixtures (`*barstyle*.mpp`) with delays on tasks without predecessors |
| Critical | Shown as stored (`Critical`); Project's own rule is total slack at or below `CriticalSlackLimit`, not complete, auto-scheduled | MPXJ Task.calculateCritical L6820-6839 |

**Refused files** (reported with the reason; nothing is approximated):

| Refusal | Reason given | Why |
|---|---|---|
| Scheduled from finish (`ScheduleFromStart` 0) | the project is scheduled from its finish date; only start-date scheduling is modelled | No rule (MPXJ: unsupported); 6 corpus files, none with logic |
| Incomplete manually scheduled tasks | N manually scheduled tasks are incomplete: their dates are typed, not computed, so the schedule cannot be recalculated | MPXJ's pass-through rule reproduces 0 of the 6 corpus files refused only for this |
| Levelling delay on an assignment | N assignments carry a levelling delay in regular duration units, which the oracle has not validated | A task's delay is honoured (above); an assignment's is in working units on the assignment's calendar, with no oracle file |
| Split or contoured tasks | N tasks are split or contoured: the stored dates span more working time than the duration | Splits live in timephased data the reader does not keep; the longer span gives them away (an in-progress split also as `Resume` after `Stop` with working time between) |
| Recurring tasks | N recurring tasks: Project generates and constrains their occurrences itself | MPXJ: unsupported, though it reproduces the 3 corpus files refused only for this; revisited when a real file turns up |
| Inserted or external projects, cross-project links | N tasks or relationships belong to inserted or external projects: their dates come from another file | Dates from another file |
| Summary-task constraints | N summary tasks carry a constraint | MPXJ: unsupported; none in the corpus |
| `MultipleCriticalPaths` on | the project calculates multiple critical paths, a rule the oracle has not validated | MPXJ does not implement it, Microsoft's page names the option only, no corpus file with logic uses it |
| Resource-driven tasks | N tasks are scheduled by resource assignments on other working time than the task's, or with delayed or contoured assignments | A work resource (units > 0) whose calendar defines other working time than the task's effective calendar, an assignment levelling delay, or assignment dates off the task's. A resource on the same working time changes nothing: the stored `Duration` already embodies work and units. MPXJ reproduces none of the 7 corpus files refused only for this and all the files on the near side of the rule |
| No project `StartDate`; a logic loop | the project has no start date; logic loop through N tasks | Nothing to schedule from |

Not refusals: `HonorConstraints` (uninformative, above), a missing `StatusDate` (the passes
do not use it; the checks that need it stay "not checkable"), inactive tasks (ignored, as
Project ignores them).

**Uncovered rules.** Deadlines, ALAP, SNLT, FNLT, FNET and MSO constraints, constraints
on started tasks, elapsed durations, elapsed and percentage lags, relationships across
two calendars, and a levelling delay outside its validated case (a started or constrained
task, non-FS or lagged predecessors, or a delayed start off a working start) have a
documented rule (above) but no example in the oracle files. A file
that uses one is still recalculated and compared, since the comparison validates the rule
on that file, and the report lists the rules under `uncovered`; the Critical Path Test,
which applies the rules to a schedule the file never stored, is **withheld** until an
oracle file for the rule reproduces. The Health Check names them.

**Local oracle files** (`examples/*.mpp`, gitignored and never committed: two of
Microsoft's own Project templates and a third party's coursework schedule;
`tests/test_msp_examples.py` checks them when present and skips otherwise;
`scripts/msp_corpus.py examples` reports them): *Commercial construction project plan*
(126 tasks, 176 links with lags), *Microsoft Office Project 2003 deployment* (250 tasks,
75 summary links) and the coursework file (22 tasks, 4 in progress, a status date, a
levelling delay) all reproduce with 0 differences and pass the Critical Path Test
exactly. The coursework file is the first oracle with both progress and a status date:
its started tasks keep their actual start and full duration, with `Stop`/`Resume` at
the status date and no working time between, exactly as the progress rule above says.

**What the oracle proved.** `scripts/msp_oracle_coverage.py` (stage 1 of phase 3) found
the corpus a thin oracle: 54 of its 749 Project files carry any relationship, and after
the refusals **33 files, 397 tasks and 237 links** are in scope (135 FS, 24 SS, 24 FF, 24
SF; 126 lagged links in days and weeks, 6 of them leads; 129 SNET and 3 MFO constraints; 8
milestones; 5 progressed files; Project 98 to 2019 in both formats). The engine reproduces
**32 of the 33** with 0 differences and passes the Critical Path Test on 31 (the other,
`slack9.mpp`, has no activity whose finish drives its Must-Finish-On milestone, so there
is nothing to delay). The one exception, `bug1.mpp`, a Project 2003 file, stores late
dates on two tasks three days later than any rule gives, which MPXJ misses too; it is
reported as a difference, as the product would, and excluded from the acceptance
criterion by name. The confidential real-world `.mpp` (51 tasks, 50 FS links, one
relationship on a summary task) reproduces with 0 differences and passes the test
exactly. Across the whole corpus the recalculation matches 554 files (32 with logic),
differs on 10 (bug1, a Project 2002 file whose started task stores late dates equal to its
early ones, the seven elapsed-duration fixtures whose working tasks store late finishes
two days before the project finish, and a cost-resource timephased file whose task starts
at a period's end), and refuses 185 with a reason (five files once refused for a task
levelling delay now match). What the corpus **cannot** prove is the
uncovered list above, progress beyond three tasks per file, and any file with both
progress and a status date. `scripts/msp_corpus.py` prints the per-file result.

## Not done

- Modelling of resource-dependent activities, resource levelling, cross-project
  relationships, multiple float paths and WBS summary activities in the recalculation
  (see *Refused files*), and on Project files the refusals of *Recalculation of Microsoft
  Project files* (resource-driven tasks on other calendars, levelling, splits, manual and
  recurring tasks, inserted projects, multiple critical paths, scheduling from the finish
  date). No what-if rescheduling beyond the Critical Path Test.
- BEI against a baseline.
- Cost, earned value, resource levelling or loading analysis.
- Schedule risk analysis, e.g. Monte Carlo (AACE 57R-09).

## Verifying it yourself

- `pytest` covers the working-time arithmetic (weekends, holidays, worked exceptions,
  24-hour calendars, snapping), the driving rule, agreement with P6's flags on the sample,
  the CPLI hand calculation, % complete per type, the scheduling-options decoding, every
  engine rule above on a minimal network (`tests/test_cpm.py`), and exact reproduction of
  the sample with a passing Critical Path Test (`tests/test_cpm_sample.py`).
- `scripts/cpm_oracle.py` runs the recalculation on any `.xer` files you hold and prints
  per-file match counts only (no activity content), for checking the engine against your
  own P6 exports.
- `tests/test_cpm_msp.py` covers every Project scheduling rule above on a minimal network,
  and `tests/test_recalc_msp.py` each refusal, the uncovered-rule policy, summary-task
  logic and the resource rule on minimal MSPDI documents.
- `scripts/msp_oracle_coverage.py` measures what the corpus can prove (features per file,
  the in-scope set, and MPXJ's own scheduler as a second reference); `scripts/msp_corpus.py`
  reports the recalculation's result per corpus file.
- `tests/test_mspdi.py` covers every Microsoft Project rule above on minimal MSPDI
  documents, and the agreement of `examples/sample-schedule.xml` (the same demo project
  as Project would save it) with the `.xer` sample on the critical set; `tests/test_mpp.py`
  the `.mpp` conversion (skipped without a Java runtime).
- `scripts/msp_corpus.py` runs both readers over MPXJ's test corpus and reports, in
  aggregate, what parses, what is refused and why, and whether each `.mpp` agrees with
  its MSPDI twin.
- `npm run test:run` in `frontend/` covers each health-check rule on minimal synthetic
  schedules, plus pinned finding counts on both samples.
- For any finding, the **Raw tables** view shows the exact `TASK`, `TASKPRED`, `CALENDAR`
  and `SCHEDOPTIONS` rows (or, for a Project file, the Tasks, PredecessorLinks and
  Calendars records) it came from.
