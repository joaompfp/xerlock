# Schedule App — Design Critique & Redesign Spec

Prepared as a pre-sprint design review. Part 1 is the critique (evidence-based, from reading
`App.vue`, `GanttChart.vue`, `CriticalPathGraph.vue`, `WBSNode.vue` and from live screenshots of
the app loaded with real LIS1 schedule data — `LIS10-Draft 19.xer`, 483 activities). Part 2 is an
implementable spec for the next sprint.

---

## Part 1 — Critique

### 0. The headline finding: this palette is not a design choice, it's a default

Before anything else: pull the exact hex values used across `App.vue`, `GanttChart.vue`, and
`CriticalPathGraph.vue` and compare them to the famous **Flat UI Colors** palette
(flatuicolors.com, 2013) — the single most reused "instant Bootstrap admin theme" palette on the
web, and the go-to default for scaffolded dashboards:

| In this app | Hex | Flat UI Colors name |
|---|---|---|
| `.stat-card strong` positive number, `.status-badge.TK_Complete` text | `#27ae60` / `#1e8449` | **Nephritis** |
| Critical bars, critical dots, critical edges (`e74c3c`) | `#e74c3c` | **Alizarin** |
| `.float-crit`, stat-card negative number | `#c0392b` | **Pomegranate** |
| Milestone diamonds, milestone badge | `#8e44ad` | **Wisteria** |

Four independently-chosen "accent" colors in this app are exact hex matches for four colors from
the single most recognizable stock palette in web development. That's not a coincidence a
professional designer would let slide — it's the tell. On top of that, the primary brand color,
`#2F5496`, is not a custom brand blue either: it's the default **Word/PowerPoint "Blue, Accent 1,
Darker 25%"** heading color baked into Microsoft Office themes. So the one color meant to carry
this tool's identity is literally an Office document heading color, and the semantic accents are
literally a copy-pasted Bootstrap-tutorial palette. This is *why* the app "feels AI boilerplate" —
it's not a vibe, it's traceable to specific, extremely common default values. Nothing here reads
as chosen for *this* tool, this domain, or this data.

### 1. Color palette

- **Not distinctive.** See §0. Every hue in the app is a stock default. There is no color in the
  current system that says "scheduling tool" rather than "generic SaaS dashboard tutorial."
- **Semantic coloring is inconsistent across the three surfaces that need to agree most:**
  - Gantt bars: critical = `#f0a099` fill / `#e74c3c` border, near = `#f2d693` fill / `#d4a017`
    border, normal = `#aebbd6` fill / `#2f5496` border (`GanttChart.vue` lines 569-571).
  - Network diagram nodes: critical = `#fdeeed` fill / `#e74c3c` border, near = `#fdf6e6` fill /
    `#d4a017` border, other = `#f5f6f8` fill / `#c9cdd4` border (`CriticalPathGraph.vue` lines
    518-520).
  - Activity table: no background color at all for status — critical is signaled only by a 3px
    `border-left: #e74c3c` (`App.vue` line 471), milestone by a 3px `border-left: #8e44ad`. Float
    values get a *third*, unrelated color treatment (`.float-crit` = `#c0392b`, a color that
    exists nowhere else in the critical-state vocabulary — Pomegranate red, not Alizarin red).
  - Result: "critical" is a pastel-fill-plus-saturated-border pattern in two views and a
    left-border-only pattern in the third, and the red used for float text isn't even the same red
    used for critical bars/nodes/edges. A user pattern-matching color across tabs has to re-learn
    the rule each time.
- **Near-critical amber (`#d4a017`) is fine as a hue choice** but is applied with the same
  fill+border recipe as critical, just swapped colors — there's no differentiation in *shape* or
  *weight* between "urgent" and "watch this," only hue, which is a real accessibility gap for
  colorblind users (red/amber confusion is common in deuteranopia).
