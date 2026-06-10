"""
Side-by-side video swing compare — phase-locked dual-video player.

A new "Watch them side by side" section for the Compare page
(compare_swings_page.py). Given two of a player's own swings, it renders both
clips side by side, locked on a single phase-aware scrubber so scrubbing to
"contact" shows contact on BOTH even when the swings differ in tempo or length.
A per-side frame nudge fine-tunes the alignment when phase detection drifts, and
a baseball-seam stitch divides the two panes.

Rendered inside a components.html iframe (like the swing report) so the custom
transport, the seam SVG, and the sync JS survive Streamlit's sanitizer.

Public API:
    shared_phase_marks(phases_a, phases_b) -> list[dict]   (pure, tested)
    build_compare_video_html(...)          -> str          (pure, tested)
    render_compare_video(rec_a, rec_b)     -> None          (Streamlit entry)

Gating: Pro-only video, and only when BOTH swings have a saved clip and at least
two shared phases. Otherwise the section self-suppresses (the page's metric
comparison still renders). No DB or pipeline changes.
"""

from __future__ import annotations

import html
import json
from typing import Any, Dict, List, Optional


# Canonical swing phases, earliest -> latest. peak_rotation is intentionally
# omitted: it sits between contact and finish and is the noisiest to detect, so
# it makes a poor alignment anchor. label is what the scrubber shows.
_PHASE_ORDER = [
    ("load_start", "Load"),
    ("foot_plant", "Foot plant"),
    ("launch", "Launch"),
    ("contact", "Contact"),
    ("finish", "Finish"),
]


