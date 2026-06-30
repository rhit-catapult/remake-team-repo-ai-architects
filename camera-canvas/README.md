# Real-Time Neural Style Transfer Webcam

A desktop app that re-renders your webcam feed — live or from a still photo —
in different visual styles: painterly neural styles (Candy / Mosaic / Rain
Princess / Udnie), **AdaIN** arbitrary style (point it at any image, including
a Starry Night for "Van Gogh mode"), and seven CV filters (Sketch / Pixel /
Cartoon / Oil Painting / Crayon / Watercolor / Charcoal). Switch styles live,
tweak strength, screenshot, and record — or capture/upload a single photo and
generate full-quality artwork from it.

This is **neural style transfer**, not a deepfake — no face swapping or
identity synthesis.

Built for Apple Silicon with **PyTorch MPS** (clean CPU fallback), **pygame**
UI, and **OpenCV** capture.

## Quick start

```bash
pip install -r requirements.txt
python scripts/download_weights.py     # fetch pretrained weights (best-effort)
python main.py                         # opens the home screen, fullscreen by default
```

The app runs even with no weights at all — the seven CV filters always work,
and a clear on-screen message appears if the camera is busy or missing.
Neural styles and AdaIN appear automatically the moment their weights land in
`weights/`; nothing needs to be reconfigured.

```bash
python main.py --device cpu     # force CPU, e.g. to compare against MPS
python main.py --camera 1       # pick a camera index if you have more than one
python main.py --benchmark      # FPS sweep across resolutions -> outputs/*.csv
```

## The three screens

1. **Home** — pick a mode: Live Style Transfer or Create from Photo. Shows a
   small live camera preview and a device/camera status line so you can
   sanity-check the rig before going live. `Left`/`Right` or `1`/`2` to
   select, `Enter` to confirm, `Esc` to quit the app.
2. **Live Style Transfer** — the real-time webcam pipeline. `Esc` returns to
   Home rather than quitting, so switching modes mid-session is cheap.
3. **Create from Photo** — capture a still frame from the camera (`C`) or
   upload an image (`O`, or drag-and-drop onto the window), pick a style, and
   generate full-quality artwork on a background thread so the UI never
   freezes while a neural model runs. Shows the original and the result
   side-by-side; `S` saves the result as a PNG to `outputs/`. `Esc` returns
   to Home.

The camera capture thread is started once, at launch, and shared by all three
screens — Home's live preview, Snapshot's capture button, and Live's pipeline
all read from the same frame buffer. The heavier inference worker, by
contrast, is created fresh each time you enter Live and torn down the moment
you leave it, so a style model isn't quietly burning GPU and battery while
you're sitting on the Home screen or generating a snapshot.

## Controls

**Live screen** (keyboard-first; mouse works too, but nothing requires
precision clicking):

| Key | Action |
|-----|--------|
| `Left` / `Right` or `1`–`9` | cycle / jump to style |
| `Up` / `Down` | strength (AdaIN alpha / filter intensity) |
| `[` / `]` | inference resolution down / up |
| `Tab` | side-by-side original \| styled |
| `S` | screenshot (PNG → outputs/) |
| `R` | toggle recording (mp4 → outputs/) |
| `O` | open style-image picker (AdaIN) |
| `P` | cycle preset style images (AdaIN) |
| `F` | toggle fullscreen |
| `B` | run a benchmark sweep |
| `Esc` | back to Home |

You can also **drag-and-drop** an image onto the window to use it as the
AdaIN style. Buttons (record / screenshot / thumbnail) are clickable.

**Create from Photo** uses the same style-cycling keys (`Left`/`Right`,
`1`-`9`, `Up`/`Down` for strength) plus `C` capture, `O` upload, `Enter`
generate, `S` save.

## Architecture

### Why a threaded pipeline

The naive approach — capture a frame, run the model, draw it, repeat — ties
your frame rate to your slowest model. A heavy neural style at 12 FPS would
make the whole window feel like it's hung, even though pygame itself could
easily redraw at 60 FPS. The fix is to decouple the three stages completely:

1. **Capture thread** writes the newest webcam frame into a single-slot
   buffer, overwriting whatever was there before. It never queues stale
   frames, and it never blocks waiting for a consumer.
2. **Inference worker** reads the latest frame, runs the active style
   processor at a small *inference resolution* (configurable live with `[`
   and `]`), and writes the styled result into its own single-slot buffer.
   If the model is slow, it simply produces fewer frames — it never backs up
   capture or display.