- What a real scheduling tool's palette looks like, for contrast: P6 and MS Project both lean on
  desaturated ink/graphite neutrals for 95% of the UI, with color reserved *strictly* for the
  critical-path signal — not decorating stat cards, not tinting hover states, not coloring
  "Complete" green just because green means done in every dashboard template ever built.

### 2. Typography

- Font stack is `-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif` — the literal
  default "system-ui" stack recommended in every CSS reset tutorial since 2017. It's not wrong,
  but it contributes zero personality and is indistinguishable from thousands of other
  scaffolded apps.
- **Density vs. hierarchy conflict.** This is a data-dense scheduling tool — the whole point is
  scanning hundreds of rows of codes, dates, floats — yet most text sits at 12-14px with only
  `font-weight` doing hierarchy work, and weight usage is inconsistent: activity names are
  `font-weight: 500` (`.act-name`), WBS short names are `700` (`.wbs-name`), stat numbers are
  `700` at 22px, insight-card headers are `700` at 16px. There's no defined scale — every
  component picked its own size/weight combination independently, which is exactly what happens
  when a UI is built incrementally across sessions without a shared type scale (confirmed: user's
  own framing of the project history).
- **No monospace/tabular-numeral discipline for numeric columns.** `.data-table .code` and
  `.g-act-code` correctly use monospace, but dates, durations, and float values in the same table
  don't — so numeric columns in the activity table don't align on their digits, which matters a
  lot when someone is scanning a Float column for the `0h`/`8h`/`16h` pattern.
- Screenshot evidence (`Activity Table` tab): CODE column is monospace and reads sharp; every
  other numeric column (DUR, START, END, FLOAT) is proportional-width and visibly ragged.

### 3. Spacing & layout rhythm

- Border-radius values in use, uncoordinated: `2px` (progress bar), `3px` (bar-wbs, badge),
  `4px` (bars, milestone), `6px` (buttons, inputs), `8px` (cards, table wrap, wbs-tree), `9px`
  (network-diagram node `rx`), `10px` (gantt-wrap, graph-wrap), `10px`/`999px` (status badge
  pill). Ten different radii across a small app, no evident system.
- Padding is similarly ad hoc: stat-card `12px 16px`, insight-card `20px`, table cell `6px 10px`,
  toolbar `14px 18px`, legend `8px 18px`, graph-toolbar `10px 14px`. Nothing lines up to a shared
  4/8px rhythm even though most values happen to be multiples of 2 — they just aren't multiples
  of a *chosen* base unit applied consistently.
- **The "gray box" recipe is copy-pasted everywhere regardless of content:** stat-card,
  insight-card, `.rel-row td`, `.detail-panel` in the network graph, and the WBS tree wrapper all
  use the identical `background: #f8f9fc; border: 1px solid #e8e8e8; border-radius: 8px` (or a
  close variant). Four or five structurally different pieces of content — a KPI, a watchlist
  table, an inline relationship expando, a node detail panel — all get the same undifferentiated
  gray card treatment. That's the single clearest symptom of "built by pattern-matching to a
  generic card component" rather than by designing each piece for what it actually contains.
- **The stat-card row reads as the laziest part of the app.** Seven near-identical boxes
  (Activities / Critical / Longest Path / Milestones / Complete / Earliest start / Latest end),
  each just `<strong>` over `<span>`, each with a pointless `translateY(-1px)` hover-lift and
  drop-shadow — a micro-interaction borrowed from marketing landing pages that serves no purpose
  on values nobody clicks. Confirmed via screenshot: at 1600px wide the 7 cards stretch the full
  width with huge internal whitespace around each 2-3 character number, and two of the seven
  (Earliest start / Latest end) are date ranges, not headline KPIs, that only marginally deserve
  the same visual weight as "98 critical."

### 4. Iconography & affordances

