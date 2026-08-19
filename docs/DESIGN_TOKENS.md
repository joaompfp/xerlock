# XERlock — Design Tokens (current state)

Generated from `frontend/src/App.vue` — the single reference for the design system.

Two themes: **Light** (bare `:root`) and **Dark** (`[data-theme="dark"]` on `<html>`),
persisted to `localStorage['schedule-app:theme']`. Structural colours re-theme;
**semantic state colours are re-lit per theme but keep their meaning**, so criticality
never changes meaning with the theme. The sidebar stays graphite in both themes, which
is why it has its own `--nav*` scale.

**64 tokens**, 33 of them re-defined in dark.

## Surfaces & lines

| Token | Light | Dark | Used by |
|---|---|---|---|
| `--bg` | `#F1F3F5` | `#0C0F13` | App |
| `--panel` | `#FFFFFF` | `#14181E` | ActivityDetailDrawer, App, CalendarView +5 |
| `--panel-2` | `#F7F8FA` | `#191F26` | App, CalendarView, CriticalPathGraph +2 |
| `--chip` | `#EDF0F3` | `#222A33` | App, CalendarView, GanttChart +1 |
| `--line` | `#DEE2E7` | `#262E38` | ActivityDetailDrawer, App, CalendarView +5 |
| `--line-soft` | `#EBEEF1` | `#1D242B` | CalendarView, GanttChart |
| `--weekend` | `#F2F4F6` | `#10151A` | _via alias_ |

## Text

| Token | Light | Dark | Used by |
|---|---|---|---|
| `--ink` | `#14181D` | `#E9EDF2` | ActivityDetailDrawer, App, CalendarView +7 |
| `--ink-2` | `#454E58` | `#AEB8C4` | ActivityDetailDrawer, App, CalendarView +4 |
| `--ink-3` | `#616B76` | `#8B96A2` | ActivityDetailDrawer, App, CalendarView +5 |

## Interactive

| Token | Light | Dark | Used by |
|---|---|---|---|
| `--accent` | `#2456E6` | `#7BA2FF` | ActivityDetailDrawer, App, CalendarView +6 |
| `--accent-soft` | `#E8EDFD` | `#1A2740` | ActivityDetailDrawer, App, CalendarView +7 |

## Semantic state

| Token | Light | Dark | Used by |
|---|---|---|---|
| `--crit` | `#B4291B` | `#FF8272` | ActivityDetailDrawer, AnnotationEditor, App +7 |
| `--crit-soft` | `#FBE7E3` | `#331A19` | ActivityDetailDrawer, App, CalendarView +2 |
| `--near` | `#8A5F00` | `#E3B341` | ActivityDetailDrawer, AnnotationEditor, App +6 |
| `--near-soft` | `#FAF1DA` | `#2E2413` | ActivityDetailDrawer, App |
| `--ok` | `#2F6B4A` | `#7FC49A` | AnnotationEditor, App, CompareView +4 |
| `--ok-soft` | `#E5EFE8` | `#16261D` | App |
| `--ms` | `#6A3E9E` | `#B98BFF` | App, GanttChart |
| `--on-solid` | `#FFFFFF` | `#12161B` | App, CalendarView, CriticalPathGraph +2 |

## Navigation / section strips

| Token | Light | Dark | Used by |
|---|---|---|---|
| `--nav` | `#171C23` | `#080B0E` | App, GanttChart |
| `--nav-2` | `#1F262F` | `#12171D` | App |
| `--nav-line` | `#2B333D` | `#1E252D` | App |
| `--nav-ink` | `#FFFFFF` | `#E9EDF2` | App, GanttChart |
| `--nav-ink-2` | `#AAB4C0` | `#A6B0BC` | App |
| `--nav-ink-3` | `#8C96A2` | `#8A939E` | App |
| `--crit-bright` | `#FF8272` | `#FF8272` | App |
| `--near-bright` | `#E3B341` | `#E3B341` | App |
| `--ok-bright` | `#7FC49A` | `#7FC49A` | App |

## Derived chart values

| Token | Light | Dark | Used by |
|---|---|---|---|
| `--crit-deep` | `#7A1A10` | `#FFB3A8` | CalendarView, GanttChart |
| `--float-tail` | `#CBD2D9` | `#39424D` | GanttChart |
| `--bar-normal-fill` | `rgba(36,86,230,0.16)` | `rgba(123,162,255,0.20)` | _via alias_ |
| `--bar-progress` | `rgba(20,24,29,0.30)` | `rgba(233,237,242,0.28)` | _via alias_ |

## Legacy aliases

| Token | Light | Dark | Used by |
|---|---|---|---|
| `--white` | `var(--panel)` | `—` | AnnotationEditor, App, CalendarView +6 |
| `--ink-soft` | `var(--ink-2)` | `—` | App, CompareView, GanttChart +3 |
| `--gray-100` | `var(--panel-2)` | `—` | App, CalendarView, CompareView +6 |
| `--gray-150` | `var(--chip)` | `—` | App, CalendarView, CompareView +6 |
| `--gray-300` | `var(--line)` | `—` | AnnotationEditor, App, CalendarView +7 |
| `--gray-500` | `var(--ink-3)` | `—` | AnnotationEditor, App, CalendarView +5 |
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
| `--font-mono` | `"IBM Plex Mono", "SF Mono", "Fira Code", ui-monospace, monospace` | `—` | ActivityDetailDrawer, App, CalendarView +7 |
| `--text-h1` | `700 23px/1.3 var(--font-ui)` | `—` | App |
| `--text-h2` | `700 17px/1.3 var(--font-ui)` | `—` | App |
| `--text-h3` | `700 15px/1.35 var(--font-ui)` | `—` | App, CalendarView, GanttChart |
| `--text-body` | `400 14px/1.5 var(--font-ui)` | `—` | App, CalendarView, WBSNode |
| `--text-small` | `500 13px/1.4 var(--font-ui)` | `—` | ActivityDetailDrawer, AnnotationEditor, App +7 |
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
| `--radius-sm` | `4px` | `—` | ActivityDetailDrawer, AnnotationEditor, App +8 |
| `--radius-md` | `8px` | `—` | App, CalendarView, CompareView +5 |

## Rules

- Semantic state colours (`--crit`, `--near`, `--ok`, `--ms`, `--accent`) are the only
  colours permitted to encode criticality/float/status, and mean the same thing everywhere.
- `--on-solid` is the lettering drawn **on** a solid semantic fill; it flips per theme,
  because the dark theme's semantics are luminous and white lettering would fail on them.
- `--nav*` is the graphite sidebar and does **not** invert. `--crit-bright` /
  `--near-bright` / `--ok-bright` are the semantic variants legible on it.
- Legacy names (`--gray-*`, `--white`, `--*-tint`, `--milestone`, `--ink-soft`, `--active*`)
  alias onto the tokens above and re-theme automatically. Do not add new uses of them.
- Never write a raw hex in a `color`/`background`/`border` declaration — add a token.
- A class used by more than one component belongs in `App.vue`'s global block. Defined in
  one component's `scoped` block it silently renders unstyled everywhere else — this has
  bitten `.btn-tiny-light`, `.btn-tiny`, `.ctrl-btn` and `.tb-chip`.

## Runtime-only variables

`--print-w` / `--print-h` are set per render as inline style from the chosen paper size,
so they intentionally have no `:root` definition.
