# Side-by-Side Video Swing Compare — Design

> Status: design, approved in substance via mock (localhost:8512). No code until
> the implementation plan is approved.

## Goal

Add a phase-locked, side-by-side video comparison to the Compare page so a
player or coach can watch any two of the player's own swings together, jump to
any swing phase, and fine-tune alignment by a few frames, with a baseball-seam
divider between the two clips.

## Current state

- `compare_swings_page.py` renders a metric/score comparison driven by two
  in-session A/B `st.selectbox` pickers. No video today.
- Each Pro swing stores a clip (`swings.video_path` ->
  `player_storage.get_swing_video_signed_url`) and `phases_t` (load_start,
  foot_plant, launch, contact, peak_rotation, finish, in seconds). Pose JSON
  exists per swing but is not needed here.
- Video is Pro-only and was wired recently, so older clips have no saved video.

## Scope

In: a new "Watch them side by side" section on the Compare page; a phase-locked
dual-video player; phase markers; a per-side fine-tune nudge; the baseball-seam
divider; Pro gating with graceful fallback.

Out (future): pose-skeleton overlay on the compare videos; telestrator/drawing;
exporting the comparison as a clip; persisting nudge offsets across sessions.

## Placement and data flow

- New section on `compare_swings_page.py`, directly under the A/B picker card and
  above the "versus" metric centerpiece. Watching is the headline; the numbers
  support it.
- Driven by the existing `a_idx` / `b_idx` selectboxes (no new picker).
- Per selected record: signed URL via
  `get_swing_video_signed_url(rec["_video_path"])` and `rec["phases_t"]`.
- Rendered with `streamlit.components.v1.html` (iframe) so the custom transport,
  seam SVG, and sync JS survive Streamlit's sanitizer, matching the swing
  report's proven pattern.

## New module: `compare_video_view.py`

Pure, unit-testable builders (mirrors `compare_swings_page.py`'s tested-helpers
pattern):

- `shared_phase_marks(phases_a, phases_b) -> list[dict]`: intersection of the
  canonical order `[load_start, foot_plant, launch, contact, finish]` present in
  BOTH swings, each as `{key, label, frac, ta, tb}` where `frac = i/(n-1)` (even
  spacing) and `ta`/`tb` are the phase's seconds in each clip. Returns `[]` when
  fewer than 2 phases are shared.
- `build_compare_video_html(url_a, url_b, marks, meta_a, meta_b, fps_a, fps_b)
  -> str`: the full self-contained iframe document (CSS + markup + server-built
  seam SVG + JS). Returns `""` when a URL is missing or `marks` has fewer than 2
  entries (self-suppress). The seam SVG is built from numeric coordinates in
  Python (no client-side `innerHTML` of dynamic strings).
- `render_compare_video(rec_a, rec_b) -> None`: page entry. Mints URLs, builds
  marks, calls `components.html` at a fixed height sized so the scrubber and hint
  are never clipped. Renders nothing (page unchanged) when either side lacks a
  video or there are fewer than 2 shared phases.

## Phase-locked player (in-iframe behavior)

- Two portrait videos side by side. Each pane is sized near a portrait aspect
  with the video `object-fit: contain` on black, max-height ~440px, so letterbox
  bars stay minimal.
- A normalized 0..1 swing axis. Phase markers sit at fixed, evenly-spaced
  fractions; the scrubber opens at Contact (the money moment).
- Scrub: maps progress `p` to each clip's real time by piecewise-linear
  interpolation between that clip's own phase timestamps (`timeFor(p, side)`),
  adds that side's nudge offset, seeks both, pauses.
- Markers: labeled ticks (Load, Foot plant, Launch, Contact, Finish). Click jumps
  both videos to that phase and pauses; the current-phase label shows in the
  transport.
- Play: Swing A is the clock. Within each phase segment, Swing B's `playbackRate`
  is scaled to that segment's A:B duration ratio and B is resynced at each phase
  boundary, so the two stay aligned smoothly without per-frame seeking. Playback
  loops the Load->Finish window (skips dead setup/walk-away). Slow-mo toggle
  0.25x / 0.5x / 1x scales the base rate. (The mock used per-frame rAF seeking;
  production uses the playbackRate-scaling approach for smoothness.)
- Fine-tune nudge: per-side back/forward buttons bump that side's offset by one
  frame (`1/fps`; fps from `pose_meta` when available, else 30). The offset
  persists across scrubbing within the session for the current A/B pair and
  resets when the picks change. It is a viewing aid only, never persisted.

## Baseball-seam divider

- A vertical center column (~46px) between the panes: a faint bone seam line with
  two columns of red stitches angled toward the seam, alternating lean each row,
  repeating down the full height (SVG built server-side from numeric
  coordinates).
- Mobile (<=720px): panes stack and the seam becomes a horizontal stitch row
  between them.

## Gating and fallback (real-data-only)

- Pro-only. The video section renders only when BOTH selected swings have a saved
  clip AND there are at least 2 shared phases.
- Otherwise: a slim inline note ("Side-by-side video needs two swings with a
  saved clip"), plus an upgrade nudge for Free users. The existing metric
  comparison below always renders, unchanged.
- Because video was wired recently, the section lights up once a player has two
  newly-analyzed Pro swings; older clips fall back to the numbers.

## Error handling

- Missing or expired signed URL, missing phases, or fewer than 2 shared phases:
  the builder returns `""`, the section self-suppresses, the page is unchanged.
- A clip that fails to load in the browser: its pane shows a small "clip
  unavailable" state; the other pane and the scrubber still work.

## Testing

- Unit tests (`tests/test_compare_video_view.py`): `shared_phase_marks`
  intersection, ordering, and `frac` math; `build_compare_video_html` returns
  `""` on missing inputs and includes both `<video>` srcs plus every shared phase
  label when valid.
- Probe verification (established workflow): render in a `components.html` probe
  with two real swing clips; in real Streamlit via Playwright confirm both videos
  load, scrub seeks both, markers jump both, play stays aligned, the nudge shifts
  one side, and the seam renders; check mobile stacking.

## Non-goals / confirmations

No DB changes. No changes to the analyze pipeline. No new dependencies.