- Every expand/collapse/sort affordance in the app is a raw Unicode glyph: `▼` `▶` `▲` in
  `WBSNode.vue` and `App.vue`'s sort headers, `◆` for milestones in the network diagram legend
  and node labels, plus a hand-drawn CSS diamond (`transform: rotate(45deg)`) for the *actual*
  milestone markers in the Gantt — meaning milestones are represented by *two different visual
  languages* in two different views (a Unicode ◆ character in the network graph, a CSS square
  rotated 45° in the Gantt), which don't render at quite the same optical weight or size.
- Unicode glyphs render inconsistently across platforms/fonts (different baseline, different
  optical size relative to surrounding text), and they read as placeholder icons — the visual
  equivalent of shipping with `TODO: replace with real icon`. This is one of the fastest tells of
  an unfinished/AI-scaffolded UI to any designer's eye.
- **Tiny bordered gray buttons are the app's only interactive-affordance pattern**, and they're
  everywhere: `.btn-tiny` (7+ instances in the Gantt toolbar alone — Expand all, Collapse all,
  Today, Fullscreen, plus zoom levels, plus critical-basis toggle, plus Links checkbox), `.btn-
  outline` (Export, Load another), `.btn-collapse`. They all look alike regardless of importance
  or grouping, so "Fullscreen" (a mode-changing action) has the exact same visual weight as
  "Today" (a scroll shortcut) has the exact same visual weight as a zoom-level radio option.
  Nothing distinguishes primary actions from secondary toggles from radio-style selections except
  which ones happen to have an `.active` class at a given moment.

### 5. The dark Gantt toolbar

- Screenshot evidence confirms the intent (make the Gantt feel "flagship") doesn't land cleanly.
  The toolbar is `#1a1a2e` (near-black navy), but it sits directly above the legend bar and
  timeline header, both `#fafbfc` (near-white) — a hard, high-contrast seam runs directly under
  the toolbar's bottom edge, one component tall, with no dark surface anywhere else in the app to
  make it feel intentional rather than pasted on. It's a single dark rectangle inside an
  otherwise all-white product, which reads as "a component from a different app was dropped in,"
  not as a deliberate instrument-panel treatment.
- The internal contrast on the dark toolbar is also inconsistent: `.toolbar-sub` is `#a8adc0`
  (readable), `.basis-group button` text is `#c5c9dc`, `.btn-tiny` text is also `#c5c9dc` — fine —
  but the *active* critical-basis button uses solid `#e74c3c` fill (Alizarin again), while the
  active zoom button uses `#2f5496` fill — two different "you are here" treatments sitting 40px
  apart in the same toolbar, for buttons that are conceptually the same kind of control (a
  segmented toggle).
- Verdict: the dark toolbar isn't wrong as a direction, but as implemented it's a half-measure —
  committing to "this one strip is dark" without extending the treatment far enough to read as a
  system, and without enough internal consistency to feel controlled rather than improvised.

### 6. Component-specific issues

- **Stat-card row** — see §3. Recommend replacing outright (spec below).
- **Tab nav** — the least offensive part of the app: text tabs with an underline on active state
  is a reasonable, low-chrome pattern for a data tool. Its only real problem is proximity to the
  dark Gantt toolbar immediately below it — light tab nav → light stat cards → light tab nav →
  **dark** toolbar is a jarring value flip on first paint of the Gantt tab, screenshot-confirmed.
- **WBS tree rows (`WBSNode.vue`)** — a plain, unstyled-feeling list. Hierarchy is communicated
  only by 20px indent per level and a bold/gray weight split between `wbs_short_name` and
  `wbs_name`; the activity count is right-floated with no visual container, leaving a huge dead
  gap between name and count on wide screens (screenshot-confirmed: at 1600px, "3 activities" sits
  visually orphaned ~1000px away from its label with nothing connecting them). No zebra striping,
  no depth guide-lines — compare to the Gantt's own tree column, which *does* zebra-stripe and
  bold WBS rows, meaning the app already contains a better-designed tree than the one on the
  dedicated WBS Tree tab.
