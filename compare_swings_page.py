"""
Compare Swings — standalone page.

A premium, editorial side-by-side comparison of any two of a player's own
swings. Built on the player's own saved records (reliable ~30fps phone clips),
independent of the MLB reference library. Matches the BarrelLabs "Edge" design
system (Instrument Serif italic + Geist / Geist Mono, bone/gold/red on near
black) used by the swing report.

Layout (top → bottom):
  1. Edge masthead (Compare tab active) + page wrapper
  2. Hero (eyebrow + serif title + "N swings on file")
  3. Two in-session swing pickers (st.selectbox — never <a href>, which would
     full-reload and log the user out)
  4. History stat strip (first / latest / best / average / total)
  5. The "versus" centerpiece — Swing A · delta medallion · Swing B (score
     rings, band pills, focus area)
  6. Auto narrative summary
  7. Metric deltas — dual A/B bars per metric, improvement chips
  8. Improved / Still-to-close split
  9. Focus-area timeline (all swings, A & B highlighted)

Public entry point: render_compare_swings_page(user).
Pure helpers (kpi_stats / compare_metric_rows / summary_sentence / …) are unit
tested in tests/test_compare_swings_page.py.
"""

from __future__ import annotations

import html
import statistics
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st

from bl_edge_chrome import (
    render_edge_masthead,
    render_edge_page_wrapper_open,
    render_edge_page_wrapper_close,
)
from bl_theme import inject_global_theme
from swing_report_dashboard_preview import _ring_svg, _band_class_srd


# =====================================================================
#  PURE HELPERS (unit tested)
# =====================================================================
def score_of(rec: Dict[str, Any]) -> Optional[float]:
    """Headline score for a record — prefers the age-fair swing_score, falls
    back to the legacy similarity score. None when neither is present."""
    for key in ("swing_score", "score"):
        v = rec.get(key)
        if v is not None:
            try:
                return float(v)
            except (TypeError, ValueError):
                continue
    return None


def band_of(rec: Dict[str, Any]) -> str:
    """green / amber / red for a record's score."""
    s = score_of(rec)
    return _band_class_srd(rec.get("score_band_color") or "", int(round(s)) if s is not None else 0)


def swing_no(rec: Dict[str, Any]) -> Optional[int]:
    try:
        return int(rec.get("swing_number"))
    except (TypeError, ValueError):
        return None


def swing_label(rec: Dict[str, Any]) -> str:
    n = swing_no(rec)
    return f"Swing #{n:02d}" if n is not None else "Swing"


def fmt_date(rec: Dict[str, Any]) -> str:
    ts = rec.get("timestamp") or rec.get("created_at") or rec.get("date")
    if not ts:
        return "—"
    if isinstance(ts, str):
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00")).strftime("%b %-d · %Y")
        except Exception:
            return ts[:10]
    try:
        return ts.strftime("%b %-d · %Y")
    except Exception:
        return str(ts)


def metric_pcts(rec: Dict[str, Any]) -> Dict[str, int]:
    """{metric label → similarity %} from the record's metric_table, skipping
    flagged (camera-view-unreliable) rows. Robust to missing/odd shapes."""
    out: Dict[str, int] = {}
    table = rec.get("metric_table") or {}
    if not isinstance(table, dict):
        return out
    for rows in table.values():
        if not isinstance(rows, list):
            continue
        for r in rows:
            if not isinstance(r, dict) or r.get("flagged"):
                continue
            label, pct = r.get("label"), r.get("sim_pct")
            if label is None or pct is None:
                continue
            try:
                out[str(label)] = int(round(float(pct)))
            except (TypeError, ValueError):
                continue
    return out


