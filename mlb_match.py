"""Scale-invariant movement match — pure functions. Spec System 2."""
from __future__ import annotations
import json, math, os
from typing import Optional

_EPS = 1e-6


def _g(d, *path, default=0.0):
    for k in path:
        d = (d or {}).get(k)
        if d is None:
            return default
    return d


def movement_vector(fp: dict) -> list:
    t = fp.get("timing_ms") or {}
    total = (t.get("total_swing") or 0) or _EPS
    rot = fp.get("rotation_deg") or {}
    ph = fp.get("phases_t") or {}
    kn = fp.get("knee_deg") or {}
    plant_to_contact = ((ph.get("contact") or 0) - (ph.get("foot_plant") or 0)) or _EPS
    return [
        float((t.get("load_duration") or 0) / total),
        float((t.get("foot_plant_to_launch") or 0) / total),
        float((t.get("launch_to_contact") or 0) / total),
        float(((rot.get("peak_separation_t") or 0) - (ph.get("foot_plant") or 0)) / plant_to_contact),
        float((rot.get("separation_at_contact") or 0) / ((rot.get("peak_separation") or 0) or _EPS)),
        float((rot.get("peak_hip") or 0) / (abs(rot.get("peak_separation") or 0) + _EPS)),
        float((kn.get("re_extension") or 0) / (((kn.get("at_foot_plant") or 0) - (kn.get("min_during_load") or 0)) + _EPS)),
        float(_g(fp, "head_movement_normalized_foot_plant_to_contact", "total_drift_torso")),
    ]


def zscore(vec, stats):
    return [(v - m) / (s or _EPS) for v, m, s in zip(vec, stats["means"], stats["stds"])]


def _dist(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


_MATCH_SCALE = 3.0


def match_pro(z_vector: list, stats: dict) -> dict:
    ci = min(range(len(stats["centroids"])), key=lambda i: _dist(z_vector, stats["centroids"][i]))
    in_cluster = [p for p in stats["pros"] if p["cluster"] == ci] or stats["pros"]
    best = min(in_cluster, key=lambda p: _dist(z_vector, p["z"]))
    pct = round(100.0 * math.exp(-_dist(z_vector, best["z"]) / _MATCH_SCALE))
    return {"slug": best["slug"], "name": best["name"],
            "movement_match_pct": max(0, min(100, pct)), "cluster": ci}
