# Swing Score + MLB Match — "Identity + The Climb" Design Spec

**Date:** 2026-05-23
**Status:** APPROVED by founder (2026-05-23); open decisions resolved (see end); ready for implementation plan
**Supersedes:** the current pro-similarity scoring in `analyzer.py` / `reference_library.py`

## Goal
Re-architect the swing analysis — the product's bread-and-butter — into **two independent systems** that reinforce each other:
1. **MLB Match** — *who you swing like* (the viral hero), the real pro name, matched on movement, locked on the first swing.
2. **Swing Score** — *how good your swing is + what to fix* (the credible engine), an independent, age-fair, principle-based 0-100 grade that climbs as you improve.

## Why we're replacing the current engine
Today `analyzer.py` sets `overall_score = mean similarity to ONE pro × 100`, and the metrics least similar to that pro become the faults/drills. Two problems:
- **The pro is matched arbitrarily.** `reference_library.py::_match_score` ranks pros on handedness + camera-view delta + rotation method only — none describe swing shape. Worse, all 17 references share `rotation_method = "2d_width_ratio"`, so that term (weighted ×3) is always zero, and the camera-view term (×2) literally rewards matching *how the phone was held*. The match tracks the camera, not the swing.
- **Grading youth by deviation-from-an-adult-pro is unsound.** The 17 pros disagree wildly (hip-shoulder separation ranges −38° to +54° across them); a 10-year-old *should* differ from a 6'7" adult, so "you differ from Judge" flags normal development as a fault. Every serious competitor (Blast, Diamond Kinetics, K-Vest) grades against absolute, age-banded standards — none use single-pro similarity.

Market research is equally clear the MLB comparison must STAY the hero: *"MLB Similarity Score as hero, not feature — the entire top-of-funnel marketing wedge, the most viral, shareable, differentiated component."* No competitor has it.

So: keep the Match as the central viral hero, but make it a *real movement match* you can model after; move all diagnosis to an independent, age-fair Swing Score.

---

## The two systems + the weave

| | MLB Match (hero) | Swing Score (engine) |
|---|---|---|
| **Question** | Who do you *move* like? | How *good* is your swing + what to fix? |
| **Basis** | Scale-invariant movement shape | Absolute good-swing principles, age-fair |
| **Output** | A real pro name ("You swing like Juan Soto") | 0-100 grade + 4 pillar sub-scores |
| **Over time** | **LOCKED** on first swing — never changes | **CLIMBS** as the kid improves |
| **Drives** | Identity, sharing, aspiration | All diagnosis + drills |
| **Never** | a grade or a fault | tied to one pro |

**The weave (resolves the climb-vs-stable contradiction):** the **Swing Score is what climbs**; the **MLB Match stays locked**. The locked pro is the **aspirational face of every fix** — each drill carries one short, motivating pro-relative line — but the drill is always chosen by the absolute Score, never by pro-difference. The reconciliation line, shown between the two on every report:

> **"Your Match is who you move like; your Swing Score is how well you're executing it — you grow your Score, not your Match."**

---

## System 1 — The Swing Score Engine

Independent, age-fair, principle-compliance grade built ONLY from 2D-phone-reliable signals already on the fingerprint (`detect_phases.py`). Each pillar yields a **compliance** score in [0,1] and a **confidence** in [0,1]; confidence down-weights the pillar in aggregation but never alters the compliance value. v1 is **compliance-only — no fabricated youth percentiles** (we have no youth dataset).

### Pillar 1 — Sequence (kinetic chain: hips lead → torso → hands)
- **Signal:** reuse `sequence.sequencing_lag_ms` (`biomech.compute_sequence`). Do not recompute.
- **Direction:** hips peak before shoulders = good. (`lag >= 0` good; `−50..0` nearly synced; `< −50` casting.) 2D compresses magnitude, so DIRECTION is trusted, never a precise ms.
- **Compliance:** soft ramp — 1.0 at `lag >= 0`, ~0.6 at −50ms, ~0.1 strongly negative (continuous so the score climbs as casting reduces).
- **Age-fairness:** widen the "synced" band for 8-10 (e.g. −70..0).
- **Confidence:** halve when `rotation_view_sensitive` (mixed method / `view_diff > 0.45`); 0 if lag suppressed.

### Pillar 2 — Stability (quiet head/posture)
- **Signal:** `head_movement_normalized_foot_plant_to_contact.total_drift_torso` (already torso-normalized, camera-distance invariant).
- **Direction:** less drift = better.
- **Compliance:** ~1.0 at `<=0.15T`, ~0.5 near `0.35T`, ~0 past `0.6T`.
- **Age-fairness:** allow ~0.25T before penalty for 8-10.
- **Confidence:** scale by nose/shoulder visibility (reuse `LOW_VISIBILITY_THRESHOLD`); rarely suppressed (most camera-robust pillar).

