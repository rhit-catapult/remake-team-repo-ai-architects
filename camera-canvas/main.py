"""Real-Time Neural Style Transfer Webcam - entry point."""

import os
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import sys
import glob
import argparse

import yaml
import torch
import pygame

from app.processors.registry import build_registry
from app.pipeline import build_capture, build_worker, warmup_all, FPSCounter
from app.recorder import Recorder
from app.ui import UI
from app.ui_home import HomeScreen
from app.ui_snapshot import SnapshotScreen
from app.benchmark import run_benchmark


def select_device(override=None):
    if override:
        return torch.device(override)
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def load_config(path="config.yaml"):
    with open(path) as f:
        return yaml.safe_load(f)


def discover_styles(styles_dir):
    exts = ("*.jpg", "*.jpeg", "*.png", "*.bmp", "*.webp")
    out = []
    for e in exts:
        out.extend(sorted(glob.glob(os.path.join(styles_dir, e))))
    return out


class AppState:
    """Shared mutable state read by the worker (processor, infer_res) and the UI."""

    def __init__(self, registry, adain, config, device, preset_styles):
        self.registry = registry
        self.ids = list(registry.keys())
        self.adain = adain
        self.device_name = device.type
        self.preset_styles = preset_styles
        self.preset_idx = 0

        self.resolutions = config["resolutions"]
        try:
            self.res_idx = self.resolutions.index(config["default_resolution"])
        except ValueError:
            self.res_idx = 0

        default = config.get("default_style", self.ids[0])
        self.idx = self.ids.index(default) if default in self.ids else 0
        self.processor = self.entry().processor
        self.style_id = self.ids[self.idx]

        self.side_by_side = False
        self.fullscreen = config.get("start_fullscreen", False)
        self.window_w = config["window_width"]
        self.window_h = config["window_height"]
        self.reduce_motion = config.get("reduce_motion", False)

    @property
    def infer_res(self):
        return self.resolutions[self.res_idx]

    def entry(self):
        return self.registry[self.ids[self.idx]]

    def _apply(self):
        self.processor = self.entry().processor
        self.style_id = self.ids[self.idx]

    def cycle_style(self, d):
        self.idx = (self.idx + d) % len(self.ids)
        self._apply()

    def jump_style(self, n):
        if 0 <= n < len(self.ids):
            self.idx = n
            self._apply()

    def change_strength(self, d):
        p = self.processor
        if p.has_strength:
            p.set_strength(max(0.0, min(1.0, p.get_strength() + d)))

    def cycle_res(self, d):
        self.res_idx = max(0, min(len(self.resolutions) - 1, self.res_idx + d))

    def _switch_to_adain(self):
        if "adain" in self.ids:
            self.idx = self.ids.index("adain")
            self._apply()

    def use_style_image(self, path):
        if self.adain and self.adain.set_style_image(path):
            self._switch_to_adain()
            print(f"[state] AdaIN style set: {path}")

    def next_preset(self):
        if self.adain and self.preset_styles:
            self.preset_idx = (self.preset_idx + 1) % len(self.preset_styles)
            if self.adain.set_style_image(self.preset_styles[self.preset_idx]):
                self._switch_to_adain()


def run_live_screen(screen, state, raw_slot, recorder, capture, config, registry, device):
    """One visit to the Live screen. Returns 'home' or 'quit'."""
    out_slot, worker, worker_stop = build_worker(raw_slot, state)
    print("[main] warming up...")
    warmup_all(registry, state.infer_res, stop_event=worker_stop)
    worker.start()

    display_fps = FPSCounter()
    ui = UI(screen, state, out_slot, raw_slot, recorder, capture,
            display_fps, lambda: worker.fps.value())
    clock = pygame.time.Clock()

    try:
        while not ui.want_quit and not ui.want_back:
            ui.handle_events()
            if ui.want_benchmark:
                print("[main] running benchmark (UI paused)...")
                run_benchmark(registry, device, config["resolutions"],
                              frames=config.get("benchmark_frames", 60),
                              outputs_dir=config["outputs_dir"],
                              display_size=(config["display_height"], config["display_width"]))
            ui.draw()
            if recorder.recording:
                styled = out_slot.get()
                if styled is not None:
                    recorder.write(styled)
            clock.tick(60)
    finally:
        worker_stop.set()
        recorder.stop()
        worker.join(timeout=1.0)

    return "quit" if ui.want_quit else "home"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default=None, help="mps | cpu")
    parser.add_argument("--camera", type=int, default=None)
    parser.add_argument("--benchmark", action="store_true")
    args = parser.parse_args()

    config = load_config()
    device = select_device(args.device)
    camera_index = args.camera if args.camera is not None else config["camera_index"]
    print(f"[main] device={device.type}")

    registry, adain = build_registry(device, config["weights_dir"],
                                     use_half=config.get("use_half", False))
    preset_styles = discover_styles(config["styles_dir"])

    if args.benchmark:
        if adain and preset_styles:
            adain.set_style_image(preset_styles[0])
        run_benchmark(registry, device, config["resolutions"],
                      frames=config.get("benchmark_frames", 60),
                      outputs_dir=config["outputs_dir"],
                      display_size=(config["display_height"], config["display_width"]))
        return

    if adain and preset_styles:
        adain.set_style_image(preset_styles[0])

    state = AppState(registry, adain, config, device, preset_styles)

    pygame.init()
    pygame.display.set_caption("Neural Style Transfer - Webcam")
    if state.fullscreen:
        screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    else:
        screen = pygame.display.set_mode((state.window_w, state.window_h))

    raw_slot, capture, capture_stop = build_capture(
        camera_index, config["display_width"], config["display_height"])
    capture.start()

    recorder = Recorder(config["outputs_dir"])

    try:
        action = "home"
        while action != "quit":
            screen = pygame.display.get_surface()
            if action == "home":
                action = HomeScreen(screen, capture, raw_slot, state.device_name,
                                    len(state.ids)).run()
            elif action == "live":
                action = run_live_screen(screen, state, raw_slot, recorder, capture,
                                         config, registry, device)
            elif action == "snapshot":
                action = SnapshotScreen(screen, registry, raw_slot, capture, recorder).run()
            else:
                action = "quit"
    finally:
        capture_stop.set()
        recorder.stop()
        capture.join(timeout=1.0)
        pygame.quit()
        print("[main] clean shutdown")


if __name__ == "__main__":
    main()
    sys.exit(0)
