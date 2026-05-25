"""
Compare v3 and v4 detector outputs against hand-labeled ground truth.

Reads fingerprint JSONs produced by `detect_phases.py DETECTOR_V4=true`
plus manifest entries with ground-truth labels, then computes:

  PER-SWING METRICS
    - v3 foot_plant frame error    (signed, frames)
    - v4 foot_plant frame error    (signed, frames)
    - v3 foot_plant timing error   (signed, ms; uses fingerprint.fps)
    - v4 foot_plant timing error   (signed, ms)
    - v4 stride_style correct      (bool — v3 doesn't classify stride style)
    - v3-v4 disagreement           (frames)
    - v4 confidence                (from detector_v4.confidence)
    - winner                       ("v3" | "v4" | "tie" — by absolute error)

  AGGREGATE METRICS
    - mean / median absolute error (v3, v4)
    - % swings within 3 / 10 frames of ground truth (v3, v4)
    - % swings where v4 beat v3, lost to v3, tied
    - stride-style confusion matrix and per-class accuracy
    - count of skipped swings (missing fingerprint, unlabeled, etc.)

Both raw per-swing rows and aggregate summary are returned for the
report writer to consume.
"""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional

from .manifest import Manifest, SwingEntry, GroundTruth, VALID_STRIDE_STYLES


THRESHOLD_FRAMES_TIGHT = 3   # "near match"
THRESHOLD_FRAMES_LOOSE = 10  # "in the ballpark"

# A foot_plant at/below this frame means the detector returned ~0 — it didn't
# find a plant at all. Those are crashes, not mis-timing, and must be excluded
# from accuracy aggregates so the headline isn't dominated by them.
DETECTION_FAILURE_MAX_FRAME = 1
# Clips at/above this fps behave very differently from ~30fps phone video, so
# accuracy is reported split at this boundary.
FPS_SPLIT = 40.0


@dataclass
class SwingResult:
    """One row of the comparison table."""
    id: str
    status: str               # "scored" | "unlabeled" | "missing_fingerprint" |
                              # "v4_unavailable" | "load_error"
    notes: str = ""

    # Ground truth
    gt_stride_style: Optional[str] = None
    gt_final_plant: Optional[int] = None
    gt_contact: Optional[int] = None

    # Detector outputs
    v3_foot_plant: Optional[int] = None
    v4_foot_plant: Optional[int] = None
    v3_contact: Optional[int] = None
    v4_contact: Optional[int] = None
    v4_confidence: Optional[float] = None
    v4_stride_style: Optional[str] = None
    v4_fallback: Optional[bool] = None
    fps: Optional[float] = None

    # Foot-plant errors (signed: detector - ground_truth)
    v3_error_frames: Optional[int] = None
    v4_error_frames: Optional[int] = None
    v3_error_ms: Optional[float] = None
    v4_error_ms: Optional[float] = None

    # Contact errors (signed: detector - ground_truth). Field names follow the
    # `{which}_error_frames` / `{which}_error_ms` convention so _detector_metrics
    # can aggregate them via which="v3_contact" / "v4_contact".
    v3_contact_error_frames: Optional[int] = None
    v4_contact_error_frames: Optional[int] = None
    v3_contact_error_ms: Optional[float] = None
    v4_contact_error_ms: Optional[float] = None

    # Cross-detector
    v3_v4_delta_frames: Optional[int] = None
    stride_style_correct: Optional[bool] = None
    winner: Optional[str] = None  # "v3" | "v4" | "tie"


@dataclass
class StrideStyleMetrics:
    """Confusion matrix + per-class accuracy."""
    confusion: dict[str, dict[str, int]] = field(default_factory=dict)
    per_class_accuracy: dict[str, float] = field(default_factory=dict)
    overall_accuracy: float = 0.0
    n_evaluated: int = 0
    n_correct: int = 0


