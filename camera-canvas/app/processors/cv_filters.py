"""Cheap OpenCV/NumPy filters - run inline at full framerate, no GPU."""

import cv2
import numpy as np

from app.processors.base import Processor


class SketchProcessor(Processor):
    name = "Sketch"
    category = "filter"
    has_strength = True

    def __init__(self):
        self._strength = 0.6

    def set_strength(self, value):
        self._strength = max(0.0, min(1.0, value))

    def get_strength(self):
        return self._strength

    def process(self, frame_bgr):
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        inv = 255 - gray
        k = int(7 + self._strength * 34)
        k = k + 1 if k % 2 == 0 else k
        blur = cv2.GaussianBlur(inv, (k, k), 0)
        sketch = cv2.divide(gray, 255 - blur, scale=256)
        return cv2.cvtColor(sketch, cv2.COLOR_GRAY2BGR)


class PixelProcessor(Processor):
    name = "Pixel"
    category = "filter"
    has_strength = True

    def __init__(self):
        self._strength = 0.4

    def set_strength(self, value):
        self._strength = max(0.0, min(1.0, value))

    def get_strength(self):
        return self._strength

    def process(self, frame_bgr):
        h, w = frame_bgr.shape[:2]
        k = int(2 + self._strength * 22)
        small = cv2.resize(frame_bgr, (max(1, w // k), max(1, h // k)),
                           interpolation=cv2.INTER_LINEAR)
        return cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)


class CartoonProcessor(Processor):
    name = "Cartoon"
    category = "filter"
    has_strength = True

    def __init__(self):
        self._strength = 0.5

    def set_strength(self, value):
        self._strength = max(0.0, min(1.0, value))

    def get_strength(self):
        return self._strength

    def process(self, frame_bgr):
        sigma_s = 40 + self._strength * 90
        sigma_r = 0.35 + self._strength * 0.15
        try:
            return cv2.stylization(frame_bgr, sigma_s=sigma_s, sigma_r=sigma_r)
        except Exception:
            return self._manual_cartoon(frame_bgr)

    def _manual_cartoon(self, frame_bgr):
        color = cv2.bilateralFilter(frame_bgr, 9, 250, 250)
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        gray = cv2.medianBlur(gray, 7)
        edges = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                      cv2.THRESH_BINARY, 9, 2)
        edges = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
        return cv2.bitwise_and(color, edges)


class OilPaintingProcessor(Processor):
    name = "Oil Painting"
    category = "filter"
    has_strength = True

    def __init__(self):
        self._strength = 0.4

    def set_strength(self, value):
        self._strength = max(0.0, min(1.0, value))

    def get_strength(self):
        return self._strength

    def process(self, frame_bgr):
        passes = 1 + (1 if self._strength > 0.6 else 0)
        d = 6 + int(round(self._strength * 5))
        out = frame_bgr
        for _ in range(passes):
            out = cv2.bilateralFilter(out, d, 50, 50)
        hsv = cv2.cvtColor(out, cv2.COLOR_BGR2HSV).astype(np.float32)
        hsv[:, :, 1] = np.clip(hsv[:, :, 1] * (1.0 + 0.3 * self._strength), 0, 255)
        out = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)

        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        edge_strength = np.clip(cv2.magnitude(gx, gy) / 255.0, 0, 1) ** 0.7
        darken = (1.0 - edge_strength[:, :, None] * 0.35).astype(np.float32)
        out = np.clip(out.astype(np.float32) * darken, 0, 255).astype(np.uint8)
        return out


class CrayonProcessor(Processor):
    name = "Crayon"
    category = "filter"
    has_strength = True

    def __init__(self):
        self._strength = 0.5

    def set_strength(self, value):
        self._strength = max(0.0, min(1.0, value))

    def get_strength(self):
        return self._strength

    def process(self, frame_bgr):
        h, w = frame_bgr.shape[:2]
        levels = max(3, 9 - int(round(self._strength * 5)))
        step = 256 // levels
        poster = (frame_bgr // step) * step + step // 2
        poster = np.clip(poster, 0, 255).astype(np.uint8)

        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        gray = cv2.medianBlur(gray, 5)
        edges = cv2.Canny(gray, 60, 150)
        edges = cv2.dilate(edges, np.ones((2, 2), np.uint8), iterations=1)
        edge_mask = cv2.cvtColor(255 - edges, cv2.COLOR_GRAY2BGR)
        out = cv2.bitwise_and(poster, edge_mask)

        yy, xx = np.indices((h, w))
        hatch = (((xx + yy) // 3) % 2 * 14).astype(np.uint8)
        hatch = cv2.cvtColor(hatch, cv2.COLOR_GRAY2BGR)
        out = cv2.subtract(out, (hatch * (0.3 + 0.4 * self._strength)).astype(np.uint8))
        return out


class WatercolorProcessor(Processor):
    name = "Watercolor"
    category = "filter"
    has_strength = True

    def __init__(self):
        self._strength = 0.5

    def set_strength(self, value):
        self._strength = max(0.0, min(1.0, value))

    def get_strength(self):
        return self._strength

    def process(self, frame_bgr):
        sigma_s = 30 + self._strength * 60
        sigma_r = 0.3 + self._strength * 0.2
        try:
            smoothed = cv2.edgePreservingFilter(frame_bgr, flags=cv2.RECURS_FILTER,
                                                sigma_s=sigma_s, sigma_r=sigma_r)
        except Exception:
            smoothed = cv2.bilateralFilter(frame_bgr, 9, 100, 100)
        hsv = cv2.cvtColor(smoothed, cv2.COLOR_BGR2HSV).astype(np.float32)
        hsv[:, :, 1] = np.clip(hsv[:, :, 1] * 1.15, 0, 255)
        hsv[:, :, 2] = np.clip(hsv[:, :, 2] * 1.05 + 8, 0, 255)
        out = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)

        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        edge_strength = np.clip(cv2.magnitude(gx, gy) / 255.0, 0, 1) ** 0.8
        darken = (1.0 - edge_strength[:, :, None] * 0.2).astype(np.float32)
        out = np.clip(out.astype(np.float32) * darken, 0, 255).astype(np.uint8)
        return out


class CharcoalProcessor(Processor):
    name = "Charcoal"
    category = "filter"
    has_strength = True

    def __init__(self):
        self._strength = 0.55

    def set_strength(self, value):
        self._strength = max(0.0, min(1.0, value))

    def get_strength(self):
        return self._strength

    def process(self, frame_bgr):
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
        k = 3 + int(round(self._strength * 4))
        k = k + 1 if k % 2 == 0 else k
        base = cv2.GaussianBlur(gray, (k, k), 0)

        gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        grad = cv2.magnitude(gx, gy) * (0.55 + 0.55 * self._strength)

        shaded = base * 0.62 - grad * 0.45
        noise = np.random.uniform(-7, 7, shaded.shape)
        shaded = np.clip(shaded + noise, 0, 255).astype(np.uint8)
        return cv2.cvtColor(shaded, cv2.COLOR_GRAY2BGR)


def build_cv_filters():
    return [SketchProcessor(), PixelProcessor(), CartoonProcessor(),
            OilPaintingProcessor(), CrayonProcessor(), WatercolorProcessor(),
            CharcoalProcessor()]
