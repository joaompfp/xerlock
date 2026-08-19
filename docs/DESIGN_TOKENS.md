# XERlock — Design Tokens (current state)

Generated from `frontend/src/App.vue`. Authoritative reference for the design system
**as implemented**; `DESIGN_SPEC.md` is the historical review and has drifted.

Two themes: **Light** (bare `:root`) and **Dark** (`[data-theme="dark"]` on `<html>`),
persisted to `localStorage['schedule-app:theme']`. Structural colours re-theme;
**semantic state colours are re-lit per theme but keep their meaning**, so criticality
never changes meaning with the theme. The navigation/section strips stay graphite in
both themes, which is why they have their own `--nav*` scale.

**64 tokens**, 33 of them re-defined in dark.

## Surfaces & lines

| Token | Light | Dark | Used by |
|---|---|---|---|
| `--bg` | `#F1F3F5` | `#0C0F13` | App |
| `--panel` | `#FFFFFF` | `#14181E` | App |
| `--panel-2` | `#F7F8FA` | `#191F26` | App |
| `--chip` | `#EDF0F3` | `#222A33` | App |
| `--line` | `#DEE2E7` | `#262E38` | App |
| `--line-soft` | `#EBEEF1` | `#1D242B` | _via alias_ |
| `--weekend` | `#F2F4F6` | `#10151A` | _via alias_ |

## Text

| Token | Light | Dark | Used by |
|---|---|---|---|
| `--ink` | `#14181D` | `#E9EDF2` | App, CalendarView, CompareView +6 |
| `--ink-2` | `#454E58` | `#AEB8C4` | App |
| `--ink-3` | `#79838E` | `#7A8590` | App |

## Interactive

| Token | Light | Dark | Used by |
|---|---|---|---|
| `--accent` | `#2456E6` | `#7BA2FF` | App, CalendarView, CompareView +4 |
| `--accent-soft` | `#E8EDFD` | `#1A2740` | App, CompareView, CriticalPathGraph +5 |

## Semantic state

| Token | Light | Dark | Used by |
|---|---|---|---|
| `--crit` | `#B4291B` | `#FF8272` | AnnotationEditor, App, CalendarView +5 |
| `--crit-soft` | `#FBE7E3` | `#331A19` | App |
| `--near` | `#8A5F00` | `#E3B341` | AnnotationEditor, App, CalendarView +5 |
| `--near-soft` | `#FAF1DA` | `#2E2413` | App |
| `--ok` | `#2F6B4A` | `#7FC49A` | AnnotationEditor, App, CompareView +4 |
| `--ok-soft` | `#E5EFE8` | `#16261D` | App |
| `--ms` | `#6A3E9E` | `#B98BFF` | App |
| `--on-solid` | `#FFFFFF` | `#12161B` | App, CalendarView, CriticalPathGraph +2 |

## Navigation / section strips

| Token | Light | Dark | Used by |
|---|---|---|---|
| `--nav` | `#171C23` | `#080B0E` | CalendarView, CompareView, CriticalPathGraph +4 |
| `--nav-2` | `#1F262F` | `#12171D` | _via alias_ |
| `--nav-line` | `#2B333D` | `#1E252D` | _via alias_ |
| `--nav-ink` | `#FFFFFF` | `#E9EDF2` | CalendarView, CompareView, CriticalPathGraph +4 |
| `--nav-ink-2` | `#AAB4C0` | `#A6B0BC` | CalendarView, CompareView, CriticalPathGraph +4 |
| `--nav-ink-3` | `#78838F` | `#6F7A85` | HealthCheck |
| `--crit-bright` | `#FF8272` | `#FF8272` | HealthCheck |
| `--near-bright` | `#E3B341` | `#E3B341` | HealthCheck |
| `--ok-bright` | `#7FC49A` | `#7FC49A` | HealthCheck |

## Derived chart values

| Token | Light | Dark | Used by |
|---|---|---|---|
| `--crit-deep` | `#7A1A10` | `#FFB3A8` | CalendarView, GanttChart |
| `--float-tail` | `#CBD2D9` | `#39424D` | _via alias_ |
| `--bar-normal-fill` | `rgba(36,86,230,0.16)` | `rgba(123,162,255,0.20)` | _via alias_ |
| `--bar-progress` | `rgba(20,24,29,0.30)` | `rgba(233,237,242,0.28)` | _via alias_ |

## Legacy aliases

