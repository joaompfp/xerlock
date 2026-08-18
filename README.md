# Schedule App

**A self-hosted Primavera P6 schedule viewer and review tool.** Upload a `.xer` export and get an
interactive Gantt chart, a critical-path network diagram, DCMA-14-style schedule quality checks,
progress tracking, and snapshot comparison — everything a planner needs to review a contractor's
programme in detail, without a P6 license.

Built for project controls professionals: the checks, terminology, and defaults follow how
schedules actually get reviewed (total float severity bands, longest-path vs TF≤0 critical basis,
open-end detection, lag/lead audits, out-of-sequence progress).

![Gantt chart](docs/screenshots/gantt.png)

## Features

**Gantt Chart** — the primary view
- WBS-hierarchical activity grid with duration, start, and finish columns
- Continuous zoom (presets + Ctrl/scroll), drag-pan, fit-to-width, resizable activity column
- Critical-path link overlay drawn *above* bars so logic never hides behind unrelated activities
- Two critical-basis modes: TF ≤ 0 or Longest Path (driving-chain trace from the finish)
- Progress line, today marker, weekend shading, filter bar (text/status/critical/activity codes)
- Right-side detail drawer: stat tiles for duration/float/dates/status, predecessor and successor
  lists with dates, durations, and lags — click any related activity to jump to it
- Print-friendly export

**Critical Path** — activity-on-node network diagram
![Critical path network](docs/screenshots/critical-path.png)
- Dagre-based DAG layout folded into a "snake" so long chains stay readable
- Shows the critical + near-critical set by default; expand hidden neighbors on demand
- Pan/zoom canvas, full-width, with the same detail panel and jump navigation

**Health Check** — DCMA-14-inspired logic & quality scorecard
![Health check](docs/screenshots/health-check.png)
- Open ends (missing predecessor/successor), relationship-type mix, negative lags ("leads"),
  oversized lags, hard/soft constraint register, negative float, high-duration activities,
  LOE-on-critical-path anomalies, out-of-sequence progress, missing resource assignments
- Cross-checks the app's computed longest path against P6's own `driving_path_flag`
- Every finding is one click away from the activity in the Gantt

**Progress** — status-date-anchored monitoring
![Progress view](docs/screenshots/progress.png)
- Milestone tracker with target-vs-forecast variance
- 4/8-week look-ahead window with remaining vs original durations
- Planned-vs-actual S-curve anchored to the schedule's data date

**Compare** — diff two `.xer` snapshots
- Upload last month's submission alongside the current one: date slips, float erosion,
  critical-path churn (with a stability score), logic changes, added/removed activities
- Activities matched by code (stable across re-exports), not internal IDs

**Review workflow**
- Attach notes with severity tags (Query / Risk / Logic Issue / Resolved) to any activity;
  flags show across every view, persisted in your browser per project
- Export an annotated Review Report (.xlsx), a full schedule workbook, or filtered CSVs
- The app remembers your last opened file (browser-local) for one-click reopening

## Try it

A synthetic sample schedule ships in [`examples/sample-schedule.xer`](examples/sample-schedule.xer)
(24 activities, realistic logic, a critical path, negative float, in-progress work). Upload it to
explore every feature.

## Architecture

```
┌────────────┐  .xer upload   ┌──────────────────┐
│  Vue 3 SPA │ ─────────────▶ │ FastAPI backend   │
│  (Vite)    │ ◀───────────── │ + PyP6XER parser  │
└────────────┘  parsed JSON   └──────────────────┘
```

- **Backend** (`backend/main.py`): FastAPI + [PyP6XER](https://github.com/HotaOsman/PyP6XER).
  One endpoint (`POST /api/upload`) parses the `.xer` in memory and returns the full schedule as
  JSON — activities with float/constraints/actuals/codes, the WBS tree, and project stats
  including a longest-path trace. **Nothing is persisted server-side**; files are parsed and
  discarded.
- **Frontend** (`frontend/`): Vue 3 (Options API) + Vite. No UI framework — hand-rolled CSS on a
  design-token system. [dagre](https://github.com/dagrejs/dagre) computes the network layout;
  [ExcelJS](https://github.com/exceljs/exceljs) (lazy-loaded) generates the Excel exports.
  Annotations and the last-opened file live in `localStorage` only.
- In production, FastAPI serves the built frontend from `frontend/dist/` — a single container
  runs everything.

## Run locally

Requires Python ≥ 3.10 and Node ≥ 18.

```bash
# backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn backend.main:app --reload --port 8000

# frontend (separate terminal)
cd frontend && npm install && npm run dev
```

Open http://localhost:5173 — the dev server proxies `/api` to the backend on port 8000.

## Deploy

**Docker (recommended):**

```bash
cd frontend && npm install && npm run build && cd ..
docker compose up -d --build
```

Or without compose:

```bash
docker build -t schedule-app .
docker run -d -p 8000:8000 schedule-app
```

The container serves the whole app on port 8000. Put your reverse proxy of choice
(Traefik, Caddy, nginx) in front for TLS.

> The frontend must be built (`npm run build`) *before* the image build — the Dockerfile copies
> `frontend/dist/` rather than running Node inside the image, keeping it a slim single-stage
> Python image. If you prefer building inside Docker, a multi-stage
> `node:20-alpine → python:3.12-slim` Dockerfile works too.

## Development notes

- All colors/typography/spacing are CSS custom properties defined once in `App.vue` (`:root`
  block). Semantic status colors (`--crit`, `--near`, `--ok`, `--milestone`) mean the same thing
  in every view — don't introduce new colors for criticality states.
- The Gantt deliberately avoids `position: sticky` for its frozen header/label column
  (Chromium mis-renders sticky grid items near scroll boundaries); positions are tracked
  manually from the scroll handler. See comments in `GanttChart.vue`.
- Numeric text (codes, dates, durations, floats) renders in tabular monospace app-wide.
- `docs/DESIGN_SPEC.md` records the design-review that produced the current visual system.

## License

[MIT](LICENSE). Depends on [PyP6XER](https://github.com/HotaOsman/PyP6XER) (LGPL-2.1, used as an
unmodified library), dagre, ExcelJS, Vue, and IBM Plex fonts (OFL, loaded from Google Fonts).

Primavera and P6 are trademarks of Oracle. This project is not affiliated with or endorsed by
Oracle; it merely reads the documented `.xer` interchange format.
