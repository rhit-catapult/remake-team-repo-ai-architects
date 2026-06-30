"""Style registry: id -> Processor (+ metadata)."""

import os
from collections import OrderedDict

from app.processors.cv_filters import build_cv_filters
from app.processors.neural_fast import FastStyleProcessor

FAST_STYLE_FILES = OrderedDict([
    ("candy.pth", "Candy"),
    ("mosaic.pth", "Mosaic"),
    ("rain_princess.pth", "Rain Princess"),
    ("udnie.pth", "Udnie"),
])

ADAIN_VGG = "vgg_normalised.pth"
ADAIN_DECODER = "decoder.pth"


class StyleEntry:
    def __init__(self, style_id, processor):
        self.id = style_id
        self.processor = processor
        self.name = processor.name
        self.category = processor.category
        self.has_strength = processor.has_strength


def build_registry(device, weights_dir, use_half=False):
    """Return (OrderedDict[id -> StyleEntry], adain_processor_or_None)."""
    registry = OrderedDict()

    for proc in build_cv_filters():
        sid = proc.name.lower().replace(" ", "_")
        registry[sid] = StyleEntry(sid, proc)

    for filename, display in FAST_STYLE_FILES.items():
        path = os.path.join(weights_dir, filename)
        if os.path.isfile(path):
            try:
                proc = FastStyleProcessor(display, path, device, use_half=use_half)
                registry[display.lower().replace(" ", "_")] = StyleEntry(
                    display.lower().replace(" ", "_"), proc)
            except Exception as exc:
                print(f"[registry] failed to load {filename}: {exc}")

    adain_proc = None
    vgg_path = os.path.join(weights_dir, ADAIN_VGG)
    dec_path = os.path.join(weights_dir, ADAIN_DECODER)
    if os.path.isfile(vgg_path) and os.path.isfile(dec_path):
        try:
            from app.processors.neural_adain import AdaINProcessor
            adain_proc = AdaINProcessor(vgg_path, dec_path, device)
            registry["adain"] = StyleEntry("adain", adain_proc)
        except Exception as exc:
            print(f"[registry] failed to load AdaIN: {exc}")

    print(f"[registry] {len(registry)} styles: {', '.join(registry.keys())}")
    return registry, adain_proc