- **Activity table status badges** — pastel-pill badges (`TK_Complete` green, `TK_Active` amber,
  `TK_NotStart` gray) are a workable *concept*, but the specific colors are, again, Flat-UI-
  palette-adjacent, the pill radius (`10px`, i.e. fully rounded on a ~20px-tall element) doesn't
  match any other radius token in the app, and color is the *only* signal — no icon, no shape
  differentiation — which is a real problem for colorblind users distinguishing amber-Active from
  the near-critical amber used two tabs over for something entirely different.
- **Network diagram nodes (`CriticalPathGraph.vue`)** — rounded-rect mini-cards (`rx="9"`, four
  lines of text: code, name, meta) that read as generic **flowchart/automation-builder nodes**
  (n8n, Zapier, Miro sticky-note-with-rounded-corners), not as project-schedule activity nodes.
  This matters because professional scheduling has its own, very recognizable visual convention
  for this exact diagram — the **activity-on-node (AON) box**, taught in every PM textbook and
  used in P6's own network views: a rectangle divided into labeled fields (ES/EF on top corners,
  LS/LF on bottom corners, duration and float in the middle). Using that convention instead of a
  generic rounded card would be an instant, low-effort signal of domain credibility that a
  Trello-style card can never provide, however well-styled.
- **Network diagram canvas usage** — screenshot-confirmed (1600px browser, "Fit" view, 483-
  activity file): the wrapped/snake dagre layout renders into a narrow ~450px-wide column
  centered in a canvas with roughly 700px of empty dot-grid on either side. Zooming in 3 steps
  still shows only 3-4 node-columns on screen at once even though the panel is wide enough for
  more. This is a functional readability problem, not just a style one — the implementer should
  check whether `ranksPerRow` in the wrap-layout math (`CriticalPathGraph.vue` `layout` computed,
  lines ~253-257) is under-using `canvasWidth`, or whether `resetView`'s scale-to-fit is being
  driven entirely by the (very tall, many-row) graph height and shrinking horizontal usage as a
  side effect. Either way, most of the panel a user is given to read a dense critical-path network
  in currently sits empty.
- **Upload / empty state** — a dashed-border drop-zone with a centered `+` icon and "Drop a file
  here, or click to browse" is the single most-cloned empty-state pattern in SaaS onboarding
  (screenshot-confirmed). It's not broken, but it's the part of the app most likely to make a
  first-time viewer conclude "generic template" before they've even loaded data.

### 7. Other things a product designer would flag on sight

- **Gray-box sameness across unrelated content types** (§3) is the single most fixable
  "boilerplate" signal in the app — more so than color, because it's structural: five different
  kinds of content (KPI, watchlist table, inline expando, node detail panel, tree wrapper) using
  one undifferentiated card recipe.
- **Every secondary/tertiary text color in the app is the same `#888`** (`.header-meta`,
  `.subtitle`, `.stat-card span`, `.data-table th`, `.rel-type`, `.node-meta`, etc.) — convenient,
  but it means there's no muted-text *scale*, just one gray used for wildly different jobs (column
  headers, help text, metadata, disabled-feeling labels).
- The app has no distinct **data-ink identity** — nothing about the way numbers, codes, or dates
  are set typographically says "this is a scheduling engine's output" the way, say, monospaced
  tabular figures with a slightly technical/blueprint feel would.

---

## Part 2 — Spec for next sprint

Scope note: this is a solo-maintained internal tool. The spec below is a **token set + concrete
per-component direction**, not a component library. No dark mode, no animation framework, no new
dependencies beyond (optionally) a self-hosted variable font.

### 2.1 Color palette

Design intent: move off "flat pastel dashboard" toward "technical instrument" — closer to what
P6/MS Project/a blueprint actually look like: mostly ink and graphite neutrals, one restrained
brand hue, and semantic color reserved *exclusively* for float/criticality state, used identically
everywhere it appears.

