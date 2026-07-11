"""Per-motor and global application state, plus position tracking.

Steppers have no position feedback, so we track position by counting every
step we command, assuming each motor starts at 0° (home). `current_step` is
integrated smoothly for a live display; step *commands* always use rounded
integers so we never drift off the step grid.
"""

from config import (
    DEG_PER_STEP,
    STEPS_PER_REV,
    DEFAULT_SPEED,
    MIN_SPEED,
    MAX_SPEED,
    NUM_MOTORS,
)


def _sign(n):
    return 1 if n > 0 else (-1 if n < 0 else 0)


class MotorState:
    """Tracked state for a single 28BYJ-48 motor."""

    def __init__(self, index, color):
        self.index = index
        self.color = color
        self.current_step = 0.0     # absolute step count from home (0), float for smooth anim
        self.target_step = 0        # where we're heading (angle/steps mode)
        self.speed = DEFAULT_SPEED  # steps/sec (speed mode + move rate)
        self.direction = +1         # +1 / -1 (speed mode)
        self.mode = "angle"         # "angle" | "speed" | "steps"
        self.running = False        # speed mode continuous run flag
        self.moving = False         # currently executing a move (angle/steps)
        self.home_flash = 0.0       # seconds remaining on the "homed" confirm flash

    # ── readouts ──────────────────────────────────────────────────────────
    def current_angle(self):
        return (self.current_step * DEG_PER_STEP) % 360.0

    def state_word(self):
        if self.running:
            return "running"
        if self.moving:
            return "moving"
        return "idle"

    def is_active(self):
        return self.running or self.moving

    # ── commands (return the signed step delta to send to the controller) ──
    def set_target_angle(self, deg):
        """Set a shortest-path absolute-angle target. Returns signed step delta."""
        deg = max(0.0, min(360.0, float(deg)))
        target_mod = round(deg / 360.0 * STEPS_PER_REV) % STEPS_PER_REV
        current = round(self.current_step)
        current_mod = current % STEPS_PER_REV
        diff = target_mod - current_mod
        half = STEPS_PER_REV // 2
        if diff > half:
            diff -= STEPS_PER_REV
        elif diff < -half:
            diff += STEPS_PER_REV
        self.target_step = current + diff
        self.moving = diff != 0
        self.running = False
        return diff

    def jog(self, steps):
        """Queue a relative move of `steps` (signed). Returns signed step delta."""
        steps = int(steps)
        self.target_step = round(self.current_step) + steps
        self.moving = steps != 0
        self.running = False
        return steps

    def home(self):
        """Define the current position as 0°. Does NOT physically move the motor."""
        self.current_step = 0.0
        self.target_step = 0
        self.moving = False
        self.running = False
        self.home_flash = 0.6

    def stop(self):
        self.running = False
        self.moving = False
        self.target_step = round(self.current_step)

    def set_speed(self, speed):
        self.speed = int(max(MIN_SPEED, min(MAX_SPEED, speed)))

    # ── per-frame integration (for the live angle readout / dial) ──────────
    def update(self, dt):
        if self.home_flash > 0.0:
            self.home_flash = max(0.0, self.home_flash - dt)

        if self.running:
            self.current_step += self.direction * self.speed * dt
        elif self.moving:
            remaining = self.target_step - self.current_step
            if remaining == 0:
                return
            move = self.speed * dt
            if move >= abs(remaining):
                self.current_step = float(self.target_step)
            else:
                self.current_step += _sign(remaining) * move


class AppState:
    """Global app state + command orchestration (single motor and sync-all)."""

    def __init__(self, motors, controller):
        self.motors = motors                # list[MotorState], length NUM_MOTORS
        self.controller = controller        # SerialController
        self.sync_enabled = False           # when true, the sync panel drives all motors
        self.focused = 0                    # index of the card being interacted with
        self.stop_flash = 0.0               # seconds left on the STOP-ALL alarm flash

    # ── single-motor commands ─────────────────────────────────────────────
    def move_to_angle(self, m, deg):
        motor = self.motors[m]
        diff = motor.set_target_angle(deg)
        if diff != 0:
            self.controller.move(m, abs(diff), _sign(diff), motor.speed)

    def jog(self, m, steps):
        motor = self.motors[m]
        diff = motor.jog(steps)
        if diff != 0:
            self.controller.move(m, abs(diff), _sign(diff), motor.speed)

    def run(self, m):
        motor = self.motors[m]
        motor.running = True
        motor.moving = False
        self.controller.run(m, motor.direction, motor.speed)

    def stop(self, m):
        self.motors[m].stop()
        self.controller.stop(m)

    def home(self, m):
        self.motors[m].home()

    # ── all-motor commands ─────────────────────────────────────────────────
    def move_all_to_angle(self, deg):
        for m in range(len(self.motors)):
            self.move_to_angle(m, deg)

    def jog_all(self, steps):
        for m in range(len(self.motors)):
            self.jog(m, steps)

    def run_all(self, direction, speed):
        for motor in self.motors:
            motor.direction = direction
            motor.set_speed(speed)
        for m in range(len(self.motors)):
            self.run(m)

    def stop_all(self):
        for motor in self.motors:
            motor.stop()
        self.controller.stop_all()
        self.stop_flash = 0.45

    def home_all(self):
        for motor in self.motors:
            motor.home()

    # ── frame updates ──────────────────────────────────────────────────────
    def update(self, dt):
        if self.stop_flash > 0.0:
            self.stop_flash = max(0.0, self.stop_flash - dt)
        for motor in self.motors:
            motor.update(dt)

    def on_move_done(self, m):
        """Called when the controller reports a move completed."""
        if 0 <= m < len(self.motors):
            self.motors[m].moving = False


def build_app_state(controller, motor_colors):
    motors = [MotorState(i, motor_colors[i]) for i in range(NUM_MOTORS)]
    return AppState(motors=motors, controller=controller)
