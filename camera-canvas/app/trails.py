"""Motion paint trails: wave at the camera and leave glowing paint streaks.

Frame-differencing on a small grayscale copy of the raw feed finds "what
moved"; that motion mask deposits paint (a hue that drifts through the
rainbow over time) onto a low-resolution float canvas. Each camera frame the
canvas fades a little and diffuses a little, so streaks bleed and dissolve
like wet ink. The canvas is upscaled and screen-composited over the styled
frame at draw time.

Everything heavy happens at WORK_W (320px) resolution, so the whole effect
costs well under a millisecond per camera frame.
"""

import time

import cv2
import numpy as np

WORK_W = 320          # processing width; height follows the frame aspect
FADE = 0.94           # canvas persistence per camera frame (~1.5s tail at 30fps)
DIFFUSE_SIGMA = 1.0   # per-frame blur -> paint bleeds outward like wet ink
DIFF_THRESH = 26      # min per-pixel gray delta to count as motion
GAIN = 2.4            # motion -> paint intensity
HUE_DEG_PER_SEC = 36  # paint color drifts through the rainbow


class MotionTrails:
    def __init__(self, enabled=True):
        self.enabled = enabled
        self._canvas = None       # float32 BGR paint canvas at work resolution
        self._prev_gray = None
        self._last_frame_id = None
        self._activity = 0.0      # smoothed 0..1 "how much is moving right now"

    # ── public readouts ──────────────────────────────────────────────────
    @property
    def activity(self):
        """Smoothed 0..1 motion level, for UI meters."""
        return self._activity

    def current_color(self):
        """The BGR color paint is currently being laid down in."""
        return self._hue_to_bgr(self._hue_now())

    # ── controls ─────────────────────────────────────────────────────────
    def toggle(self):
        self.enabled = not self.enabled
        if not self.enabled:
            self.clear()
        return self.enabled

    def clear(self):
        if self._canvas is not None:
            self._canvas[:] = 0.0

    # ── per-camera-frame update ──────────────────────────────────────────
    def update(self, frame_bgr):
        """Feed the latest raw camera frame. Safe to call every display tick;
        work only happens when a genuinely new frame arrives."""
        if not self.enabled or frame_bgr is None:
            return
        if id(frame_bgr) == self._last_frame_id:
            return
        self._last_frame_id = id(frame_bgr)

        h, w = frame_bgr.shape[:2]
        work_h = max(1, round(h * WORK_W / w))
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, (WORK_W, work_h), interpolation=cv2.INTER_AREA)
        gray = cv2.GaussianBlur(gray, (0, 0), 1.2)

        if (self._canvas is None or self._canvas.shape[:2] != (work_h, WORK_W)):
            self._canvas = np.zeros((work_h, WORK_W, 3), np.float32)
            self._prev_gray = None

        if self._prev_gray is not None:
            diff = cv2.absdiff(gray, self._prev_gray)
            _, mask = cv2.threshold(diff, DIFF_THRESH, 255, cv2.THRESH_BINARY)
            mask = cv2.dilate(mask, None, iterations=1)
            mask = cv2.GaussianBlur(mask, (0, 0), 2.0)

            level = float(mask.mean()) / 255.0
            self._activity += (min(1.0, level * 6.0) - self._activity) * 0.15

            # Fade + diffuse the existing paint, then deposit the new stroke.
            self._canvas *= FADE
            self._canvas = cv2.GaussianBlur(self._canvas, (0, 0), DIFFUSE_SIGMA)
            color = self._hue_to_bgr(self._hue_now())
            m = (mask.astype(np.float32) / 255.0) * GAIN
            for c in range(3):
                self._canvas[:, :, c] += m * color[c]
            np.clip(self._canvas, 0.0, 255.0, out=self._canvas)

        self._prev_gray = gray

    # ── compositing ──────────────────────────────────────────────────────
    def composite(self, styled_bgr):
        """Screen-blend the paint canvas over a styled frame. Returns a new
        array (or the input untouched when there is nothing to draw)."""
        if not self.enabled or self._canvas is None or styled_bgr is None:
            return styled_bgr
        if self._canvas.max() < 2.0:
            return styled_bgr
        h, w = styled_bgr.shape[:2]
        trail = cv2.resize(self._canvas, (w, h), interpolation=cv2.INTER_LINEAR)
        trail = trail.astype(np.uint8)
        # Additive glow: bright streaks bloom toward white over any style.
        return cv2.add(styled_bgr, trail)

    # ── internals ────────────────────────────────────────────────────────
    @staticmethod
    def _hue_now():
        return (time.time() * HUE_DEG_PER_SEC) % 360.0

    @staticmethod
    def _hue_to_bgr(hue_deg):
        hsv = np.uint8([[[int(hue_deg / 2) % 180, 255, 255]]])
        b, g, r = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)[0, 0]
        return (int(b), int(g), int(r))
