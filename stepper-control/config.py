"""All constants for the Stepper Control Panel: pins, motor math, limits, serial, UI."""

# ─── HARDWARE ────────────────────────────────────────────────────────────────
NUM_MOTORS = 5

# Each 28BYJ-48 via ULN2003 needs 4 pins (IN1..IN4). Rows = motors.
# M3/M4/M5 are wired to the low pins (2..13), matching the physical build.
MOTOR_PINS = [
    [22, 23, 24, 25],   # M1
    [26, 27, 28, 29],   # M2
    [ 2,  3,  4,  5],   # M3
    [ 6,  7,  8,  9],   # M4
    [10, 11, 12, 13],   # M5
]

# ─── MOTOR MATH ──────────────────────────────────────────────────────────────
STEPS_PER_REV = 4096            # half-step full revolution of the output shaft
DEG_PER_STEP = 360.0 / STEPS_PER_REV

# Speed limits (steps/second). 28BYJ-48 is geared/slow — keep modest.
MIN_SPEED = 1
MAX_SPEED = 600                 # steps/sec; tune down if motors stall
DEFAULT_SPEED = 200

# Jog presets for Steps mode (buttons)
JOG_PRESETS = [1, 10, 50, 100, 512]   # 512 half-steps = 45°

# ─── SERIAL ──────────────────────────────────────────────────────────────────
SERIAL_PORT = None              # None = auto-detect
SERIAL_BAUD = 115200
SERIAL_AUTODETECT_PATTERNS = ["usbmodem", "usbserial", "ttyACM", "ttyUSB"]

# ─── UI ──────────────────────────────────────────────────────────────────────
WINDOW_W = 1200                 # windowed-mode size; fullscreen overrides at launch
WINDOW_H = 820
FULLSCREEN = True               # start fullscreen; F toggles at runtime
FPS = 60
WINDOW_TITLE = "Stepper Control Panel"
U = 8                           # base spacing unit