### Pillar 3 — Timing / Tempo
- **Signal:** `timing_ms` (prefer `timing_ms_corrected` for slow-mo): load_duration, foot_plant_to_launch, launch_to_contact, total_swing.
- **Direction:** judged as *ratios/tempo*, NOT absolute speed — a crisp gather→fire (load substantially longer than the explosive launch_to_contact) = good.
- **Compliance:** score the `load_duration : launch_to_contact` ratio against a target band with soft shoulders; corrected ms so slow-mo scores identically.
- **Age-fairness:** widen bands for younger brackets (longer downswings are normal).
- **Confidence:** from phase-detection certainty (`score_foot_plant/launch/contact_confidence` in `phase_debug.py`); suppress on multiple-contact/toe-tap warnings.

### Pillar 4 — Stride / Base (front-side firmness)
- **Signal:** stride direction/length (`phases_t` foot motion + `stride_px`) + `knee_deg.re_extension` (front-leg brace).
- **Direction:** controlled forward stride + front knee that re-extends into contact = good.
- **Compliance:** soft ramp on re_extension degrees + a stride-direction sanity gate (toward pitcher).
- **Age-fairness:** lower the re-extension anchor + widen stride tolerance for 8-10.
- **Confidence:** front-ankle visibility; suppress when handedness confidence is low (`handedness_auto_ratio < 1.3`) since front/back may be swapped.

### Aggregation, label, exclusions
- **Score (0-100)** = confidence-weighted mean of compliance across *available* pillars: `round(100 × Σ(compliance×confidence)/Σ(confidence))`. Pillars with confidence 0 drop out (never score 0 and drag the swing down).
- **Overall confidence label** (green/yellow/red) from mean pillar confidence — a first-class badge.
- **User-facing:** a grade *for the kid's age* ("Solid for 10U" / "Building" / "Needs work — clear fixes"), **NOT a percentile** in v1.
- **Excluded (and why):** absolute velocities / bat speed / exit velo (need sensors — "Barrel Lock"); `peak_hip_omega_deg_s` + `front_side_stability_pct` (read backwards / uncomputable from 2D — kept in the fingerprint for later sensor use, never surfaced); rotation magnitudes when `rotation_view_sensitive`; fabricated youth percentiles.

---

## System 2 — The MLB Match Engine

Answers only *which real MLB hitter does this kid move like?* It is the prominent hero on every result, **descriptive identity only** — never a grade, category, or fault. Scale-invariant so a 4'8" kid genuinely matches a 6'7" pro.

### Scale-invariant movement feature vector
~8 dimensionless features derived from fields present on **both** player fingerprints and pro references (`timing_ms`, `rotation_deg`, `knee_deg`, `head_movement_normalized_*`, `phases_t`) — no pixels, no raw degrees-as-magnitude, no body size:
1. `load_ratio` = load_duration / total_swing (tempo)
2. `plant_to_launch_ratio` = foot_plant_to_launch / total_swing
3. `launch_to_contact_ratio` = launch_to_contact / total_swing
4. `sep_timing_frac` = when peak separation occurs as a fraction of plant→contact
5. `sep_retention` = separation_at_contact / peak_separation (power↔contact)
6. `rotational_linear_lean` = peak_hip / max(|peak_separation|, ε)
7. `knee_extension_ratio` = re_extension / (at_foot_plant − min_during_load + ε)
8. `head_drift_ratio` = total_drift_torso (already dimensionless)

Z-scored against the pro distribution (frozen constants); Euclidean distance. Handedness is already mirror-normalized upstream, so it's dropped from matching.
> **Implementation note:** exact field names (e.g. `rotation_deg.peak_separation_t`, `separation_at_contact`) MUST be verified to exist on BOTH the player fingerprint and the pro reference JSONs during build; substitute equivalents where a field is player-only (the `sequence` block is player-only and is NOT used in this vector).

### Clustering → real pro name (robust with 17 exemplars)
Pre-compute ~3 style clusters (k-means, frozen offline) over the pro z-vectors (e.g. rotational/loaded, linear/contact, quick/compact). At match time: assign the kid to the nearest cluster centroid (stable coarse decision), then pick the nearest **individual pro within that cluster**. The user sees only the **real pro name** — never the cluster label.

### Lock (already wired — reuse, don't rebuild)
`players.locked_mlb_slug` exists end-to-end (`auth.py`, persisted via `app.py` `_save_lock`). On the first swing with no lock, run the new vector match and store the slug. Every later swing replays the locked slug — the match is computed **once**. Manual sidebar override continues to bypass the lock without mutating it.

