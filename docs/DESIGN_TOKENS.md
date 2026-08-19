# XERlock — Design Tokens (current state)

Generated from `frontend/src/App.vue`. This is the **authoritative reference for the
design system as implemented**. `DESIGN_SPEC.md` is the historical design-review that
produced this system and has since drifted in places — trust this file for values.

**41 tokens** in `:root`. Themes override structural tokens only; semantic
state colors are pinned identically across all four themes so criticality never
changes meaning with the theme.

## Brand / structural

| Token | Value | Themed | Used by |
|---|---|---|---|
| `--ink` | `#1C1917` | yes | App, CalendarView, CompareView, CriticalPathGraph +5 |
| `--ink-soft` | `#4A4038` | yes | App, CompareView, CriticalPathGraph, GanttChart +3 |
| `--accent` | `#2951C4` | yes | App, CalendarView, CompareView, CriticalPathGraph +3 |
| `--accent-soft` | `#E4EAFB` | yes | App, CompareView, CriticalPathGraph, GanttChart +4 |

## Semantic state

| Token | Value | Themed | Used by |
|---|---|---|---|
| `--crit` | `#A5291D` | — | AnnotationEditor, App, CalendarView, CompareView +4 |
| `--crit-tint` | `#F7E1DC` | — | AnnotationEditor, App, CalendarView, CompareView +3 |
| `--near` | `#8F6300` | — | AnnotationEditor, App, CalendarView, CriticalPathGraph +4 |
| `--near-tint` | `#F5EBD3` | — | AnnotationEditor, App, CalendarView, CriticalPathGraph +4 |
| `--ok` | `#3F7355` | — | AnnotationEditor, App, CompareView, CriticalPathGraph +3 |
| `--ok-tint` | `#E2ECE3` | — | AnnotationEditor, App, CompareView, ProgressView |
| `--milestone` | `#6A3E9E` | — | App, CriticalPathGraph, GanttChart |
| `--active` | `#2951C4` | — | AnnotationEditor, App, CalendarView, CriticalPathGraph +4 |
| `--active-soft` | `#E4EAFB` | — | AnnotationEditor, App, CalendarView, GanttChart +2 |
| `--crit-deep` | `#6E150D` | — | CalendarView, GanttChart |
| `--crit-bright` | `#F08A7E` | — | HealthCheck |
| `--near-bright` | `#E3B341` | — | HealthCheck |
| `--ok-bright` | `#7FC49A` | — | HealthCheck |

## Neutrals (warm stone scale

| Token | Value | Themed | Used by |
|---|---|---|---|
| `--gray-900` | `#1F1B17` | yes | _unused_ |
| `--gray-700` | `#5C5347` | yes | AnnotationEditor, App, CalendarView, CompareView +6 |
| `--gray-500` | `#8C8175` | yes | ActivityDetailDrawer, AnnotationEditor, App, CalendarView +5 |
| `--gray-300` | `#DCD5C9` | yes | AnnotationEditor, App, CalendarView, CompareView +6 |
| `--gray-150` | `#F1ECE4` | yes | App, CalendarView, CompareView, CriticalPathGraph +5 |
| `--gray-100` | `#F8F5F0` | yes | App, CalendarView, CompareView, CriticalPathGraph +5 |
| `--white` | `#FFFFFF` | — | AnnotationEditor, App, CalendarView, CompareView +5 |

## Type

| Token | Value | Themed | Used by |
|---|---|---|---|
| `--font-ui` | `"IBM Plex Sans", -apple-system, "Segoe UI", Roboto, sans-serif` | — | AnnotationEditor, App, CompareView, CriticalPathGraph +2 |
| `--font-mono` | `"IBM Plex Mono", "SF Mono", "Fira Code", ui-monospace, monospace` | — | App, CalendarView, CompareView, CriticalPathGraph +5 |
| `--text-h1` | `700 23px/1.3 var(--font-ui)` | — | App |
| `--text-h2` | `700 17px/1.3 var(--font-ui)` | — | App, CalendarView, CompareView, CriticalPathGraph +4 |
| `--text-h3` | `700 15px/1.35 var(--font-ui)` | — | App, CalendarView |
| `--text-body` | `400 14px/1.5 var(--font-ui)` | — | App, CalendarView, WBSNode |
| `--text-small` | `500 13px/1.4 var(--font-ui)` | — | AnnotationEditor, App, CalendarView, CompareView +5 |
| `--text-micro` | `600 11px/1.3 var(--font-ui)` | — | ActivityDetailDrawer, AnnotationEditor, App, CalendarView +7 |

## Spacing & radius

| Token | Value | Themed | Used by |
|---|---|---|---|
| `--space-1` | `4px` | — | App, HealthCheck |
| `--space-2` | `8px` | — | ActivityDetailDrawer, AnnotationEditor, App, CalendarView +6 |
| `--space-3` | `12px` | — | AnnotationEditor, App, CalendarView, CompareView +5 |
| `--space-4` | `16px` | — | AnnotationEditor, App, CalendarView, CompareView +5 |
| `--space-5` | `20px` | — | App, CalendarView, ProgressView |
| `--space-6` | `24px` | — | App, CriticalPathGraph, GanttChart, HealthCheck |
| `--space-8` | `32px` | — | App |
| `--radius-sm` | `4px` | — | AnnotationEditor, App, CalendarView, CompareView +6 |
| `--radius-md` | `8px` | — | App, CalendarView, CompareView, CriticalPathGraph +4 |

## Themes

Selected via `data-theme` on `<html>`, persisted to `localStorage['schedule-app:theme']`.
Default (Sepia) is bare `:root` with no attribute set.

| Theme | Overrides |
|---|---|
| Sepia (default) | — base `:root` |
| Slate | `--accent`, `--accent-soft`, `--gray-100`, `--gray-150`, `--gray-300`, `--gray-500`, `--gray-700`, `--gray-900`, `--ink`, `--ink-soft` |
| Clay | `--accent`, `--accent-soft`, `--gray-100`, `--gray-150`, `--gray-300`, `--gray-500`, `--gray-700`, `--gray-900`, `--ink`, `--ink-soft` |
| Ink | `--accent`, `--accent-soft`, `--gray-100`, `--gray-150`, `--gray-300`, `--gray-500`, `--gray-700`, `--gray-900`, `--ink`, `--ink-soft` |

## Runtime-only variables

`--print-w` / `--print-h` are **not** design tokens: `CriticalPathGraph.vue` sets them as
an inline style per render from the selected paper size. They intentionally have no
`:root` definition.

## Rules

- Semantic state colors (`--crit`, `--near`, `--ok`, `--milestone`, `--active`) are the
  only colors permitted to encode criticality/float/status, and mean the same thing in
  every view.
- `*-bright` variants exist for the dark section strips (ground `--ink`), where the
  standard semantic colors fail contrast.
- Never introduce a raw hex/rgb in a `color`/`background`/`border` declaration — add a
  token instead. Never use a `var(--x, fallback)` fallback to paper over a missing token.