@dataclass
class DetectorMetrics:
    """Per-detector aggregate timing accuracy."""
    n: int = 0
    mean_abs_error_frames: float = 0.0
    median_abs_error_frames: float = 0.0
    mean_abs_error_ms: float = 0.0
    median_abs_error_ms: float = 0.0
    pct_within_tight: float = 0.0   # % within ±3 frames
    pct_within_loose: float = 0.0   # % within ±10 frames
    mean_signed_error_frames: float = 0.0  # bias (positive = picks too late)


@dataclass
class FpsBucketMetrics:
    """v3/v4 foot-plant accuracy for a frame-rate band (failures excluded)."""
    label: str
    fps_lo: float
    fps_hi: float
    v3: "DetectorMetrics" = field(default_factory=lambda: DetectorMetrics())
    v4: "DetectorMetrics" = field(default_factory=lambda: DetectorMetrics())


@dataclass
class HeadToHead:
    """Pairwise comparison of v3 vs v4."""
    n: int = 0
    v4_better: int = 0
    v3_better: int = 0
    tie: int = 0
    pct_v4_better: float = 0.0
    pct_v3_better: float = 0.0
    pct_tie: float = 0.0


@dataclass
class V4Activity:
    """Did v4 actually do anything? A tie only means something when v4 ran its
    own detection — when v4 falls back to v3 the picks are identical by
    construction. Divergence (v4 pick != v3 pick) is the real signal for
    whether promoting v4 would change any outcomes."""
    n_scored: int = 0
    n_fallback: int = 0          # v4 punted to v3 (detector_v4.fallback_to_v3)
    n_diverged: int = 0          # v4 pick differs from v3 pick
    diverged_v4_better: int = 0  # of diverged, v4 closer to ground truth
    diverged_v3_better: int = 0  # of diverged, v3 closer
    pct_fallback: float = 0.0
    pct_diverged: float = 0.0


@dataclass
class Summary:
    """Aggregate validation report."""
    n_total: int = 0
    n_scored: int = 0
    n_skipped: int = 0
    skipped_by_reason: dict[str, int] = field(default_factory=dict)
    v3: DetectorMetrics = field(default_factory=DetectorMetrics)
    v4: DetectorMetrics = field(default_factory=DetectorMetrics)
    v3_contact: DetectorMetrics = field(default_factory=DetectorMetrics)
    v4_contact: DetectorMetrics = field(default_factory=DetectorMetrics)
    # Accuracy with detection-failures excluded (the honest headline).
    v3_clean: DetectorMetrics = field(default_factory=DetectorMetrics)
    v4_clean: DetectorMetrics = field(default_factory=DetectorMetrics)
    n_detection_failures: int = 0
    detection_failure_ids: list[str] = field(default_factory=list)
    fps_buckets: list[FpsBucketMetrics] = field(default_factory=list)
    head_to_head: HeadToHead = field(default_factory=HeadToHead)
    v4_activity: V4Activity = field(default_factory=V4Activity)
    stride_style: StrideStyleMetrics = field(default_factory=StrideStyleMetrics)
    per_stride_style: dict[str, DetectorMetrics] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Fingerprint loading + per-swing scoring
# ---------------------------------------------------------------------------


def load_fingerprint(path: str | Path) -> dict:
    """Load a fingerprint JSON from disk."""
    with open(path) as f:
        return json.load(f)


