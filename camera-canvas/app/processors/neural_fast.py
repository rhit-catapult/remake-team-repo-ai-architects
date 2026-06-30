"""Fast per-style neural nets (TransformerNet). One trained model = one style."""

import cv2
import torch

from app.processors.base import Processor
from app.models.transformer_net import load_transformer_net


class FastStyleProcessor(Processor):
    category = "neural"
    has_strength = False

    def __init__(self, name, weight_path, device, use_half=False):
        self.name = name
        self.device = device
        self.dtype = torch.float16 if use_half else torch.float32
        self.model = load_transformer_net(weight_path, device, self.dtype)

    def process(self, frame_bgr):
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        t = torch.from_numpy(rgb).to(self.device)
        t = t.permute(2, 0, 1).unsqueeze(0).to(self.dtype)
        with torch.inference_mode():
            out = self.model(t)
        out = out.clamp(0, 255).squeeze(0).permute(1, 2, 0)
        out = out.to("cpu", torch.uint8).numpy()
        return cv2.cvtColor(out, cv2.COLOR_RGB2BGR)

    def warmup(self, height, width):
        import numpy as np
        dummy = np.zeros((height, width, 3), dtype=np.uint8)
        self.process(dummy)
