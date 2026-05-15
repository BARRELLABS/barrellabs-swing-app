"""
Milestone 2: Extract baseball swing metrics from pose data.

What this does:
  Reads your swing video, runs MediaPipe pose detection, and computes
  per-frame biomechanical metrics. Saves a CSV (one row per frame),
  a chart (PNG), and prints a summary to terminal.

How to use:
  1. Make sure swing.mp4 is in the same folder.
  2. Set HANDEDNESS below to "RIGHT" or "LEFT" depending on the batter.
  3. Run from terminal:  python extract_metrics.py
  4. Open swing_metrics.png to see the chart.
  5. Open swing_metrics.csv in Excel/Numbers to see the raw numbers.
"""

import math
import csv

import cv2
import mediapipe as mp
import matplotlib
matplotlib.use("Agg")  # non-GUI backend, just write the chart to file
import matplotlib.pyplot as plt

# ---- CONFIG ----
INPUT_VIDEO = "swing.mp4"
OUTPUT_CSV = "swing_metrics.csv"
OUTPUT_CHART = "swing_metrics.png"
HANDEDNESS = "RIGHT"   # change to "LEFT" if your buddy bats lefty
# ----------------

# MediaPipe Pose landmark indices (from official docs)
NOSE = 0
LEFT_SHOULDER, RIGHT_SHOULDER = 11, 12
LEFT_HIP, RIGHT_HIP = 23, 24
LEFT_KNEE, RIGHT_KNEE = 25, 26
LEFT_ANKLE, RIGHT_ANKLE = 27, 28

# Pick "front" side based on handedness.
# For a right-handed hitter, the FRONT side (closer to the pitcher) is the LEFT side of the body.
# For a left-handed hitter, it's the opposite.
if HANDEDNESS == "RIGHT":
    FRONT_SHOULDER, FRONT_HIP, FRONT_KNEE, FRONT_ANKLE = LEFT_SHOULDER, LEFT_HIP, LEFT_KNEE, LEFT_ANKLE
    BACK_ANKLE = RIGHT_ANKLE
else:
    FRONT_SHOULDER, FRONT_HIP, FRONT_KNEE, FRONT_ANKLE = RIGHT_SHOULDER, RIGHT_HIP, RIGHT_KNEE, RIGHT_ANKLE
    BACK_ANKLE = LEFT_ANKLE


def line_angle_deg(p1, p2):
    """Angle of the line from p1 to p2, in degrees."""
    return math.degrees(math.atan2(p2[1] - p1[1], p2[0] - p1[0]))


def joint_angle_deg(a, b, c):
    """Inner angle at point b formed by rays b->a and b->c, in degrees."""
    ba = (a[0] - b[0], a[1] - b[1])
    bc = (c[0] - b[0], c[1] - b[1])
    dot = ba[0] * bc[0] + ba[1] * bc[1]
    mag_ba = math.hypot(*ba)
    mag_bc = math.hypot(*bc)
    if mag_ba == 0 or mag_bc == 0:
        return 0.0
    cos_a = max(-1.0, min(1.0, dot / (mag_ba * mag_bc)))
    return math.degrees(math.acos(cos_a))


# Set up MediaPipe Pose
mp_pose = mp.solutions.pose
pose = mp_pose.Pose(
    static_image_mode=False,
    model_complexity=2,
    enable_segmentation=False,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5,
)

# Open video
cap = cv2.VideoCapture(INPUT_VIDEO)
if not cap.isOpened():
    raise FileNotFoundError(f"Could not open '{INPUT_VIDEO}'.")

fps = cap.get(cv2.CAP_PROP_FPS)
width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

print(f"Processing '{INPUT_VIDEO}' ({width}x{height} at {fps:.1f} fps, {HANDEDNESS}-handed)...")

records = []
frame_idx = 0