### Camera-confidence gating + the % framing
Camera angle is removed from *matching* but reused for *confidence*. When stance ratio is in the well-conditioned band (~0.33–0.45) and the view isn't flagged sensitive, show the pro name **plus a quiet "movement match" %** clearly labeled as *how closely your movement matches* — never a 0-100 grade, never red-banded. When confidence is low, show the **name without a %** plus a "film a cleaner side-angle to confirm" nudge (never a blank hero). **The pro name is always the hero; the % is a quiet sub-label.**

### Migration
Replace `_match_score`'s body with the z-scored vector distance; keep `find_best_match` / `find_all_ranked` signatures. **Existing users keep their locked pro** (re-rolling would break their training journey); only recompute on explicit "re-match" or for accounts with no lock.

---

## Diagnosis, Drills & Language

### Faults from the Score only
Faults derive **exclusively** from the Score's weakest **confident** pillar(s) (lowest 1-2). A low-but-not-confident pillar is skipped, not diagnosed. The MLB Match is NEVER an input to `build_drill_plan`. This is a real refactor: `drills.py` today consumes `gaps_ranked` (sorted by similarity to `ref_name`) — that input must be re-sourced from the Score pillars, and `ref_name` dropped from diagnosis copy. `classify_gap` routing stays; only its input changes.

**Pillar → existing drill category mapping:**
| Pillar | Primary category | Folds in |
|---|---|---|
| Sequence | `sequencing` | `hip_shoulder_separation`, `hip_rotation`, `rotational_speed` |
| Stability | `head_stability` | `front_side_stability` (when upper-body fly-out) |
| Timing/Tempo | `timing` | — |
| Stride/Base | `knee_extension` | `front_side_stability` (when front-side firmness) |

Keep `build_drill_plan`'s weight = 5−rank, top-2 categories, and `GOAL_CATEGORY_BOOSTS` tie-break (boost only already-surfaced categories) — but `rank` is now pillar-weakness rank.

### Light pro-relative drill line (founder requirement — motivation only)
Every fix card gets ONE short line: *"This one tightens the move that gets you closer to how {PRO} {pillar_verb}."* (verbs: Sequence→"sequences", Stability→"stays quiet on the ball", Timing→"stays on time", Stride→"lands and braces"). Rules: one line per card; `{PRO}` = locked match; the drill is still chosen by the absolute Score; **never** phrased as a fault ("you don't sequence like {PRO}" is banned). This is the only place the pro name touches diagnosis copy.

### External-focus cues (science-backed for youth) — replace internal cues
| Fault | External cue (required) |
|---|---|
| Casting / poor sequence | "Make the bat stay back until the last second, then whip the barrel straight at the ball." |
| Flying open | "Keep your front shoulder pointed at the pitcher until the ball's almost there, then fire the barrel through the line." |
| Weight transfer / stride | "Land soft, then push the ground away so the bat launches up and out." |
| Head movement | "Keep your eyes glued to the contact spot so you can read the ball the whole way." |
Internal cues allowed only inside numbered drill `how` steps, never in the player-facing "what the fix feels like" line.

### Plain language (kill jargon in player-facing copy)
| Jargon | Plain |
|---|---|
| kinematic sequence / kinetic chain | the order your body fires — hips, then chest, then hands |
| hip-shoulder separation / X-Factor | the stretch between your hips and shoulders before you swing |
| knee re-extension | front leg straightening back up at contact |
| torso-relative head drift | how much your head moves compared to your body |
Jargon allowed only in internal labels / an optional "for parents" expander. (`DRILL_DB` `why_it_matters` + `_narrate_*` strings hardcode these terms — edit or add a presentation-layer translation.)

---

## Report UX, Data Model & Must-Haves

### Report order (replaces today's co-equal two-card hero)
1. **MLB Match reveal** — full-width hero at the very top: pro name + headshot/initials, team/position, descriptive style identity ("Explosive rotational hitter — you swing like Juan Soto"); renders the LOCKED pro from the saved record (not a fresh pick); quiet "movement match" % only when confident.
2. **Swing Score** — the ring + 0-100 + band + Δ-vs-prior; pillar mini-bars (Sequence/Stability/Timing/Stride) replace the old pro-similarity radar; **"What you did well"** positive line renders BEFORE any fix.
3. **The reconciliation line** sits between (1) and (2).
4. **Top fixes + drills** — from the Score's weakest pillars; each with an external cue + the one light pro-relative line.
5. **You-vs-your-pro overlay** — aspiration; reframe the existing compare machinery against the locked pro at synced foot-plant.
6. **Share + track-the-climb** — Match is the constant, Score is the line that climbs.

