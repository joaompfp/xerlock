# Contributing

Thanks for your interest! This is a small, focused tool — contributions that keep it that way are
the most welcome.


## Before opening a PR

```bash
pytest                                  # backend
cd frontend && npm run test:run && npm run build
```

Please add a test with any change to parsing, float/date arithmetic, or the health
checks — those numbers end up in someone's review report.

## Ground rules

- **Semantic colors are sacred.** `--crit`, `--near`, `--ok`, and `--milestone` are the only
  colors allowed to represent criticality/float/status, and they must mean the same thing in
  every view. All colors come from the design tokens in `App.vue`'s `:root` block — no hardcoded
  hex values in components.
- **Nothing is persisted server-side.** The backend parses uploads in memory and discards them.
  Features that require server-side storage change the trust model and need discussion first —
  open an issue before building.
- **Scheduling semantics must be defensible.** Float bands, critical-basis definitions, DCMA-style
  checks, and date math follow established planning practice. If you change how a metric is
  computed, cite the convention you're following in the PR description.
- Match the existing code style: Vue 3 Options API, design-token CSS, comments that explain
  *constraints* rather than narrate the code.

## Workflow

1. Fork, branch from `main`.
2. Make your change. Keep PRs focused — one concern per PR.
3. Verify locally:
   - `cd frontend && npm run build` must pass clean.
   - Load `examples/sample-schedule.xer` and click through the affected views with the browser
     console open — zero errors/warnings is the bar.
   - If you touched the backend, confirm `POST /api/upload` still parses the sample file.
4. Open a PR with a short description of what changed and why.

## Reporting bugs

Include the app version/commit, what you did, what you expected, and — if the issue is
parse-related — whether `examples/sample-schedule.xer` reproduces it. **Never attach a real
project's `.xer` file to a public issue**; they contain commercially sensitive information.
If you can, reproduce with a minimal or anonymized file instead.
