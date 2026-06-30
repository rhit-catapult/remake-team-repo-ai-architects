"""Benchmark mode: sweep inference resolutions per processor, log FPS to CSV."""

import os
import csv
import time
import statistics

import numpy as np
import torch

from app.pipeline import scale_to_long_edge


def _sync(device):
    """Block until queued GPU work finishes so timings are accurate."""
    if device.type == "mps":
        torch.mps.synchronize()
    elif device.type == "cuda":
        torch.cuda.synchronize()


def run_benchmark(registry, device, resolutions, frames=60, outputs_dir="outputs",
                  display_size=(720, 1280)):
    os.makedirs(outputs_dir, exist_ok=True)
    out_path = os.path.join(outputs_dir, f"benchmark_{device.type}_{time.strftime('%Y%m%d_%H%M%S')}.csv")
    h, w = display_size
    base = (np.random.rand(h, w, 3) * 255).astype(np.uint8)

    rows = []
    print(f"[benchmark] device={device.type} frames={frames} "
          f"resolutions={resolutions}")
    for style_id, entry in registry.items():
        proc = entry.processor
        if entry.category == "arbitrary" and getattr(proc, "style_feat", None) is None:
            print(f"[benchmark] skipping {style_id} (no style image set)")
            continue
        for res in resolutions:
            small = scale_to_long_edge(base, res)
            try:
                proc.process(small)
                _sync(device)
            except Exception as exc:
                print(f"[benchmark] {style_id}@{res} warmup failed: {exc}")
                continue

            times = []
            for _ in range(frames):
                t0 = time.perf_counter()
                proc.process(small)
                _sync(device)
                times.append(time.perf_counter() - t0)
            mean_fps = 1.0 / statistics.mean(times)
            median_fps = 1.0 / statistics.median(times)
            rows.append({
                "device": device.type,
                "style": style_id,
                "category": entry.category,
                "infer_res": res,
                "mean_fps": round(mean_fps, 2),
                "median_fps": round(median_fps, 2),
                "frames": frames,
            })
            print(f"  {style_id:>14} @ {res:>4}: "
                  f"mean {mean_fps:6.1f} fps | median {median_fps:6.1f} fps")

    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "device", "style", "category", "infer_res",
            "mean_fps", "median_fps", "frames"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"[benchmark] wrote {out_path}")
    return out_path
