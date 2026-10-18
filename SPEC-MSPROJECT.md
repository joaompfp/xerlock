# SPEC: Microsoft Project files

Status: **phases 0-2 in progress** (target release 1.2.0). Phase 3 is specified here but
starts only after phases 0-2 are merged. Written 2026-10-18. Read `docs/METHODOLOGY.md`
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

## 7. Phase 3 (later; not part of 1.2.0)

A Project scheduling engine (`backend/cpm_msp.py`, or `cpm.py` with a per-format rule
set), with Project as the oracle. It must reproduce stored Start/Finish, LateStart/
LateFinish, TotalSlack and FreeSlack on the corpus files, rule by rule, before the
recalculation or the Critical Path Test is enabled for Project files. It must refuse
with a reason: effort-driven or resource-scheduled tasks, levelling, manually scheduled
tasks on the path, and inserted or external projects.
