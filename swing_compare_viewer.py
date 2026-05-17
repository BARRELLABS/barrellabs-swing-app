"""
Side-by-Side Swing Comparison viewer.

Renders an interactive HTML/JS component that puts the user's swing video
(with pose skeleton overlay) next to an animated stick figure of the MLB
reference player, synchronized at foot plant.

Why this lives in its own module:
- The HTML/JS bundle is self-contained — no streamlit-component build step.
- It gets injected via `st.components.v1.html()` into the v2 report.
- The pose schemas for both sides are identical (`{f, t, kp}` per frame,
  normalized 0..1, 33 MediaPipe landmarks), so the renderer treats them
  uniformly — see pose_extract.LM_NAMES.

Entitlement: requires Pro (user pose JSON is only uploaded for Pro users
in player_storage._upload_swing_pose_json). For Free users we render a
small upgrade CTA instead.

Public entry point: `render_compare_block(record, mlb_reference, ...)`.
"""

from __future__ import annotations

import html
import json
from typing import Any, Dict, List, Optional


# MediaPipe pose skeleton connections — keep this in sync with
# pose_extract.LM_NAMES ordering. Indices reference the 33-keypoint array.
_CONNECTIONS: List[List[int]] = [
    # Head → shoulders (anchors the figure visually)
    [0, 11], [0, 12],
    # Torso box
    [11, 12], [11, 23], [12, 24], [23, 24],
    # Left arm
    [11, 13], [13, 15], [15, 17], [15, 19], [15, 21],
    # Right arm
    [12, 14], [14, 16], [16, 18], [16, 20], [16, 22],
    # Left leg
    [23, 25], [25, 27], [27, 29], [27, 31], [29, 31],
    # Right leg
    [24, 26], [26, 28], [28, 30], [28, 32], [30, 32],
]


def _phases_dict(record_or_ref: Dict[str, Any]) -> Dict[str, float]:
    """Pull `phases_t` out of either a swing record or an MLB reference.

    Both schemas use the same key names (load_start, foot_plant, launch,
    contact, peak_rotation, finish) but the record nests them differently
    in some legacy shapes — handle both.
    """
    pt = record_or_ref.get("phases_t")
    if isinstance(pt, dict):
        return {str(k): float(v) for k, v in pt.items()
                if isinstance(v, (int, float))}
    # Fallback: try metric_table or top-level
    return {}


