# SPEC: CPM recalculation engine and DCMA 12 Critical Path Test

Status: **draft for a future iteration**, not started. Written 2026-10-12 to hand to an
implementing agent. Read `docs/METHODOLOGY.md` first: it defines every figure the app
already shows, and this spec builds on those definitions.

## 1. Objective

XERlock reads the dates, float and flags P6 computed and recomputes only driving
relationships, the Longest Path and the CPLI to cross-check them. It cannot run the
**DCMA 12 Critical Path Test**, which adds a delay to the critical path, reschedules, and
confirms the project finish moves by the same amount. It also cannot independently verify
every date and float in a submission.

Build a **CPM scheduling engine** that recomputes a schedule from the file's own logic,
durations, calendars, constraints, progress and scheduling options. It must reproduce
P6's stored results. On top of it, implement the Critical Path Test.

**Users:** project controls professionals reviewing contractor programmes. They need
findings they can defend: every recomputed figure must either match P6 or be reported as a
difference, with the reason.

**The governing rule: P6 is the oracle.** The engine is trusted on a file only when it
reproduces P6's stored dates and float for that file. Where it does not, the app says so
("recalculation differs from P6 on N activities") and does not offer the Critical Path
Test. That difference is itself a review finding, because it usually means the submission
was edited and not rescheduled. The existing Longest Path cross-check works the same way
and matched P6 on all 12 real files tested.

### Acceptance criteria

1. **Reproduction.** Unprogressed, task-dependent schedules: early start/finish, late
   start/finish, total float and free float match P6's stored values on every activity
   (dates to the minute, float to 0.01 h). Measured over the oracle corpus (§6).
2. **Progress.** For progressed schedules, the same comparison against P6's stored
   remaining-early dates (`restart_date`, `reend_date`), remaining-late dates
   (`rem_late_start_date`, `rem_late_end_date`) and float. Covers all three P6
   out-of-sequence modes: Retained Logic, Progress Override, Actual Dates.
3. **Self-check.** Every parse reports, per file: the number of activities whose
   recomputed values differ from P6's, with the field and delta for each. This drives a
   new Health Check item: *Recalculation matches P6*.
4. **Critical Path Test (DCMA 12),** enabled only when criterion 3 reports zero
   differences:
   - Pick the first incomplete activity on the Longest Path.
   - Add a test delay to its remaining duration, configurable, default 600 working days
     (a common DCMA practice value; record the source used).
   - Reschedule. The test **passes** when the project finish moves by exactly that delay,
     in working time on the finish activity's calendar.
   - Report the finish delta, the expected delta and pass/fail. On failure, report the
     activity where the delay was absorbed: the first activity on the trace whose own
     movement is smaller than the delay.
5. **Graceful refusal.** Files the engine cannot model (§5, "Ask first" and "Never") are
   reported as such with the reason. They are never approximated silently.
6. `docs/METHODOLOGY.md` describes the engine's rules and moves DCMA 12 out of "Not done".
   README claims change only once 1–4 hold on the corpus.

## 2. Commands

```bash
# backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/pytest                         # all backend tests (CI runs this)
.venv/bin/pytest tests/test_cpm*.py      # engine tests only
# oracle harness: NOT in CI; real files are client-confidential and never committed
.venv/bin/python scripts/cpm_oracle.py /path/to/xers/*.xer   # per-file match report

# frontend
cd frontend && npm install && npm run test:run && npm run build

# run locally
.venv/bin/uvicorn backend.main:app --reload --port 8000
cd frontend && npm run dev
```

## 3. Project structure

New and changed files. Keep the existing separation: backend computes, frontend displays,
and rules live in pure modules with tests beside them.

```
backend/
  worktime.py        EXISTS: WorkCalendar (working_hours_between, add_working_hours).
                     Reuse it. Extend it only if P6 snapping rules need it (e.g. "next
                     working moment at or after t").
  cpm.py             NEW: the engine. Pure functions over plain data, no FastAPI or
                     PyP6XER imports. Input: activities, relationships, calendars, options,
                     data date. Output: per-activity ES/EF/LS/LF/TF/FF plus driving flags.
  cpm_options.py     NEW (optional, only if cpm.py grows past ~400 lines): option
                     decoding and out-of-sequence modes.
  main.py            calls cpm.py after parsing; adds the per-file recalculation report
                     and the CPT result to ProjectSummary as new optional fields.
                     Existing fields keep their meaning.
scripts/
  cpm_oracle.py      NEW: runs the engine on given .xer paths and prints match counts
                     only. Never prints activity names or codes (client confidentiality).
tests/
  test_cpm.py        NEW: synthetic networks, one rule per test (§4)
  test_cpm_sample.py NEW: engine reproduces examples/sample-schedule.xer exactly
frontend/src/utils/healthChecks.ts   'cpt' check becomes available when the backend
                                     reports a result; add 'recalc' (XERlock) check
frontend/src/components/HealthCheck.vue  CPT result card plus recalculation differences
docs/METHODOLOGY.md                  engine rules, CPT method, refusal cases
```

