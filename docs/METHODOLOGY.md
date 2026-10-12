# Methodology

How XERlock computes every figure it shows, which standard each one follows, and where it
departs from that standard. Written for a reviewer who has to defend a finding: each
definition names the `.xer` fields it reads, so it can be re-checked by hand in the
**Raw tables** view against the file as exported.

## The principle: read P6's results, recompute only to cross-check

XERlock is not a scheduling engine. Early/late dates, total float, free float and
remaining durations are **P6's own computed values**, read from the `TASK` table exactly as
exported. The app never reschedules.

It does recompute three things independently, from those dates and the file's calendars,
so that they can be checked against what P6 stored:

| Recomputed | Checked against | Disagreement means |
|---|---|---|
| Driving relationships | (P6 does not export per-link driving flags) | — |
| Longest Path | `TASK.driving_path_flag` | the schedule was edited and not recalculated, or a defect in XERlock |
| CPLI | — (P6 does not compute it) | — |

On the 12 real contractor submissions used in development (not published), the
recomputed Longest Path matched P6's flag on every activity: 0 differences.

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

Every rule lives in `frontend/src/utils/healthChecks.js`, with unit tests beside it.

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
| DCMA 12 | Critical Path Test | **Not performed** (see below) | — | — |
| DCMA 13 | CPLI | (CPL + TF) / CPL | ratio | ≥ 0.95 |
| XERlock | Out-of-sequence | Successor started before an FS predecessor finished, started before an SS predecessor started, or finished before an FF predecessor finished | count | 0 |
| XERlock | ALAP constraints | As Late As Possible, primary or secondary | count | 0 |
| XERlock | LOE on critical | Level of effort that is critical or on the Longest Path | count | 0 |
| XERlock | Driving path cross-check | P6's stored Longest Path flag ≠ recomputed Longest Path | count | 0 |

Deviations from DCMA, stated so they can be weighed:

- **DCMA 01** counts only missing predecessors or successors. XERlock also counts dangling
  ends (a start tied only by FF/SF links, a finish tied only by SS/SF), following GAO's
  guidance on dangling logic. The Open Ends list labels which case each one is.
- **DCMA 11 and 14** measure against the baseline. A single `.xer` carries none, so Missed
  Tasks uses P6's Planned Finish (`target_end_date`). P6 moves planned dates with the
  forecast on work that has not started. Read the result as a check against the current
  plan, not a baseline execution index. **BEI (DCMA 14)** is not computed.
- **DCMA 12 (Critical Path Test)** adds a delay to the critical path, reschedules, and
  checks that the finish moves by the same amount. That needs a scheduling engine, which
  XERlock deliberately is not. The Driving Path Cross-Check and the Logic checks cover part
  of the same ground (an unbroken, driving chain to the finish), but they are not a
  substitute.

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
- **S-curve**: the cumulative *count* of activities planned to finish (planned dates) and
  actually finished (actual dates), by month. The curve is unweighted (not by cost,
  hours or duration) and not baselined, and the chart says so.

## Not done

- Rescheduling, or any CPM forward/backward pass (so no Critical Path Test).
- BEI against a baseline.
- Cost, earned value, resource levelling or loading analysis.
- Schedule risk analysis, e.g. Monte Carlo (AACE 57R-09).

## Verifying it yourself

- `pytest` covers the working-time arithmetic (weekends, holidays, worked exceptions,
  24-hour calendars), the driving rule, agreement with P6's flags on the sample, the CPLI
  hand calculation, % complete per type, and the scheduling-options decoding.
- `npm run test:run` in `frontend/` covers each health-check rule on minimal synthetic
  schedules, plus pinned finding counts on the sample.
- For any finding, the **Raw tables** view shows the exact `TASK`, `TASKPRED`, `CALENDAR`
  and `SCHEDOPTIONS` rows it came from.
