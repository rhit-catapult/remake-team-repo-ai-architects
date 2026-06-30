"""Decoupled threaded pipeline: capture -> inference -> display."""

import time
import threading
from collections import deque

import cv2
import numpy as np

from app.capture import CaptureThread


class LatestSlot:
    """Holds only the most recent item; readers get the freshest, writers never block."""

    def __init__(self):
        self._lock = threading.Lock()
        self._item = None

    def put(self, item):
        with self._lock:
            self._item = item

    def get(self):
        with self._lock:
            return self._item


class FPSCounter:
    """Rolling-average FPS from recent tick timestamps."""

    def __init__(self, window=30):
        self._times = deque(maxlen=window)

    def tick(self):
        self._times.append(time.time())

    def value(self):
        if len(self._times) < 2:
            return 0.0
        span = self._times[-1] - self._times[0]
        if span <= 0:
            return 0.0
        return (len(self._times) - 1) / span


def scale_to_long_edge(frame, long_edge):
    """Resize so the longer side == long_edge, preserving aspect ratio."""
    h, w = frame.shape[:2]
    if max(h, w) == long_edge:
        return frame
    if w >= h:
        new_w = long_edge
        new_h = max(1, round(h * long_edge / w))
    else:
        new_h = long_edge
        new_w = max(1, round(w * long_edge / h))
    interp = cv2.INTER_AREA if long_edge < max(h, w) else cv2.INTER_LINEAR
    return cv2.resize(frame, (new_w, new_h), interpolation=interp)


def cap_long_edge(frame, cap_px):
    """Downscale if the long edge exceeds cap_px; never upscale."""
    h, w = frame.shape[:2]
    if max(h, w) <= cap_px:
        return frame
    return scale_to_long_edge(frame, cap_px)


def _sharpen(frame, amount=0.45, sigma=1.4):
    """Light unsharp mask to recover definition lost to a small inference resolution."""
    blurred = cv2.GaussianBlur(frame, (0, 0), sigmaX=sigma)
    return cv2.addWeighted(frame, 1 + amount, blurred, -amount, 0)


class InferenceWorker(threading.Thread):
    """Grabs the latest raw frame, runs the active processor at the inference
    resolution, upscales the result to display size, and publishes it."""

    def __init__(self, raw_slot, out_slot, stop_event, state):
        super().__init__(daemon=True)
        self.raw_slot = raw_slot
        self.out_slot = out_slot
        self.stop_event = stop_event
        self.state = state
        self.fps = FPSCounter()
        self._last_id = None

    def run(self):
        while not self.stop_event.is_set():
            frame = self.raw_slot.get()
            if frame is None or id(frame) == self._last_id:
                time.sleep(0.002)
                continue
            self._last_id = id(frame)

            proc = self.state.processor
            long_edge = self.state.infer_res
            h, w = frame.shape[:2]
            try:
                small = scale_to_long_edge(frame, long_edge)
                styled_small = proc.process(small)
                if styled_small.shape[:2] != (h, w):
                    styled = cv2.resize(styled_small, (w, h), interpolation=cv2.INTER_CUBIC)
                    styled = _sharpen(styled)
                else:
                    styled = styled_small
            except Exception as exc:
                print(f"[inference] {proc.name} failed: {exc}")
                styled = frame
            self.out_slot.put(styled)
            self.fps.tick()


def warmup_all(registry, infer_res, stop_event=None):
    """Run one dummy inference per processor so the first live frame is smooth."""
    dummy = np.zeros((infer_res, infer_res, 3), dtype=np.uint8)
    for entry in registry.values():
        if stop_event is not None and stop_event.is_set():
            return
        try:
            entry.processor.warmup(infer_res, infer_res)
            entry.processor.process(dummy)
        except Exception as exc:
            print(f"[warmup] {entry.name}: {exc}")


def build_capture(camera_index, display_w, display_h):
    """Create the long-lived capture slot + thread, shared by every screen."""
    stop_event = threading.Event()
    raw_slot = LatestSlot()
    capture = CaptureThread(raw_slot, stop_event, index=camera_index,
                            width=display_w, height=display_h)
    return raw_slot, capture, stop_event


def build_worker(raw_slot, state):
    """Create a fresh inference worker + output slot for one Live-screen visit."""
    stop_event = threading.Event()
    out_slot = LatestSlot()
    worker = InferenceWorker(raw_slot, out_slot, stop_event, state)
    return out_slot, worker, stop_event