def evaluate_swing(
    entry: SwingEntry,
    fingerprint: Optional[dict],
    *,
    load_error: Optional[str] = None,
) -> SwingResult:
    """Score one swing against its ground truth.

    Returns a SwingResult populated with whichever fields could be computed.
    Sets `status` to indicate why a swing was or wasn't scored.
    """
    result = SwingResult(
        id=entry.id,
        status="unknown",
        gt_stride_style=entry.ground_truth.stride_style,
        gt_final_plant=entry.ground_truth.final_plant_frame,
        gt_contact=entry.ground_truth.contact_frame,
    )

    if load_error:
        result.status = "load_error"
        result.notes = load_error
        return result

    if fingerprint is None:
        result.status = "missing_fingerprint"
        result.notes = (
            f"no fingerprint at {entry.fingerprint_path or '(no path)'} "
            f"and no video at {entry.video_path or '(no path)'}"
        )
        return result

    fps = fingerprint.get("fps")
    if isinstance(fps, (int, float)):
        result.fps = float(fps)

    # v3 phases — always present
    phases_frame = fingerprint.get("phases_frame") or {}
    result.v3_foot_plant = phases_frame.get("foot_plant")
    result.v3_contact = phases_frame.get("contact")

    # v4 phases — only present when DETECTOR_V4 was on at processing time
    phases_frame_v4 = fingerprint.get("phases_frame_v4")
    detector_v4_block = fingerprint.get("detector_v4")
    if phases_frame_v4 and detector_v4_block:
        result.v4_foot_plant = phases_frame_v4.get("foot_plant")
        result.v4_contact = phases_frame_v4.get("contact")
        result.v4_confidence = detector_v4_block.get("confidence")
        result.v4_fallback = detector_v4_block.get("fallback_to_v3", False)
    # phase_debug stride_style — comes from analysis_debug, not detector_v4
    analysis_debug = fingerprint.get("analysis_debug")
    if analysis_debug:
        result.v4_stride_style = analysis_debug.get("stride_style")

    if not entry.ground_truth.is_labeled:
        result.status = "unlabeled"
        result.notes = "ground_truth.final_plant_frame is null — cannot score"
        # Still compute v3-v4 disagreement if we can
        if (result.v3_foot_plant is not None
                and result.v4_foot_plant is not None):
            result.v3_v4_delta_frames = (
                result.v4_foot_plant - result.v3_foot_plant
            )
        return result

    if result.v3_foot_plant is None:
        result.status = "load_error"
        result.notes = "fingerprint has no phases_frame.foot_plant"
        return result

    if result.v4_foot_plant is None:
        result.status = "v4_unavailable"
        result.notes = (
            "fingerprint has no phases_frame_v4 (process with DETECTOR_V4=true)"
        )
        # Still score v3
        result.v3_error_frames = (
            result.v3_foot_plant - entry.ground_truth.final_plant_frame
        )
        if result.fps:
            result.v3_error_ms = result.v3_error_frames * 1000.0 / result.fps
        return result

    # Both detectors available + ground truth available — full scoring.
    gt_plant = entry.ground_truth.final_plant_frame
    result.v3_error_frames = result.v3_foot_plant - gt_plant
    result.v4_error_frames = result.v4_foot_plant - gt_plant
    if result.fps:
        result.v3_error_ms = result.v3_error_frames * 1000.0 / result.fps
        result.v4_error_ms = result.v4_error_frames * 1000.0 / result.fps
    result.v3_v4_delta_frames = result.v4_foot_plant - result.v3_foot_plant

    # Contact-frame scoring (parallel to foot-plant). Opportunistic: only when
    # the contact label and detector contact picks are all present.
    gt_contact = entry.ground_truth.contact_frame
    if gt_contact is not None:
        if result.v3_contact is not None:
            result.v3_contact_error_frames = result.v3_contact - gt_contact
        if result.v4_contact is not None:
            result.v4_contact_error_frames = result.v4_contact - gt_contact
        if result.fps:
            if result.v3_contact_error_frames is not None:
                result.v3_contact_error_ms = (
                    result.v3_contact_error_frames * 1000.0 / result.fps
                )
            if result.v4_contact_error_frames is not None:
                result.v4_contact_error_ms = (
                    result.v4_contact_error_frames * 1000.0 / result.fps
                )

    if result.v4_stride_style is not None:
        result.stride_style_correct = (
            result.v4_stride_style == entry.ground_truth.stride_style
        )

    v3_abs = abs(result.v3_error_frames)
    v4_abs = abs(result.v4_error_frames)
    if v4_abs < v3_abs:
        result.winner = "v4"
    elif v3_abs < v4_abs:
        result.winner = "v3"
    else:
        result.winner = "tie"

    result.status = "scored"
    return result