def _phase_seconds(phases: Optional[Dict[str, Any]], key: str) -> Optional[float]:
    """A phase's timestamp in seconds, or None if missing/unparseable."""
    if not isinstance(phases, dict):
        return None
    v = phases.get(key)
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def shared_phase_marks(phases_a: Optional[Dict[str, Any]],
                       phases_b: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """One mark per canonical phase present in BOTH swings, earliest->latest.

    Each mark: {key, label, frac, ta, tb} where `frac` is the evenly-spaced
    normalized position on the shared scrubber (i/(n-1)) and ta/tb are the
    phase's seconds in swing A / B. Returns [] when fewer than 2 phases are
    shared (nothing meaningful to lock onto).
    """
    pairs = []
    for key, label in _PHASE_ORDER:
        ta = _phase_seconds(phases_a, key)
        tb = _phase_seconds(phases_b, key)
        if ta is not None and tb is not None:
            pairs.append((key, label, ta, tb))
    n = len(pairs)
    if n < 2:
        return []
    marks = []
    for i, (key, label, ta, tb) in enumerate(pairs):
        marks.append({
            "key": key,
            "label": label,
            "frac": i / (n - 1),
            "ta": round(ta, 4),
            "tb": round(tb, 4),
        })
    return marks


# Plain-language coaching map: metric label substrings -> what it means in kid
# terms + what to watch for in the video + which phase to scrub to. Keeps the
# comparison about the SWING, not a wall of percentages.
_PHASE_LABELS = {"load_start": "Load", "foot_plant": "Foot plant",
                 "launch": "Launch", "contact": "Contact", "finish": "Finish"}

_WATCH_MAP = [
    (("total head drift", "head drift"), "Head stability",
     "How still your head stays through the swing.",
     "keep your eyes quiet and your head still from load to the ball", "contact"),
    (("total swing duration",), "Swing length",
     "How long the whole swing takes, start to finish.",
     "a quicker, more compact move beats long and loopy", "launch"),
    (("launch → contact", "launch -> contact", "launch to contact"), "Bat to the ball",
     "How fast the bat gets to the ball once you commit.",
     "watch the barrel take a short, direct path to contact", "contact"),
    (("foot plant → launch", "foot plant -> launch", "foot plant to launch"), "Gather to fire",
     "The beat between landing your stride and starting the swing.",
     "see how long you hold after the foot lands before the hands go", "launch"),
    (("peak hip-shoulder separation", "separation at foot plant"), "Hip-shoulder separation",
     "The stretch between your hips and shoulders before you fire, your rubber band.",
     "your hips start opening while your shoulders stay back", "foot_plant"),
    (("hip rotation at contact",), "Hip rotation",
     "How far your hips turn through the ball.",
     "look at your belt buckle, more open to the pitcher means more rotation", "contact"),
    (("hip rotation at foot plant",), "Early hip turn",
     "How much your hips have opened when your front foot lands.",
     "quieter hips at landing usually set up a better turn", "foot_plant"),
    (("re-extension",), "Front-leg brace",
     "Your front leg straightening to brace against at contact.",
     "look at your front knee, straighter and firmer braces the swing", "contact"),
    (("most bent", "(load)"), "Lower-half load",
     "How much you sit into your legs as you gather.",
     "watch your knees bend as you load into the back side", "load_start"),
]


def _match_watch(label: str):
    low = str(label or "").lower()
    for needles, friendly, what, watch, phase in _WATCH_MAP:
        if any(nd in low for nd in needles):
            return friendly, what, watch, phase
    return None


def watch_cards(rows: List[Dict[str, Any]], limit: int = 3) -> List[Dict[str, Any]]:
    """Turn the biggest metric moves between two swings into plain-language
    'what changed, where to watch' cards. `rows` is compare_swings_page's
    compare_metric_rows output ({label, a_pct, b_pct, delta}; delta is B-A and
    higher % = closer to the pro = better). One card per friendly group (the
    biggest move wins), the `limit` largest absolute moves, sorted strongest
    first. Returns [] when nothing maps."""
    best: Dict[str, Dict[str, Any]] = {}
    for r in rows or []:
        m = _match_watch(r.get("label", ""))
        if not m:
            continue
        friendly, what, watch, phase = m
        cur = best.get(friendly)
        if cur is None or abs(r.get("delta", 0)) > abs(cur.get("delta", 0)):
            best[friendly] = {**r, "friendly": friendly, "what": what,
                              "watch": watch, "phase": phase}
    ranked = sorted(best.values(), key=lambda c: abs(c.get("delta", 0)), reverse=True)
    cards = []
    for c in ranked[:limit]:
        d = c.get("delta", 0)
        if d >= 4:
            tag, trend, change = "Sharper", "up", "Closer to your pro swing in the later one."
        elif d <= -4:
            tag, trend, change = "Slipped", "down", "A step back from the earlier swing, worth a look."
        else:
            tag, trend, change = "Held", "flat", "About the same in both swings."
        cards.append({
            "tag": tag, "trend": trend, "title": c["friendly"],
            "meaning": c["what"], "change": change,
            "phase": _PHASE_LABELS.get(c["phase"], c["phase"]),
            "watch": c["watch"], "a": c.get("a_pct"), "b": c.get("b_pct"), "delta": d,
        })
    return cards


def build_watch_breakdown_html(cards: List[Dict[str, Any]]) -> str:
    """Plain-language 'what changed, where to watch' section, or "" when there's
    nothing to say. Designed to sit right under the side-by-side video, styled
    with the Compare page's cmp-* tokens."""
    if not cards:
        return ""
    items = []
    for c in cards:
        pct = (f'<span class="pct">{c["a"]}% &rarr; {c["b"]}%</span>'
               if c["a"] is not None and c["b"] is not None else "")
        items.append(
            f'<div class="cmp-watch-card {c["trend"]}">'
            f'<div class="cwc-top"><span class="cwc-tag">{html.escape(c["tag"])}</span>'
            f'<span class="cwc-ttl">{html.escape(c["title"])}</span>{pct}</div>'
            f'<div class="cwc-mean">{html.escape(c["meaning"])} {html.escape(c["change"])}</div>'
            f'<div class="cwc-look"><span class="cwc-eye">&#9655;</span> Look for it at '
            f'<b>{html.escape(c["phase"])}</b>: {html.escape(c["watch"])}.</div>'
            f'</div>'
        )
    return (
        '<div class="cmp-section cmp-rise" style="animation-delay:.16s">'
        '<div class="cmp-sec-head"><h2 class="cmp-sec-title">What changed, and where to watch</h2>'
        '<span class="cmp-sec-sub">Plain English &middot; scrub to the phase</span></div>'
        f'<div class="cmp-watch-grid">{"".join(items)}</div>'
        '</div>'
    )


def _seam_svg(height: int = 460, width: int = 46) -> str:
    """Baseball double-stitch seam as a static SVG string (built server-side, so
    no client innerHTML). A faint bone seam line down the center with two columns
    of red stitches angled toward it, alternating lean each row."""
    cx = width / 2
    parts = [
        f'<svg viewBox="0 0 {width} {height}" preserveAspectRatio="none" '
        f'class="cvv-seam-svg" aria-hidden="true">',
        f'<line x1="{cx}" y1="0" x2="{cx}" y2="{height}" '
        f'stroke="rgba(244,239,230,0.14)" stroke-width="1.2"/>',
    ]
    step = 15
    row = 0
    y = 8
    while y < height - 4:
        lean = 6 if row % 2 == 0 else -6
        parts.append(
            f'<line x1="{cx-9:.1f}" y1="{y}" x2="{cx-1:.1f}" y2="{y+lean}" '
            f'stroke="#E64530" stroke-width="2" stroke-linecap="round"/>'
        )
        parts.append(
            f'<line x1="{cx+1:.1f}" y1="{y+lean}" x2="{cx+9:.1f}" y2="{y}" '
            f'stroke="#E64530" stroke-width="2" stroke-linecap="round"/>'
        )
        y += step
        row += 1
    parts.append("</svg>")
    return "".join(parts)


def _meta_chip(meta: Dict[str, Any], *, is_b: bool) -> str:
    role = html.escape(str(meta.get("role") or ("Swing B" if is_b else "Swing A")))
    date = html.escape(str(meta.get("date") or ""))
    score = meta.get("score")
    score_html = (f'<span class="sc">{int(round(float(score)))}</span>'
                  if score is not None else "")
    return (f'<div class="chip"><span class="role">{role}</span>'
            f'<span class="meta">{date}</span>{score_html}</div>')


def build_compare_video_html(url_a: Optional[str],
                             url_b: Optional[str],
                             marks: List[Dict[str, Any]],
                             meta_a: Dict[str, Any],
                             meta_b: Dict[str, Any],
                             fps_a: float = 30.0,
                             fps_b: float = 30.0) -> str:
    """Full self-contained iframe document for the dual-video player, or "" when
    inputs are insufficient (missing URL, or fewer than 2 shared phases) so the
    caller can self-suppress."""
    if not url_a or not url_b or not marks or len(marks) < 2:
        return ""

    data = {
        "marks": marks,
        "fpsA": float(fps_a or 30.0),
        "fpsB": float(fps_b or 30.0),
    }
    data_json = json.dumps(data)
    seam = _seam_svg()
    chip_a = _meta_chip(meta_a, is_b=False)
    chip_b = _meta_chip(meta_b, is_b=True)
    src_a = html.escape(url_a, quote=True)
    src_b = html.escape(url_b, quote=True)

    return _DOC_TEMPLATE \
        .replace("__DATA__", data_json) \
        .replace("__SEAM__", seam) \
        .replace("__CHIPA__", chip_a) \
        .replace("__CHIPB__", chip_b) \
        .replace("__SRCA__", src_a) \
        .replace("__SRCB__", src_b)


def estimate_height() -> int:
    """Fixed iframe height: header + ~460px video stage + transport + scrubber."""
    return 720


def render_compare_video(rec_a: Dict[str, Any], rec_b: Dict[str, Any]) -> None:
    """Streamlit entry. Renders the side-by-side video player for two records, or
    a slim note when either lacks a saved clip / shared phases. The page's metric
    comparison renders regardless (this is purely additive)."""
    import streamlit as st
    import streamlit.components.v1 as components

    path_a = rec_a.get("_video_path")
    path_b = rec_b.get("_video_path")
    # phases_t lives in a DB column on newer swings, but swings saved before that
    # column existed carry it only inside the pose JSON. Fall back to the pose
    # JSON (same lazy-load the report uses) so two valid clips never silently
    # self-suppress. We also pick up the real fps there for the nudge step.
    pa, fps_a = _phases_and_fps(rec_a)
    pb, fps_b = _phases_and_fps(rec_b)
    marks = shared_phase_marks(pa, pb)

    if not path_a or not path_b or len(marks) < 2:
        # Self-suppress with a quiet, on-theme note. Free users (no saved video)
        # see an upgrade hint; otherwise it's just "needs two clips".
        is_pro_user = _is_pro_user()
        msg = ("Side-by-side video needs two swings with a saved clip."
               if is_pro_user else
               "Side-by-side video is a Pro feature. Upgrade to watch any two "
               "of your swings together, phase by phase.")
        st.markdown(
            f'<div class="cvv-note">{html.escape(msg)}</div>',
            unsafe_allow_html=True,
        )
        return

    from player_storage import get_swing_video_signed_url
    url_a = get_swing_video_signed_url(path_a)
    url_b = get_swing_video_signed_url(path_b)
    if not url_a or not url_b:
        st.markdown(
            '<div class="cvv-note">Couldn\'t load one of the clips just now. '
            'Refresh to try again.</div>',
            unsafe_allow_html=True,
        )
        return

    meta_a = {"role": "Swing A · earlier", "date": _fmt(rec_a), "score": _score(rec_a)}
    meta_b = {"role": "Swing B · later", "date": _fmt(rec_b), "score": _score(rec_b)}

    doc = build_compare_video_html(url_a, url_b, marks, meta_a, meta_b, fps_a, fps_b)
    if not doc:
        return
    components.html(doc, height=estimate_height(), scrolling=False)


# --------------------------------------------------------------------
#  small record helpers (kept local; the page has its own copies for its
#  own builders, but render_compare_video shouldn't depend on that module)
# --------------------------------------------------------------------
def _score(rec: Dict[str, Any]) -> Optional[float]:
    for key in ("swing_score", "score"):
        v = rec.get(key)
        if v is not None:
            try:
                return float(v)
            except (TypeError, ValueError):
                continue
    return None


def _fmt(rec: Dict[str, Any]) -> str:
    from datetime import datetime
    ts = rec.get("timestamp") or rec.get("date") or rec.get("created_at")
    if not ts:
        return ""
    if isinstance(ts, str):
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00")).strftime("%b %-d · %Y")
        except Exception:
            return ts[:10]
    try:
        return ts.strftime("%b %-d · %Y")
    except Exception:
        return str(ts)


def _phases_and_fps(rec: Dict[str, Any]):
    """Return (phases_t, fps) for a swing.

    Prefers the swing's phases_t column; for older swings where it's empty,
    lazy-loads the pose JSON (which always carries phases_t and pose_meta.fps).
    fps drives the per-frame nudge step; phone clips are ~30fps so that's the
    default when no pose_meta is available.
    """
    phases = rec.get("phases_t") or {}
    fps = 30.0
    needs_phases = not (isinstance(phases, dict) and len(phases) >= 2)
    pose_path = rec.get("_pose_path")
    if (needs_phases or rec.get("pose_meta") is None) and pose_path:
        try:
            from player_storage import load_swing_pose_data
            pose = load_swing_pose_data(pose_path) or {}
            if needs_phases:
                pj = pose.get("phases_t") or {}
                if isinstance(pj, dict) and len(pj) >= 2:
                    phases = pj
            meta = pose.get("pose_meta") or {}
            f = meta.get("fps")
            if f:
                fps = float(f)
        except Exception:
            pass
    else:
        meta = rec.get("pose_meta") or {}
        try:
            f = float(meta.get("fps"))
            if f > 0:
                fps = f
        except (TypeError, ValueError):
            pass
    return phases, fps


def _is_pro_user() -> bool:
    try:
        from entitlements import can_save_video
        from subscription_storage import load_my_plan
        return bool(can_save_video(load_my_plan()))
    except Exception:
        return False


# --------------------------------------------------------------------
#  iframe document template (CSS + markup + sync JS). Placeholders:
#    __DATA__ __SEAM__ __CHIPA__ __CHIPB__ __SRCA__ __SRCB__
# --------------------------------------------------------------------
_DOC_TEMPLATE = r"""<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Geist:wght@400;500;600&family=Geist+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root{--bone:#F4EFE6;--bone-70:rgba(244,239,230,.7);--bone-50:rgba(244,239,230,.5);
--bone-35:rgba(244,239,230,.35);--ink:#0A0B0E;--gold:#E8C170;--red:#E64530;--green:#4AE38C;
--line:rgba(244,239,230,.08);--line-hi:rgba(244,239,230,.16);--glass:rgba(255,255,255,.025);
--serif:'Instrument Serif',Georgia,serif;--sans:'Geist',system-ui,sans-serif;--mono:'Geist Mono',monospace;}
*{box-sizing:border-box;} html,body{margin:0;background:var(--ink);color:var(--bone);font-family:var(--sans);}
.wrap{max-width:1100px;margin:0 auto;padding:6px 4px 24px;}
.stage{display:grid;grid-template-columns:1fr 46px 1fr;gap:0;align-items:stretch;}
.pane{position:relative;border:1px solid var(--line);border-radius:18px;overflow:hidden;background:#000;
display:flex;align-items:center;justify-content:center;height:460px;width:100%;max-width:300px;}
.pane.a{justify-self:end;} .pane.b{justify-self:start;}
.pane.b{border-color:rgba(230,69,48,.28);}
.pane video{width:100%;height:100%;max-height:458px;object-fit:contain;background:#000;display:block;}
.pane .chip{position:absolute;top:12px;left:12px;z-index:3;display:flex;flex-direction:column;gap:3px;
background:rgba(10,11,14,.62);backdrop-filter:blur(8px);border:1px solid var(--line-hi);border-radius:11px;padding:7px 11px;}
.chip .role{font-family:var(--mono);font-size:8.5px;font-weight:600;letter-spacing:.2em;text-transform:uppercase;color:var(--bone-50);}
.pane.b .chip .role{color:var(--red);}
.chip .meta{font-family:var(--mono);font-size:10px;color:var(--bone-70);letter-spacing:.04em;}
.chip .sc{font-family:var(--serif);font-style:italic;font-size:1.15rem;color:var(--bone);line-height:1;}
.nudge{position:absolute;bottom:12px;left:50%;transform:translateX(-50%);z-index:3;display:flex;align-items:center;gap:8px;
background:rgba(10,11,14,.66);backdrop-filter:blur(8px);border:1px solid var(--line-hi);border-radius:999px;padding:5px 8px;}
.nudge .lab{font-family:var(--mono);font-size:8.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--bone-50);}
.nudge button{width:26px;height:24px;border-radius:7px;border:1px solid var(--line-hi);background:rgba(244,239,230,.05);
color:var(--bone-70);font-size:12px;cursor:pointer;line-height:1;}
.nudge button:hover{background:rgba(232,193,112,.14);color:var(--gold);border-color:rgba(232,193,112,.45);}
.nudge .off{font-family:var(--mono);font-size:9.5px;color:var(--bone-50);min-width:30px;text-align:center;}

.seam{position:relative;display:flex;align-items:stretch;justify-content:center;}
.seam .cvv-seam-svg{height:100%;width:46px;}

.transport{display:flex;align-items:center;gap:14px;margin:16px 2px 8px;}
.play{width:46px;height:46px;border-radius:50%;border:1px solid var(--line-hi);background:rgba(244,239,230,.05);
color:var(--bone);font-size:15px;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:.15s;}
.play:hover{background:rgba(232,193,112,.12);border-color:rgba(232,193,112,.5);}
.now{font-family:var(--mono);font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:var(--gold);min-width:96px;}
.spacer{flex:1;}
.seg{display:flex;border:1px solid var(--line);border-radius:10px;overflow:hidden;}
.seg button{background:transparent;border:none;color:var(--bone-50);font-family:var(--mono);font-size:10.5px;
letter-spacing:.08em;padding:7px 11px;cursor:pointer;transition:.15s;}
.seg button.on{background:rgba(232,193,112,.16);color:var(--gold);}
.loop{font-family:var(--mono);font-size:10.5px;letter-spacing:.08em;color:var(--bone-50);border:1px solid var(--line);
border-radius:10px;padding:7px 12px;background:transparent;cursor:pointer;}
.loop.on{color:var(--green);border-color:rgba(74,227,140,.4);}

.scrub{position:relative;margin:8px 4px 0;height:54px;}
.track{position:absolute;top:8px;left:0;right:0;height:4px;border-radius:999px;background:rgba(244,239,230,.10);}
.fill{position:absolute;top:8px;left:0;height:4px;border-radius:999px;background:linear-gradient(90deg,var(--gold),var(--red));}
.playhead{position:absolute;top:2px;width:2px;height:16px;background:var(--bone);border-radius:2px;transform:translateX(-1px);box-shadow:0 0 8px rgba(244,239,230,.6);}
.mk{position:absolute;top:0;transform:translateX(-50%);display:flex;flex-direction:column;align-items:center;cursor:pointer;}
.mk .tick{width:2px;height:18px;background:var(--bone-35);border-radius:2px;transition:.15s;}
.mk .lab{font-family:var(--mono);font-size:9px;letter-spacing:.08em;text-transform:uppercase;color:var(--bone-50);margin-top:7px;white-space:nowrap;transition:.15s;}
.mk:hover .tick,.mk.active .tick{background:var(--gold);height:22px;}
.mk:hover .lab,.mk.active .lab{color:var(--gold);}
.range{position:absolute;top:0;left:0;width:100%;height:24px;opacity:0;cursor:pointer;margin:0;}
.hint{font-family:var(--mono);font-size:10px;letter-spacing:.06em;color:var(--bone-35);text-align:center;margin-top:14px;}
@media(max-width:720px){.stage{grid-template-columns:1fr;}.seam{height:38px;}.seam .cvv-seam-svg{width:100%;height:38px;transform:rotate(90deg);}}
</style></head><body>
<div class="wrap">
  <div class="stage">
    <div class="pane a">
      __CHIPA__
      <video id="va" src="__SRCA__" playsinline muted preload="auto"></video>
      <div class="nudge"><span class="lab">Nudge A</span><button id="aMinus">&#9664;</button><span class="off" id="aOff">0f</span><button id="aPlus">&#9654;</button></div>
    </div>
    <div class="seam">__SEAM__</div>
    <div class="pane b">
      __CHIPB__
      <video id="vb" src="__SRCB__" playsinline muted preload="auto"></video>
      <div class="nudge"><span class="lab">Nudge B</span><button id="bMinus">&#9664;</button><span class="off" id="bOff">0f</span><button id="bPlus">&#9654;</button></div>
    </div>
  </div>

  <div class="transport">
    <button class="play" id="play">&#9654;</button>
    <div class="now" id="now">Contact</div>
    <div class="spacer"></div>
    <div class="seg" id="speed">
      <button data-s="0.25">0.25x</button>
      <button data-s="0.5" class="on">0.5x</button>
      <button data-s="1">1x</button>
    </div>
    <button class="loop on" id="loop">LOOP</button>
  </div>

  <div class="scrub" id="scrub">
    <div class="track"></div>
    <div class="fill" id="fill"></div>
    <div class="playhead" id="ph"></div>
    <input class="range" id="range" type="range" min="0" max="1000" value="750">
  </div>
  <div class="hint">Drag to scrub &middot; click a phase to jump both &middot; nudge either side to line them up</div>
</div>
<script>
const D = __DATA__;
const marks = D.marks, fpsA = D.fpsA, fpsB = D.fpsB;
const va=document.getElementById('va'), vb=document.getElementById('vb');
let p=0.75, playing=false, speed=0.5, loop=true, raf=null;
let offA=0, offB=0;               // seconds of manual nudge per side
const stepA=1/fpsA, stepB=1/fpsB; // one frame

function timeFor(pp, side){
  const T = side==='a' ? 'ta' : 'tb';
  const off = side==='a' ? offA : offB;
  let t;
  if(pp<=marks[0].frac) t=marks[0][T];
  else if(pp>=marks[marks.length-1].frac) t=marks[marks.length-1][T];
  else{
    t=marks[0][T];
    for(let i=0;i<marks.length-1;i++){
      const a=marks[i], b=marks[i+1];
      if(pp>=a.frac && pp<=b.frac){ const u=(pp-a.frac)/((b.frac-a.frac)||1); t=a[T]+u*(b[T]-a[T]); break; }
    }
  }
  return Math.max(0, t+off);
}
function curPhaseLabel(pp){ let best=marks[0]; for(const m of marks){ if(Math.abs(m.frac-pp)<Math.abs(best.frac-pp)) best=m; } return best.label; }
// Is A's phase-timestamp sequence strictly increasing? Phase detection can be
// noisy on busy clips and emit non-monotonic timestamps; if so, the segment
// scan below is meaningless, so we map playback by even time across the window.
const aMono=(function(){ for(let i=0;i<marks.length-1;i++){ if(marks[i+1].ta<=marks[i].ta) return false; } return true; })();
function pFromA(t){ // map A real time (minus offset) back to normalized frac
  const tt=t-offA, t0=marks[0].ta, t1=marks[marks.length-1].ta;
  if(!aMono){ return (t1<=t0)?marks[0].frac:Math.max(0,Math.min(1,(tt-t0)/(t1-t0))); }
  if(tt<=t0) return marks[0].frac;
  if(tt>=t1) return marks[marks.length-1].frac;
  for(let i=0;i<marks.length-1;i++){ const a=marks[i],b=marks[i+1];
    if(tt>=a.ta && tt<=b.ta){ const u=(tt-a.ta)/((b.ta-a.ta)||1); return a.frac+u*(b.frac-a.frac); } }
  return marks[marks.length-1].frac;
}
function segIndexForP(pp){ for(let i=0;i<marks.length-1;i++){ if(pp>=marks[i].frac && pp<=marks[i+1].frac) return i; } return marks.length-2; }
function rateForSeg(i){ const dA=marks[i+1].ta-marks[i].ta, dB=marks[i+1].tb-marks[i].tb; return (dA>0? (dB/dA):1); }

function seek(pp){ va.currentTime=timeFor(pp,'a'); vb.currentTime=timeFor(pp,'b'); }
function paint(pp){
  const pc=(pp*100).toFixed(2)+'%';
  document.getElementById('fill').style.width=pc;
  document.getElementById('ph').style.left=pc;
  document.getElementById('range').value=Math.round(pp*1000);
  document.getElementById('now').textContent=curPhaseLabel(pp);
  document.querySelectorAll('.mk').forEach((el,i)=>el.classList.toggle('active', Math.abs(marks[i].frac-pp)<0.04));
}

// markers
const scrub=document.getElementById('scrub');
marks.forEach((m,i)=>{ const el=document.createElement('div'); el.className='mk'; el.style.left=(m.frac*100)+'%';
  const tick=document.createElement('div'); tick.className='tick';
  const lab=document.createElement('div'); lab.className='lab'; lab.textContent=m.label;
  el.appendChild(tick); el.appendChild(lab);
  el.addEventListener('click',()=>{ stop(); p=m.frac; seek(p); paint(p); });
  scrub.appendChild(el);
});
document.getElementById('range').addEventListener('input',e=>{ stop(); p=e.target.value/1000; seek(p); paint(p); });

// playback: A is the clock; B's rate is scaled per phase segment, resynced at boundaries
let curSeg=-1;
function applySeg(i){ curSeg=i; va.playbackRate=speed; vb.playbackRate=Math.max(0.0625, rateForSeg(i)*speed); }
function tick(){
  if(!playing) return;
  p=pFromA(va.currentTime);
  const i=segIndexForP(p);
  if(i!==curSeg){ applySeg(i); vb.currentTime=timeFor(marks[i].frac,'b'); }
  paint(p);
  if(va.currentTime>=timeFor(1,'a')-0.02 || p>=0.999){
    if(loop){ p=0; seek(0); va.play(); vb.play(); applySeg(0); }
    else stop();
  }
  raf=requestAnimationFrame(tick);
}
function play(){ if(p>=0.999) p=0; playing=true; document.getElementById('play').innerHTML='&#10074;&#10074;';
  seek(p); applySeg(segIndexForP(p)); va.play(); vb.play(); raf=requestAnimationFrame(tick); }
function stop(){ playing=false; document.getElementById('play').innerHTML='&#9654;'; va.pause(); vb.pause(); if(raf) cancelAnimationFrame(raf); }
document.getElementById('play').addEventListener('click',()=>{ playing?stop():play(); });
document.getElementById('loop').addEventListener('click',function(){ loop=!loop; this.classList.toggle('on',loop); });
document.querySelectorAll('#speed button').forEach(b=>b.addEventListener('click',()=>{
  speed=parseFloat(b.dataset.s); document.querySelectorAll('#speed button').forEach(x=>x.classList.remove('on')); b.classList.add('on');
  if(playing) applySeg(curSeg);
}));

// nudge
function nudge(side, dir){
  const step = side==='a'?stepA:stepB;
  if(side==='a') offA+=dir*step; else offB+=dir*step;
  const off = side==='a'?offA:offB, fps = side==='a'?fpsA:fpsB;
  const frames = Math.round(off*fps);
  document.getElementById(side==='a'?'aOff':'bOff').textContent=(frames>0?'+':'')+frames+'f';
  const v = side==='a'?va:vb;
  if(playing){ v.currentTime=Math.max(0, v.currentTime+dir*step); } else { seek(p); }
}
document.getElementById('aMinus').addEventListener('click',()=>nudge('a',-1));
document.getElementById('aPlus').addEventListener('click',()=>nudge('a',1));
document.getElementById('bMinus').addEventListener('click',()=>nudge('b',-1));
document.getElementById('bPlus').addEventListener('click',()=>nudge('b',1));

let ready=0; [va,vb].forEach(v=>v.addEventListener('loadedmetadata',()=>{ if(++ready===2){ seek(p); paint(p); } }));
setTimeout(()=>{ if(ready<2){ seek(p); paint(p); } }, 1600);
</script></body></html>"""