while True:
    ret, frame = cap.read()
    if not ret:
        break

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = pose.process(rgb)

    if results.pose_landmarks:
        lm = results.pose_landmarks.landmark

        def pt(idx):
            return (lm[idx].x * width, lm[idx].y * height)

        # Hip + shoulder line angles (from camera's perspective)
        hip_a = line_angle_deg(pt(LEFT_HIP), pt(RIGHT_HIP))
        shoulder_a = line_angle_deg(pt(LEFT_SHOULDER), pt(RIGHT_SHOULDER))
        sep = shoulder_a - hip_a
        sep = ((sep + 180) % 360) - 180  # wrap to [-180, 180]
        hip_shoulder_sep = abs(sep)

        # Head position (using nose as proxy)
        head_x, head_y = pt(NOSE)

        # Front knee flex (hip - knee - ankle, smaller angle = more bent)
        knee_flex = joint_angle_deg(pt(FRONT_HIP), pt(FRONT_KNEE), pt(FRONT_ANKLE))

        # Stride: horizontal distance between front and back ankle (in pixels)
        front_x, _ = pt(FRONT_ANKLE)
        back_x, _ = pt(BACK_ANKLE)
        stride_px = abs(front_x - back_x)

        records.append({
            "frame": frame_idx,
            "time_s": frame_idx / fps,
            "hip_shoulder_sep_deg": hip_shoulder_sep,
            "head_x": head_x,
            "head_y": head_y,
            "front_knee_angle_deg": knee_flex,
            "stride_px": stride_px,
        })

    frame_idx += 1

cap.release()
pose.close()

if not records:
    raise RuntimeError("No frames had a detected pose. Check the video.")

# Save CSV
with open(OUTPUT_CSV, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(records[0].keys()))
    writer.writeheader()
    writer.writerows(records)

# Compute summary stats
times = [r["time_s"] for r in records]
seps = [r["hip_shoulder_sep_deg"] for r in records]
heads_x = [r["head_x"] for r in records]
heads_y = [r["head_y"] for r in records]
knees = [r["front_knee_angle_deg"] for r in records]
strides = [r["stride_px"] for r in records]

peak_sep = max(seps)
peak_sep_time = times[seps.index(peak_sep)]
head_range_x = max(heads_x) - min(heads_x)
head_range_y = max(heads_y) - min(heads_y)
head_total_drift = math.hypot(head_range_x, head_range_y)
peak_stride = max(strides)
min_knee = min(knees)
max_knee = max(knees)

print()
print("=" * 50)
print("           SWING METRICS SUMMARY")
print("=" * 50)
print(f"Frames analyzed:                {len(records)}")
print(f"Duration:                       {times[-1]:.2f} s")
print()
print(f"Peak hip-shoulder separation:   {peak_sep:.1f}°  (at t={peak_sep_time:.2f}s)")
print(f"Head total drift:               {head_total_drift:.0f} px  ({head_range_x:.0f} horiz, {head_range_y:.0f} vert)")
print(f"Front knee flex range:          {min_knee:.0f}° (most bent)  →  {max_knee:.0f}° (most straight)")
print(f"Peak stride distance:           {peak_stride:.0f} px")
print()
print(f"Saved per-frame data → {OUTPUT_CSV}")

# Make a chart with 4 stacked subplots
fig, axes = plt.subplots(4, 1, figsize=(11, 9), sharex=True)

axes[0].plot(times, seps, color="#1f77b4", linewidth=2)
axes[0].set_ylabel("Hip-shoulder\nseparation (°)")
axes[0].set_title("Swing Biomechanics over Time", fontsize=14, fontweight="bold")
axes[0].grid(True, alpha=0.3)

axes[1].plot(times, knees, color="#2ca02c", linewidth=2)
axes[1].set_ylabel("Front knee\nangle (°)")
axes[1].grid(True, alpha=0.3)

axes[2].plot(times, strides, color="#ff7f0e", linewidth=2)
axes[2].set_ylabel("Stride distance\n(px)")
axes[2].grid(True, alpha=0.3)

# Plot head movement in 2D-style: x range and y range over time
axes[3].plot(times, [x - heads_x[0] for x in heads_x], color="#9467bd", linewidth=2, label="head Δx")
axes[3].plot(times, [y - heads_y[0] for y in heads_y], color="#d62728", linewidth=2, label="head Δy")
axes[3].set_ylabel("Head drift\nfrom start (px)")
axes[3].set_xlabel("Time (s)")
axes[3].grid(True, alpha=0.3)
axes[3].legend(loc="upper left", fontsize=9)

plt.tight_layout()
plt.savefig(OUTPUT_CHART, dpi=120)
plt.close()

print(f"Saved chart        → {OUTPUT_CHART}")
print()
print("Open the PNG to see the curves. The CSV is per-frame raw data you can")
print("open in Numbers/Excel and play with.")