| Token | Light | Dark | Used by |
|---|---|---|---|
| `--white` | `var(--panel)` | `—` | AnnotationEditor, App, CalendarView +6 |
| `--ink-soft` | `var(--ink-2)` | `—` | App, CompareView, CriticalPathGraph +4 |
| `--gray-100` | `var(--panel-2)` | `—` | App, CalendarView, CompareView +6 |
| `--gray-150` | `var(--chip)` | `—` | App, CalendarView, CompareView +6 |
| `--gray-300` | `var(--line)` | `—` | AnnotationEditor, App, CalendarView +7 |
| `--gray-500` | `var(--ink-3)` | `—` | ActivityDetailDrawer, AnnotationEditor, App +6 |
| `--gray-700` | `var(--ink-2)` | `—` | AnnotationEditor, App, CalendarView +7 |
| `--gray-900` | `var(--ink)` | `—` | _via alias_ |
| `--crit-tint` | `var(--crit-soft)` | `—` | AnnotationEditor, App, CalendarView +4 |
| `--near-tint` | `var(--near-soft)` | `—` | AnnotationEditor, App, CalendarView +5 |
| `--ok-tint` | `var(--ok-soft)` | `—` | AnnotationEditor, App, CompareView +1 |
| `--milestone` | `var(--ms)` | `—` | App, CriticalPathGraph, GanttChart |
| `--active` | `var(--accent)` | `—` | AnnotationEditor, App, CalendarView +5 |
| `--active-soft` | `var(--accent-soft)` | `—` | AnnotationEditor, App, CalendarView +3 |

## Type

| Token | Light | Dark | Used by |
|---|---|---|---|
| `--font-ui` | `"IBM Plex Sans", -apple-system, "Segoe UI", Roboto, sans-serif` | `—` | AnnotationEditor, App, CompareView +3 |
| `--font-mono` | `"IBM Plex Mono", "SF Mono", "Fira Code", ui-monospace, monospace` | `—` | App, CalendarView, CompareView +6 |
| `--text-h1` | `700 23px/1.3 var(--font-ui)` | `—` | App |
| `--text-h2` | `700 17px/1.3 var(--font-ui)` | `—` | App, CalendarView, CompareView +5 |
| `--text-h3` | `700 15px/1.35 var(--font-ui)` | `—` | App, CalendarView, GanttChart |
| `--text-body` | `400 14px/1.5 var(--font-ui)` | `—` | App, CalendarView, WBSNode |
| `--text-small` | `500 13px/1.4 var(--font-ui)` | `—` | AnnotationEditor, App, CalendarView +6 |
| `--text-micro` | `600 11px/1.3 var(--font-ui)` | `—` | ActivityDetailDrawer, AnnotationEditor, App +8 |

## Spacing & radius

| Token | Light | Dark | Used by |
|---|---|---|---|
| `--space-1` | `4px` | `—` | App, HealthCheck |
| `--space-2` | `8px` | `—` | ActivityDetailDrawer, AnnotationEditor, App +7 |
| `--space-3` | `12px` | `—` | AnnotationEditor, App, CalendarView +6 |
| `--space-4` | `16px` | `—` | AnnotationEditor, App, CalendarView +6 |
| `--space-5` | `20px` | `—` | App, CalendarView, ProgressView |
| `--space-6` | `24px` | `—` | App, CriticalPathGraph, GanttChart +1 |
| `--space-8` | `32px` | `—` | App |
| `--radius-sm` | `4px` | `—` | AnnotationEditor, App, CalendarView +7 |
| `--radius-md` | `8px` | `—` | App, CalendarView, CompareView +5 |

## Rules

- Semantic state colours (`--crit`, `--near`, `--ok`, `--ms`, `--accent`) are the only
  colours permitted to encode criticality/float/status, and mean the same thing in every view.
- `--on-solid` is the text colour for lettering drawn **on** a solid semantic fill. It flips
  per theme, because the dark theme's semantics are luminous and white lettering would fail.
- `--nav*` is the graphite furniture (sidebar, section strips) and does **not** invert.
  `--crit-bright` / `--near-bright` / `--ok-bright` are the semantic variants legible on it.
- Legacy names (`--gray-*`, `--white`, `--*-tint`, `--milestone`, `--ink-soft`, `--active*`)
  alias onto the tokens above and re-theme automatically. They exist so components can adopt
  the new names view by view; do not introduce new uses of them.
- Never write a raw hex in a `color`/`background`/`border` declaration — add a token.
- Never paper over a missing token with a `var(--x, fallback)` fallback.

## Runtime-only variables

`--print-w` / `--print-h` are set per render as inline style from the chosen paper size.
They intentionally have no `:root` definition.