def compare_metric_rows(
    older: Dict[str, Any], newer: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """One row per metric present in BOTH swings: label, older %, newer %, delta.
    Sorted by largest absolute change first. Higher % = closer to pro = better."""
    a, b = metric_pcts(older), metric_pcts(newer)
    rows = []
    for label in a.keys() & b.keys():
        rows.append({
            "label": label,
            "a_pct": a[label],
            "b_pct": b[label],
            "delta": b[label] - a[label],
        })
    rows.sort(key=lambda r: abs(r["delta"]), reverse=True)
    return rows


def kpi_stats(history: List[Dict[str, Any]]) -> Dict[str, Any]:
    """First / latest / best / average / total over a player's score history
    (oldest-first). latest_is_pb is True when the most recent ties the best."""
    scores = [score_of(r) for r in history]
    scores = [s for s in scores if s is not None]
    if not scores:
        return {"first": None, "latest": None, "best": None,
                "average": None, "total": len(history), "latest_is_pb": False}
    return {
        "first": scores[0],
        "latest": scores[-1],
        "best": max(scores),
        "average": statistics.mean(scores),
        "total": len(history),
        "latest_is_pb": scores[-1] >= max(scores),
    }


def focus_area(rec: Dict[str, Any]) -> str:
    """The swing's top focus — its #1 narrative title."""
    narr = rec.get("narratives") or []
    if isinstance(narr, list) and narr and isinstance(narr[0], dict):
        return str(narr[0].get("title") or "—")
    return "—"


def delta_class(d: Optional[float], *, eps: float = 0.5) -> str:
    if d is None or abs(d) < eps:
        return "flat"
    return "up" if d > 0 else "down"


def summary_sentence(
    older: Dict[str, Any], newer: Dict[str, Any], rows: List[Dict[str, Any]]
) -> str:
    """Auto narrative: how many metrics improved, the score move, the biggest
    gain and the largest remaining gap. Uses only real, present data."""
    improved = [r for r in rows if r["delta"] > 0]
    sa, sb = score_of(older), score_of(newer)
    parts: List[str] = []
    if rows:
        parts.append(
            f"{len(improved)} of {len(rows)} tracked metrics improved between "
            f"{swing_label(older)} and {swing_label(newer)}."
        )
    if sa is not None and sb is not None:
        d = sb - sa
        verb = "rose" if d > 0 else ("dropped" if d < 0 else "held")
        arrow = f"{int(round(sa))} → {int(round(sb))}"
        parts.append(f"Overall score {verb} {arrow}.")
    gains = [r for r in rows if r["delta"] > 0]
    if gains:
        top = max(gains, key=lambda r: r["delta"])
        parts.append(f"Biggest gain: {top['label']} (+{top['delta']}%).")
    drops = [r for r in rows if r["delta"] < 0]
    if drops:
        worst = min(drops, key=lambda r: r["delta"])
        parts.append(f"Largest opportunity remaining: {worst['label']} ({worst['delta']}%).")
    return " ".join(parts) if parts else "Not enough shared data to compare these two swings."


# =====================================================================
#  STYLES — scoped to .cmp-wrap, reusing Edge tokens
# =====================================================================
_CMP_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Geist:wght@400;500;600&family=Geist+Mono:wght@400;500;600&display=swap');

/* ====================================================================
   TOKENS + LAYOUT scoped to the REAL content container.
   Streamlit auto-closes a bare `<div class="cmp-wrap">` into an empty
   phantom node, so design tokens keyed only to `.cmp-wrap` never reach
   the page content (it renders as SIBLINGS of the phantom inside
   [data-testid="stMainBlockContainer"]). We define everything on the
   block container itself — on a Compare render it holds only this page.
   The `.cmp-wrap` fallback keeps tokens valid for any nested use. */
[data-testid="stMainBlockContainer"]:has(.cmp-wrap),
.cmp-wrap{
  --bone:#F4EFE6; --bone-70:rgba(244,239,230,0.70); --bone-50:rgba(244,239,230,0.50);
  --bone-35:rgba(244,239,230,0.35); --ink:#0A0B0E; --gold:#E8C170; --red:#E64530;
  --green:#4AE38C; --line:rgba(244,239,230,0.08); --line-hi:rgba(244,239,230,0.16);
  --glass:rgba(255,255,255,0.025); --glass-2:rgba(255,255,255,0.045);
  --serif:'Instrument Serif',Georgia,serif; --sans:'Geist',-apple-system,sans-serif;
  --mono:'Geist Mono',ui-monospace,monospace;
  font-family:var(--sans); color:var(--bone);
}
/* Real content frame (1560 / 40px) so Compare aligns with the nav and
   every other page, with no horizontal overflow. */
[data-testid="stMainBlockContainer"]:has(.cmp-wrap){
  max-width:1560px !important; margin:0 auto !important;
  padding:8px 40px 64px !important; box-sizing:border-box !important;
}
.cmp-wrap{ display:contents; }
[data-testid="stMainBlockContainer"]:has(.cmp-wrap) *{box-sizing:border-box;}
@keyframes cmpUp{from{opacity:0;transform:translateY(14px);}to{opacity:1;transform:none;}}
.cmp-rise{opacity:0; animation:cmpUp .7s cubic-bezier(.2,.7,.2,1) forwards;}

/* hero */
.cmp-hero{display:flex; align-items:flex-end; justify-content:space-between;
  gap:24px; flex-wrap:wrap; padding:14px 0 18px; border-bottom:1px solid var(--line);}
.cmp-eyebrow{font-family:var(--mono); font-size:11px; font-weight:600;
  letter-spacing:.28em; text-transform:uppercase; color:var(--red);
  display:flex; align-items:center; gap:9px; margin-bottom:12px;}
.cmp-eyebrow .dot{width:6px;height:6px;border-radius:50%;background:var(--red);
  box-shadow:0 0 10px var(--red); animation:cmpPulse 2.4s ease-in-out infinite;}
@keyframes cmpPulse{0%,100%{opacity:1;}50%{opacity:.35;}}
.cmp-title{font-family:var(--serif); font-style:italic; font-size:3.4rem;
  line-height:.98; letter-spacing:-.02em; color:var(--bone); margin:0;}
.cmp-title .amp{color:var(--gold);}
.cmp-meta{font-family:var(--mono); font-size:11px; letter-spacing:.08em;
  color:var(--bone-50); text-align:right; white-space:nowrap;}

/* kpi strip */
.cmp-kpis{display:grid; grid-template-columns:repeat(5,1fr); gap:12px; margin:24px 0 8px;}
@media(max-width:760px){.cmp-kpis{grid-template-columns:repeat(2,1fr);}}
.cmp-kpi{border:1px solid var(--line); border-radius:14px; padding:15px 16px;
  background:var(--glass);}
.cmp-kpi.pb{border-color:rgba(232,193,112,.45);
  background:radial-gradient(120% 90% at 50% 0%,rgba(232,193,112,.10),transparent 70%),var(--glass);}
.cmp-kpi .k{font-family:var(--mono); font-size:9.5px; font-weight:600;
  letter-spacing:.2em; text-transform:uppercase; color:var(--bone-50);}
.cmp-kpi .v{font-family:var(--serif); font-style:italic; font-size:2rem;
  line-height:1; color:var(--bone); margin-top:8px;}
.cmp-kpi.pb .v{color:var(--gold);}

/* versus centerpiece */
.cmp-versus{display:grid; grid-template-columns:1fr 132px 1fr; gap:14px;
  align-items:stretch; margin:14px 0 8px;}
@media(max-width:760px){.cmp-versus{grid-template-columns:1fr; }
  .cmp-medallion{order:2; height:84px;}}
.cmp-card{border:1px solid var(--line); border-radius:22px; padding:26px 26px 24px;
  background:radial-gradient(120% 70% at 50% 0%,rgba(244,239,230,.04),transparent 65%),var(--glass);
  display:flex; flex-direction:column; align-items:center; text-align:center;}
.cmp-card.b{border-color:rgba(230,69,48,.30);
  background:radial-gradient(120% 70% at 50% 0%,rgba(230,69,48,.10),transparent 62%),var(--glass);}
.cmp-card .role{font-family:var(--mono); font-size:9.5px; font-weight:600;
  letter-spacing:.24em; text-transform:uppercase; color:var(--bone-50); margin-bottom:14px;}
.cmp-card.b .role{color:var(--red);}
.cmp-card .lab{font-family:var(--serif); font-style:italic; font-size:1.5rem;
  color:var(--bone); margin:14px 0 2px;}
.cmp-card .date{font-family:var(--mono); font-size:10px; letter-spacing:.06em;
  color:var(--bone-35); margin-bottom:14px;}
.cmp-band{font-family:var(--mono); font-size:9.5px; font-weight:600; letter-spacing:.16em;
  text-transform:uppercase; display:inline-flex; align-items:center; gap:7px;
  padding:5px 12px; border-radius:999px; border:1px solid var(--line-hi);}
.cmp-band .d{width:6px;height:6px;border-radius:50%;box-shadow:0 0 8px currentColor;}
.cmp-band.green{color:var(--green);} .cmp-band.amber{color:var(--gold);} .cmp-band.red{color:var(--red);}
.cmp-card .foot{font-family:var(--sans); font-size:12.5px; color:var(--bone-50);
  margin-top:16px; line-height:1.5; max-width:30ch;}
.cmp-card .foot b{color:var(--bone-70); font-weight:500;}

/* central medallion */
.cmp-medallion{display:flex; align-items:center; justify-content:center;}
.cmp-med-inner{width:104px; height:104px; border-radius:50%;
  display:flex; flex-direction:column; align-items:center; justify-content:center;
  border:1px solid var(--line-hi); background:rgba(10,11,14,.7);
  font-family:var(--mono);}
.cmp-med-inner.up{border-color:rgba(74,227,140,.5); color:var(--green);}
.cmp-med-inner.down{border-color:rgba(230,69,48,.5); color:var(--red);}
.cmp-med-inner.flat{color:var(--bone-50);}
.cmp-med-inner .arrow{font-size:22px; line-height:1;}
.cmp-med-inner .num{font-family:var(--serif); font-style:italic; font-size:2.1rem; line-height:1; margin-top:2px;}
.cmp-med-inner .cap{font-size:8.5px; letter-spacing:.2em; text-transform:uppercase;
  color:var(--bone-50); margin-top:5px;}

/* sections */
.cmp-section{margin-top:40px;}
.cmp-sec-head{display:flex; align-items:baseline; justify-content:space-between;
  gap:16px; padding-bottom:12px; border-bottom:1px solid var(--line); margin-bottom:20px;}
.cmp-sec-title{font-family:var(--serif); font-style:italic; font-size:1.7rem;
  letter-spacing:-.015em; color:var(--bone); margin:0;}
.cmp-sec-sub{font-family:var(--mono); font-size:10px; letter-spacing:.12em;
  text-transform:uppercase; color:var(--bone-50);}

/* summary */
.cmp-summary{border:1px solid var(--line); border-left:2px solid var(--gold);
  border-radius:14px; padding:18px 22px; background:var(--glass);
  font-family:var(--sans); font-size:14.5px; line-height:1.6; color:var(--bone-70);}

/* metric dual-bars */
.cmp-metric{display:grid; grid-template-columns:190px 1fr 78px; gap:18px;
  align-items:center; padding:14px 4px; border-bottom:1px solid var(--line);}
@media(max-width:760px){.cmp-metric{grid-template-columns:1fr; gap:8px;}}
.cmp-metric .name{font-family:var(--mono); font-size:10.5px; font-weight:600;
  letter-spacing:.12em; text-transform:uppercase; color:var(--bone-70);}
.cmp-bars{display:flex; flex-direction:column; gap:7px;}
.cmp-bar{display:flex; align-items:center; gap:10px;}
.cmp-bar .tag{font-family:var(--mono); font-size:9px; letter-spacing:.1em;
  color:var(--bone-35); width:14px;}
.cmp-track{flex:1; height:8px; border-radius:999px; background:rgba(244,239,230,.07);
  overflow:hidden;}
.cmp-fill{height:100%; border-radius:999px;}
.cmp-fill.green{background:linear-gradient(90deg,rgba(74,227,140,.5),var(--green));}
.cmp-fill.amber{background:linear-gradient(90deg,rgba(232,193,112,.5),var(--gold));}
.cmp-fill.red{background:linear-gradient(90deg,rgba(230,69,48,.5),var(--red));}
.cmp-bar .pct{font-family:var(--mono); font-size:11px; color:var(--bone-70); width:34px; text-align:right;}
.cmp-bar.is-b .pct{color:var(--bone);}
.cmp-chip{font-family:var(--mono); font-size:11.5px; font-weight:600; text-align:right;}
.cmp-chip.up{color:var(--green);} .cmp-chip.down{color:var(--red);} .cmp-chip.flat{color:var(--bone-35);}

/* improved / needs-work split */
.cmp-split{display:grid; grid-template-columns:1fr 1fr; gap:16px;}
@media(max-width:760px){.cmp-split{grid-template-columns:1fr;}}
.cmp-col{border:1px solid var(--line); border-radius:16px; padding:18px 20px; background:var(--glass);}
.cmp-col .h{font-family:var(--mono); font-size:10px; font-weight:600; letter-spacing:.18em;
  text-transform:uppercase; margin-bottom:14px; display:flex; align-items:center; gap:8px;}
.cmp-col.win .h{color:var(--green);} .cmp-col.work .h{color:var(--red);}
.cmp-li{display:flex; align-items:center; justify-content:space-between; gap:12px;
  padding:9px 0; border-bottom:1px solid var(--line); font-size:13px; color:var(--bone-70);}
.cmp-li:last-child{border-bottom:none;}
.cmp-li .m{font-family:var(--sans);}
.cmp-li .d{font-family:var(--mono); font-size:12px; font-weight:600;}
.cmp-li .d.up{color:var(--green);} .cmp-li .d.down{color:var(--red);}
.cmp-empty-col{font-family:var(--sans); font-size:12.5px; color:var(--bone-35); font-style:italic;}

/* timeline */
.cmp-timeline{position:relative; margin-top:6px; padding-left:22px;}
.cmp-timeline::before{content:""; position:absolute; left:4px; top:6px; bottom:6px;
  width:1px; background:linear-gradient(180deg,transparent,var(--line-hi),transparent);}
.cmp-tl{position:relative; display:flex; align-items:center; justify-content:space-between;
  gap:14px; padding:11px 0;}
.cmp-tl::before{content:""; position:absolute; left:-22px; top:50%; transform:translateY(-50%);
  width:9px; height:9px; border-radius:50%; background:var(--ink); border:1px solid var(--bone-35);}
.cmp-tl.is-a::before{border-color:var(--gold); box-shadow:0 0 10px rgba(232,193,112,.6);}
.cmp-tl.is-b::before{border-color:var(--red); box-shadow:0 0 10px rgba(230,69,48,.6);}
.cmp-tl .left{display:flex; flex-direction:column; gap:2px;}
.cmp-tl .sw{font-family:var(--mono); font-size:10px; letter-spacing:.1em; color:var(--bone-50);}
.cmp-tl .fa{font-family:var(--sans); font-size:13px; color:var(--bone-70);}
.cmp-tl .sc{font-family:var(--serif); font-style:italic; font-size:1.3rem; color:var(--bone);}
.cmp-tl.is-a .sc{color:var(--gold);} .cmp-tl.is-b .sc{color:var(--red);}

/* side-by-side video self-suppress note */
.cvv-note{border:1px solid var(--line); border-radius:14px; padding:18px 22px;
  background:var(--glass); font-family:var(--sans); font-size:13.5px; color:var(--bone-50);
  text-align:center; margin:4px 0 8px;}

/* plain-language "what changed, where to watch" cards (under the video) */
.cmp-watch-grid{display:grid; grid-template-columns:repeat(3,1fr); gap:12px;}
@media(max-width:860px){.cmp-watch-grid{grid-template-columns:1fr;}}
.cmp-watch-card{border:1px solid var(--line); border-left:2px solid var(--bone-35);
  border-radius:14px; padding:16px 18px; background:var(--glass);}
.cmp-watch-card.up{border-left-color:var(--green);}
.cmp-watch-card.down{border-left-color:var(--red);}
.cwc-top{display:flex; align-items:center; gap:9px; margin-bottom:9px; flex-wrap:wrap;}
.cwc-tag{font-family:var(--mono); font-size:9px; font-weight:600; letter-spacing:.16em;
  text-transform:uppercase; padding:3px 8px; border-radius:999px; border:1px solid var(--line-hi); color:var(--bone-50);}
.cmp-watch-card.up .cwc-tag{color:var(--green); border-color:rgba(74,227,140,.4);}
.cmp-watch-card.down .cwc-tag{color:var(--red); border-color:rgba(230,69,48,.4);}
.cwc-ttl{font-family:var(--serif); font-style:italic; font-size:1.18rem; color:var(--bone);}
.cwc-top .pct{margin-left:auto; font-family:var(--mono); font-size:10.5px; color:var(--bone-50); letter-spacing:.04em;}
.cwc-mean{font-family:var(--sans); font-size:13px; line-height:1.5; color:var(--bone-70); margin-bottom:11px;}
.cwc-look{font-family:var(--sans); font-size:12.5px; line-height:1.5; color:var(--bone-50);
  border-top:1px solid var(--line); padding-top:10px;}
.cwc-look b{color:var(--gold); font-weight:500; font-family:var(--mono); font-size:10.5px;
  letter-spacing:.08em; text-transform:uppercase;}
.cwc-eye{color:var(--gold); margin-right:4px;}

/* empty state */
.cmp-empty{text-align:center; padding:64px 24px; border:1px dashed var(--line-hi);
  border-radius:20px; background:var(--glass); margin-top:24px;}
.cmp-empty .ic{font-size:30px; color:var(--bone-35); margin-bottom:14px;}
.cmp-empty .t{font-family:var(--serif); font-style:italic; font-size:1.7rem; color:var(--bone); margin-bottom:10px;}
.cmp-empty .b{font-family:var(--sans); font-size:14px; color:var(--bone-50); line-height:1.6; max-width:46ch; margin:0 auto;}

/* ====================================================================
   SWING PICKERS — a real keyed st.container so the editorial card frame
   + dark selectbox polish actually wrap the two st.selectbox widgets
   (the default Streamlit white selects were the "old looking" controls).
   Scoped to the keyed container so it can't bleed into the masthead.
   ==================================================================== */
.st-key-cmp_picker_card{
  background:var(--glass) !important; border:1px solid var(--line) !important;
  border-radius:16px !important; padding:16px 18px 18px !important;
  margin:24px 0 8px !important;
}
.st-key-cmp_picker_card .cmp-picker-eyebrow{
  font-family:var(--mono); font-size:10px; font-weight:600; letter-spacing:.2em;
  text-transform:uppercase; color:var(--bone-50); margin-bottom:12px;}
.st-key-cmp_picker_card label, .st-key-cmp_picker_card label p{
  font-family:var(--mono) !important; font-size:10px !important;
  letter-spacing:.18em !important; text-transform:uppercase !important;
  color:var(--bone-50) !important;}
.st-key-cmp_picker_card [data-baseweb="select"] > div{
  background:#0F1115 !important; border-color:var(--line-hi) !important;
  color:var(--bone) !important; border-radius:12px !important;
  font-family:var(--sans) !important;}
.st-key-cmp_picker_card [data-baseweb="select"] div{ color:var(--bone) !important; }
.st-key-cmp_picker_card [data-baseweb="select"] svg{ fill:var(--bone-50) !important; }

/* ====================================================================
   RESPONSIVE GUTTER — placed AFTER base rules so source order can't let
   the base 40px padding override these (known codebase gotcha). The
   gutter lives on the block container, tracking the masthead's gutter. */
@media(max-width:1100px){
  [data-testid="stMainBlockContainer"]:has(.cmp-wrap){
    padding:8px 22px 64px !important;}
  .cmp-title{font-size:2.8rem;}
}
@media(max-width:560px){
  [data-testid="stMainBlockContainer"]:has(.cmp-wrap){
    padding:8px 16px 56px !important;}
  .cmp-title{font-size:2.4rem;}
  .cmp-hero{padding:12px 0 14px;}
}
</style>
"""


# =====================================================================
#  HTML BUILDERS
# =====================================================================
def _tier(pct: int) -> str:
    return "green" if pct >= 80 else ("amber" if pct >= 60 else "red")


def _hero_html(total: int) -> str:
    return f"""
<div class="cmp-hero cmp-rise" style="animation-delay:.02s">
  <div>
    <div class="cmp-eyebrow"><span class="dot"></span>Compare</div>
    <h1 class="cmp-title">Swing <span class="amp">vs.</span> Swing</h1>
  </div>
  <div class="cmp-meta">{total} swing{'s' if total != 1 else ''} on file</div>
</div>
"""


def _kpi_html(k: Dict[str, Any]) -> str:
    def fmt(v):
        return "—" if v is None else f"{int(round(v))}"
    pb = " pb" if k.get("latest_is_pb") and k.get("total", 0) > 1 else ""
    tiles = [
        ("First", fmt(k["first"]), ""),
        ("Latest", fmt(k["latest"]), ""),
        ("Best", fmt(k["best"]), pb),
        ("Average", fmt(k["average"]), ""),
        ("Swings", str(k["total"]), ""),
    ]
    cells = "".join(
        f'<div class="cmp-kpi{cls}"><div class="k">{lab}</div><div class="v">{val}</div></div>'
        for lab, val, cls in tiles
    )
    return f'<div class="cmp-kpis cmp-rise" style="animation-delay:.08s">{cells}</div>'


def _card_html(rec: Dict[str, Any], role: str, is_b: bool) -> str:
    s = score_of(rec)
    if s is None:
        # No score on this record — show a neutral state, not a red "Rebuild".
        ring = _ring_svg(0, "amber", size=120)
        band_html = '<span class="cmp-band amber"><span class="d"></span>No score</span>'
    else:
        band = band_of(rec)
        ring = _ring_svg(int(round(s)), band, size=120)
        band_label = {"green": "Elite", "amber": "Strong", "red": "Rebuild"}[band]
        band_html = f'<span class="cmp-band {band}"><span class="d"></span>{band_label}</span>'
    ref = rec.get("reference_name") or rec.get("mlb_comp")
    fa = focus_area(rec)
    bits = []
    if ref:
        bits.append(f'vs. <b>{html.escape(str(ref))}</b>')
    if fa and fa != "—":
        bits.append(f'Focus · <b>{html.escape(fa)}</b>')
    foot = f'<div class="foot">{"<br>".join(bits)}</div>' if bits else ""
    return f"""
<div class="cmp-card{' b' if is_b else ''}">
  <div class="role">{html.escape(role)}</div>
  {ring}
  <div class="lab">{html.escape(swing_label(rec))}</div>
  <div class="date">{html.escape(fmt_date(rec))}</div>
  {band_html}
  {foot}
</div>
"""


def _medallion_html(older: Dict[str, Any], newer: Dict[str, Any]) -> str:
    sa, sb = score_of(older), score_of(newer)
    if sa is None or sb is None:
        return '<div class="cmp-medallion"><div class="cmp-med-inner flat"><span class="num">—</span><span class="cap">Score</span></div></div>'
    d = int(round(sb - sa))
    cls = delta_class(d, eps=0.5)
    arrow = {"up": "↑", "down": "↓", "flat": "→"}[cls]
    num = f"+{d}" if d > 0 else (f"{d}" if d < 0 else "±0")
    return f"""
<div class="cmp-medallion">
  <div class="cmp-med-inner {cls}">
    <span class="arrow">{arrow}</span>
    <span class="num">{num}</span>
    <span class="cap">Score Δ</span>
  </div>
</div>
"""


def _versus_html(older: Dict[str, Any], newer: Dict[str, Any]) -> str:
    return f"""
<div class="cmp-versus cmp-rise" style="animation-delay:.14s">
  {_card_html(older, "Swing A · earlier", is_b=False)}
  {_medallion_html(older, newer)}
  {_card_html(newer, "Swing B · later", is_b=True)}
</div>
"""


def _summary_html(older, newer, rows) -> str:
    return f"""
<div class="cmp-section cmp-rise" style="animation-delay:.2s">
  <div class="cmp-summary">{html.escape(summary_sentence(older, newer, rows))}</div>
</div>
"""


def _metric_rows_html(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return ""
    out = ['<div class="cmp-section cmp-rise" style="animation-delay:.26s">',
           '<div class="cmp-sec-head"><h2 class="cmp-sec-title">Metric by metric</h2>'
           '<span class="cmp-sec-sub">% match to pro · A → B</span></div>']
    for r in rows:
        cls = delta_class(r["delta"], eps=0.5)
        arrow = {"up": "↑", "down": "↓", "flat": "→"}[cls]
        chip = f"+{r['delta']}" if r["delta"] > 0 else (f"{r['delta']}" if r["delta"] < 0 else "±0")
        out.append(f"""
<div class="cmp-metric">
  <div class="name">{html.escape(r['label'])}</div>
  <div class="cmp-bars">
    <div class="cmp-bar"><span class="tag">A</span>
      <div class="cmp-track"><div class="cmp-fill {_tier(r['a_pct'])}" style="width:{max(2,min(100,r['a_pct']))}%"></div></div>
      <span class="pct">{r['a_pct']}%</span></div>
    <div class="cmp-bar is-b"><span class="tag">B</span>
      <div class="cmp-track"><div class="cmp-fill {_tier(r['b_pct'])}" style="width:{max(2,min(100,r['b_pct']))}%"></div></div>
      <span class="pct">{r['b_pct']}%</span></div>
  </div>
  <div class="cmp-chip {cls}">{arrow} {chip}</div>
</div>""")
    out.append("</div>")
    return "".join(out)


def _split_html(rows: List[Dict[str, Any]]) -> str:
    wins = [r for r in rows if r["delta"] > 0][:5]
    work = sorted([r for r in rows if r["delta"] < 0], key=lambda r: r["delta"])[:5]
    if not wins and not work:
        return ""

    def col(items, kind, head, empty):
        if not items:
            body = f'<div class="cmp-empty-col">{empty}</div>'
        else:
            body = "".join(
                f'<div class="cmp-li"><span class="m">{html.escape(r["label"])}</span>'
                f'<span class="d {"up" if r["delta"]>0 else "down"}">'
                f'{"+" if r["delta"]>0 else ""}{r["delta"]}%</span></div>'
                for r in items
            )
        dot = "▲" if kind == "win" else "▼"
        return f'<div class="cmp-col {kind}"><div class="h">{dot} {head}</div>{body}</div>'

    return f"""
<div class="cmp-section cmp-rise" style="animation-delay:.32s">
  <div class="cmp-sec-head"><h2 class="cmp-sec-title">What moved</h2>
    <span class="cmp-sec-sub">Swing A → Swing B</span></div>
  <div class="cmp-split">
    {col(wins, "win", "Improved", "No metric improved between these two.")}
    {col(work, "work", "Still to close", "Nothing regressed — clean sheet.")}
  </div>
</div>
"""


def _timeline_html(history: List[Dict[str, Any]], a_idx: int, b_idx: int) -> str:
    rows = []
    for i, rec in enumerate(history):
        s = score_of(rec)
        cls = " is-a" if i == a_idx else (" is-b" if i == b_idx else "")
        fa = focus_area(rec)
        fa_html = f'<span class="fa">{html.escape(fa)}</span>' if fa and fa != "—" else ""
        rows.append(f"""
<div class="cmp-tl{cls}">
  <div class="left">
    <span class="sw">{html.escape(swing_label(rec))} · {html.escape(fmt_date(rec))}</span>
    {fa_html}
  </div>
  <span class="sc">{int(round(s)) if s is not None else '—'}</span>
</div>""")
    return f"""
<div class="cmp-section cmp-rise" style="animation-delay:.38s">
  <div class="cmp-sec-head"><h2 class="cmp-sec-title">Every swing, in order</h2>
    <span class="cmp-sec-sub">{len(history)} logged · A in gold · B in red</span></div>
  <div class="cmp-timeline">{''.join(rows)}</div>
</div>
"""


def _empty_html(title: str, body: str) -> str:
    return f"""
<div class="cmp-empty cmp-rise">
  <div class="ic">◇</div>
  <div class="t">{html.escape(title)}</div>
  <div class="b">{html.escape(body)}</div>
</div>
"""


# =====================================================================
#  PAGE RENDERER
# =====================================================================
def render_compare_swings_page(user: Dict[str, Any]) -> None:
    """Standalone Compare Swings page. Loads the player's history and renders a
    side-by-side comparison of two selected swings."""
    inject_global_theme()
    render_edge_masthead(user, active_page="compare_swings")
    render_edge_page_wrapper_open()
    st.markdown(_CMP_CSS, unsafe_allow_html=True)
    st.markdown('<div class="cmp-wrap">', unsafe_allow_html=True)

    history = _load_history(user)
    total = len(history)
    st.markdown(_hero_html(total), unsafe_allow_html=True)

    if total == 0:
        st.markdown(_empty_html(
            "No swings to compare yet",
            "Upload and analyze a swing from the Dashboard. Once you have two, "
            "this page lines them up side by side automatically.",
        ), unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        render_edge_page_wrapper_close()
        return

    st.markdown(_kpi_html(kpi_stats(history)), unsafe_allow_html=True)

    if total == 1:
        st.markdown(_empty_html(
            "One swing so far",
            "Comparison unlocks with your second analyzed swing. Your first is "
            "logged and ready — upload another from the Dashboard.",
        ), unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        render_edge_page_wrapper_close()
        return

    # --- in-session swing pickers (default to the latest two) ---
    # Wrapped in a real keyed container so the editorial card frame + dark
    # selectbox polish actually reach the widgets (a bare markdown <div>
    # collapses into a phantom sibling and never wraps them).
    labels = [f"{swing_label(r)} · {int(round(score_of(r))) if score_of(r) is not None else '—'} · {fmt_date(r)}"
              for r in history]
    idxs = list(range(total))
    with st.container(key="cmp_picker_card"):
        st.markdown('<div class="cmp-picker-eyebrow">Pick two swings</div>',
                    unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            a_idx = st.selectbox("Swing A (earlier)", idxs, index=total - 2,
                                 format_func=lambda i: labels[i], key="cmp_swing_a")
        with c2:
            b_idx = st.selectbox("Swing B (later)", idxs, index=total - 1,
                                 format_func=lambda i: labels[i], key="cmp_swing_b")

    # Enforce earlier→later regardless of pick order, so "improved/regressed"
    # and the score delta are always computed in the right direction. History
    # is oldest-first, so the smaller index is the earlier swing.
    lo, hi = sorted((a_idx, b_idx))
    older, newer = history[lo], history[hi]
    rows = compare_metric_rows(older, newer)

    # --- Watch them side by side (phase-locked dual video) ---
    # Additive: renders only when both swings have a saved clip + shared phases,
    # otherwise self-suppresses to a quiet note. The metric comparison below
    # always renders regardless.
    st.markdown(
        """
        <div class="cmp-section cmp-rise" style="animation-delay:.12s">
          <div class="cmp-sec-head"><h2 class="cmp-sec-title">Watch them side by side</h2>
            <span class="cmp-sec-sub">Phase-locked · scrub once, both move</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    try:
        from compare_video_view import (
            render_compare_video, watch_cards, build_watch_breakdown_html,
        )
        render_compare_video(older, newer)
        # Plain-language "what changed, where to watch" right under the video, so
        # the numbers become something to actually look for in the two swings.
        st.markdown(build_watch_breakdown_html(watch_cards(rows)),
                    unsafe_allow_html=True)
    except Exception:
        # Video + breakdown are a bonus on top of the metric compare; never let
        # them break the page. Fall through to the numbers.
        pass

    st.markdown(_versus_html(older, newer), unsafe_allow_html=True)
    st.markdown(_summary_html(older, newer, rows), unsafe_allow_html=True)
    st.markdown(_metric_rows_html(rows), unsafe_allow_html=True)
    st.markdown(_split_html(rows), unsafe_allow_html=True)
    st.markdown(_timeline_html(history, lo, hi), unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)
    render_edge_page_wrapper_close()


def _load_history(user: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Player swing history (oldest-first). Degrades to [] (empty state) rather
    than crashing. `load_swing_history` already surfaces real storage errors via
    st.error, so anything reaching the except here is an unexpected bug in this
    page's path — surface it (don't masquerade a broken import / bad user shape
    as 'no swings')."""
    slug = (user.get("slug") or user.get("id")) if isinstance(user, dict) else None
    if not slug:
        return []
    try:
        from player_storage import load_swing_history
        return list(load_swing_history(slug) or [])
    except Exception as exc:  # noqa: BLE001 — surface, then degrade
        st.warning(f"Couldn't load your swing history: {exc}")
        return []
