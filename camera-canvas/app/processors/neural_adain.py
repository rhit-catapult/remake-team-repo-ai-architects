"""AdaIN arbitrary-style processor. One model handles any style image."""

import os

import cv2
import numpy as np
import torch

from app.processors.base import Processor
from app.models.adain import build_encoder, build_decoder, adain


class AdaINProcessor(Processor):
    name = "AdaIN"
    category = "arbitrary"
    has_strength = True

    def __init__(self, vgg_path, decoder_path, device):
        self.device = device
        self.encoder = build_encoder(vgg_path, device)
        self.decoder = build_decoder(decoder_path, device)
        self.alpha = 1.0
        self.style_feat = None
        self.style_name = None
        self.style_thumb = None

    def set_strength(self, value):
        self.alpha = max(0.0, min(1.0, value))

    def get_strength(self):
        return self.alpha

    def set_style_image(self, path):
        """Load + encode a style image once; cache its features."""
        img = cv2.imread(path)
        if img is None:
            return False
        self.style_name = os.path.splitext(os.path.basename(path))[0]
        self.style_thumb = img.copy()
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        t = torch.from_numpy(rgb).to(self.device).permute(2, 0, 1).unsqueeze(0)
        with torch.inference_mode():
            self.style_feat = self.encoder(t)
        return True

    def process(self, frame_bgr):
        if self.style_feat is None:
            return frame_bgr
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        c = torch.from_numpy(rgb).to(self.device).permute(2, 0, 1).unsqueeze(0)
        with torch.inference_mode():
            c_feat = self.encoder(c)
            t = adain(c_feat, self.style_feat)
            t = self.alpha * t + (1 - self.alpha) * c_feat
            out = self.decoder(t)
        out = out.clamp(0, 1).squeeze(0).permute(1, 2, 0).to("cpu").numpy()
        out = (out * 255).astype(np.uint8)
        return cv2.cvtColor(out, cv2.COLOR_RGB2BGR)

    def warmup(self, height, width):
        if self.style_feat is None:
            return
        dummy = np.zeros((height, width, 3), dtype=np.uint8)
        self.process(dummy)