# ---------------------------------------------------------------------------
# Aggregate metrics
# ---------------------------------------------------------------------------


def _detector_failed(r: SwingResult, which: str = "v3") -> bool:
    """The detector returned no real plant (frame ≈0) for this swing."""
    fp = getattr(r, f"{which}_foot_plant")
    return fp is None or fp <= DETECTION_FAILURE_MAX_FRAME


def _detector_metrics(
    rows: list[SwingResult], *, which: str, predicate=None
) -> DetectorMetrics:
    """Compute aggregate timing metrics for one detector ('v3'/'v4', or the
    contact variants 'v3_contact'/'v4_contact'). `predicate` optionally filters
    which scored rows are included (used for fps buckets / failure exclusion)."""
    err_field = f"{which}_error_frames"
    ms_field = f"{which}_error_ms"
    scored = [
        r for r in rows
        if r.status == "scored" and getattr(r, err_field) is not None
        and (predicate is None or predicate(r))
    ]
    n = len(scored)
    if n == 0:
        return DetectorMetrics()

    err_frames = [getattr(r, err_field) for r in scored]
    abs_err_frames = [abs(e) for e in err_frames]
    err_ms_present = [getattr(r, ms_field) for r in scored
                      if getattr(r, ms_field) is not None]
    abs_err_ms = [abs(e) for e in err_ms_present]

    m = DetectorMetrics()
    m.n = n
    m.mean_abs_error_frames = statistics.mean(abs_err_frames)
    m.median_abs_error_frames = statistics.median(abs_err_frames)
    if abs_err_ms:
        m.mean_abs_error_ms = statistics.mean(abs_err_ms)
        m.median_abs_error_ms = statistics.median(abs_err_ms)
    m.mean_signed_error_frames = statistics.mean(err_frames)
    m.pct_within_tight = sum(
        1 for e in abs_err_frames if e <= THRESHOLD_FRAMES_TIGHT
    ) / n
    m.pct_within_loose = sum(
        1 for e in abs_err_frames if e <= THRESHOLD_FRAMES_LOOSE
    ) / n
    return m


def _head_to_head(rows: list[SwingResult]) -> HeadToHead:
    scored = [r for r in rows if r.status == "scored" and r.winner is not None]
    n = len(scored)
    h = HeadToHead(n=n)
    if n == 0:
        return h
    h.v4_better = sum(1 for r in scored if r.winner == "v4")
    h.v3_better = sum(1 for r in scored if r.winner == "v3")
    h.tie = sum(1 for r in scored if r.winner == "tie")
    h.pct_v4_better = h.v4_better / n
    h.pct_v3_better = h.v3_better / n
    h.pct_tie = h.tie / n
    return h


def _v4_activity(rows: list[SwingResult]) -> V4Activity:
    """How often v4 fell back to v3 vs genuinely diverged, and who won the
    divergent calls. Computed over scored swings only."""
    scored = [r for r in rows if r.status == "scored"]
    a = V4Activity(n_scored=len(scored))
    if not scored:
        return a
    a.n_fallback = sum(1 for r in scored if r.v4_fallback)
    diverged = [r for r in scored if r.v3_v4_delta_frames not in (None, 0)]
    a.n_diverged = len(diverged)
    a.diverged_v4_better = sum(1 for r in diverged if r.winner == "v4")
    a.diverged_v3_better = sum(1 for r in diverged if r.winner == "v3")
    a.pct_fallback = a.n_fallback / a.n_scored
    a.pct_diverged = a.n_diverged / a.n_scored
    return a