## 4. Code style and testing strategy

**Style.** Match `backend/main.py` and `backend/worktime.py`:
- Plain functions and small classes; standard library only.
- Comments explain *why*, citing the P6 behaviour or standard being reproduced.
- Hours as floats; `datetime` for instants; every duration measured on a named calendar.

An example of the expected density:

```python
def early_start(succ, links, cals, opts):
    """Latest date any predecessor link allows, never before the data date. P6 places
    the start at the first working moment on the successor's own calendar at or
    after that date."""
```

**Test-driven, one rule per test, smallest network that shows it.** Required cases:

- FS, SS, FF, SF, each with zero, positive and negative lag; lag on each of the four
  `sched_calendar_on_relationship_lag` settings.
- Mixed calendars across a link (5-day pred → 7-day succ and back); holidays; worked
  exceptions; 24-hour calendars.
- Each constraint type, as primary and as secondary: early-side (Start On or After, etc.),
  late-side (Finish On or Before, etc.), mandatory, ALAP. Expected negative float where a
  constraint is unachievable.
- Float types `FT_FF` / `FT_SF` / smallest; `sched_open_critical_flag`;
  `sched_use_project_end_date_for_float` with and without a project must-finish date.
- Milestones: start milestones at the start of a work period, finish milestones at the
  end. This is the most common source of off-by-one-period mismatches.
- Progress: in-progress remaining work from the data date; out-of-sequence work under
  each of Retained Logic, Progress Override and Actual Dates; completed predecessors.
- LOE spanning its predecessors and successors, and never driving.
- Expected finish (`expect_end_date`) when `sched_use_expect_end_flag` is set.
- Loops in the logic are detected and reported, not looped on.
- CPT: passes on a clean chain; fails when a constraint or a parallel path absorbs the
  delay, and names the absorbing activity.

**Oracle corpus (not in CI).** Twelve real P6 exports were used in development; the
current maintainer holds them. They are **client-confidential**: never commit them, copy
them into the repo, put their contents in test names, fixtures, logs or screenshots, or
send them to any external service. `scripts/cpm_oracle.py` reports aggregate counts only.
The sample file in `examples/` is the only schedule that may appear in the repository.

**Done means:** CI is green, and the oracle harness reports 0 differences on every corpus
file the engine claims to support. Report any file it refuses, with the reason.

## 5. Boundaries

**Always**
- Treat P6's stored values as the reference. A mismatch is a bug or a finding, never
  "close enough". Tolerances are 1 minute on dates and 0.01 h on float, as the existing
  driving rule uses.
- Measure every duration, lag and float in working time on the calendar P6 would use.
- Keep the read-only promise: recalculation happens in memory on parsed data. The
  uploaded file is never modified, re-saved or stored.
- Refactor before changing behaviour (repo `AGENTS.md`). Separate commits.
- Update `docs/METHODOLOGY.md` in the same change as any rule.

**Ask first**
- Resource-dependent activities (`TT_Rsrc`). These schedule on resource calendars
  (`TASKRSRC` / `RSRC`), which many exports omit. Propose detection plus refusal before
  attempting to model them.
- Levelled schedules: P6's levelling heuristics are not reproducible. Propose detection
  (resource-levelled dates differ from logic-driven ones) plus refusal.
- External (cross-project) relationships. Today they are dropped at parse time; P6 uses
  `external_early_start_date` / `external_late_end_date`. Decide with the maintainer.
- Multiple-float-path or multiple-longest-path options.
- Any new dependency, or exposing the engine for user-driven what-if scenarios. That is
  out of scope for this iteration.

**Never**
- Approximate silently. Unmodelled cases are reported, and the CPT is withheld.
- Commit or expose real client schedules or their contents (see §4).
- Change the meaning of existing API fields. Saved snapshots in users' browsers depend on
  them; add new optional fields instead.
- Present the CPT result on a file where recalculation does not reproduce P6.

## 6. Open questions for the maintainer

1. CPT test delay: keep the 600-working-day default, or use a contract-defined value?
2. Should a recalculation mismatch count toward the Health Check score, or be informational?
3. Is reproduction of *late* dates required before shipping, or are early dates plus total
   float enough for v1?