### Must-haves
- **Per-reading confidence badge (green/yellow/red)** on the Score card AND per-pillar (head/rotation/sequencing degrade independently). Red = down-weight that pillar AND say so ("Couldn't read your hips cleanly from this angle — re-film for an accurate Sequence score"). Never fake or freeze a number to hide low confidence.
- **"Film it like this" guide** — pre-upload one-screen card AND auto-injected inline above fixes whenever any pillar badge is yellow/red: **120/240fps slow-mo, ~45° three-quarter angle, full body in frame, good light.** Biggest reliability lever.
- **"What you did well"** — mandatory positive line every report, from the highest-confidence/highest-scoring pillar; if none clears the strength bar, fall back to an effort/identity line tied to the Match (never empty/negative).

### Data model (`analyze()` result)
- Remove `overall_score = pro-similarity` as the headline.
- Add: `swing_score:int`; `pillars:{sequence|stability|timing|stride:{subscore, confidence, confidence_reason}}`; `mlb_match:{pro_name, slug, style_fit_pct, identity_label, locked}`; `style_vector:list[float]` (persisted on the saved swing so re-renders never re-match); `what_you_did_well:str`.
- **Renderer:** split `_build_hero` → `_build_match_reveal` (card 1) + `_build_score` (card 2); add the reconciliation caption; replace the similarity radar with pillar bars; add `_build_confidence_badge`.
- **Backward-compat:** old saved swings lack the new fields — `swing_score = record.get("swing_score") or record.get("score")`; hide pillar bars if absent; derive a read-only Match card from the legacy `reference` block with `style_fit_pct` omitted. Never invent a number; never crash.

---

## Phasing
- **v1 (ships first):** principle-based Swing Score (4 pillars, compliance + confidence, NO percentiles); movement-based MLB Match + clustering + lock reuse; drills wired ONLY to the Score; report in the new order with reconciliation line; confidence badge; "film it like this"; "what you did well"; external cues + plain-language pass; pro-relative drill line. Refactor `analyzer.py` to stop using pro-similarity as the score and `drills.py` to source faults from pillars.
- **v2:** age-percentile overlay (age × handedness × camera-view buckets) shown *beside* the compliance Score once N is sufficient — without changing v1 scores; "The Climb" history view; per-pillar deltas on re-upload; you-vs-pro overlay polish.
- **v3:** expand the pro library to sharpen archetypes; optional multi-angle capture to lift Match/rotation confidence; longitudinal age-progression curves.

## Risks (honestly unresolved)
1. **Youth biomechanics norms are thin** — v1 age-widened bands are principled estimates, not validated youth science; model risk until v2 percentiles arrive (from real data).
2. **2D degrades at oblique angles** even with gating — some legit swings return low-confidence/muted reports (a quality tax we mitigate, not eliminate).
3. **17-pro archetypes are coarse** — a kid near a cluster edge may get a borderline match; cluster-first + confidence gating reduces but doesn't remove flicker.
4. **Score↔Match independence is designed, not proven** — if, in real youth data, movement-style and quality correlate strongly, the two-number distinction could blur; monitor their correlation and re-purify the Match if it leaks magnitude.
5. **Field-schema mismatch** — the Match vector assumes fields exist on both player + reference JSONs; must be verified in build (see implementation note).

## Testing strategy
- **Unit:** each pillar compliance curve (direction + soft ramps + age bands); confidence down-weighting/suppression; aggregation drop-out of zero-confidence pillars; Match vector is scale-invariant (scaling a swing's size leaves the vector unchanged); cluster assignment is stable across camera angles for held-out pros; lock persists + replays.
- **Calibration:** re-run the pro-vs-amateur cohort — amateurs should score lower on the weak pillars; the Match should land each held-out pro in a sensible cluster.
- **Snapshot:** report renders the new order, reconciliation line, confidence badges, "what you did well"; backward-compat render of a legacy saved swing (no crash, no fake numbers).
- **Manual:** founder reviews real youth uploads for face-validity of both the pro match and the diagnosis.

## Resolved decisions (founder, 2026-05-23)
1. **Age brackets:** **8-10 / 11-12 / 13-14 / 15-17** — the four pillars' compliance bands widen/lower-anchor per bracket.
2. **Match display:** show the **pro name PLUS a quiet "movement match %"** — rendered ONLY when camera-angle confidence is adequate, clearly labeled as a *movement match* (never a 0-100 quality grade), and never red-banded. When confidence is low, show the name without the %.
3. **Pro library:** ship v1 with the existing **17 pros + style clustering**; expand the library in a later phase.