def _fps_buckets(rows: list[SwingResult]) -> list[FpsBucketMetrics]:
    """Foot-plant accuracy split by frame rate, detection-failures excluded —
    the ~30fps phone clips and the 50-60fps clips behave so differently that a
    blended number is meaningless."""
    specs = [
        ("≤40 fps (real-time, ~30fps phone)", 0.0, FPS_SPLIT),
        (">40 fps (high-fps / slow-mo)",      FPS_SPLIT, float("inf")),
    ]
    out: list[FpsBucketMetrics] = []
    for label, lo, hi in specs:
        def in_range(r, lo=lo, hi=hi):
            return r.fps is not None and lo <= r.fps < hi
        out.append(FpsBucketMetrics(
            label=label, fps_lo=lo, fps_hi=hi,
            v3=_detector_metrics(
                rows, which="v3",
                predicate=lambda r, ir=in_range: ir(r) and not _detector_failed(r, "v3"),
            ),
            v4=_detector_metrics(
                rows, which="v4",
                predicate=lambda r, ir=in_range: ir(r) and not _detector_failed(r, "v4"),
            ),
        ))
    return out


def _stride_style_metrics(rows: list[SwingResult]) -> StrideStyleMetrics:
    """Confusion matrix + per-class accuracy for the v4/phase_debug
    stride_style classifier."""
    sm = StrideStyleMetrics()
    # Initialize confusion matrix with every known class
    sm.confusion = {gt: {pred: 0 for pred in VALID_STRIDE_STYLES + ("uncertain",)}
                    for gt in VALID_STRIDE_STYLES}
    evaluated = [r for r in rows
                 if r.gt_stride_style is not None
                 and r.v4_stride_style is not None]
    sm.n_evaluated = len(evaluated)
    if sm.n_evaluated == 0:
        return sm
    sm.n_correct = 0
    for r in evaluated:
        gt = r.gt_stride_style
        pred = r.v4_stride_style
        if gt in sm.confusion:
            row = sm.confusion[gt]
            row[pred] = row.get(pred, 0) + 1
        if gt == pred:
            sm.n_correct += 1
    sm.overall_accuracy = sm.n_correct / sm.n_evaluated

    for cls, row in sm.confusion.items():
        total = sum(row.values())
        if total == 0:
            continue
        correct = row.get(cls, 0)
        sm.per_class_accuracy[cls] = correct / total
    return sm


def _per_stride_style_breakdown(
    rows: list[SwingResult],
) -> dict[str, DetectorMetrics]:
    """For each ground-truth stride style, compute v4 timing metrics on the
    swings of that class. Useful for spotting "v4 is great on toe_tap but
    weak on leg_kick" patterns."""
    out: dict[str, DetectorMetrics] = {}
    for cls in VALID_STRIDE_STYLES:
        subset = [r for r in rows if r.gt_stride_style == cls]
        out[cls] = _detector_metrics(subset, which="v4")
    return out


def summarize(rows: list[SwingResult]) -> Summary:
    """Roll up per-swing results into the aggregate Summary."""
    s = Summary()
    s.n_total = len(rows)
    s.n_scored = sum(1 for r in rows if r.status == "scored")
    s.n_skipped = s.n_total - s.n_scored
    skipped: dict[str, int] = {}
    for r in rows:
        if r.status != "scored":
            skipped[r.status] = skipped.get(r.status, 0) + 1
    s.skipped_by_reason = skipped
    s.v3 = _detector_metrics(rows, which="v3")
    s.v4 = _detector_metrics(rows, which="v4")
    s.v3_contact = _detector_metrics(rows, which="v3_contact")
    s.v4_contact = _detector_metrics(rows, which="v4_contact")
    # Detection failures (EITHER detector returned frame ≈0) + failure-excluded
    # metrics. Union so a v4-only crash can't hide behind a v3-only count.
    scored = [r for r in rows if r.status == "scored"]
    failures = [r for r in scored
                if _detector_failed(r, "v3") or _detector_failed(r, "v4")]
    s.n_detection_failures = len(failures)
    s.detection_failure_ids = [r.id for r in failures]
    s.v3_clean = _detector_metrics(
        rows, which="v3", predicate=lambda r: not _detector_failed(r, "v3"))
    s.v4_clean = _detector_metrics(
        rows, which="v4", predicate=lambda r: not _detector_failed(r, "v4"))
    s.fps_buckets = _fps_buckets(rows)
    s.head_to_head = _head_to_head(rows)
    s.v4_activity = _v4_activity(rows)
    s.stride_style = _stride_style_metrics(rows)
    s.per_stride_style = _per_stride_style_breakdown(rows)
    return s


