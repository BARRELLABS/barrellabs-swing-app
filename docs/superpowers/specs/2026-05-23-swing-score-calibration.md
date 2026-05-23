# Swing Score + MLB Match — v1 Calibration Notes

**Date:** 2026-05-23
**Branch:** `claude/swing-engine`
**Harness:** `/tmp/calibrate_swing_score.py` (pure: reuses `swing_score.py` + `mlb_match.py`, no video reprocessing)
**Cohort:** the 17 frozen MLB reference fingerprints in `references/*.json`, scored at the `15-17` (adult-closest, tightest-threshold) bracket.

This run validates the two engines against the same code paths the app uses, before merge. v1 grades **principle compliance** — there are deliberately **no age percentiles** yet (see Deferred).

---

## 1. Swing Score — pillar compliance (pros)

Reference JSONs carry no `sequence` block, so the **Sequence** pillar legitimately drops out for pros; their score below is the confidence-weighted mean of **Stability / Timing / Stride** (confidence forced to 1.0 to expose the *raw* signal — the live path additionally confidence-gates each pillar).

| Pro | Stability | Timing | Stride | Swing Score |
|-----|:--:|:--:|:--:|:--:|
| Manny Machado | 1.00 | 1.00 | 1.00 | **100** |
| Yandy Díaz | 1.00 | 1.00 | 0.89 | **96** |
| Yordan Alvarez | 1.00 | 1.00 | 0.70 | **90** |
| Aaron Judge | 1.00 | 1.00 | 0.51 | **84** |
| Ronald Acuña Jr. | 1.00 | 1.00 | 0.53 | **84** |
| Mike Trout | 1.00 | 1.00 | 0.42 | **81** |
| Francisco Lindor | 1.00 | 1.00 | 0.39 | **80** |
| Kyle Schwarber | 1.00 | 1.00 | 0.41 | **80** |
| Shohei Ohtani | 1.00 | 1.00 | 0.41 | **80** |
| Alex Bregman | 1.00 | 1.00 | 0.32 | **77** |
| Spencer Torkelson | 1.00 | 1.00 | 0.22 | **74** |
| Juan Soto | 1.00 | 1.00 | 0.14 | **71** |
| Kyle Tucker | 1.00 | 1.00 | 0.08 | **69** |
| Gunnar Henderson | 1.00 | 1.00 | 0.02 | **67** |
| José Ramírez | 1.00 | 1.00 | 0.00 | **67** |
| Mookie Betts | 1.00 | 1.00 | 0.00 | **67** |
| Freddie Freeman | 1.00 | 0.32 | 0.02 | **45** |

**Pro cohort:** min 45, **mean 77**, max 100 (n=17).

**Read:** Stability and Timing saturate at 1.00 for the cohort — exactly as expected for pros (quiet heads, real gather→fire tempo). The score spread is driven almost entirely by the **Stride** pillar (front-leg brace via knee re-extension), which is the noisiest signal (see Risks).

## 2. Score discrimination — synthetic amateur

A constructed clearly-flawed swing (rushed gather + slow drag to contact, casting hips, no front-leg brace, head lurch of 0.55T):

| | Sequence | Stability | Timing | Stride | Swing Score |
|--|:--:|:--:|:--:|:--:|:--:|
| Synthetic amateur | 0.20 | 0.11 | 0.02 | 0.05 | **9** (all 4) / **6** (3 shared w/ pros) |

**Δ vs pro mean on shared pillars = −71.** The score cleanly separates a good swing from a bad one, which is the core requirement.

## 3. MLB Match — held-out "who do you move like"

Each pro is removed from its own candidate pool, then matched to the nearest *other* pro within its nearest cluster (movement-% via `exp(−dist/3)`):

| Pro | Cluster | Held-out nearest pro | Match % |
|-----|:--:|-----|:--:|
| Francisco Lindor | 0 | Freddie Freeman | 79 |
| Freddie Freeman | 0 | Francisco Lindor | 79 |
| Kyle Tucker | 0 | Shohei Ohtani | 75 |
| Shohei Ohtani | 0 | Kyle Tucker | 75 |
| Mike Trout | 0 | Freddie Freeman | 62 |
| Mookie Betts | 2 | Yandy Díaz | 61 |
| Ronald Acuña Jr. | 0 | Francisco Lindor | 59 |
| Kyle Schwarber | 2 | Yandy Díaz | 56 |
| Juan Soto | 2 | Alex Bregman | 55 |
| Alex Bregman | 2 | Juan Soto | 55 |
| Spencer Torkelson | 2 | Kyle Schwarber | 52 |
| Gunnar Henderson | 0 | Freddie Freeman | 64 |
| José Ramírez | 0 | Gunnar Henderson | 37 |
| Yordan Alvarez | 0 | Ronald Acuña Jr. | 32 |
| Aaron Judge | 1* | Yandy Díaz | 31 |
| Manny Machado | 0 | Francisco Lindor | 26 |
| Yandy Díaz | 2 | Mookie Betts | 61 |