def _pose_payload_from_record(record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Return the `{frames, fps, video_width, video_height}` block for
    the user's swing if it's been loaded onto the record.

    The pose JSON lives in Supabase Storage under `record["pose_path"]`.
    Callers are responsible for fetching it (via get_swing_pose_signed_url)
    and attaching it to the record as `record["pose_payload"]` before
    passing into this viewer. This keeps the viewer pure / testable.
    """
    payload = record.get("pose_payload")
    if not isinstance(payload, dict):
        return None
    if not payload.get("pose_frames"):
        return None
    meta = payload.get("pose_meta") or {}
    return {
        "frames": payload["pose_frames"],
        "fps": float(meta.get("fps") or 30.0),
        "video_width": int(meta.get("video_width") or 1080),
        "video_height": int(meta.get("video_height") or 1920),
    }


def _pose_payload_from_reference(ref: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Return the same-shaped pose payload for an MLB reference JSON.

    MLB reference files store frames under `pose_frames` (matching the
    user record schema), each with `{f, t, kp}`. Video dims live in
    `pose_meta`. We also accept the legacy `frames` key for forward
    compat in case someone hand-crafts a reference that way.
    """
    frames = ref.get("pose_frames")
    if not isinstance(frames, list) or not frames:
        # Fallback: older / alternate schema with frames at top level.
        frames = ref.get("frames")
    if not isinstance(frames, list) or not frames:
        return None

    # Video dims: prefer pose_meta (the canonical place for MLB refs),
    # then top-level video_width/height, then a `video_dims` block.
    meta = ref.get("pose_meta") or {}
    vw = (meta.get("video_width")
          or ref.get("video_width")
          or (ref.get("video_dims") or {}).get("width")
          or 1280)
    vh = (meta.get("video_height")
          or ref.get("video_height")
          or (ref.get("video_dims") or {}).get("height")
          or 720)

    fps = meta.get("fps") or ref.get("fps") or 30.0

    return {
        "frames": frames,
        "fps": float(fps),
        "video_width": int(vw),
        "video_height": int(vh),
        # slow_mo_factor: MLB references are typically broadcast slow-mo
        # captures. Their `t` values are video-time (slow), so to compare
        # at real-world speed we scale playback by this factor.
        "slow_mo_factor": float(ref.get("slow_mo_factor") or 1.0),
        "handedness": str(ref.get("handedness") or "RIGHT").upper(),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def render_compare_block(record: Dict[str, Any],
                         mlb_reference: Dict[str, Any],
                         user_video_url: Optional[str] = None,
                         mlb_display_name: str = "MLB Reference",
                         user_handedness: Optional[str] = None) -> str:
    """Render the side-by-side comparison HTML.

    Args:
      record:           The user's swing record. Must include `phases_t`
                        and (for the overlay to render) `pose_payload`
                        with `pose_frames` + `pose_meta`.
      mlb_reference:    The MLB reference dict loaded from
                        references/<slug>.json. Must include `frames`
                        and `phases_t`.
      user_video_url:   A signed URL to the user's uploaded video. If
                        None, the viewer falls back to skeleton-only on
                        the user side.
      mlb_display_name: Pretty player name to show under the right panel.
      user_handedness:  "RIGHT" or "LEFT". Used to mirror the MLB stick
                        figure if the two are opposite, so both swings
                        face the same direction.

    Returns:
      A self-contained HTML string ready to pass into
      st.components.v1.html(height=..., scrolling=False).
    """
    user_pose = _pose_payload_from_record(record)
    mlb_pose = _pose_payload_from_reference(mlb_reference)

    # If we have neither side's pose data, return a fallback card. The
    # caller will typically check this and show an upgrade CTA instead,
    # but render something sensible if they don't.
    if not mlb_pose:
        return _render_unavailable(
            "MLB reference pose data missing for this player."
        )

    user_phases = _phases_dict(record)
    mlb_phases = _phases_dict(mlb_reference)

    # Handedness mirroring — if the user and MLB ref swing opposite hands,
    # we mirror the MLB skeleton horizontally so both face the same way
    # in the side-by-side. Most comparisons will be same-handed, so this
    # is a no-op the vast majority of the time.
    mlb_hand = mlb_pose.get("handedness", "RIGHT")
    user_hand = (user_handedness or "RIGHT").upper()
    mirror_mlb = mlb_hand != user_hand

    payload = {
        "user": {
            "pose": user_pose,            # may be None for Free users
            "phases": user_phases,
            "video_url": user_video_url,  # may be None
        },
        "mlb": {
            "pose": mlb_pose,
            "phases": mlb_phases,
            "display_name": mlb_display_name,
            "mirror": mirror_mlb,
        },
        "connections": _CONNECTIONS,
    }

    payload_json = json.dumps(payload, separators=(",", ":"))

    return _HTML_TEMPLATE.replace("__PAYLOAD__", payload_json)


def _render_unavailable(reason: str) -> str:
    return (
        '<div style="background:#0f0f12;border:1px solid #2a2a2e;'
        'border-radius:14px;padding:24px;color:#a0a0a8;'
        'font:14px/1.5 system-ui;text-align:center;">'
        f'{html.escape(reason)}'
        '</div>'
    )


# ---------------------------------------------------------------------------
# Orchestration: fetch pose data + video URL, load reference, render block.
#
# Kept separate from the pure renderer so the renderer stays unit-testable
# without I/O. This helper does the Supabase round-trips and is what the
# v2 swing report calls directly.
# ---------------------------------------------------------------------------

def build_compare_section(record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Build the side-by-side comparison block for a swing record.

    Returns a dict with:
        - "html": the HTML string to pass into st.components.v1.html()
        - "height": recommended iframe height in pixels
        - "ready": True if everything wired up; False = upgrade CTA shown

    Returns None if the comparison can't be rendered AT ALL (e.g., no
    reference slug, no MLB reference file). Callers should treat None as
    "skip this section entirely."

    Safe to call from any context — all I/O is wrapped in try/except so
    a network blip never crashes the report render.
    """
    # 1. Find the MLB reference to compare against.
    ref_meta = record.get("reference") or {}
    slug = ref_meta.get("slug")
    if not slug:
        # Some legacy records only have reference_name and never persisted
        # the slug. Try a fuzzy lookup as a last resort.
        slug = record.get("reference_name")
    if not slug:
        return None

    try:
        from reference_library import load_reference
        mlb_ref = load_reference(slug)
    except Exception:
        mlb_ref = None
    if not mlb_ref:
        return None

    # 2. Pull the user's pose payload (Pro-only). The pose JSON lives in
    #    Supabase Storage under record["_pose_path"]; we fetch it via a
    #    signed URL and parse JSON. Cached by storage path so subsequent
    #    reruns of the same swing don't re-download.
    pose_path = record.get("_pose_path") or record.get("pose_path")
    pose_payload = _fetch_pose_payload(pose_path)

    # 3. Sign the user's video URL (Pro-only). Free users get None → the
    #    viewer shows MLB-only with an upgrade CTA at the bottom.
    video_path = record.get("_video_path") or record.get("video_path")
    user_video_url = _fetch_video_signed_url(video_path)

    # 4. Build a record-shaped dict the pure renderer expects. We carry
    #    over phases_t (user's foot plant etc.) — either from the record
    #    column (post-migration) or from inside the pose JSON (fallback).
    user_phases = record.get("phases_t") or {}
    if not user_phases and pose_payload:
        user_phases = pose_payload.get("phases_t") or {}

    renderer_record = {
        "phases_t": user_phases,
        "pose_payload": pose_payload,  # may be None for Free users
    }

    user_hand = (record.get("player_handedness") or "RIGHT").upper()
    display_name = ref_meta.get("name") or _slug_to_display(slug)

    html_bundle = render_compare_block(
        record=renderer_record,
        mlb_reference=mlb_ref,
        user_video_url=user_video_url,
        mlb_display_name=display_name,
        user_handedness=user_hand,
    )

    # Height heuristic: viewport capped at 480px (set in CSS), plus the
    # panel label (~36px), controls block (~120px), and a small footnote
    # row (~30px) = ~666px. Add a 20px slack so the iframe never crops
    # the jump-buttons row.
    return {
        "html": html_bundle,
        "height": 690,
        "ready": bool(pose_payload),
    }


def _slug_to_display(slug: str) -> str:
    """Best-effort prettifier: 'mike_trout' → 'Mike Trout'."""
    return " ".join(part.capitalize() for part in str(slug).split("_"))


def _fetch_pose_payload(storage_path: Optional[str]) -> Optional[Dict[str, Any]]:
    """Fetch the per-frame pose JSON from Supabase Storage.

    Returns None for Free users (no pose_path) or if the signed-URL flow
    fails for any reason. Memoized per storage path via st.cache_data so
    repeated reruns of the same report don't re-download multi-MB blobs.
    """
    if not storage_path:
        return None
    try:
        import streamlit as st
        # Cache key is the storage path; TTL matches the signed-URL
        # expiry so we re-mint after an hour.
        @st.cache_data(ttl=3300, show_spinner=False)
        def _cached_fetch(path: str) -> Optional[Dict[str, Any]]:
            try:
                from player_storage import get_swing_pose_signed_url
                url = get_swing_pose_signed_url(path)
                if not url:
                    try:
                        import streamlit as _st
                        _st.warning(f"[pose-fetch] no signed URL returned for path: {path}")
                    except Exception:
                        pass
                    return None
                import urllib.request, json as _json
                with urllib.request.urlopen(url, timeout=15) as resp:
                    body = resp.read()
                payload = _json.loads(body.decode("utf-8"))
                # Surface schema sanity so we can see if the file is the
                # wrong shape vs a network/auth failure.
                try:
                    import streamlit as _st
                    if not isinstance(payload, dict):
                        _st.warning(f"[pose-fetch] payload is not a dict (type={type(payload).__name__})")
                    elif "pose_frames" not in payload:
                        _st.warning(f"[pose-fetch] payload missing 'pose_frames' key. keys={list(payload.keys())}")
                except Exception:
                    pass
                return payload
            except Exception as exc:
                try:
                    import streamlit as _st
                    _st.warning(f"[pose-fetch] inner failure for {path}: {type(exc).__name__}: {exc}")
                except Exception:
                    pass
                return None
        return _cached_fetch(storage_path)
    except Exception as exc:
        # If anything (including streamlit import) goes sideways, just
        # render the MLB-only fallback rather than crashing the report.
        try:
            import streamlit as _st
            _st.warning(f"[pose-fetch] outer failure: {type(exc).__name__}: {exc}")
        except Exception:
            pass
        return None


def _fetch_video_signed_url(storage_path: Optional[str]) -> Optional[str]:
    """Mint a short-lived signed URL for the user's video. Returns None
    for Free users or on any failure.
    """
    if not storage_path:
        return None
    try:
        from player_storage import get_swing_video_signed_url
        return get_swing_video_signed_url(storage_path)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# The HTML/JS bundle. Single string, embedded payload, no external deps.
# ---------------------------------------------------------------------------
# Notes on the math:
#   relativeT  = user_video.currentTime - user_phases.foot_plant
#                (negative pre-foot-plant, positive after)
#   mlbVideoT  = mlb_phases.foot_plant + relativeT * mlb_slow_mo
#                (where slow_mo accounts for broadcast slow-mo capture)
# So both swings hit foot plant at the same playback moment, and the
# user sees their own real-time pacing against MLB's real-time pacing.

_HTML_TEMPLATE = r"""
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
  :root {
    --bg: #0a0a0c;
    --surface: #0f0f12;
    --line: #2a2a2e;
    --line-2: #3a3a40;
    --ink: #ffffff;
    --ink-60: #a0a0a8;
    --ink-40: #6a6a72;
    --red: #ff3b30;
    --green: #6ee7b7;
    --amber: #fbbf24;
  }
  * { box-sizing: border-box; }
  html, body {
    margin: 0; padding: 0;
    background: transparent;
    color: var(--ink);
    font: 13px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
          Helvetica, Arial, sans-serif;
  }
  .bl-compare { width: 100%; }
  .row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
  }
  .panel {
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 14px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }
  .panel-label {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 14px 8px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--ink-60);
  }
  .panel-label .dot {
    width: 7px; height: 7px;
    border-radius: 50%;
    background: var(--red);
    flex: 0 0 auto;
  }
  .panel-label .name {
    color: var(--ink);
    font-size: 13px;
    letter-spacing: 0;
    text-transform: none;
  }
  .viewport {
    /* Width-driven sizing: fill the column up to ~270px, then let
       aspect-ratio derive the height (~480px at full width). This
       prevents the 9:16 portrait from blowing up to ~1000px tall on
       desktop while still keeping the panel non-zero in width.
       max-width = max-height * 9/16 (480 * 9/16 = 270). */
    position: relative;
    width: 100%;
    max-width: 270px;
    aspect-ratio: 9 / 16;
    margin: 0 auto;
    background: #000;
    overflow: hidden;
  }
  .viewport.mlb { background: #050507; }
  .viewport video, .viewport canvas {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    object-fit: contain;
  }
  .viewport video { z-index: 0; }
  .viewport canvas { z-index: 1; pointer-events: none; }
  .phase-tag {
    position: absolute;
    top: 10px; left: 10px;
    z-index: 2;
    padding: 4px 10px;
    background: rgba(255, 59, 48, 0.92);
    color: #fff;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.08em;
    border-radius: 999px;
    opacity: 0;
    transition: opacity 0.18s;
  }
  .phase-tag.on { opacity: 1; }
  .controls {
    margin-top: 12px;
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 14px;
    padding: 14px 16px;
  }
  .ctl-row {
    display: flex;
    align-items: center;
    gap: 14px;
  }
  .play-btn {
    width: 38px; height: 38px;
    border-radius: 50%;
    border: none;
    background: var(--red);
    color: #fff;
    font-size: 14px;
    cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    flex: 0 0 auto;
    transition: transform 0.08s ease;
  }
  .play-btn:active { transform: scale(0.94); }
  .slider-wrap {
    flex: 1 1 auto;
    position: relative;
    height: 38px;
    display: flex;
    align-items: center;
  }
  .slider-track {
    position: absolute;
    inset: 17px 0;
    height: 4px;
    background: var(--line-2);
    border-radius: 2px;
  }
  .slider-fill {
    position: absolute;
    left: 0; top: 17px;
    height: 4px;
    background: var(--red);
    border-radius: 2px;
    pointer-events: none;
  }
  .slider {
    position: relative;
    -webkit-appearance: none;
    appearance: none;
    width: 100%;
    height: 38px;
    background: transparent;
    cursor: pointer;
    margin: 0;
  }
  .slider::-webkit-slider-thumb {
    -webkit-appearance: none;
    width: 14px; height: 14px;
    border-radius: 50%;
    background: #fff;
    cursor: pointer;
    border: none;
    box-shadow: 0 0 0 2px var(--red);
  }
  .slider::-moz-range-thumb {
    width: 14px; height: 14px;
    border-radius: 50%;
    background: #fff;
    cursor: pointer;
    border: none;
    box-shadow: 0 0 0 2px var(--red);
  }
  .keymark {
    position: absolute;
    top: 11px;
    transform: translateX(-50%);
    width: 2px; height: 16px;
    background: var(--ink-40);
    border-radius: 1px;
    pointer-events: none;
  }
  .keymark.fp { background: var(--red); height: 20px; top: 9px; }
  .keymark-label {
    position: absolute;
    top: 30px;
    transform: translateX(-50%);
    font-size: 9px;
    color: var(--ink-40);
    letter-spacing: 0.05em;
    text-transform: uppercase;
    white-space: nowrap;
    pointer-events: none;
  }
  .keymark-label.fp { color: var(--red); font-weight: 700; }
  .time-label {
    flex: 0 0 auto;
    font-variant-numeric: tabular-nums;
    color: var(--ink-60);
    font-size: 11px;
    min-width: 56px;
    text-align: right;
  }
  .jumps {
    display: flex;
    gap: 8px;
    margin-top: 12px;
    flex-wrap: wrap;
  }
  .jump-btn {
    background: transparent;
    border: 1px solid var(--line-2);
    color: var(--ink-60);
    border-radius: 999px;
    padding: 6px 12px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.04em;
    cursor: pointer;
    transition: all 0.12s ease;
  }
  .jump-btn:hover {
    color: #fff;
    border-color: var(--red);
  }
  .jump-btn.active {
    background: var(--red);
    border-color: var(--red);
    color: #fff;
  }
  .footnote {
    margin-top: 10px;
    font-size: 11px;
    color: var(--ink-40);
    line-height: 1.5;
  }
  /* Skeleton-only (no user video) state */
  .viewport.no-video { background: #050507; }
  .viewport.no-video::before {
    content: "Skeleton only \2014 video unavailable";
    position: absolute;
    bottom: 8px; left: 0; right: 0;
    text-align: center;
    font-size: 10px;
    color: var(--ink-40);
    letter-spacing: 0.04em;
    text-transform: uppercase;
    z-index: 0;
  }
  @media (max-width: 600px) {
    .row { grid-template-columns: 1fr; }
    .viewport { aspect-ratio: 9 / 12; }
  }
</style>
</head>
<body>
<div class="bl-compare">
  <div class="row">
    <div class="panel">
      <div class="panel-label">
        <span class="dot"></span>
        <span>You</span>
      </div>
      <div class="viewport" id="user-vp">
        <video id="user-video" preload="auto" muted playsinline></video>
        <canvas id="user-canvas"></canvas>
        <div class="phase-tag" id="user-phase">FOOT PLANT</div>
      </div>
    </div>
    <div class="panel">
      <div class="panel-label">
        <span class="dot"></span>
        <span class="name" id="mlb-name">MLB Reference</span>
      </div>
      <div class="viewport mlb">
        <canvas id="mlb-canvas"></canvas>
        <div class="phase-tag" id="mlb-phase">FOOT PLANT</div>
      </div>
    </div>
  </div>

  <div class="controls">
    <div class="ctl-row">
      <button class="play-btn" id="play-btn" aria-label="Play">▶</button>
      <div class="slider-wrap" id="slider-wrap">
        <div class="slider-track"></div>
        <div class="slider-fill" id="slider-fill"></div>
        <input type="range" class="slider" id="slider"
               min="0" max="1000" value="0" step="1">
        <!-- Keymarks injected by JS -->
      </div>
      <div class="time-label" id="time-label">0.00s</div>
    </div>
    <div class="jumps" id="jumps">
      <button class="jump-btn" data-phase="load_start">Load</button>
      <button class="jump-btn" data-phase="foot_plant">Foot Plant</button>
      <button class="jump-btn" data-phase="launch">Launch</button>
      <button class="jump-btn" data-phase="contact">Contact</button>
    </div>
    <div class="footnote" id="footnote">
      Both swings synchronized at foot plant. Drag the slider or use the
      jump buttons to step through key moments.
    </div>
  </div>
</div>

<script>
(function() {
  const PAYLOAD = __PAYLOAD__;
  const CONNECTIONS = PAYLOAD.connections;

  const USER = PAYLOAD.user;
  const MLB  = PAYLOAD.mlb;

  // Resolve phases — if a phase is missing on the user side, the slider
  // still works but the jump button is dimmed.
  const userPhases = USER.phases || {};
  const mlbPhases  = MLB.phases || {};
  const userFP = userPhases.foot_plant;
  const mlbFP  = mlbPhases.foot_plant || 0;
  const mlbSlowMo = (MLB.pose && MLB.pose.slow_mo_factor) || 1.0;

  // Fallback mode: user has no phases_t (legacy record or non-Pro upload).
  // We drive the timeline from MLB phases so the playback covers the
  // actual swing window — otherwise we'd play through Trout's pre-pitch
  // stance and stop before he ever swings. In fallback mode userT is
  // interpreted directly as MLB video time (mlbT = userT, the existing
  // lockstep branch in render()).
  const useUserTimeline = (userFP !== undefined && userFP !== null);
  const refPhases = useUserTimeline ? userPhases : mlbPhases;
  const refFP     = useUserTimeline ? userFP     : mlbFP;

  // -----------------------------------------------------------------
  // Figure-bounds (scale normalization).
  //
  // Each swing's pose data is normalized to its own source video frame,
  // so a figure shot tight on iPhone portrait and a figure shot wide on
  // a broadcast camera end up at very different on-screen sizes if we
  // map them naively to the canvas. We fix this by computing each
  // swing's bounding box across all frames (using stable torso+leg
  // landmarks only — hands swing way outside the body envelope and
  // would shrink the figure to a dot) and rendering the figure into
  // a uniform ~92% of the canvas in both panels.
  // -----------------------------------------------------------------
  function computeFigureBounds(frames) {
    // 0 = nose, 11/12 = shoulders, 23/24 = hips,
    // 25/26 = knees, 27/28 = ankles. Stable across the swing.
    const ANCHORS = [0, 11, 12, 23, 24, 25, 26, 27, 28];
    let xMin = 1, xMax = 0, yMin = 1, yMax = 0, count = 0;
    for (let i = 0; i < frames.length; i++) {
      const kp = frames[i].kp;
      if (!kp) continue;
      for (let j = 0; j < ANCHORS.length; j++) {
        const p = kp[ANCHORS[j]];
        if (!p || p[2] < 0.3) continue;
        if (p[0] < xMin) xMin = p[0];
        if (p[0] > xMax) xMax = p[0];
        if (p[1] < yMin) yMin = p[1];
        if (p[1] > yMax) yMax = p[1];
        count++;
      }
    }
    if (count < 10 || xMax <= xMin || yMax <= yMin) {
      return { xMin: 0, xMax: 1, yMin: 0, yMax: 1 };
    }
    // 10% pad horizontally (arm reach), 6% vertically (head/foot slack)
    const padX = (xMax - xMin) * 0.10;
    const padY = (yMax - yMin) * 0.06;
    return {
      xMin: Math.max(0, xMin - padX),
      xMax: Math.min(1, xMax + padX),
      yMin: Math.max(0, yMin - padY),
      yMax: Math.min(1, yMax + padY),
    };
  }

  const userBounds = (USER.pose && USER.pose.frames && USER.pose.frames.length)
    ? computeFigureBounds(USER.pose.frames) : null;
  const mlbBounds  = computeFigureBounds(MLB.pose.frames);

  // TEMP (Push 1.3.10): on-screen debug overlay so we can verify scale /
  // sync state without browser dev tools. Remove once visuals are dialed.
  function _dbgOverlay() {
    try {
      const ufLen = (USER.pose && USER.pose.frames) ? USER.pose.frames.length : 0;
      const mfLen = (MLB.pose && MLB.pose.frames) ? MLB.pose.frames.length : 0;
      const ufRange = ufLen ? [USER.pose.frames[0].t, USER.pose.frames[ufLen-1].t] : null;
      const mfRange = mfLen ? [MLB.pose.frames[0].t, MLB.pose.frames[mfLen-1].t] : null;
      const fmt3 = (v) => (typeof v === 'number') ? v.toFixed(3) : '—';
      const fmtRange = (r) => r ? '[' + fmt3(r[0]) + ',' + fmt3(r[1]) + ']' : '—';
      const userVW = USER.pose ? USER.pose.video_width : '—';
      const userVH = USER.pose ? USER.pose.video_height : '—';
      const mlbVW  = MLB.pose ? MLB.pose.video_width : '—';
      const mlbVH  = MLB.pose ? MLB.pose.video_height : '—';
      const anchorStr = _timeAnchors.map(
        p => '(' + fmt3(p[0]) + '→' + fmt3(p[1]) + ')').join(' ');
      const relStr = _midPhasesReliable ? 'YES' : 'NO';
      const fpcStr = (_fpToContact === null) ? '—'
                     : (_fpToContact * 1000).toFixed(0) + 'ms';
      const lines = [
        'userPhases ' + JSON.stringify(USER.phases || {}),
        'mlbPhases  ' + JSON.stringify(MLB.phases || {}),
        'userVideo  ' + userVW + '×' + userVH
          + '   mlbVideo ' + mlbVW + '×' + mlbVH,
        'userFrames ' + ufLen + ' t=' + fmtRange(ufRange),
        'mlbFrames  ' + mfLen + ' t=' + fmtRange(mfRange),
        'userBounds ' + (userBounds ? JSON.stringify(userBounds) : '—'),
        'mlbBounds  ' + JSON.stringify(mlbBounds),
        'fp→contact ' + fpcStr + '  midPhasesReliable=' + relStr,
        'anchors[' + _timeAnchors.length + '] ' + anchorStr,
      ];
      const d = document.createElement('div');
      d.style.cssText = 'position:fixed;left:6px;top:6px;background:rgba(0,0,0,0.86);'
        + 'color:#0f0;font:10px/1.35 ui-monospace,Menlo,monospace;'
        + 'padding:6px 8px;border-radius:6px;max-width:80vw;'
        + 'white-space:pre-wrap;z-index:9999;pointer-events:none;';
      d.textContent = lines.join('\n');
      document.body.appendChild(d);
    } catch (e) { /* swallow */ }
  }
  // NB: _dbgOverlay() is called AFTER _timeAnchors / _midPhasesReliable
  // are defined further below — calling it here would TDZ-throw inside
  // the function body and the try/catch would silently swallow it
  // (which is what was happening through 1.3.12 — the overlay was
  // never actually rendering anchor or reliability info).

  // -----------------------------------------------------------------
  // Phase-anchored time warp.
  //
  // A single foot-plant anchor + constant slow-mo factor isn't enough
  // to keep both swings aligned end-to-end — user swings vary in
  // duration phase-to-phase, and so do MLB references. Instead we
  // build a list of [userT, mlbT] anchors for every phase that exists
  // on both sides, then map any user time by piecewise-linear interp
  // through those anchors. Result: load ↔ load, foot_plant ↔ foot_plant,
  // launch ↔ launch, contact ↔ contact, finish ↔ finish — both swings
  // hit every key moment at the same playback position.
  // -----------------------------------------------------------------
  const _PHASE_ORDER = ['load_start','foot_plant','launch',
                        'contact','peak_rotation','finish'];

  // Reliability heuristic for user mid-swing phases. Phase detection
  // sometimes clusters foot_plant / launch / contact within tens of
  // milliseconds (real values are 100-250ms between each), which then
  // creates 5-10x slope amplifications in the piecewise time-warp —
  // MLB visually blasts from load pose straight to follow-through in
  // a single frame. When we detect that, we ignore the unreliable
  // intermediate anchors and rely on the longer-baseline load_start
  // and finish anchors instead.
  const _fpToContact = (typeof userPhases.foot_plant === 'number'
                        && typeof userPhases.contact === 'number')
    ? (userPhases.contact - userPhases.foot_plant) : null;
  const _midPhasesReliable = (_fpToContact === null)
    || (_fpToContact >= 0.080);

  const _timeAnchors = (function() {
    const a = [];
    for (let i = 0; i < _PHASE_ORDER.length; i++) {
      const k = _PHASE_ORDER[i];
      const ut = userPhases[k], mt = mlbPhases[k];
      if (typeof ut !== 'number' || typeof mt !== 'number') continue;
      // Skip intermediate phases when user detection clustered them.
      // load_start and finish are long-baseline and stable, so we
      // always keep those if present.
      if (!_midPhasesReliable
          && (k === 'foot_plant' || k === 'launch'
              || k === 'contact'  || k === 'peak_rotation')) {
        continue;
      }
      a.push([ut, mt]);
    }
    // Tail safety: ensure there's an anchor at the very end of both
    // swings so post-contact playback paces sensibly. The user side
    // uses their `finish` phase (or last frame fallback). The MLB side
    // prefers `finish` if labeled, otherwise synthesizes a finish point
    // past `peak_rotation` using a follow-through duration scaled to
    // the user's swing — so MLB animates through its full motion
    // (impact extension, top-hand release, post-rotation pose) rather
    // than freezing at peak_rotation (which is just past bat impact,
    // not the visual end of the swing).
    function _userEnd() {
      if (typeof userPhases.finish === 'number') return userPhases.finish;
      if (typeof userPhases.peak_rotation === 'number') return userPhases.peak_rotation;
      if (USER.pose && USER.pose.frames && USER.pose.frames.length) {
        const lf = USER.pose.frames[USER.pose.frames.length - 1];
        if (lf && typeof lf.t === 'number') return lf.t;
      }
      return null;
    }
    function _mlbEnd() {
      // Best: MLB has a labeled finish phase.
      if (typeof mlbPhases.finish === 'number') return mlbPhases.finish;
      // Without a labeled finish, pair the user's finish with MLB's
      // very last captured frame. This guarantees the MLB stick figure
      // plays through its complete motion (bat extension, top-hand
      // release, body rotation completing into finish stance) during
      // the user's playback window. Earlier synthesized estimates
      // (peak_rotation, peak_rotation + small buffer) stopped MLB
      // mid-follow-through, which is what users see as "MLB only
      // showing the end of the swing".
      if (MLB.pose && MLB.pose.frames && MLB.pose.frames.length) {
        const lf = MLB.pose.frames[MLB.pose.frames.length - 1];
        if (lf && typeof lf.t === 'number') return lf.t;
      }
      // Fallback: last available labeled phase.
      const keys = ['peak_rotation','contact','launch','foot_plant'];
      for (const k of keys) {
        if (typeof mlbPhases[k] === 'number') return mlbPhases[k];
      }
      return null;
    }
    const userEnd = _userEnd();
    const mlbEnd  = _mlbEnd();
    if (typeof userEnd === 'number' && typeof mlbEnd === 'number') {
      const last = a[a.length - 1];
      // Append only if the synthetic tail is genuinely past the last
      // existing anchor on the user side. Prevents duplicate / inverted
      // anchors when finish/finish was already added by the loop above.
      if (!last || last[0] < userEnd - 1e-3) {
        a.push([userEnd, mlbEnd]);
      }
    }
    return a;
  })();

  // Now safe to render the debug overlay — all referenced vars exist.
  _dbgOverlay();

  function userToMlbTime(userT) {
    // Fallback lockstep when user has no phases at all.
    if (!useUserTimeline) return userT;
    // Degenerate case: not enough anchors for piecewise — fall back
    // to the legacy single-anchor + slow_mo behavior so we still
    // produce sensible motion instead of a frozen frame.
    if (_timeAnchors.length < 2) {
      return mlbFP + (userT - userFP) * mlbSlowMo;
    }
    // Before first anchor: extrapolate using first segment's slope.
    if (userT <= _timeAnchors[0][0]) {
      const u0 = _timeAnchors[0][0], m0 = _timeAnchors[0][1];
      const u1 = _timeAnchors[1][0], m1 = _timeAnchors[1][1];
      return m0 + (userT - u0) * (m1 - m0) / Math.max(1e-6, u1 - u0);
    }
    // In range: walk segments and linear-interp inside the right one.
    for (let i = 0; i < _timeAnchors.length - 1; i++) {
      const u0 = _timeAnchors[i][0],   m0 = _timeAnchors[i][1];
      const u1 = _timeAnchors[i+1][0], m1 = _timeAnchors[i+1][1];
      if (userT <= u1) {
        const alpha = (userT - u0) / Math.max(1e-6, u1 - u0);
        return m0 + alpha * (m1 - m0);
      }
    }
    // After last anchor: extrapolate using last segment's slope.
    const n = _timeAnchors.length;
    const uA = _timeAnchors[n-2][0], mA = _timeAnchors[n-2][1];
    const uB = _timeAnchors[n-1][0], mB = _timeAnchors[n-1][1];
    return mB + (userT - uB) * (mB - mA) / Math.max(1e-6, uB - uA);
  }

  // -----------------------------------------------------------------
  // DOM refs
  // -----------------------------------------------------------------
  const userVideo = document.getElementById('user-video');
  const userCanvas = document.getElementById('user-canvas');
  const userVP = document.getElementById('user-vp');
  const userPhaseTag = document.getElementById('user-phase');
  const mlbCanvas = document.getElementById('mlb-canvas');
  const mlbPhaseTag = document.getElementById('mlb-phase');
  const playBtn = document.getElementById('play-btn');
  const slider = document.getElementById('slider');
  const sliderFill = document.getElementById('slider-fill');
  const sliderWrap = document.getElementById('slider-wrap');
  const timeLabel = document.getElementById('time-label');
  const mlbNameEl = document.getElementById('mlb-name');
  const jumps = document.getElementById('jumps');
  const footnote = document.getElementById('footnote');

  mlbNameEl.textContent = MLB.display_name || 'MLB Reference';

  // -----------------------------------------------------------------
  // Wire video source (Pro users with stored video).
  // For Free users / missing video, the user side falls back to
  // skeleton-only mode (canvas only, dark background).
  // -----------------------------------------------------------------
  if (USER.video_url) {
    userVideo.src = USER.video_url;
  } else {
    userVP.classList.add('no-video');
    userVideo.style.display = 'none';
  }

  // If user pose missing entirely (Free user), we still render the
  // MLB side and show a hint. The "user" canvas just stays blank.
  const hasUserPose = !!(USER.pose && USER.pose.frames && USER.pose.frames.length);
  if (!hasUserPose) {
    footnote.textContent =
      "Upgrade to Pro to see your own swing skeleton overlay next to "
      + (MLB.display_name || "the MLB reference") + ".";
  }

  // -----------------------------------------------------------------
  // Resize canvases to their viewport (devicePixelRatio aware).
  // -----------------------------------------------------------------
  function sizeCanvas(canvas) {
    const r = canvas.getBoundingClientRect();
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width  = Math.max(1, Math.round(r.width  * dpr));
    canvas.height = Math.max(1, Math.round(r.height * dpr));
    const ctx = canvas.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    return ctx;
  }
  let userCtx = sizeCanvas(userCanvas);
  let mlbCtx  = sizeCanvas(mlbCanvas);
  window.addEventListener('resize', () => {
    userCtx = sizeCanvas(userCanvas);
    mlbCtx  = sizeCanvas(mlbCanvas);
  });

  // -----------------------------------------------------------------
  // Skeleton drawing.
  //
  // The pose data is normalized 0..1 in the source video's frame.
  // We compute a "fit" rectangle for the source aspect inside the
  // current canvas, then map kp coords into that rectangle. This
  // means the skeleton lines up with a `object-fit: contain` video
  // on the user side, and shows the MLB figure at its natural aspect
  // on the right side.
  // -----------------------------------------------------------------
  function fitRect(canvasW, canvasH, srcW, srcH) {
    const srcAR = srcW / srcH;
    const dstAR = canvasW / canvasH;
    let w, h;
    if (srcAR > dstAR) {
      w = canvasW;
      h = canvasW / srcAR;
    } else {
      h = canvasH;
      w = canvasH * srcAR;
    }
    return {
      x: (canvasW - w) / 2,
      y: (canvasH - h) / 2,
      w: w, h: h,
    };
  }

  // Fit the FIGURE (per bounds) into a uniform 92% of the canvas, in
  // the figure's own aspect ratio. Returned rect carries bounds for
  // drawSkeleton to remap kp coords by.
  function fitFigureRect(canvasW, canvasH, bounds, srcW, srcH) {
    const figW = Math.max(1e-3, bounds.xMax - bounds.xMin) * srcW;
    const figH = Math.max(1e-3, bounds.yMax - bounds.yMin) * srcH;
    const figAR = figW / figH;
    const padFrac = 0.04;  // 4% margin around the figure
    const targetW = canvasW * (1 - padFrac * 2);
    const targetH = canvasH * (1 - padFrac * 2);
    let w, h;
    if (figAR > targetW / targetH) {
      w = targetW;
      h = w / figAR;
    } else {
      h = targetH;
      w = h * figAR;
    }
    return {
      x: (canvasW - w) / 2,
      y: (canvasH - h) / 2,
      w: w, h: h,
      bounds: bounds,
    };
  }

  function drawSkeleton(ctx, kp, rect, opts) {
    if (!kp) return;
    const mirror = !!(opts && opts.mirror);
    const lineColor = (opts && opts.lineColor) || '#ff3b30';
    const dotColor  = (opts && opts.dotColor)  || '#ffffff';
    const lineWidth = (opts && opts.lineWidth) || 3;
    // When rect.bounds is set, coords are remapped so the bounded
    // figure fills the rect (scale-normalized mode). Otherwise the
    // legacy video-aligned mapping is used.
    const bounds = (rect && rect.bounds)
      ? rect.bounds
      : { xMin: 0, xMax: 1, yMin: 0, yMax: 1 };
    const xRange = Math.max(1e-6, bounds.xMax - bounds.xMin);
    const yRange = Math.max(1e-6, bounds.yMax - bounds.yMin);

    function projX(raw) {
      let xNorm = (raw - bounds.xMin) / xRange;
      if (mirror) xNorm = 1 - xNorm;
      return rect.x + xNorm * rect.w;
    }
    function projY(raw) {
      return rect.y + (raw - bounds.yMin) / yRange * rect.h;
    }

    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.strokeStyle = lineColor;
    ctx.lineWidth = lineWidth;

    // Bones
    for (let i = 0; i < CONNECTIONS.length; i++) {
      const a = CONNECTIONS[i][0], b = CONNECTIONS[i][1];
      const pa = kp[a], pb = kp[b];
      if (!pa || !pb || pa[2] < 0.3 || pb[2] < 0.3) continue;
      ctx.beginPath();
      ctx.moveTo(projX(pa[0]), projY(pa[1]));
      ctx.lineTo(projX(pb[0]), projY(pb[1]));
      ctx.stroke();
    }

    // Joints
    ctx.fillStyle = dotColor;
    for (let i = 0; i < kp.length; i++) {
      const p = kp[i];
      if (!p || p[2] < 0.3) continue;
      ctx.beginPath();
      ctx.arc(projX(p[0]), projY(p[1]),
              Math.max(2, lineWidth - 1), 0, Math.PI * 2);
      ctx.fill();
    }
  }

  // Binary-search closest frame by time t.
  function findFrameAt(frames, targetT) {
    if (!frames || !frames.length) return null;
    let lo = 0, hi = frames.length - 1;
    if (targetT <= frames[lo].t) return frames[lo];
    if (targetT >= frames[hi].t) return frames[hi];
    while (lo < hi) {
      const mid = (lo + hi) >>> 1;
      if (frames[mid].t < targetT) lo = mid + 1; else hi = mid;
    }
    // lo and lo-1 bracket targetT — pick whichever's closer
    const a = frames[Math.max(0, lo - 1)];
    const b = frames[lo];
    return (Math.abs(a.t - targetT) <= Math.abs(b.t - targetT)) ? a : b;
  }

  // -----------------------------------------------------------------
  // Render frame at given user-video time.
  // -----------------------------------------------------------------
  function render(userT) {
    // User side. With a video, we keep the legacy video-aligned fit so
    // the red skeleton tracks the body inside the video. Without a video
    // (skeleton-only fallback), we use figure-bounds fitting so the
    // figure occupies a consistent fraction of the canvas and matches
    // the MLB side's scale.
    if (hasUserPose) {
      userCtx.clearRect(0, 0, userCanvas.width, userCanvas.height);
      const r = userCanvas.getBoundingClientRect();
      const rect = USER.video_url
        ? fitRect(r.width, r.height,
                  USER.pose.video_width, USER.pose.video_height)
        : (userBounds
            ? fitFigureRect(r.width, r.height, userBounds,
                            USER.pose.video_width, USER.pose.video_height)
            : fitRect(r.width, r.height,
                      USER.pose.video_width, USER.pose.video_height));
      const f = findFrameAt(USER.pose.frames, userT);
      if (f) drawSkeleton(userCtx, f.kp, rect,
                          { lineColor: '#ff3b30', dotColor: '#fff', lineWidth: 3 });
    }

    // MLB side — always figure-bounds fit, since there's no video to
    // align against on this panel.
    mlbCtx.clearRect(0, 0, mlbCanvas.width, mlbCanvas.height);
    {
      const r = mlbCanvas.getBoundingClientRect();
      const rect = fitFigureRect(r.width, r.height, mlbBounds,
                                 MLB.pose.video_width, MLB.pose.video_height);
      const mlbT = userToMlbTime(userT);
      const f = findFrameAt(MLB.pose.frames, mlbT);
      if (f) drawSkeleton(mlbCtx, f.kp, rect, {
        lineColor: '#6ee7b7',
        dotColor: '#ffffff',
        lineWidth: 2.5,
        mirror: !!MLB.mirror,
      });
    }

    // Phase tags — light up when each side is within ~80ms of a key
    // phase on its own timeline.
    updatePhaseTag(userPhaseTag, userT, userPhases);
    updatePhaseTag(mlbPhaseTag, userToMlbTime(userT), mlbPhases);
  }

  function updatePhaseTag(el, t, phases) {
    const NAMES = { load_start: 'LOAD', foot_plant: 'FOOT PLANT',
                    launch: 'LAUNCH', contact: 'CONTACT',
                    peak_rotation: 'PEAK ROT', finish: 'FINISH' };
    let best = null, bestD = 0.08;  // 80ms window
    for (const k in phases) {
      const pt = phases[k];
      if (typeof pt !== 'number') continue;
      const d = Math.abs(pt - t);
      if (d < bestD) { bestD = d; best = k; }
    }
    if (best) {
      el.textContent = NAMES[best] || best.toUpperCase();
      el.classList.add('on');
    } else {
      el.classList.remove('on');
    }
  }

  // -----------------------------------------------------------------
  // Slider <-> video time mapping.
  // The slider runs from "load_start - 200ms" to "finish + 200ms" on
  // the user's timeline (or, if no user phases, the video's full
  // duration). 1000 ticks total — cheap and smooth.
  // -----------------------------------------------------------------
  function userDuration() {
    return (userVideo.duration && isFinite(userVideo.duration))
      ? userVideo.duration : 2.0;
  }
  // User's actual pose-frame extents — fallback when user phases are
  // incomplete (e.g., load_start/finish missing). Without this fallback
  // the slider gets clamped to userDuration()=2s which can chop off the
  // back half of a 2.5s swing.
  function userPoseExtent() {
    const f = USER.pose && USER.pose.frames;
    if (!f || !f.length) return null;
    const firstT = (typeof f[0].t === 'number') ? f[0].t : 0;
    const lastT  = (typeof f[f.length-1].t === 'number') ? f[f.length-1].t : 2.0;
    return [firstT, lastT];
  }
  function timelineRange() {
    // Compute a tight window around the swing, with 200ms pad each side,
    // so the slider doesn't spend 80% of its width on empty setup time.
    //
    // Preference order:
    //   1. User phases load_start + finish (best case — proper bracket)
    //   2. Whatever user phases we have, padded by pose-frame extents
    //   3. MLB phases (lockstep fallback when user has no phases)
    //   4. Raw video duration (worst case)
    let lo, hi;
    const poseExt = userPoseExtent();

    if (useUserTimeline
        && userPhases.load_start !== undefined
        && userPhases.finish !== undefined) {
      lo = Math.max(0, userPhases.load_start - 0.2);
      hi = userPhases.finish + 0.2;
    } else if (useUserTimeline && poseExt) {
      // Partial phases — anchor what we have, fall back to pose extents
      // for the unknown endpoints.
      lo = (userPhases.load_start !== undefined)
         ? Math.max(0, userPhases.load_start - 0.2)
         : poseExt[0];
      hi = (userPhases.finish !== undefined)
         ? userPhases.finish + 0.2
         : poseExt[1];
    } else if (mlbPhases.load_start !== undefined
               && mlbPhases.finish !== undefined) {
      // Fallback: MLB-driven range (userT directly = MLB video time).
      lo = Math.max(0, mlbPhases.load_start - 0.2);
      hi = mlbPhases.finish + 0.2;
    } else if (poseExt) {
      lo = poseExt[0]; hi = poseExt[1];
    } else {
      lo = 0; hi = userDuration();
    }

    // Cap by user video duration ONLY when we have a real video; in
    // skeleton-only mode the userDuration() fallback (2.0s) would
    // truncate longer swings.
    if (USER.video_url) hi = Math.min(hi, userDuration());

    if (hi - lo < 0.4) {
      // Sanity floor — never produce a degenerate range
      if (poseExt) { lo = poseExt[0]; hi = poseExt[1]; }
      else { lo = 0; hi = userDuration(); }
    }
    return [lo, hi];
  }

  function tickToTime(v) {
    const [lo, hi] = timelineRange();
    return lo + (v / 1000) * (hi - lo);
  }
  function timeToTick(t) {
    const [lo, hi] = timelineRange();
    return Math.max(0, Math.min(1000,
      ((t - lo) / Math.max(1e-6, (hi - lo))) * 1000));
  }

  function placeKeymarks() {
    // Drop old marks
    sliderWrap.querySelectorAll('.keymark, .keymark-label')
      .forEach(n => n.remove());

    const [lo, hi] = timelineRange();
    const labels = {
      load_start: ['L', false],
      foot_plant: ['FP', true],
      launch:     ['LA', false],
      contact:    ['C', false],
    };
    const rect = sliderWrap.getBoundingClientRect();
    const usable = rect.width - 14;  // account for thumb size

    Object.keys(labels).forEach(k => {
      const t = refPhases[k];
      if (t === undefined || t < lo || t > hi) return;
      const pct = (t - lo) / (hi - lo);
      const xpx = 7 + pct * usable;
      const mark = document.createElement('div');
      mark.className = 'keymark' + (labels[k][1] ? ' fp' : '');
      mark.style.left = xpx + 'px';
      sliderWrap.appendChild(mark);
      const lbl = document.createElement('div');
      lbl.className = 'keymark-label' + (labels[k][1] ? ' fp' : '');
      lbl.style.left = xpx + 'px';
      lbl.textContent = labels[k][0];
      sliderWrap.appendChild(lbl);
    });
  }

  // -----------------------------------------------------------------
  // Playback loop.
  // -----------------------------------------------------------------
  let rafId = null;
  function startLoop() {
    cancelAnimationFrame(rafId);
    const loop = () => {
      const t = userVideo.currentTime;
      slider.value = timeToTick(t);
      updateSliderFill();
      timeLabel.textContent = formatTime(t);
      render(t);
      updateJumpActive(t);
      if (!userVideo.paused && !userVideo.ended) {
        // Auto-stop at end of swing window so playback feels tight
        const [, hi] = timelineRange();
        if (t >= hi) {
          userVideo.pause();
          setPlayLabel(false);
          rafId = null;
          return;
        }
        rafId = requestAnimationFrame(loop);
      }
    };
    rafId = requestAnimationFrame(loop);
  }

  function formatTime(t) {
    // Always show time relative to the reference foot plant (user's or
    // MLB's in fallback mode), so the label reads "−250ms" → "+0ms" →
    // "+150ms" as we cross foot plant. Easier to interpret than raw
    // video timestamps.
    if (refFP !== undefined && refFP !== null) {
      const rel = t - refFP;
      const sign = rel >= 0 ? '+' : '−';
      return sign + Math.abs(rel * 1000).toFixed(0) + 'ms';
    }
    return t.toFixed(2) + 's';
  }

  function updateSliderFill() {
    sliderFill.style.width = (parseFloat(slider.value) / 10) + '%';
  }
  function setPlayLabel(playing) {
    playBtn.textContent = playing ? '❚❚' : '▶';
  }
  function updateJumpActive(t) {
    jumps.querySelectorAll('.jump-btn').forEach(b => {
      const phase = b.dataset.phase;
      const pt = refPhases[phase];
      const on = (pt !== undefined && Math.abs(pt - t) < 0.06);
      b.classList.toggle('active', on);
    });
  }

  // -----------------------------------------------------------------
  // Event wiring.
  // -----------------------------------------------------------------
  playBtn.addEventListener('click', () => {
    if (!USER.video_url) {
      // No video — fake-play by scrubbing the slider through the timeline
      fakePlayTimeline();
      return;
    }
    if (userVideo.paused) {
      // If at end, rewind to start of timeline
      const [lo, hi] = timelineRange();
      if (userVideo.currentTime >= hi - 0.02) {
        userVideo.currentTime = lo;
      }
      userVideo.play();
      setPlayLabel(true);
      startLoop();
    } else {
      userVideo.pause();
      setPlayLabel(false);
    }
  });

  slider.addEventListener('input', () => {
    const t = tickToTime(parseFloat(slider.value));
    if (USER.video_url) {
      userVideo.currentTime = t;
    }
    updateSliderFill();
    timeLabel.textContent = formatTime(t);
    render(t);
    updateJumpActive(t);
  });

  jumps.addEventListener('click', (e) => {
    const btn = e.target.closest('.jump-btn');
    if (!btn) return;
    const phase = btn.dataset.phase;
    const t = refPhases[phase];
    if (t === undefined) return;
    if (USER.video_url) {
      userVideo.pause();
      setPlayLabel(false);
      userVideo.currentTime = t;
    }
    slider.value = timeToTick(t);
    updateSliderFill();
    timeLabel.textContent = formatTime(t);
    render(t);
    updateJumpActive(t);
  });

  // Skeleton-only fake playback for users with no video.
  let fakeRaf = null, fakeStartWall = 0, fakeStartT = 0, fakePlaying = false;
  function fakePlayTimeline() {
    const [lo, hi] = timelineRange();
    if (fakePlaying) {
      cancelAnimationFrame(fakeRaf);
      fakePlaying = false;
      setPlayLabel(false);
      return;
    }
    fakeStartWall = performance.now();
    fakeStartT = (parseFloat(slider.value) > 980) ? lo : tickToTime(parseFloat(slider.value));
    fakePlaying = true;
    setPlayLabel(true);
    const tick = () => {
      const elapsed = (performance.now() - fakeStartWall) / 1000;
      const t = fakeStartT + elapsed;
      if (t >= hi) {
        fakePlaying = false;
        setPlayLabel(false);
        slider.value = timeToTick(hi);
        updateSliderFill();
        timeLabel.textContent = formatTime(hi);
        render(hi);
        return;
      }
      slider.value = timeToTick(t);
      updateSliderFill();
      timeLabel.textContent = formatTime(t);
      render(t);
      updateJumpActive(t);
      fakeRaf = requestAnimationFrame(tick);
    };
    fakeRaf = requestAnimationFrame(tick);
  }

  // -----------------------------------------------------------------
  // Boot: when the video metadata is ready (so duration / aspect are
  // known), seek to load_start and render a frame so the panel isn't
  // black on first paint.
  // -----------------------------------------------------------------
  function boot() {
    placeKeymarks();
    const [lo] = timelineRange();
    if (USER.video_url) {
      try { userVideo.currentTime = lo; } catch (e) {}
    }
    slider.value = timeToTick(lo);
    updateSliderFill();
    timeLabel.textContent = formatTime(lo);
    render(lo);
  }

  if (USER.video_url) {
    if (userVideo.readyState >= 1) {
      boot();
    } else {
      userVideo.addEventListener('loadedmetadata', boot, { once: true });
    }
    userVideo.addEventListener('ended', () => setPlayLabel(false));
    userVideo.addEventListener('pause', () => {
      setPlayLabel(false);
      if (rafId) { cancelAnimationFrame(rafId); rafId = null; }
    });
    userVideo.addEventListener('play', () => {
      setPlayLabel(true);
      startLoop();
    });
  } else {
    // No-video boot path — render the MLB-side stick figure at load_start
    // (or t=0) so the panel isn't blank. The slider drives playback.
    boot();
  }

  // Re-place keymarks on resize (slider width changes)
  window.addEventListener('resize', placeKeymarks);
})();
</script>
</body>
</html>
"""