# ---------------------------------------------------------------------------
# Cutover criteria — auto promote/don't-promote verdict for v4
# ---------------------------------------------------------------------------

MIN_CUTOVER_SWINGS = 30
STRIDE_OVERALL_MIN = 0.90
STRIDE_PER_CLASS_MIN = 0.80
WIN_OR_TIE_MIN = 0.75


@dataclass
class CutoverCriterion:
    name: str
    passed: bool
    detail: str


@dataclass
class CutoverReport:
    """Whether v4 clears the documented promotion bar. `all_passed` requires
    every criterion AND the minimum-sample gate."""
    n_scored: int = 0
    min_n_met: bool = False
    criteria: list[CutoverCriterion] = field(default_factory=list)
    all_passed: bool = False


def evaluate_cutover(rows: list[SwingResult], summary: Summary) -> CutoverReport:
    """Evaluate the README's v4 cutover criteria against the scored rows.

    'v3 was already correct' (for the no-regression check) is defined as v3
    within ±THRESHOLD_FRAMES_TIGHT frames of ground truth — consistent with the
    report's tight tolerance band."""
    scored = [r for r in rows if r.status == "scored"]
    rep = CutoverReport(n_scored=len(scored))
    rep.min_n_met = len(scored) >= MIN_CUTOVER_SWINGS
    crit: list[CutoverCriterion] = []

    # 1. Stride-style accuracy ≥ 90% overall, ≥ 80% per class.
    sm = summary.stride_style
    per_class = sm.per_class_accuracy
    stride_ok = (
        sm.n_evaluated > 0
        and sm.overall_accuracy >= STRIDE_OVERALL_MIN
        and all(a >= STRIDE_PER_CLASS_MIN for a in per_class.values())
    )
    worst = min(per_class.items(), key=lambda kv: kv[1]) if per_class else None
    crit.append(CutoverCriterion(
        "Stride-style accuracy",
        stride_ok,
        f"overall {sm.overall_accuracy:.0%} (need ≥{STRIDE_OVERALL_MIN:.0%}); "
        + (f"weakest class `{worst[0]}` {worst[1]:.0%} (need ≥{STRIDE_PER_CLASS_MIN:.0%})"
           if worst else "no classes evaluated"),
    ))

    # 2. v4 foot-plant MAE < v3 MAE.
    mae_ok = (
        summary.v3.n > 0 and summary.v4.n > 0
        and summary.v4.mean_abs_error_frames < summary.v3.mean_abs_error_frames
    )
    crit.append(CutoverCriterion(
        "v4 foot-plant MAE < v3 MAE",
        mae_ok,
        f"v4 {summary.v4.mean_abs_error_frames:.2f}f vs v3 "
        f"{summary.v3.mean_abs_error_frames:.2f}f",
    ))

    # 3. v4 wins or ties ≥ 75% of head-to-head.
    h2h = summary.head_to_head
    wot = (h2h.v4_better + h2h.tie) / h2h.n if h2h.n else 0.0
    crit.append(CutoverCriterion(
        "v4 wins or ties ≥ 75%",
        h2h.n > 0 and wot >= WIN_OR_TIE_MIN,
        f"{wot:.0%} ({h2h.v4_better} wins + {h2h.tie} ties of {h2h.n})",
    ))

    # 4. No regression on standard_stride: among swings where v3 was already
    #    correct, v4 must stay within ±tight of v3's pick.
    std_correct = [
        r for r in scored
        if r.gt_stride_style == "standard_stride"
        and r.v3_error_frames is not None
        and abs(r.v3_error_frames) <= THRESHOLD_FRAMES_TIGHT
    ]
    regressions = [
        r for r in std_correct
        if r.v3_v4_delta_frames is not None
        and abs(r.v3_v4_delta_frames) > THRESHOLD_FRAMES_TIGHT
    ]
    crit.append(CutoverCriterion(
        "No standard_stride regression",
        len(regressions) == 0,
        f"{len(regressions)} of {len(std_correct)} v3-correct standard_stride "
        f"swings moved >±{THRESHOLD_FRAMES_TIGHT}f under v4",
    ))

    rep.criteria = crit
    rep.all_passed = rep.min_n_met and all(c.passed for c in crit)
    return rep


