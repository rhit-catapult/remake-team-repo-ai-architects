"""Screenshots (PNG) and screen recording (mp4) of the styled stream."""

import os
import time

import cv2


def _timestamp():
    return time.strftime("%Y%m%d_%H%M%S")


class Recorder:
    def __init__(self, outputs_dir):
        self.outputs_dir = outputs_dir
        os.makedirs(outputs_dir, exist_ok=True)
        self._writer = None
        self._imageio_writer = None
        self._size = None
        self.recording = False
        self.last_path = None

    def screenshot(self, frame_bgr, suffix=""):
        name = f"shot_{_timestamp()}{suffix}.png"
        path = os.path.join(self.outputs_dir, name)
        cv2.imwrite(path, frame_bgr)
        self.last_path = path
        print(f"[recorder] screenshot -> {path}")
        return path

    def toggle_recording(self, fps, frame_bgr):
        if self.recording:
            self.stop()
            return False
        self._start(fps, frame_bgr)
        return self.recording

    def _start(self, fps, frame_bgr):
        h, w = frame_bgr.shape[:2]
        self._size = (w, h)
        fps = max(1.0, float(fps))
        path = os.path.join(self.outputs_dir, f"rec_{_timestamp()}.mp4")
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(path, fourcc, fps, (w, h))
        if writer.isOpened():
            self._writer = writer
            self.last_path = path
            self.recording = True
            print(f"[recorder] recording -> {path} @ {fps:.0f}fps")
            return
        writer.release()
        try:
            import imageio
            self._imageio_writer = imageio.get_writer(path, fps=fps, macro_block_size=None)
            self.last_path = path
            self.recording = True
            print(f"[recorder] recording (imageio) -> {path} @ {fps:.0f}fps")
        except Exception as exc:
            print(f"[recorder] could not start recording: {exc}")
            self.recording = False

    def write(self, frame_bgr):
        if not self.recording:
            return
        if (frame_bgr.shape[1], frame_bgr.shape[0]) != self._size:
            frame_bgr = cv2.resize(frame_bgr, self._size)
        if self._writer is not None:
            self._writer.write(frame_bgr)
        elif self._imageio_writer is not None:
            self._imageio_writer.append_data(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))

    def stop(self):
        if self._writer is not None:
            self._writer.release()
            self._writer = None
        if self._imageio_writer is not None:
            try:
                self._imageio_writer.close()
            except Exception:
                pass
            self._imageio_writer = None
        if self.recording:
            print(f"[recorder] saved -> {self.last_path}")
        self.recording = False
