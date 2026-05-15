"""
Milestone 1: Skeleton overlay on a swing video.

What this does:
  Reads a video file, runs MediaPipe pose detection on every frame,
  draws the 33-point body skeleton on top, and saves a new video.

How to use:
  1. Put your swing video in the same folder as this file.
  2. Change the INPUT_VIDEO line below to match your video's filename.
  3. Run from terminal:  python pose_overlay.py
  4. Watch the new file (swing_with_skeleton.mp4) in your folder.
"""

import cv2
import mediapipe as mp

# ---- CHANGE THIS to your video's filename ----
INPUT_VIDEO = "swing.mp4"
OUTPUT_VIDEO = "swing_with_skeleton.mp4"
# ----------------------------------------------

# Set up MediaPipe Pose
mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils
pose = mp_pose.Pose(
    static_image_mode=False,
    model_complexity=2,          # 0 = fastest, 2 = most accurate
    enable_segmentation=False,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5,
)

# Open the input video
cap = cv2.VideoCapture(INPUT_VIDEO)
if not cap.isOpened():
    raise FileNotFoundError(
        f"Could not open '{INPUT_VIDEO}'. "
        "Check that the file exists and the filename matches exactly."
    )

# Get video properties so the output matches the input
fps = cap.get(cv2.CAP_PROP_FPS)
width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

# Set up the output video writer
fourcc = cv2.VideoWriter_fourcc(*"mp4v")
out = cv2.VideoWriter(OUTPUT_VIDEO, fourcc, fps, (width, height))

print(f"Processing '{INPUT_VIDEO}' ({width}x{height} at {fps:.1f} fps)...")

frame_count = 0
detected_count = 0

while True:
    ret, frame = cap.read()
    if not ret:
        break  # end of video

    # MediaPipe expects RGB, OpenCV gives us BGR
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # Run pose detection on this frame
    results = pose.process(rgb_frame)

    # If a body was detected, draw the skeleton on the original frame
    if results.pose_landmarks:
        detected_count += 1
        mp_drawing.draw_landmarks(
            frame,
            results.pose_landmarks,
            mp_pose.POSE_CONNECTIONS,
            mp_drawing.DrawingSpec(color=(0, 255, 0), thickness=2, circle_radius=3),
            mp_drawing.DrawingSpec(color=(255, 255, 255), thickness=2),
        )

    out.write(frame)
    frame_count += 1

    if frame_count % 30 == 0:
        print(f"  ... {frame_count} frames processed")

# Clean up
cap.release()
out.release()
pose.close()

print(f"\nDone.")
print(f"  Total frames:    {frame_count}")
print(f"  Pose detected:   {detected_count} ({100*detected_count/max(frame_count,1):.1f}%)")
print(f"  Output saved to: {OUTPUT_VIDEO}")
