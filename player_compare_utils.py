"""
BarrelLabs / SwingAI — player-comparison utility helpers.

Pure-data helpers extracted from the (now-retired) dashboard.py renderer
so live code can keep computing MLB match % and reference-name display
without depending on the dead renderer module.

Consumers:
    development_tracker.py  (_similarity_pct, _pretty_player_name)

These functions take/return plain dicts and strings only — no Streamlit
or rendering dependencies.
"""

from __future__ import annotations

from typing import Any, Dict, List


def _similarity_pct(record: Dict[str, Any]) -> float:
    score = record.get("score")
    if isinstance(score, (int, float)) and 0 <= float(score) <= 100:
        return float(score)
    sims: List[float] = []
    mt = record.get("metric_table") or {}
    if isinstance(mt, dict):
        for group_rows in mt.values():
            if not isinstance(group_rows, list):
                continue
            for r in group_rows:
                try:
                    sims.append(float(r.get("sim_pct", 0)))
                except Exception:
                    pass
    return (sum(sims) / len(sims)) if sims else 0.0


def _pretty_player_name(slug: str) -> str:
    if not slug:
        return ""
    base = str(slug)
    for suffix in ("_swing", " copy", ".mp4"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
    base = base.replace("_", " ").replace("-", " ").strip()
    return " ".join(
        w.capitalize() if w.lower() not in ("jr", "sr") else w.upper() + "."
        for w in base.split()
    )