# ---------------------------------------------------------------------------
# Top-level evaluation
# ---------------------------------------------------------------------------


def evaluate_manifest(
    manifest: Manifest,
    *,
    fingerprint_dir: Optional[Path] = None,
) -> tuple[list[SwingResult], Summary]:
    """Evaluate every swing in the manifest, returning (rows, summary).

    `fingerprint_dir` is the directory to search for fingerprints when an
    entry has no explicit `fingerprint_path`. Convention: searches for
    `<entry.id>_fingerprint.json` and `<entry.id>.json`.
    """
    rows: list[SwingResult] = []
    for entry in manifest.swings:
        fp = None
        load_error = None
        try:
            if entry.fingerprint_path:
                fp = load_fingerprint(entry.fingerprint_path)
            elif fingerprint_dir is not None:
                # Convention-based lookup
                candidates = [
                    fingerprint_dir / f"{entry.id}_fingerprint.json",
                    fingerprint_dir / f"{entry.id}.json",
                ]
                for c in candidates:
                    if c.exists():
                        fp = load_fingerprint(c)
                        break
        except Exception as e:
            load_error = f"failed to load fingerprint: {e!r}"

        rows.append(evaluate_swing(entry, fp, load_error=load_error))

    return rows, summarize(rows)


def as_dicts(rows: list[SwingResult]) -> list[dict]:
    """Serialize per-swing rows for JSON output."""
    return [asdict(r) for r in rows]


def summary_as_dict(summary: Summary) -> dict:
    """Serialize the summary for JSON output."""
    return {
        "n_total": summary.n_total,
        "n_scored": summary.n_scored,
        "n_skipped": summary.n_skipped,
        "skipped_by_reason": dict(summary.skipped_by_reason),
        "v3": asdict(summary.v3),
        "v4": asdict(summary.v4),
        "v3_contact": asdict(summary.v3_contact),
        "v4_contact": asdict(summary.v4_contact),
        "v3_clean": asdict(summary.v3_clean),
        "v4_clean": asdict(summary.v4_clean),
        "n_detection_failures": summary.n_detection_failures,
        "detection_failure_ids": list(summary.detection_failure_ids),
        "fps_buckets": [asdict(b) for b in summary.fps_buckets],
        "head_to_head": asdict(summary.head_to_head),
        "v4_activity": asdict(summary.v4_activity),
        "stride_style": {
            "n_evaluated": summary.stride_style.n_evaluated,
            "n_correct": summary.stride_style.n_correct,
            "overall_accuracy": summary.stride_style.overall_accuracy,
            "per_class_accuracy": dict(summary.stride_style.per_class_accuracy),
            "confusion": {
                gt: dict(row) for gt, row in summary.stride_style.confusion.items()
            },
        },
        "per_stride_style": {
            cls: asdict(m) for cls, m in summary.per_stride_style.items()
        },
    }