```
/* Brand / structural */
--ink:            #14213D   /* primary text, headers, dark toolbar surface — deep navy-black, not pure black */
--ink-soft:       #2B3A5A   /* secondary ink, hover states on dark surfaces */
--accent:         #2E5C8A   /* single brand/interactive blue — links, active tab, progress fill, "normal" bar/node */
--accent-soft:    #DCE6F0   /* accent tint for selection backgrounds, hover fills */

/* Semantic state — used identically in Gantt bars, network nodes, table rows/badges */
--crit:           #B3261E   /* critical / TF=0 — a "safety red," less candy than Alizarin */
--crit-tint:      #F8E3E1   /* critical fill/tint */
--near:           #9C6B00   /* near-critical / low float — dark goldenrod, not Sunflower yellow */
--near-tint:      #F6ECD2   /* near-critical fill/tint */
--ok:             #3F7355   /* completed / on-track — muted sage green, not Nephritis */
--ok-tint:        #E1EBE4   /* completed fill/tint */
--milestone:      #6A3E9E   /* milestone marker — kept purple family but darker/less saturated than Wisteria */

/* Neutrals (graphite scale — replaces the ad hoc #888/#ccc/#e8e8e8/#f8f9fc soup) */
--gray-900:       #14213D   /* = ink, body text */
--gray-700:       #445070   /* secondary text (labels, meta) — was #888, now on-hue with ink */
--gray-500:       #7C86A3   /* tertiary text, placeholder, disabled */
--gray-300:       #D3D8E4   /* borders, dividers */
--gray-150:       #EEF1F6   /* zebra stripe, subtle surface */
--gray-100:       #F6F8FB   /* card/panel background */
--white:          #FFFFFF   /* page background */
```

**Why this fixes the core problem:** none of these values match Flat UI Colors, Bootstrap, or an
Office theme (verify: `--crit` #B3261E, `--near` #9C6B00, `--ok` #3F7355, `--accent` #2E5C8A are
all off the common stock lists). The neutrals are tinted toward `--ink`'s navy hue instead of
true grays, so "gray boxes" throughout the app will read as belonging to one coherent surface
system instead of a generic Bootstrap-panel gray. Critical/near/ok are deliberately desaturated
("safety signage" red/amber/green rather than "flat design" candy versions) — more legible at a
glance across a dense schedule, and closer in spirit to how P6/MS Project signal risk than how a
marketing dashboard signals "success."

**Rule to enforce in implementation:** `--crit` / `--crit-tint`, `--near` / `--near-tint`, `--ok` /
`--ok-tint` are the *only* colors allowed to represent criticality/float/status, in every one of
the three surfaces (Gantt bars, network nodes, activity table). No component gets to invent its
own red. This directly fixes the Alizarin-vs-Pomegranate inconsistency documented in §1.

### 2.2 Typography

```
--font-ui:   "IBM Plex Sans", -apple-system, "Segoe UI", Roboto, sans-serif;
--font-mono: "IBM Plex Mono", "SF Mono", "Fira Code", ui-monospace, monospace;
```

