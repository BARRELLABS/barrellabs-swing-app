# Swing Report Redesign — Detailed Plan

> Goal: the swing report looks and feels like a single-swing version of the
> Dashboard (dense, rich, premium), not a short basic document. Renders in an
> iframe (already switched) so SVG gauges/radars/gradients all work.
> Status: PLAN for approval. No code changes until approved.

---

## 0. Why it kept looking basic (root causes, now understood)

1. **It was rendered with `st.html`** which strips `<svg>` and flattens
   everything. FIXED: it now renders in a `components.html` iframe like the
   dashboard, so gauges/gradients/radars render.
2. **The hero is one near-empty card.** The dashboard hero is a DENSE 3-column
   band (score ring + per-category rail | big headline + deck | info card). The
   report only shows a comp card + a gauge with whitespace. That is the "basic,
   boring top."
3. **The report shows a fraction of the data it has.** The record carries 4
   strengths, per-axis match % vs the pro, full swing-phase timing, and the
   complete metric table. Most isn't shown, so it reads "too short."

The redesign fixes 2 and 3 by mirroring the dashboard's components and using all
the data.

---

## 1. Design system (mirror the dashboard exactly)

Reuse the dashboard's tokens so it's visually a sibling:
- **Palette:** near-black `#0A0B0E` bg, bone `#F4EFE6` text, gold `#E8C170`,
  red `#E64530`, green `#4AE38C`, glass cards `rgba(255,255,255,0.02-0.045)`.
- **Type:** Geist (UI), Geist Mono (all numbers, tabular), Instrument Serif only
  as a rare accent. Section eyebrows = mono uppercase `§ NN · Label`. Headlines =
  condensed uppercase sans. Numbers dominate.
- **Cards:** 1px hairline borders, large radius, subtle top-gradient sheen, the
  same hover/active feel as dashboard cards.
- **Section heads:** `§ NN · EYEBROW` + big title + right-aligned sub, identical
  to the dashboard's `.section-head`.

---

## FINAL RENDER ORDER (least scrolling to what matters)

1. **Hero** — score gauge + headline + Mike Trout match card (dense 3-col).
2. **Where to spend your next session** — top fixes (color-coded) + drills. ← actionable, right under the hero.
3. **What you crushed** — strengths.
4. **You vs Mike Trout** — radar.
5. **Kinetic chain / timing** — phase strip.
6. **Biomechanical readout** — metric tiles with gauge bars.
7. **Full breakdown** — COLLAPSIBLE table (collapsed by default).
8. **Next session** — closing training-plan CTA.

(The lettered sections below describe each block in detail; render them in the
numeric order above, not alphabetical.)

## 2. Layout, section by section

Each section lists: **what it is**, **the data behind it (real example from your
Trout/62 swing)**, and **the dashboard component it mirrors**.

### A. Masthead + issue line  (mirrors dashboard masthead + `.issue-line`)
- Eyebrow `PREMIUM SWING REPORT`, big title `SWING No. 7` (or `LATEST SWING`),
  right side `CAPTURED Jun 09, 2026 · vs MIKE TROUT`.
- Thin issue line under it: `Swing Report · Logan Collins · RHH · IMG_8601` ·
  `Decent match` · `Jun 09 2026`.

### B. HERO — dense 3-column band  (mirrors dashboard `.hero`)  ← the big fix
Three columns, like the dashboard, so the top is full and rich:

**Left col — Swing Score gauge + category rail:**
- The big gold gauge ring (SVG) `62 / 100`, band color = amber.
- Below it, a 6-row category rail with per-area match % (mono, peak rows in
  gold), straight from `strengths` + `metric_table`:
  `MLB match 62 · Head stability 99 · Front-side firm 83 · Timing 67 · Hip rotation 65 · Re-extension 27`.
  (This is the report's version of the dashboard's `.edge-score-cats`.)

