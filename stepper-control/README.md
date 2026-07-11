# Stepper Control Panel

A desktop GUI that lets you drive **five 28BYJ-48 stepper motors** directly —
by absolute angle, by continuous speed, or by discrete step jogs — with no
coding required. Each motor is driven by a ULN2003 board wired to an Arduino
Mega 2560; a Python/pygame control panel handles everything from the laptop.

The app runs in **mock mode** with no hardware attached, so the full GUI can be
built, demoed, and tested on a laptop alone. Plug in the Arduino and it
auto-detects the serial port and drives the real motors.

## Control modes

Each of the five motors has three independent modes:

- **Angle** — rotate to a specific absolute position, 0–360°, via a draggable
  dial or a typed value. The app computes the shortest path in steps.
- **Speed** — spin continuously at an adjustable rate (steps/sec) and direction
  (CW/CCW); run/stop.
- **Steps** — jog a set number of steps forward or backward (e.g. +10, −50)
  using presets or a custom count.

Because steppers have no position feedback, the software tracks position by
counting every step it commands, assuming each motor starts at 0° (home). A
per-motor **Home** button re-zeros the counter without moving the motor. A
**Sync / All Motors** panel drives all five together.

## Quick start

```bash
pip install -r requirements.txt
python main.py
```

With no Arduino connected the top bar shows **Mock mode** and move completions
are simulated on a timer, so the UI behaves identically without hardware.

## Hardware

| Component | Part | Qty | Role |
|---|---|---|---|
| Microcontroller | Arduino Mega 2560 | 1 | Runs the step-sequencing firmware |
| Stepper motors | 28BYJ-48 (5V, unipolar, geared) | 5 | The controllable motors |
| Driver boards | ULN2003 | 5 | 4 control pins each (IN1–IN4) |
| Power | External 5V ≥1.5 A | 1 | Motor power (not the Arduino 5V pin) |
| Computer | Mac/PC | 1 | Runs the pygame GUI |

Each motor uses four Mega digital pins into a ULN2003 board (20 pins total).
The pin map lives in `config.py` (`MOTOR_PINS`). Motor power comes from a shared
external 5V rail, grounded to the Mega.

### 28BYJ-48 motor math

```
STEPS_PER_REV = 4096          # half-step mode, one full output-shaft revolution
DEG_PER_STEP  = 360 / 4096    # ≈ 0.0879° per half-step
```

To rotate to an absolute angle A°: `target_step = round(A / 360 * 4096)`, then
command `(target_step − current_step)` steps in the correct direction.

## Serial protocol (Python → Arduino)

```
A <m> <steps> <dir> <speed>   move motor m by <steps> steps (angle/steps mode)
R <m> <dir> <speed>           run motor m continuously (speed mode)
S <m>                         stop motor m
X                             stop ALL motors (emergency)
P                             ping
```

Arduino → Python: `R` ready · `A` ack · `D <m>` move done · `O` pong.

The firmware steps all five motors from a single `micros()`-based loop — no
timer ISRs — and de-energizes coils on stop/done so motors don't overheat.

## Project structure

```
stepper-control/
├── main.py                 # Entry point, main loop, layout router
├── config.py               # All constants: pins, motor math, limits, serial
├── motor/
│   └── motor_state.py       # Per-motor + global state, position tracking
├── serial_io/
│   └── controller.py        # Python ↔ Arduino serial + mock mode
├── ui/
│   ├── theme.py             # Colors, fonts, spacing (design system)
│   ├── widgets.py           # Rounded rect, text, Button, Toggle, Slider, Dial
│   ├── topbar.py            # Title, connection badge, STOP ALL
│   ├── motor_card.py        # One card per motor (3 modes inside)
│   ├── sync_panel.py        # "All motors" combined control
│   └── sidebar.py           # Live status list of all 5 motors
├── arduino/
│   └── stepper_control/
│       └── stepper_control.ino
└── requirements.txt
```

## Controls & safety

- **STOP ALL** — always visible in the top bar; also bound to `SPACE` / `Esc`.
  Immediately halts every motor, and flashes the screen edges red so the halt
  is unmissable from across a room.
- `1`–`5` — focus the corresponding motor card.
- `F` — toggle fullscreen (the app launches fullscreen; layout reflows to the
  screen size).
- **Home** (per motor) — defines the current position as 0° (does not move).

## Design

Clean dark-navy control panel. Per-motor accent colors are the only saturated
colors; everything else is neutral. No drop shadows, no gradients, no
glassmorphism, no emoji. Active controls are marked with a 2px motor-color
border (not a fill), all spacing on an 8px grid, numeric readouts tabular.

Motion is functional, not decorative: hover and press states ease over
~80ms, the segmented mode switch slides its indicator, the sync toggle's
knob glides, dials carry tick marks with a bright tip on the live-angle arc
and an eased target handle, activity dots pulse while a motor is moving, and
STOP ALL triggers a brief red edge flash. All easing is frame-rate
independent (see `theme.approach`).

## Tech stack

| Layer | Tech |
|---|---|
| Language | Python 3.11+ |
| UI | pygame |
| Serial | pyserial |
| Firmware | Arduino C++ (manual half-step sequencing, no stepper libraries) |