IBM Plex is free, self-hostable (two woff2 files, no build-step complexity — a `<link>` to
Google Fonts or a local `@font-face` is enough for a Vite dev app with no bundler concerns), and
carries an actual "engineering tool" association (IBM's own products) rather than reading as
generic system-ui. Fall back to the existing system stack so nothing breaks offline.

Apply `--font-mono` to: activity/task codes, all dates, all durations, all float values, all
percentages — i.e. every *number* in the app, not just the code column. Use
`font-variant-numeric: tabular-nums` on mono numeric cells so table columns align on digits (fixes
the ragged-column issue in §2).

Type scale (replaces the current per-component ad hoc sizes):

| Token | Size | Weight | Use |
|---|---|---|---|
| `--text-h1` | 22px | 700 | Project name (page header) |
| `--text-h2` | 16px | 700 | Section titles: "Gantt Chart", "Critical Path", card headers |
| `--text-body` | 13px | 400 | Table cells, activity names, default UI text |
| `--text-small` | 12px | 500 | Metadata, subtitles, toolbar labels |
| `--text-micro` | 10px | 600, uppercase, `letter-spacing: 0.04em` | Column headers, tiny badges/pills |

One h1, one h2, three text sizes total — down from the current ~7 uncoordinated combinations.
Every component's title picks `--text-h2`, not its own bespoke `font-size`.

### 2.3 Spacing & radius tokens

```
--space-1: 4px;
--space-2: 8px;
--space-3: 12px;
--space-4: 16px;
--space-6: 24px;
--space-8: 32px;

--radius-sm: 4px;   /* buttons, inputs, badges, bars */
--radius-md: 8px;   /* cards, panels, table wrap — the one "container" radius */
--radius-pill: 999px; /* status pills only, and only if kept — see 2.4 */
```

Two radii for 95% of the app (`--radius-sm` for controls/marks, `--radius-md` for containers)
replaces the current ten ad hoc values. All padding becomes a `--space-*` value — no more bespoke
`14px 18px` / `10px 14px` / `12px 16px` per component.

### 2.4 Component-by-component redesign direction

**Stat-card row → single metrics strip.**
Replace the 7 bordered/shadowed cards with one `--radius-md` band, `--gray-100` background, no
per-item border, no hover animation. Lay out as a flex row with a 1px `--gray-300` vertical
divider between items (not per-item boxes). Cut from 7 items to 5: drop "Earliest start" /
"Latest end" as standalone tiles and fold them into the header subtitle instead ("483 activities
· 09 Aug 2026 → 21 Oct 2027"), since a date range doesn't carry the same "headline KPI" weight as
Activities/Critical/Longest Path/Milestones/% Complete. Numbers use `--font-mono`, tabular-nums,
`--text-h1`-equivalent weight; labels use `--text-micro`.

**Tabs.** Keep the underline pattern (it's the one part of the app that doesn't need reinvention)
but set the active underline to `--accent` at 3px (up from 2px) and remove the light→dark→light
value flip into the Gantt by softening the toolbar per below.

**Unicode icons → one small inline SVG set.** Replace `▼ ▶ ▲ ◆` everywhere with a single reusable
12×12 SVG chevron (stroke 1.5, `--gray-700`, rotates 90° via CSS transform for expand/collapse
rather than swapping glyphs) and a single SVG diamond/rhombus for milestones, used identically in
`GanttChart.vue`, `CriticalPathGraph.vue`, and the legend — not a Unicode ◆ in one place and a
CSS-rotated `<div>` in another. This is the single highest-polish-per-effort fix in this spec:
it's ~2 small SVG partials swapped into 5-6 call sites.

**Buttons.** Two variants only:
- *Ghost/toggle* — no border, `--gray-700` text, `--accent-soft` background + `--accent` text
  when active. Used for all toolbar controls (zoom levels, critical-basis toggle, Links checkbox
  label, Expand/Collapse/Today/Fullscreen) — grouped into visually distinct segmented-control
  clusters (a single pill-shaped container per group, not N individually-bordered buttons).
- *Outline* — `--gray-300` border, used only for page-level actions: Export to Excel, Load
  another, Export view (.csv). Reserve this heavier treatment for the ~3 buttons in the whole app
  that leave the current view or produce a file.

**Dark Gantt toolbar → commit further, but smaller.** Don't run the full-height toolbar+legend+
timeline-header stack as one giant dark block dropped into a white page. Shrink the dark surface
to a single 40px strip holding only the title and the critical-basis toggle (the two highest-value
items). Move zoom/links/expand/collapse/today/fullscreen down into the legend bar, which stays
light (`--gray-100`) and directly adjoins the light timeline header below it — eliminating the
hard light/dark/light seam because the dark strip is now a thin, clearly-intentional banner
rather than a large panel that has to justify its size. Use `--ink` for that strip's background
(not the current near-black `#1a1a2e`, which has no relationship to any other app surface) so it
matches the new palette's ink token.

**WBS tree rows.** Add a 1px `--gray-300` left border per indent level (a depth guide-line, like a
file-tree/IDE explorer) instead of relying on padding alone to communicate depth. Render
`wbs_short_name` as a small `--font-mono` chip (background `--gray-150`, `--radius-sm`) followed
by `wbs_name` in normal weight — matching the activity table's existing `.code` monospace
convention instead of inventing a bold/gray split unique to this component. Right-align the
activity count as a small `--gray-150` pill immediately next to the row content (not floated to
the far edge of a 1600px-wide row). Add zebra striping (the Gantt's own WBS column already does
this — bring the dedicated WBS Tree tab up to that bar).

**Activity table status badges.** Swap the fully-rounded pill (`--radius-pill`) for
`--radius-sm`, matching every other small mark in the app. Use the new `--ok`/`--near`-family
tints (`--ok-tint` for Complete, a neutral `--gray-150` for Not Started — Active doesn't need to
borrow the near-critical amber at all, since it has nothing to do with float; give Active its own
neutral-accent treatment, e.g. `--accent-soft`/`--accent`, to stop it colliding conceptually with
the near-critical semantic elsewhere in the app). Add a small leading 6px dot in the same color as
the text, so status is legible by shape/position even under color-vision deficiency, not by hue
alone.

**Network diagram nodes → activity-on-node (AON) box, not a rounded card.** Redraw the SVG node
template: square-ish corners (`rx=2`, not `9`), a thin top divider under the code/duration row, and
a bottom strip split into two cells (Start date | Float) separated by a 1px vertical rule —
referencing the classic AON activity-box convention instead of a Trello-style card. Code in
`--font-mono` bold, name in `--font-ui` at `--text-small`, bottom strip in `--text-micro`. This is
the one recommendation in this spec that's about *domain credibility* specifically — it's the
difference between "this app knows what a PM diagram looks like" and "this app used the nearest
generic node-graph library default."

**Network diagram canvas usage.** Flag for the implementer to re-check the `ranksPerRow` /
`resetView` scale math (`CriticalPathGraph.vue` lines ~253-266, ~448-463) — the wrapped layout
should target filling ~85-90% of `canvasWidth` per row before wrapping, and `resetView`'s
`Math.min(...)` scale-to-fit should not let a very tall (many-row) graph collapse horizontal
usage as a side effect of fitting height. Screenshot evidence in Part 1 shows roughly 60-70% of
the visible canvas sitting empty on a 483-activity file at default "Fit" zoom — this is a
readability bug worth fixing alongside the visual node redesign, not just a style note.

**Upload/empty state.** Lower priority (it's seen once per session), but if touched: drop the
generic dashed-border-plus-`+`-icon drop-zone for a solid `--gray-300` 1px border (not dashed —
dashed borders are themselves a strong "placeholder/unfinished" signal) with the Gantt-style
logo icon already in use, and keep the copy as-is (it's fine).

### 2.5 What NOT to do (scope guardrails)

- No dark mode toggle — the one dark surface should be the trimmed Gantt toolbar strip only,
  per above, not a whole-app theme.
- No animation/transition framework — keep the existing simple CSS transitions (hover, expand),
  don't add a motion library.
- No component library extraction — apply these tokens as CSS custom properties in the existing
  global `<style>` block in `App.vue` plus scoped styles in each component; this is a token
  refresh + per-component redraw, not an architecture change.
- No new build tooling — IBM Plex can be added via a `<link>` tag or a couple of self-hosted
  woff2 files; nothing here requires webpack config changes or new npm dependencies beyond fonts.
