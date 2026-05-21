"""
Native Tkinter labeling tool for the validation manifest.

No browser. No HTTP server. No Streamlit. No CORS. Plays video natively
via OpenCV-decoded frames pumped into a Tk Canvas at the video's FPS.

Launch:
    python3 -m scripts.validation.label_desktop

Or via the convenience wrapper:
    ./scripts/validation/launch_labeling.sh   (after edit — see below)

For each swing that has a usable video, you:
  - Scrub to the foot plant, press P  (or click 📌 Mark plant)
  - Scrub to contact,        press C  (or click 📌 Mark contact)
  - Toggle toe-tap            press T  (or click the radio)
  - Save + go to next swing  press S  (or click 💾 SAVE + NEXT)

Keyboard:
    Space         play / pause
    ← / →         step -1 / +1 frame
    Shift + ← / →  jump ±10 frames
    P             mark foot plant at current frame
    C             mark contact at current frame
    T             toggle toe-tap (No ↔ Yes)
    S             save + advance to next unlabeled swing
    Q             quit
"""

from __future__ import annotations

import os
import sys
import tempfile
import traceback
from datetime import date
from pathlib import Path
from typing import Optional

import cv2
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.validation.manifest import (  # noqa: E402
    load_manifest, write_manifest, Manifest, SwingEntry,
)
from scripts.validation._video_discovery import (  # noqa: E402
    resolve_scan_dirs, auto_import_videos,
)


MANIFEST_PATH = PROJECT_ROOT / "validation" / "manifest.json"
VIDEOS_DIR = PROJECT_ROOT / "validation" / "videos"
DEFAULT_SCAN_DIRS = [VIDEOS_DIR, PROJECT_ROOT / "uploads_streamlit"]

# Rendered frame display target. The decoded frame is letterboxed into
# this rectangle preserving aspect ratio.
DISPLAY_W = 960
DISPLAY_H = 560


# ---------------------------------------------------------------------------
# Helpers (shared with the Streamlit tool)
# ---------------------------------------------------------------------------


def _save_manifest_atomic(manifest: Manifest, path: Path) -> None:
    """Write a manifest with a temp-file-then-rename so a crash can't
    corrupt the file."""
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".manifest.", suffix=".tmp")
    os.close(fd)
    tmp_path = Path(tmp)
    try:
        write_manifest(manifest, tmp_path)
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def _resolve_video(rel_or_abs: Optional[str]) -> Optional[Path]:
    if not rel_or_abs:
        return None
    p = Path(rel_or_abs)
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    return p if p.exists() else None


# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------


class LabelingApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Swing Labeling — Desktop")
        self.root.geometry("1080x900")
        # macOS: bring window to the front on launch
        self.root.attributes("-topmost", True)
        self.root.after(800, lambda: self.root.attributes("-topmost", False))

        # ----- Load manifest + auto-import any new videos -----
        try:
            self.manifest = load_manifest(MANIFEST_PATH)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror(
                "Manifest error",
                f"Could not load {MANIFEST_PATH}:\n\n{e}",
            )
            raise SystemExit(2)

        scan_dirs = resolve_scan_dirs(
            DEFAULT_SCAN_DIRS, project_root=PROJECT_ROOT,
        )
        try:
            n_added = auto_import_videos(
                self.manifest, scan_dirs, project_root=PROJECT_ROOT,
            )
            if n_added:
                _save_manifest_atomic(self.manifest, MANIFEST_PATH)
        except Exception as e:  # noqa: BLE001
            print(f"[warning] auto-import failed: {e!r}")

        # Filter to swings that have a usable video file on disk
        self.swings: list[tuple[SwingEntry, Path]] = []
        for entry in self.manifest.swings:
            video = _resolve_video(entry.video_path)
            if video:
                self.swings.append((entry, video))

        if not self.swings:
            messagebox.showerror(
                "No videos",
                f"No swings have a resolvable video_path.\n\n"
                f"Drop swing videos into:\n  {VIDEOS_DIR}\n\n"
                "Then re-launch this tool.",
            )
            raise SystemExit(2)

        # Per-app state
        self.current_idx: int = 0
        self.cap: Optional[cv2.VideoCapture] = None
        self.n_frames: int = 0
        self.fps: float = 30.0
        self.current_frame: int = 0
        self.playing: bool = False
        self.play_job_id: Optional[str] = None
        # Hold a reference to the displayed PhotoImage to prevent garbage
        # collection (Tk weakly references it, the canvas will go blank
        # otherwise).
        self.image_cache: Optional[ImageTk.PhotoImage] = None

        # Per-swing scratch marks
        self.plant_mark: Optional[int] = None
        self.contact_mark: Optional[int] = None

        self._build_ui()

        # Land on the first unlabeled swing
        for i, (entry, _) in enumerate(self.swings):
            if not entry.ground_truth.is_labeled:
                self.current_idx = i
                break
        self._load_current_swing()
        self._bind_keys()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        # Header row
        header = tk.Frame(self.root, bg="#f4efe6", padx=16, pady=10)
        header.pack(fill="x")
        self.header_label = tk.Label(
            header, text="", bg="#f4efe6",
            font=("Helvetica Neue", 18, "bold"), anchor="w",
        )
        self.header_label.pack(side="left", fill="x", expand=True)
        self.progress_label = tk.Label(
            header, text="", bg="#f4efe6",
            font=("Helvetica Neue", 13), anchor="e", fg="#444",
        )
        self.progress_label.pack(side="right")

        # Video canvas (black background; frames rendered as Image)
        self.canvas = tk.Canvas(
            self.root, width=DISPLAY_W, height=DISPLAY_H,
            bg="#000", highlightthickness=0,
        )
        self.canvas.pack(pady=6)

        # Big yellow frame-counter pill
        self.frame_counter = tk.Label(
            self.root, text="Frame —", font=("Menlo", 22, "bold"),
            fg="#1f4e79", bg="#fff7d6", padx=24, pady=8,
            relief="solid", borderwidth=1,
        )
        self.frame_counter.pack(pady=6)

        # Scrub slider
        slider_frame = tk.Frame(self.root)
        slider_frame.pack(fill="x", padx=24, pady=4)
        self.slider = ttk.Scale(
            slider_frame, from_=0, to=100, orient="horizontal",
            command=self._on_slider,
        )
        self.slider.pack(fill="x")

        # Nav buttons
        nav = tk.Frame(self.root)
        nav.pack(pady=6)
        tk.Button(
            nav, text="⏮ −10", command=lambda: self._step(-10), width=8,
        ).pack(side="left", padx=4)
        tk.Button(
            nav, text="◀ −1", command=lambda: self._step(-1), width=8,
        ).pack(side="left", padx=4)
        self.play_btn = tk.Button(
            nav, text="▶  Play", command=self._toggle_play, width=12,
            font=("Helvetica Neue", 12, "bold"),
        )
        self.play_btn.pack(side="left", padx=4)
        tk.Button(
            nav, text="+1 ▶", command=lambda: self._step(1), width=8,
        ).pack(side="left", padx=4)
        tk.Button(
            nav, text="+10 ⏭", command=lambda: self._step(10), width=8,
        ).pack(side="left", padx=4)

        # Mark rows
        marks = tk.Frame(self.root, padx=24, pady=12)
        marks.pack(fill="x")

        plant_row = tk.Frame(marks)
        plant_row.pack(fill="x", pady=4)
        tk.Label(
            plant_row, text="Step 1 · Foot plant",
            font=("Helvetica Neue", 13, "bold"), width=20, anchor="w",
        ).pack(side="left")
        self.plant_var = tk.StringVar(value="—")
        tk.Label(
            plant_row, textvariable=self.plant_var,
            font=("Menlo", 15, "bold"), fg="#1f4e79", width=8, anchor="w",
        ).pack(side="left", padx=8)
        tk.Button(
            plant_row, text="📌 Mark plant   (P)",
            command=self._mark_plant, font=("Helvetica Neue", 12, "bold"),
            bg="#e8c170",
        ).pack(side="left", padx=8)

        contact_row = tk.Frame(marks)
        contact_row.pack(fill="x", pady=4)
        tk.Label(
            contact_row, text="Step 2 · Contact",
            font=("Helvetica Neue", 13, "bold"), width=20, anchor="w",
        ).pack(side="left")
        self.contact_var = tk.StringVar(value="—")
        tk.Label(
            contact_row, textvariable=self.contact_var,
            font=("Menlo", 15, "bold"), fg="#1f4e79", width=8, anchor="w",
        ).pack(side="left", padx=8)
        tk.Button(
            contact_row, text="📌 Mark contact (C)",
            command=self._mark_contact,
            font=("Helvetica Neue", 12, "bold"), bg="#e8c170",
        ).pack(side="left", padx=8)

        toe_row = tk.Frame(marks)
        toe_row.pack(fill="x", pady=4)
        tk.Label(
            toe_row, text="Step 3 · Toe-tap?",
            font=("Helvetica Neue", 13, "bold"), width=20, anchor="w",
        ).pack(side="left")
        self.toe_var = tk.StringVar(value="no")
        tk.Radiobutton(
            toe_row, text="No (regular stride / leg-kick / no-stride)",
            variable=self.toe_var, value="no",
            font=("Helvetica Neue", 12),
        ).pack(side="left", padx=4)
        tk.Radiobutton(
            toe_row, text="Yes (toe-tap)",
            variable=self.toe_var, value="yes",
            font=("Helvetica Neue", 12),
        ).pack(side="left", padx=4)
        tk.Label(toe_row, text="(T to toggle)", fg="#888").pack(
            side="left", padx=4,
        )

        # Action buttons
        actions = tk.Frame(self.root, pady=10)
        actions.pack()
        tk.Button(
            actions, text="💾  SAVE + NEXT  (S)",
            command=self._save_and_next,
            font=("Helvetica Neue", 14, "bold"),
            bg="#1f4e79", fg="white", padx=18, pady=6,
            activebackground="#0d3258", activeforeground="white",
        ).pack(side="left", padx=6)
        tk.Button(
            actions, text="⏭ Skip (no save)",
            command=self._next_swing,
            font=("Helvetica Neue", 12), padx=12,
        ).pack(side="left", padx=6)
        tk.Button(
            actions, text="Quit (Q)",
            command=self._quit, font=("Helvetica Neue", 12), padx=12,
        ).pack(side="left", padx=6)

        # Help / status
        help_text = (
            "Space play/pause  ·  ← →  step ±1  ·  Shift+← →  ±10  ·  "
            "P  plant  ·  C  contact  ·  T  toe-tap  ·  S  save+next  ·  Q  quit"
        )
        self.status = tk.Label(
            self.root, text=help_text,
            font=("Helvetica Neue", 11), fg="#666",
        )
        self.status.pack(pady=4)

    def _bind_keys(self) -> None:
        b = self.root.bind
        b("<Left>", lambda e: self._step(-1))
        b("<Right>", lambda e: self._step(1))
        b("<Shift-Left>", lambda e: self._step(-10))
        b("<Shift-Right>", lambda e: self._step(10))
        b("<space>", lambda e: self._toggle_play())
        for k in ("p", "P"):
            b(k, lambda e: self._mark_plant())
        for k in ("c", "C"):
            b(k, lambda e: self._mark_contact())
        for k in ("t", "T"):
            b(k, lambda e: self._toggle_toe_tap())
        for k in ("s", "S"):
            b(k, lambda e: self._save_and_next())
        for k in ("q", "Q"):
            b(k, lambda e: self._quit())
        # Make sure the root window has focus so key events fire
        self.root.focus_set()

    # ------------------------------------------------------------------
    # Loading + rendering
    # ------------------------------------------------------------------

    def _load_current_swing(self) -> None:
        self._stop_play()
        if self.cap is not None:
            self.cap.release()
            self.cap = None

        if self.current_idx >= len(self.swings):
            messagebox.showinfo(
                "All done",
                "🎉 All swings have been processed.\n\nRun:\n"
                "  python3 -m scripts.validation.run_validation",
            )
            self._quit()
            return

        entry, video_path = self.swings[self.current_idx]
        self.cap = cv2.VideoCapture(str(video_path))
        if not self.cap.isOpened() or self.cap.get(cv2.CAP_PROP_FRAME_COUNT) < 1:
            self.status.config(
                text=f"⚠ Could not decode {video_path.name} — skipping. "
                     "If this happens often, transcode to H.264.",
            )
            self.current_idx += 1
            self.root.after(800, self._load_current_swing)
            return

        self.n_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.fps = float(self.cap.get(cv2.CAP_PROP_FPS) or 30.0)

        # Default start frame: existing label if any, else ~40% into clip
        if entry.ground_truth.final_plant_frame is not None:
            self.current_frame = max(
                0, min(self.n_frames - 1, entry.ground_truth.final_plant_frame),
            )
        else:
            self.current_frame = max(0, int(self.n_frames * 0.4))

        # Hydrate scratch marks from any existing labels
        self.plant_mark = entry.ground_truth.final_plant_frame
        self.contact_mark = entry.ground_truth.contact_frame
        self.toe_var.set(
            "yes" if entry.ground_truth.stride_style == "toe_tap" else "no"
        )
        self.plant_var.set(
            str(self.plant_mark) if self.plant_mark is not None else "—"
        )
        self.contact_var.set(
            str(self.contact_mark) if self.contact_mark is not None else "—"
        )

        self.slider.config(from_=0, to=max(0, self.n_frames - 1))
        self.slider.set(self.current_frame)

        labeled = sum(1 for e, _ in self.swings if e.ground_truth.is_labeled)
        status = "✓ Labeled" if entry.ground_truth.is_labeled else "○ Unlabeled"
        self.header_label.config(text=f"{entry.id}   ({video_path.name})")
        self.progress_label.config(
            text=f"{status}  ·  Swing {self.current_idx + 1} of "
                 f"{len(self.swings)}  ·  {labeled} labeled total",
        )

        self._render_frame()
        # Restore the help status text (was overwritten by skip warnings)
        self.status.config(
            text="Space play/pause  ·  ← →  ±1  ·  Shift+← →  ±10  ·  "
                 "P plant  ·  C contact  ·  T toe-tap  ·  S save+next  ·  Q quit",
        )

    def _render_frame(self) -> None:
        if self.cap is None:
            return
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame)
        ok, frame_bgr = self.cap.read()
        if not ok or frame_bgr is None:
            self.frame_counter.config(
                text=f"Frame {self.current_frame}: decode failed"
            )
            return
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        h, w = frame_rgb.shape[:2]
        scale = min(DISPLAY_W / max(w, 1), DISPLAY_H / max(h, 1))
        new_w = max(1, int(w * scale))
        new_h = max(1, int(h * scale))
        img = Image.fromarray(frame_rgb).resize((new_w, new_h), Image.BILINEAR)
        self.image_cache = ImageTk.PhotoImage(img)
        self.canvas.delete("all")
        self.canvas.create_image(
            DISPLAY_W // 2, DISPLAY_H // 2,
            image=self.image_cache, anchor="center",
        )
        t = self.current_frame / self.fps if self.fps > 0 else 0.0
        self.frame_counter.config(
            text=f"Frame {self.current_frame} / {self.n_frames - 1}"
                 f"    t = {t:.3f}s    {self.fps:.1f} fps",
        )

    # ------------------------------------------------------------------
    # Navigation + playback
    # ------------------------------------------------------------------

    def _step(self, delta: int) -> None:
        if self.cap is None:
            return
        new_frame = max(0, min(self.n_frames - 1, self.current_frame + delta))
        if new_frame != self.current_frame:
            self.current_frame = new_frame
            self.slider.set(self.current_frame)
            self._render_frame()

    def _on_slider(self, val_str: str) -> None:
        try:
            new_frame = int(float(val_str))
        except (TypeError, ValueError):
            return
        new_frame = max(0, min(max(0, self.n_frames - 1), new_frame))
        if new_frame != self.current_frame:
            self.current_frame = new_frame
            self._render_frame()

    def _toggle_play(self) -> None:
        if self.playing:
            self._stop_play()
        else:
            self._start_play()

    def _start_play(self) -> None:
        if self.cap is None:
            return
        self.playing = True
        self.play_btn.config(text="⏸  Pause")
        self._play_tick()

    def _stop_play(self) -> None:
        self.playing = False
        if self.play_job_id is not None:
            try:
                self.root.after_cancel(self.play_job_id)
            except Exception:
                pass
            self.play_job_id = None
        if hasattr(self, "play_btn"):
            try:
                self.play_btn.config(text="▶  Play")
            except tk.TclError:
                pass

    def _play_tick(self) -> None:
        if not self.playing or self.cap is None:
            return
        if self.current_frame >= self.n_frames - 1:
            self._stop_play()
            return
        self.current_frame += 1
        # Throttle slider updates (every frame is fine for short clips)
        self.slider.set(self.current_frame)
        self._render_frame()
        delay_ms = max(8, int(1000.0 / max(self.fps, 1.0)))
        self.play_job_id = self.root.after(delay_ms, self._play_tick)

    # ------------------------------------------------------------------
    # Marking + saving
    # ------------------------------------------------------------------

    def _mark_plant(self) -> None:
        if self.cap is None:
            return
        self.plant_mark = self.current_frame
        self.plant_var.set(str(self.plant_mark))

    def _mark_contact(self) -> None:
        if self.cap is None:
            return
        self.contact_mark = self.current_frame
        self.contact_var.set(str(self.contact_mark))

    def _toggle_toe_tap(self) -> None:
        self.toe_var.set("yes" if self.toe_var.get() == "no" else "no")

    def _save_and_next(self) -> None:
        if self.plant_mark is None or self.contact_mark is None:
            messagebox.showwarning(
                "Missing marks",
                "Mark BOTH the foot plant (P) and contact (C) frames "
                "before saving.",
            )
            return
        if int(self.contact_mark) <= int(self.plant_mark):
            messagebox.showwarning(
                "Invalid order",
                f"Contact (frame {self.contact_mark}) must come AFTER "
                f"foot plant (frame {self.plant_mark}). Use ← → to "
                "navigate and re-mark.",
            )
            return
        entry, _ = self.swings[self.current_idx]
        entry.ground_truth.final_plant_frame = int(self.plant_mark)
        entry.ground_truth.contact_frame = int(self.contact_mark)
        entry.ground_truth.stride_style = (
            "toe_tap" if self.toe_var.get() == "yes" else "standard_stride"
        )
        if not entry.labeled_at:
            entry.labeled_at = str(date.today())
        try:
            _save_manifest_atomic(self.manifest, MANIFEST_PATH)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror(
                "Save failed",
                f"Could not write manifest:\n\n{e}\n\n"
                "Your marks are still in memory — try again.",
            )
            return
        self._next_swing()

    def _next_swing(self) -> None:
        self._stop_play()
        # Find the next unlabeled swing AFTER the current index
        next_idx = None
        for i in range(self.current_idx + 1, len(self.swings)):
            entry, _ = self.swings[i]
            if not entry.ground_truth.is_labeled:
                next_idx = i
                break
        # Wrap around to find any unlabeled before the current
        if next_idx is None:
            for i in range(0, self.current_idx):
                entry, _ = self.swings[i]
                if not entry.ground_truth.is_labeled:
                    next_idx = i
                    break
        if next_idx is None:
            messagebox.showinfo(
                "All labeled",
                "🎉 Every swing with a video is labeled!\n\n"
                "Run the validation report:\n"
                "  python3 -m scripts.validation.run_validation",
            )
            self._quit()
            return
        self.current_idx = next_idx
        self._load_current_swing()

    def _quit(self) -> None:
        self._stop_play()
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None
        try:
            self.root.quit()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass


def main() -> int:
    root = tk.Tk()
    try:
        LabelingApp(root)
    except SystemExit:
        return 0
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        try:
            messagebox.showerror("Startup error", f"{e}\n\n{traceback.format_exc()}")
        except Exception:
            pass
        return 2
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