**Center col — headline + deck + meta:**
- Eyebrow `§ 01 · This swing's headline`.
- Auto-generated headline from the #1 fix, e.g.
  `Your front leg is the unlock — Trout territory is close.` (mirrors the
  dashboard's `.hero-headline`, condensed uppercase, the key word in gold).
- Deck paragraph = the #1 narrative's "why it costs you" line in plain English.
- Meta row: `Swing length 67ms · Match Mike Trout · Captured Jun 09`.

**Right col — Match card (Mike Trout):**
- Mirrors the dashboard `.tier-card` but as the MLB Match card: gold-ringed `MT`
  avatar, `MIKE TROUT`, `Atlanta · OF`, a band track showing where this swing
  sits (`Rebuild → Decent → Strong → Elite`) with a marker at the score, and
  `Swing Score 62 · next band Strong at 75 · +13`.

### C. § 02 · You vs Mike Trout — radar  (mirrors dashboard `.comp-radar`)
- A pentagon/hex **radar (SVG)** plotting your shape vs Trout across the 5 axes
  you measure: Rotation, Timing, Head stability, Front-side firmness, Sequencing.
  Two overlaid polygons (you = gold, Trout = bone outline), real `sim_pct` per
  axis (Head 99, Front-side 83, Timing 67, Hip rotation 65, Re-extension 27).
- Beside it: delta lines — `You match Trout on head stability and front-side
  firmness. Close the gap on re-extension (−19°) and hip rotation (−19°).`

### D. § 03 · What you crushed — strengths  (NEW, mirrors dashboard stat cards)
- 3–4 strength cards from `strengths`, each: category label, your value vs
  Trout, and a green match bar. Real: `Head stability 99% · ~1in vs ~1in`,
  `Front-side firmness 83% · +158° vs +153°`, `Timing & tempo 67%`,
  `Hip rotation 65%`. This is the encouraging "you're already pro-level here"
  section that's currently missing.

### E. § 04 · Where to spend your next session — fixes + drills  (mirrors `.coach-grid`)
- Two columns. Left = top fixes, color-coded severity rail (red = major gap,
  gold = worth fixing), each with the plain-language `why it costs you` +
  `what it feels like` copy you already wrote. Right = recommended drills with
  `DRILL 0N` thumbnails + reps. (This part you said already looks decent — keep,
  just align styling to the dashboard cards.)

### F. § 05 · Kinetic chain / timing — phase strip  (NEW, mirrors `.velocity-ladder`)
- A horizontal swing-phase timeline built from `phases_t`
  (load → foot plant → launch → contact → finish) with the ms between each, and
  a callout on the slow/fast link. Turns the timing fix into a visual.

### G. § 06 · Biomechanical readout — metric tiles  (keep, already good)
- The 4 key-metric tiles with the `% match to Trout` gauge bars
  (Hip Rotation 53%, Hip-Shoulder Sep 42%, Bat Timing 43%, Contact Timing 67%).

### H. § 07 · Full breakdown — COLLAPSIBLE  ← you explicitly want this
- A `<details>`/`<summary>` collapsible **inside the iframe** (pure HTML/CSS/JS,
  no Streamlit expander needed): summary row `Full breakdown · every measurement
  vs Mike Trout ▸`, collapsed by default. Expands to the full table (every
  metric, your value, Trout's, status). The iframe height accounts for both
  states (JS posts the new height on toggle, or we size for expanded).

### I. § 08 · Next session — training plan  (keep)
- Numbered action cards (Master the fix · Run the drill block · Re-film in 7
  days). Already looks right.

---

## 3. The collapsible (how, inside an iframe)

Use native `<details class="srd-collapse"><summary>…</summary>…table…</details>`
styled to match the app (rotating caret, hairline border, hover). On `toggle`,
a tiny script measures `document.body.scrollHeight` and `postMessage`s it to the
Streamlit parent, which updates the iframe height (same bridge the dashboard
uses). Fallback: size the iframe for the expanded state so it never clips.

---

## 4. Height / whitespace

The dashboard accepts a fixed-ish iframe height. We compute height from content
(sections + breakdown rows) and, with the collapsible, post height on toggle so
there's no large trailing whitespace in the collapsed state.

---

## 5. Data map (everything is real, already in the record)

| Section | Record fields |
|---|---|
| Hero score + cats | `score`, `score_band_*`, `strengths[].sim_pct`, `metric_table` |
| Hero headline/deck | `narratives[0].title` + `paragraphs` |
| Match card | `reference_name`, `score` → band ladder |
| Radar | per-axis `sim_pct` from `strengths` + `metric_table` |
| Strengths | `strengths[]` (label, player_str, ref_str, sim_pct) |
| Fixes + drills | `narratives[]`, `drill_plan.categories[]` |
| Phase strip | `phases_t`, `swing_duration_ms` |
| Metric tiles | `metric_table` (sim_pct → gauge bars) |
| Full breakdown | `metric_table` (all rows) |
| Next session | `drill_plan.weekly_guide`, top fix |

Everything degrades gracefully if a field is missing (older swings).

---

## 6. Build order (once approved)

1. Hero 3-column band (left rail + headline + match card) — the biggest visual win.
2. Radar (you vs Trout).
3. Strengths section.
4. Phase/timing strip.
5. Collapsible full breakdown.
6. Polish: spacing, height-on-toggle, mobile stack.
Verify each step in the iframe with your real Trout/62 data via Playwright
before moving on. Nothing pushed until you approve the result.