3. **Main thread** reads the latest styled frame and draws it at a steady 60
   FPS, regardless of how fast inference is keeping up.

Because display and inference are fully decoupled, the FPS HUD on the Live
screen shows two independent numbers — inference FPS and display FPS — and
you can watch them diverge in real time as you change styles or drop the
inference resolution. That's deliberate: it's the most direct way to *see*
the speed/quality tradeoff happening, rather than read about it.

The single-slot buffer (`LatestSlot` in `app/pipeline.py`) is intentionally
the simplest possible thread-safe structure: a lock, one item, last write
wins. There is no queue to overflow and no backpressure to manage.

A short warm-up pass runs once per processor before the live loop starts.
The first MPS call for any given model compiles its Metal kernels on the
fly, which is slow; without the warm-up, that cost would land on whatever
frame happened to trigger it, causing a visible stutter the first time each
style is selected.

### Why Create from Photo doesn't share the real-time pipeline

A single still photo has no frame-rate target, so the Snapshot screen
processes it once, synchronously in spirit but on a background thread so the
UI keeps responding. The image is capped at a 1024px long edge before
processing (smaller captures are left at their native size — never
upscaled), which keeps generation time reasonable for the heavier neural
styles without throttling quality for the common case.

The one real hazard in this design is what happens if a generation is still
running when the user captures or uploads a *different* source photo before
it finishes. Without a guard, the in-flight background thread could
eventually land its result against the new photo, silently overwriting
whatever the user expects to see. The fix is a job-id counter: every new
source photo bumps the id and resets `busy` immediately; the background
thread checks its captured id against the current one before writing its
result, so a stale job's output is discarded rather than displayed.

### Style registry

`app/processors/registry.py` builds one dictionary of style id → processor
at startup. The seven CV filters in `app/processors/cv_filters.py` are
always available since they have no external dependencies beyond OpenCV. The
four fast neural styles (Candy, Mosaic, Rain Princess, Udnie) and AdaIN are
added conditionally, only if their corresponding `.pth` weight files are
found in `weights/` — if they're missing, the app simply runs with fewer
styles rather than failing to start. Adding a new style to the app means
adding one entry to this registry; no UI code needs to change, since both
the Live and Snapshot screens iterate the registry generically.

### AdaIN style caching

AdaIN's whole value proposition is that one trained model can apply *any*
style image, by encoding both the content frame and the style image through
a shared VGG encoder and aligning their statistics. The trap is that
re-encoding the style image on every single video frame would be pure waste
— the style image doesn't change frame to frame, only the content does. The
processor in `app/processors/neural_adain.py` encodes the style image once,
when it's selected, and caches the resulting features; only the much
cheaper content encoding happens per frame.

### Fixing "blobby" output

The downscale-then-upscale step in the inference worker (process small,
stretch back up to display size) is an FPS lever, but on its own it costs
real detail: a frame processed at 384px and stretched to 1080p will look
soft, especially layered on top of ordinary webcam motion blur. Two changes
address this directly: the upscale uses cubic interpolation instead of
linear, and a light unsharp-mask pass runs immediately after, sized
conservatively (sigma ~1.4, amount ~0.45) so it recovers definition without
introducing halos — including on the deliberately blocky Pixel filter, which
doesn't pick up ringing artifacts from this treatment.

Several of the CV filters also needed their own tuning for the same reason.
Oil Painting originally had no edge reinforcement at all, so its bilateral
smoothing just dissolved detail into uniform color blobs with no visible
brush boundaries; it now layers a soft Sobel-based edge darkening on top of
a lighter smoothing pass. Watercolor had a redundant extra Gaussian blur
stacked on top of an already-smooth `edgePreservingFilter` pass — removing
the redundant blur and adding a faint pigment-boundary darkening fixed both
the blur artifacts and the readability. Cartoon's smoothing range was capped
lower, since the top of its old range flattened large regions into blobs
with no edges at all. Charcoal was rebuilt from a different technique
entirely: the original dodge-blend approach (the same one Sketch uses)
produces a near-white page with thin dark lines, which is a pencil-sketch
look, not charcoal; the current version uses gradient-magnitude shading for
a moodier, broadly dark tone with emphasized edges.

### Responsive bottom bar

