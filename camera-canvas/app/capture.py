"""Threaded webcam capture -> a single-slot buffer (always the freshest frame)."""

import time
import threading

import cv2


class CaptureThread(threading.Thread):
    """Continuously reads the camera and writes the newest frame into `slot`,
    overwriting the previous one. Never queues stale frames. Handles a
    busy/unavailable camera without crashing and supports live index switching.
    """

    def __init__(self, slot, stop_event, index=0, width=1280, height=720):
        super().__init__(daemon=True)
        self.slot = slot
        self.stop_event = stop_event
        self.index = index
        self.width = width
        self.height = height
        self.cap = None
        self.connected = False
        self.error = None
        self._lock = threading.Lock()
        self._switch_to = None

    def _open(self, index):
        backend = getattr(cv2, "CAP_AVFOUNDATION", 0)
        cap = cv2.VideoCapture(index, backend)
        if not cap.isOpened():
            cap.release()
            return None
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        return cap

    def switch_camera(self, index):
        with self._lock:
            self._switch_to = index

    def run(self):
        while not self.stop_event.is_set():
            with self._lock:
                pending = self._switch_to
                self._switch_to = None
            if pending is not None and pending != self.index:
                self.index = pending
                if self.cap is not None:
                    self.cap.release()
                    self.cap = None

            if self.cap is None:
                self.cap = self._open(self.index)
                if self.cap is None:
                    self.connected = False
                    self.error = (f"Camera {self.index} unavailable. "
                                  f"Close other apps using it, or switch index.")
                    time.sleep(0.5)
                    continue
                self.connected = True
                self.error = None

            ok, frame = self.cap.read()
            if not ok or frame is None:
                self.connected = False
                self.error = "Camera read failed; retrying..."
                self.cap.release()
                self.cap = None
                time.sleep(0.3)
                continue

            self.connected = True
            self.slot.put(frame)

        if self.cap is not None:
            self.cap.release()
            self.cap = None