\* Judge is a singleton cluster; with no same-cluster peer the harness falls back to nearest of all others (a low 31% — correctly flagging him as distinctive).

**Read:** Neighbors are archetype-consistent — smooth cluster-0 hitters pair off (Lindor/Freeman, Trout/Freeman, Ohtani/Tucker), and the compact cluster-2 group pairs off (Soto/Bregman, Mookie/Schwarber/Yandy). The synthetic amateur lands as an outlier at **0%**, which is the honest "we can't confidently name your match" signal.

---

## Risks & follow-ups (carried into v2 / production hardening)

1. **Stride pillar is the dominant source of variance and the least reliable signal.** Knee re-extension reads low for several pros (Mookie/Ramírez 0.00, Henderson/Freeman 0.02) — almost certainly a camera-view / read-quality artifact, not a genuinely soft front leg. This calibration forced confidence=1.0 to expose the raw number; **in the live path `_pillar_confidence` down-weights Stride when the rotation read is view-sensitive or pose visibility is low**, which is what keeps a noisy single-frame knee read from unfairly tanking a real player's score. Action: validate the stride confidence gate on real youth clips, and persist the stride-direction vector (#134) so the brace gate isn't hardcoded to `True`.
2. **Age fairness is inert in production until age is persisted (#134).** `analyze()` reads age from the player fingerprint; today that field is absent, so every player defaults to the `13-14` bracket and the per-bracket threshold widening never engages. The age-fair bands are built and tested but won't *vary* until detect_phases/app.py stamp age onto the fingerprint.
3. **Sequence pillar can't be cross-checked against the pro library** (reference JSONs predate the `sequence` block). It's exercised by unit tests and the live player path, not by this pro cohort.
4. **Real-video calibration still pending.** This run uses the frozen MLB fingerprints; it confirms the math and thresholds discriminate, but the absolute pro-vs-youth score distribution should be re-checked on a batch of real youth swings before these numbers drive coaching copy.

## Deferred to v2 (explicitly not in this build)
Age **percentiles** (v1 is compliance-only), "The Climb" history view, pro-library expansion beyond 17, you-vs-pro overlay polish.

## Verification status
- Full suite: **435 passed, 1 skipped** (`pytest tests/ -q`).
- Headless render: new two-system report HTML builds cleanly (Match reveal + Swing Score pillars + confidence badge + filming guide + "what you did well").

---

## Addendum (2026-05-23) — Real-video calibration + reliability tune

Ran 5 **real amateur swing clips** end-to-end (detect_phases → analyze), not just the frozen pro fingerprints. Findings drove a confidence-model tune.

**Finding:** Sequence (hips-lead) and Stride (front-leg brace) read near-zero on real single-camera phone video even for decent swings — they are the intrinsically noisy metrics (per biomech verification). At full confidence they unfairly tanked the Swing Score.

**Tune:** added `_PILLAR_RELIABILITY` structural ceilings in `analyzer.py` — Sequence & Stride capped at **0.5** confidence (count half as much), Stability & Timing stay **1.0**. A low/zero read on the noisy pillars now drags the score far less; the grade leans on what phone video measures reliably.

**Effect (real clips, age 13), before → after:**

| Clip | Before | After | Moves like (match%) |
|------|:--:|:--:|------|
| IMG_9005 | 76 | 79 | Kyle Tucker (35%) |
| MarioTSwing | 68 | 79 | Kyle Schwarber (48%) |
| IMG_8608 | 61 | 74 | Mookie Betts (51%) |
| IMG_8436 | 49 | 64 | Aaron Judge (14%) |
| My_swing | 43 | 52 | Aaron Judge (13%) |

Genuinely strong swings barely move (76→79); the clip with a real timing weakness stays lowest (52). Age-fairness confirmed live: IMG_8436 scores 70 @ age 9 → 64 @ age 15 on identical mechanics.

**Residual:** these are real *amateur* clips, not verified-age youth; the absolute ceiling (0.5) is a tunable judgment call. Sequence/Stride remain the metrics to improve (or sensor-source) long-term.
