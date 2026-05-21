# Phase 3 validation report — v3 vs v4 phase detection

_Generated (SAMPLE — synthetic data)._  _Manifest: `(synthetic demo)`._

## Executive summary

- Total swings in manifest: **11**
- Swings fully scored: **11**
- Swings skipped: **0** 

**Foot-plant accuracy headline:**

- v3 mean absolute error: **12.45 frames** (207.6 ms)
- v4 mean absolute error: **0.91 frames** (15.2 ms)
- Improvement (v4 − v3): **-11.5 frames** → ✓ v4 IS more accurate

**Head-to-head:**

- v4 wins (closer to ground truth): **10** (90.9%)
- v3 wins: **0** (0.0%)
- Ties: **1** (9.1%)

**Stride-style accuracy:** 90.9% (10/11)

## Per-detector metrics

### v3 (legacy)

- Swings scored: **11**
- Mean absolute error: **12.45 frames** (207.6 ms)
- Median absolute error: **10.0 frames** (166.7 ms)
- Mean signed error: **-12.09 frames** (positive = picks too LATE)
- Within ±3 frames: **45.5%**
- Within ±10 frames: **54.5%**

### v4 (toe-tap-aware)

- Swings scored: **11**
- Mean absolute error: **0.91 frames** (15.2 ms)
- Median absolute error: **1.0 frames** (16.7 ms)
- Mean signed error: **+0.73 frames** (positive = picks too LATE)
- Within ±3 frames: **100.0%**
- Within ±10 frames: **100.0%**

## Stride-style + per-class breakdown

### Stride-style classification (v4 / phase_debug)

- Swings evaluated: **11**
- Overall accuracy: **90.9%** (10/11)

**Per-class accuracy:**

- `no_stride`: 100.0%
- `standard_stride`: 100.0%
- `toe_tap`: 75.0%
- `leg_kick`: 100.0%

**Confusion matrix** (rows = ground truth, columns = predicted):

| GT \ Pred | leg_kick | no_stride | standard_stride | toe_tap | uncertain |
|---|---|---|---|---|---|
| **leg_kick** | **2** | 0 | 0 | 0 | 0 |
| **no_stride** | 0 | **1** | 0 | 0 | 0 |
| **standard_stride** | 0 | 0 | **4** | 0 | 0 |
| **toe_tap** | 0 | 0 | 1 | **3** | 0 |

### v4 timing accuracy by stride style

| Stride style | N | Mean abs error (frames) | Mean abs error (ms) | Within ±3 frames |
|---|---|---|---|---|
| `no_stride` | 1 | 0.00 | 0.0 | 100.0% |
| `standard_stride` | 4 | 0.25 | 4.2 | 100.0% |
| `toe_tap` | 4 | 1.50 | 25.0 | 100.0% |
| `leg_kick` | 2 | 1.50 | 25.0 | 100.0% |

### Per-swing detail

| id | stride | status | gt_plant | v3 | v4 | v3 err (f) | v4 err (f) | v3-v4 Δ | winner | v4_conf |
|---|---|---|---|---|---|---|---|---|---|---|
| toe_tap_001 | toe_tap | scored | 150 | 122 | 151 | -28 | +1 | +29 | **v4** | 0.88 |
| toe_tap_002 | toe_tap | scored | 142 | 118 | 144 | -24 | +2 | +26 | **v4** | 0.84 |
| toe_tap_003 | toe_tap | scored | 160 | 130 | 162 | -30 | +2 | +32 | **v4** | 0.82 |
| leg_kick_001 | leg_kick | scored | 148 | 138 | 150 | -10 | +2 | +12 | **v4** | 0.81 |
| leg_kick_002 | leg_kick | scored | 155 | 142 | 154 | -13 | -1 | +12 | **v4** | 0.78 |
| standard_001 | standard_stride | scored | 138 | 137 | 138 | -1 | +0 | +1 | **v4** | 0.86 |
| standard_002 | standard_stride | scored | 145 | 146 | 145 | +1 | +0 | -1 | **v4** | 0.84 |
| standard_003 | standard_stride | scored | 130 | 131 | 131 | +1 | +1 | +0 | tie | 0.85 |
| standard_004 | standard_stride | scored | 152 | 151 | 152 | -1 | +0 | +1 | **v4** | 0.87 |
| no_stride_001 | no_stride | scored | 145 | 144 | 145 | -1 | +0 | +1 | **v4** | 0.80 |
| toe_tap_004_miss | toe_tap | scored | 165 | 138 | 166 | -27 | +1 | +28 | **v4** | 0.62 |

