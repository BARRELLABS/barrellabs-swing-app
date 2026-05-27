# Re-label the 17 MLB reference clips (Logan)

**Why:** the existing contact labels on these clips are systematically marked
**late** — at *follow-through* (bat wrapped around behind), not at *contact*
(bat in the zone meeting the ball). Confirmed on `spencer_torkelson` (1341 →
real ~1230) and `jose_ramirez` (1200 → real ~1120). References built on those
labels would carry wrong "rotation at contact" / "separation at contact"
values, so I'm holding the rebuild until contacts are correct.

Everything else (tooling, rebuild script, z-space recompute) is built. Once
these labels are right, I run one command and the corrected references go live.

---

## The rule for marking contact

**Contact = the frame where the bat is at maximum forward extension in the
hitting zone**, with the arms extended toward the pitcher — that's the moment
the bat would be meeting the ball. **NOT** the follow-through (bat wrapped
around behind the body). On slow-mo clips, the gap between "bat in zone" and
"bat wrapped around" can be ~50–200 frames; the bad labels are sitting in that
later range.

**Foot-plant = the last frame where the front foot is on the ground BEFORE
rotation begins** (batter still loaded/coiled, front foot down, hips not yet
firing). Most existing plant labels look roughly OK, but please glance at each.

---

## Workflow — simple keyboard tool

```bash
.venv/bin/python scripts/validation/relabel_refs.py
```

A native OpenCV window opens on each of the 17 clips in turn, starting at the
current saved contact frame. Scrub with the keys, mark, save, auto-advances.

| Key | Action |
|---|---|
| `.` `,` | +1 / −1 frame |
| `>` `<` | +10 / −10 frames *(Shift + `.` / `,`)* |
| `]` `[` | +30 / −30 frames |
| `/` | jump to a specific frame (type digits + Enter) |
| **`c`** | mark **CONTACT** at current frame |
| **`p`** | mark **PLANT** at current frame |
| **`s`** | save this clip + advance to next |
| `n` | skip this clip (no save) |
| `b` | go back one clip |
| `r` | reset marks to the saved values |
| `h` | toggle help overlay |
| `q` | quit |

Saves are atomic (writes to `manifest.json.tmp` then renames). Each `s` is
durable; you can quit mid-batch and resume later — un-changed clips keep their
existing labels.

Optional: glance at `validation/_relabel_aids/<slug>.jpg` first (a 10-frame
montage spanning the swing region) to see the bat-in-zone area at a glance
before scrubbing.

---

## The 17 to re-label

| Slug | Video | Current contact (suspect) |
|---|---|---|
| aaron_judge → `judge_swing_copy` | `~/baseball-swing-app/judge_swing copy.mp4` | 138 |
| alex_bregman → `alex_bregman_swing` | `~/baseball-swing-app/alex_bregman_swing.mp4` | 765 |
| francisco_lindor → `francisco_lindor_swing` | `~/baseball-swing-app/francisco_lindor_swing.mp4` | 821 |
| freddie_freeman → `freddie_freeman_swing` | `~/baseball-swing-app/freddie_freeman_swing.mp4` | 501 |
| gunnar_henderson → `gunnar_henderson_swing` | `~/baseball-swing-app/gunnar_henderson_swing.mp4` | 749 |
| **jose_ramirez** → `jose_ramirez_swing` | `~/baseball-swing-app/jose_ramirez_swing.mp4` | **1200 (confirmed late — should be ~1120)** |
| juan_soto → `juan_soto_swing` | `~/baseball-swing-app/juan_soto_swing.mp4` | 394 |
| kyle_schwarber → `kyle_schwarber_swing` | `~/baseball-swing-app/kyle_schwarber_swing.mp4` | 663 |
| kyle_tucker → `kyle_tucker_swing` | `~/baseball-swing-app/kyle_tucker_swing.mp4` | 566 *(verified good — leave as-is)* |
| manny_machado → `manny_machado_swing` | `~/baseball-swing-app/manny_machado_swing.mp4` | 700 |
| mike_trout → `trout_swing` | `~/baseball-swing-app/trout_swing.mp4` | 356 |
| mookie_betts → `mookie_swing` | `~/baseball-swing-app/mookie_swing.mp4` | 944 *(looked roughly OK)* |
| ronald_acuna_jr → `ronald_acuna_jr_swing` | `~/baseball-swing-app/ronald_acuna_jr_swing.mp4` | 204 |
| shohei_ohtani → `shohei_swing` | `~/baseball-swing-app/shohei_swing.mp4` | 954 |
| **spencer_torkelson** → `spencer_torkelson_swing` | `~/baseball-swing-app/spencer_torkelson_swing.mp4` | **1341 (confirmed late — should be ~1230)** |
| yandy_diaz → `yandy_diaz_swing` | `~/baseball-swing-app/yandy_diaz_swing.mp4` | 405 |
| yordan_alvarez → `yordan_alvarez_swing` | `~/baseball-swing-app/yordan_alvarez_swing.mp4` | 641 |

---

## When you're done

Tell me. I'll run:
1. `.venv/bin/python scripts/rebuild_references.py` → stage refs from new labels.
2. Visual review of the new montages (`references_rebuilt/_verify/*.jpg`).
3. Promote staging → `references/`.
4. `.venv/bin/python scripts/build_match_stats.py` → recompute `mlb_match_stats.json`.
5. Re-check the `swing_score` stability threshold (anchored on pro distribution).
6. Full test suite + harness validation.
7. Commit + present the final state for your promote-to-live approval.