The Live screen's bottom bar can't use fixed pixel offsets for its clusters
(style name, strength slider, resolution, the FPS hero readout, device
status, AdaIN thumbnail, record/screenshot buttons) because the window can
be resized or, more commonly here, fullscreened at whatever resolution the
presenter's display happens to be. Instead it computes a width budget every
frame: the FPS hero readout and the record/screenshot buttons are
load-bearing and never move or shrink, and everything else is optional,
dropped in priority order — thumbnail first, then device status, then
resolution, then (as a last resort) the strength slider — until what
remains fits. If even the FPS numbers themselves don't have room at their
normal size, they fall back to a smaller font rather than overflowing into
the next cluster. This keeps the layout from ever overlapping itself,
regardless of whether the window ends up at 640px or 4K wide.

### Contrast

Solid-color button fills (the red recording indicator, the blue accent, the
green save/confirm color) read at roughly 2–2.4:1 contrast against white
text — well under the 4.5:1 minimum for body text. Any button with a
colored fill uses dark text instead (`DARK_ON_LIGHT` in `app/ui.py`), which
clears 6.7:1 or better against all three.

### Motion

Style-switch flashes, the recording-button pulse, and the screenshot flash
are all short (150–250ms) and serve a specific purpose: making a state
change impossible to miss at a glance, which matters when this is running on
a screen the user might be reading from across a room. Since this is a
native pygame app with no OS-level `prefers-reduced-motion` hook to read,
`config.yaml`'s `reduce_motion` flag is the explicit substitute — when set,
every flash and pulse is replaced with an instant or static equivalent (a
plain "Saved" toast instead of a flash, a solid color instead of a pulsing
one) rather than simply being switched off with nothing in its place.

## Project layout

```
main.py                         entry point: screen state machine, AppState, CLI flags
config.yaml                     camera, resolution, window, and behavior settings
app/
  capture.py                    threaded webcam capture -> LatestSlot
  pipeline.py                   LatestSlot, FPS counters, inference worker, warm-up
  dialogs.py                    shared native file-picker (tkinter)
  ui.py                         Live screen: rendering, HUD, input
  ui_home.py                    Home screen: mode picker
  ui_snapshot.py                Create from Photo screen
  recorder.py                   screenshot (PNG) + recording (mp4)
  benchmark.py                  resolution/device FPS sweep -> CSV
  processors/
    base.py                     the Processor interface every style implements
    registry.py                 style id -> Processor, conditional on weights present
    cv_filters.py                sketch / pixel / cartoon / oil painting / crayon / watercolor / charcoal
    neural_fast.py                TransformerNet wrapper (Candy/Mosaic/Rain Princess/Udnie)
    neural_adain.py               AdaIN wrapper, with style-feature caching
  models/
    transformer_net.py            fast-neural-style architecture
    adain.py                      VGG encoder + decoder + the AdaIN op itself
scripts/
  download_weights.py             fetches and caches pretrained weights
weights/  styles/  outputs/       gitignored: downloaded weights, style images, generated output
```

## Configuration (`config.yaml`)

| Key | Meaning |
|---|---|
| `camera_index` | Which camera to open at startup (`0` is usually the built-in camera). |
| `display_width`, `display_height` | Resolution the camera is opened at. |
| `default_style` | Registry id selected when the Live screen first opens. |
| `resolutions` | The inference-resolution options `[` / `]` cycle through. |
| `default_resolution` | Which of `resolutions` is active at startup. |
| `window_width`, `window_height` | Window size when not fullscreen. |
| `start_fullscreen` | Open in fullscreen immediately; `F` toggles at any time. |
| `reduce_motion` | Replace flashes/pulses with instant/static equivalents. |
| `use_half` | Try float16 on MPS for the neural nets (falls back to fp32 automatically if unsupported). |
| `benchmark_frames` | Frames timed per resolution/style in `--benchmark` mode. |
| `weights_dir`, `styles_dir`, `outputs_dir` | Paths for weights, AdaIN style images, and generated output. |

## Weights

`scripts/download_weights.py` fetches:
- **fast-neural-style** (`candy`, `mosaic`, `rain_princess`, `udnie`) from the
  pytorch/examples saved-models bundle.
- **AdaIN** (`vgg_normalised.pth`, `decoder.pth`) — these are best-effort
  direct downloads; if they fail, grab them manually from the
  naoto0804/pytorch-AdaIN project and place them in `weights/`. The app
  still runs fully without them (CV filters and any fast styles that did
  download still work).

For AdaIN "Van Gogh mode," drop a `starry_night.jpg` (or any style image)
into `styles/`; the app loads the first preset on startup and `P` cycles
through whatever's in that folder.

## Requirements

PyTorch + torchvision (MPS build on Apple Silicon), OpenCV, pygame, NumPy,
Pillow, PyYAML, imageio + imageio-ffmpeg (mp4 recording fallback). See
`requirements.txt`.
