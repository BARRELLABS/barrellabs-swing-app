"""One-shot offline builder: computes frozen movement-match stats from MLB references.

Usage: python scripts/build_match_stats.py
Writes: mlb_match_stats.json at repo root.
"""
from __future__ import annotations
import json
import math
import os
import random
import sys

# Allow importing mlb_match from repo root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mlb_match import movement_vector

_EPS = 1e-6
REFS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "references")
OUT_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "mlb_match_stats.json")

K = 3
MAX_ITERS = 20
SEED = 42


def load_references(refs_dir: str):
    pros = []
    for fname in sorted(os.listdir(refs_dir)):
        if not fname.endswith(".json"):
            continue
        slug = fname[:-5]
        path = os.path.join(refs_dir, fname)
        with open(path) as f:
            data = json.load(f)
        vec = movement_vector(data)
        pros.append({
            "slug": slug,
            "name": data.get("player_name", slug),
            "swing_style": data.get("swing_style", ""),
            "raw_vec": vec,
        })
    return pros


def compute_stats(pros):
    n = len(pros)
    dim = len(pros[0]["raw_vec"])
    means = []
    stds = []
    for i in range(dim):
        vals = [p["raw_vec"][i] for p in pros]
        mu = sum(vals) / n
        variance = sum((v - mu) ** 2 for v in vals) / n
        sigma = math.sqrt(variance) or _EPS
        means.append(mu)
        stds.append(sigma)
    return means, stds


def zscore_pros(pros, means, stds):
    dim = len(means)
    for p in pros:
        p["z"] = [(p["raw_vec"][i] - means[i]) / (stds[i] or _EPS) for i in range(dim)]
    return pros


def _dist(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def kmeans(z_vecs, k: int, max_iters: int, seed: int):
    rng = random.Random(seed)
    n = len(z_vecs)
    dim = len(z_vecs[0])
    # Initialize centroids by picking k random distinct indices
    indices = rng.sample(range(n), k)
    centroids = [list(z_vecs[i]) for i in indices]

    assignments = [0] * n
    for _ in range(max_iters):
        # Assignment step
        new_assignments = []
        for vec in z_vecs:
            best_ci = min(range(k), key=lambda ci: _dist(vec, centroids[ci]))
            new_assignments.append(best_ci)
        # Check convergence
        if new_assignments == assignments:
            break
        assignments = new_assignments
        # Update step: recompute centroids
        for ci in range(k):
            members = [z_vecs[i] for i, a in enumerate(assignments) if a == ci]
            if not members:
                # Re-seed empty cluster with a random point
                centroids[ci] = list(z_vecs[rng.randrange(n)])
            else:
                centroids[ci] = [sum(m[d] for m in members) / len(members) for d in range(dim)]

    return assignments, centroids


def main():
    pros = load_references(REFS_DIR)
    print(f"Loaded {len(pros)} reference players.")

    means, stds = compute_stats(pros)
    pros = zscore_pros(pros, means, stds)

    z_vecs = [p["z"] for p in pros]
    assignments, centroids = kmeans(z_vecs, K, MAX_ITERS, SEED)

    for i, p in enumerate(pros):
        p["cluster"] = assignments[i]

    # Build output
    out_pros = [
        {"slug": p["slug"], "name": p["name"], "z": p["z"], "cluster": p["cluster"]}
        for p in pros
    ]

    result = {
        "means": means,
        "stds": stds,
        "centroids": centroids,
        "pros": out_pros,
    }

    with open(OUT_FILE, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nWrote {OUT_FILE}")

    # Print cluster membership for human sanity-check
    print("\n=== Cluster Membership ===")
    for ci in range(K):
        members = [p for p in pros if p["cluster"] == ci]
        print(f"\nCluster {ci} ({len(members)} players):")
        for p in members:
            print(f"  - {p['name']} | {p['swing_style']}")


if __name__ == "__main__":
    main()
