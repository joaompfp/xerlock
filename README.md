# Schedule App

Primavera P6 `.xer` file viewer with an interactive critical-path network diagram.

- **Backend**: FastAPI + [PyP6XER](https://github.com/vp3rd/PyP6XER), parses uploaded `.xer` files in memory (nothing is persisted).
- **Frontend**: Vue 3 + [dagre](https://github.com/dagrejs/dagre) for DAG layout, custom SVG rendering.

## Features

- Critical-path network diagram: pan, zoom, click a node for predecessor/successor detail, expand hidden neighbors on demand.
- Activity table with search/filter/sort.
- WBS tree.

## Run locally

```bash
# backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn backend.main:app --reload --port 8000

# frontend (separate terminal)
cd frontend && npm install && npm run dev
```

Frontend dev server proxies `/api` to `localhost:8000`.

## Deploy

Built and served as a single container (FastAPI serves the built frontend). See `Dockerfile`.
