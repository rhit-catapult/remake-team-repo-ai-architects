"""One card per motor. Header + mode switch (Angle · Speed · Steps) + body + footer.

The active card (the one being interacted with, or focused via number keys) gets
a 2px motor-color border. When sync mode is on, the card's controls are disabled
and dimmed but it still shows live status.
"""

import math
import time

import pygame

from config import U, MIN_SPEED, MAX_SPEED, JOG_PRESETS
from ui import theme
from ui.theme import (
    CARD, BORDER, BORDER_MUTE, TEXT_PRI, TEXT_SEC, TEXT_MUTE,
    GREEN_DOT, AMBER,
    SIZE_H, SIZE_BODY, SIZE_LABEL, SIZE_SMALL, SIZE_TINY, SIZE_MONO,
    RADIUS_CARD, BORDER_W_DEFAULT, BORDER_W_ACTIVE,
)
from ui.widgets import Button, Segmented, Slider, TextInput

PAD = 2 * U
MODES = ["Angle", "Speed", "Steps"]


class MotorCard:
    def __init__(self, rect, motor, app_state):
        self.rect = pygame.Rect(rect)
        self.motor = motor
        self.app = app_state
        self.enabled = True

        acc = motor.color
        # Mode switch.
        sw_y = self.rect.top + PAD + 22
        self.mode_switch = Segmented(
            (self.rect.x + PAD, sw_y, self.rect.width - 2 * PAD, 28),
            MODES, MODES.index(_mode_label(motor.mode)), self._on_mode, acc,
        )

        # Footer: Home + Stop buttons on the bottom row.
        btn_h = 30
        btn_y = self.rect.bottom - PAD - btn_h
        half = (self.rect.width - 2 * PAD - U) // 2
        self.home_btn = Button(
            (self.rect.x + PAD, btn_y, half, btn_h), "Home", self._on_home,
            variant="ghost", size=SIZE_SMALL,
        )
        self.stop_btn = Button(
            (self.rect.x + PAD + half + U, btn_y, half, btn_h), "Stop", self._on_stop,
            variant="ghost", size=SIZE_SMALL,
        )
        self.footer_readout_y = btn_y - 22

        self.body_top = sw_y + 28 + PAD
        self.body_bottom = self.footer_readout_y - U
        self.body_widgets = []
        self._build_body()

    # ── geometry helpers ────────────────────────────────────────────────
    def _body_rect(self):
        return pygame.Rect(self.rect.x + PAD, self.body_top,
                           self.rect.width - 2 * PAD, self.body_bottom - self.body_top)

    # ── callbacks ─────────────────────────────────────────────────────────
    def _on_mode(self, index):
        self.motor.mode = ["angle", "speed", "steps"][index]
        self.app.focused = self.motor.index
        self._build_body()

    def _on_home(self):
        self.app.focused = self.motor.index
        self.app.home(self.motor.index)
        if self._dial is not None:
            self._dial.sync_target()

    def _on_stop(self):
        self.app.focused = self.motor.index
        self.app.stop(self.motor.index)

    # ── body construction (per mode) ───────────────────────────────────────
    def _build_body(self):
        self.body_widgets = []
        self._dial = None
        self._run_btn = None
        self._dir_switch = None
        self._speed_slider = None
        acc = self.motor.color
        body = self._body_rect()

        if self.motor.mode == "angle":
            self._build_angle(body, acc)
        elif self.motor.mode == "speed":
            self._build_speed(body, acc)
        else:
            self._build_steps(body, acc)

    def _build_angle(self, body, acc):
        # Circular dial centered in the upper body; a text entry below it.
        entry_h = 28
        dial_area_h = body.height - entry_h - U
        radius = max(48, min(body.width, dial_area_h) // 2 - 6)
        cx = body.centerx
        cy = body.top + dial_area_h // 2
        # Local import to avoid a circular import at module load time.
        from ui.widgets import Dial
        self._dial = Dial((cx, cy), radius,
                          get_current_angle=self.motor.current_angle,
                          on_set=lambda deg: self.app.move_to_angle(self.motor.index, deg),
                          accent=acc)
        entry_w = 88
        self._angle_entry = TextInput(
            (body.centerx - entry_w // 2, body.bottom - entry_h, entry_w, entry_h),
            self._submit_angle, acc, placeholder="angle°", numeric=True, size=SIZE_MONO,
        )
        self.body_widgets = [self._dial, self._angle_entry]

    def _submit_angle(self, text):
        try:
            deg = float(text)
        except ValueError:
            return
        deg = max(0.0, min(360.0, deg))
        self.app.move_to_angle(self.motor.index, deg)
        if self._dial is not None:
            self._dial.target = deg

    def _build_speed(self, body, acc):
        # Speed slider + direction toggle + big Run/Stop.
        self._speed_slider = Slider(
            (body.x, body.top + 34, body.width, 10),
            MIN_SPEED, MAX_SPEED, self.motor.speed, self._on_speed, acc,
        )
        self._dir_switch = Segmented(
            (body.x, body.top + 34 + 34, body.width, 30),
            ["CW", "CCW"], 0 if self.motor.direction > 0 else 1, self._on_dir, acc,
        )
        run_h = 44
        self._run_btn = Button(
            (body.x, body.bottom - run_h, body.width, run_h),
            "Stop" if self.motor.running else "Run", self._on_run,
            variant="accent", accent=acc, bold=True, size=SIZE_BODY,
            active=self.motor.running,
        )
        self.body_widgets = [self._speed_slider, self._dir_switch, self._run_btn]

    def _on_speed(self, value):
        self.motor.set_speed(value)

    def _on_dir(self, index):
        self.motor.direction = 1 if index == 0 else -1
        if self.motor.running:               # re-issue run with the new direction
            self.app.run(self.motor.index)

    def _on_run(self):
        self.app.focused = self.motor.index
        if self.motor.running:
            self.app.stop(self.motor.index)
        else:
            self.app.run(self.motor.index)

    def _build_steps(self, body, acc):
        # Two rows of jog presets (− on top, + below) + a custom entry & Go.
        presets = JOG_PRESETS
        n = len(presets)
        gap = U // 2
        bw = (body.width - (n - 1) * gap) // n
        bh = 30
        neg_y = body.top + 4
        pos_y = neg_y + bh + gap
        self._jog_buttons = []
        for i, p in enumerate(reversed(presets)):
            x = body.x + i * (bw + gap)
            self._jog_buttons.append(Button(
                (x, neg_y, bw, bh), f"−{p}",
                (lambda s=-p: self._jog(s)), variant="ghost", size=SIZE_SMALL))
        for i, p in enumerate(presets):
            x = body.x + i * (bw + gap)
            self._jog_buttons.append(Button(
                (x, pos_y, bw, bh), f"+{p}",
                (lambda s=p: self._jog(s)), variant="ghost", size=SIZE_SMALL))

        # Custom count + Go.
        entry_y = pos_y + bh + PAD
        go_w = 56
        self._steps_entry = TextInput(
            (body.x, entry_y, body.width - go_w - U, 30),
            self._submit_steps, acc, placeholder="steps ±", numeric=True, size=SIZE_MONO,
        )
        self._go_btn = Button(
            (body.right - go_w, entry_y, go_w, 30), "Go", self._go_steps,
            variant="accent", accent=acc, size=SIZE_SMALL,
        )
        self.body_widgets = self._jog_buttons + [self._steps_entry, self._go_btn]

    def _jog(self, steps):
        self.app.focused = self.motor.index
        self.app.jog(self.motor.index, steps)

    def _submit_steps(self, text):
        self._apply_steps(text)

    def _go_steps(self):
        self._apply_steps(self._steps_entry.text)

    def _apply_steps(self, text):
        try:
            steps = int(float(text))
        except ValueError:
            return
        if steps:
            self._jog(steps)

    # ── events ───────────────────────────────────────────────────────────
    def handle_event(self, event):
        if not self.enabled:
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 \
                and self.rect.collidepoint(event.pos):
            self.app.focused = self.motor.index
        consumed = self.mode_switch.handle_event(event)
        for w in self.body_widgets:
            if w.handle_event(event):
                consumed = True
        if self.home_btn.handle_event(event):
            consumed = True
        if self.stop_btn.handle_event(event):
            consumed = True
        return consumed

    # ── draw ─────────────────────────────────────────────────────────────
    def draw(self, surface):
        acc = self.motor.color
        focused = (self.app.focused == self.motor.index) and self.enabled
        border_color = acc if focused else BORDER
        border_w = BORDER_W_ACTIVE if focused else BORDER_W_DEFAULT
        theme.draw_rounded_rect(surface, CARD, self.rect, RADIUS_CARD,
                                border=border_w, border_color=border_color)

        # Header: state dot + "M{i}" + optional synced tag.
        hx = self.rect.x + PAD
        hy = self.rect.top + PAD + 8
        if self.motor.is_active():
            # Pulse while moving/running so activity reads at a glance.
            pulse = 0.5 + 0.5 * math.sin(time.time() * 6.0)
            dot_color = theme.lerp(AMBER, TEXT_PRI, 0.35 * pulse)
            pygame.draw.circle(surface, dot_color, (hx + 4, hy),
                               4 + int(round(pulse * 1.5)))
        else:
            pygame.draw.circle(surface, GREEN_DOT, (hx + 4, hy), 4)
        theme.draw_text(surface, f"M{self.motor.index + 1}", (hx + 16, hy - 9),
                        SIZE_H, acc, bold=True)
        if not self.enabled:
            tw = _tracked_width("SYNCED", SIZE_TINY, 1)
            theme.draw_text(surface, "SYNCED", (self.rect.right - PAD - tw, hy - 5),
                            SIZE_TINY, TEXT_MUTE, tracking=1, upper=True)

        self.mode_switch.draw(surface)

        # Body.
        for w in self.body_widgets:
            w.draw(surface)

        # Angle-mode center readouts (drawn over the dial's clear center).
        if self.motor.mode == "angle" and self._dial is not None:
            c = self._dial.center
            theme.draw_text(surface, f"{self.motor.current_angle():.0f}°", c,
                            22, TEXT_PRI, bold=True, center=True, mono=True)
            theme.draw_text(surface, f"target {self._dial.target:.0f}°",
                            (c[0], c[1] + 20), SIZE_SMALL, TEXT_MUTE, center=True)

        # Speed-mode readout above the slider.
        if self.motor.mode == "speed" and self._speed_slider is not None:
            r = self._speed_slider.rect
            theme.draw_text(surface, f"{self.motor.speed} steps/s",
                            (r.x, r.y - 22), SIZE_MONO, TEXT_PRI, mono=True)

        # Footer: current angle readout + Home/Stop.
        fy = self.footer_readout_y
        label = self.motor.state_word()
        theme.draw_text(surface, f"{self.motor.current_angle():.0f}°",
                        (self.rect.x + PAD, fy), SIZE_MONO, TEXT_SEC, mono=True)
        lw = theme.font(SIZE_SMALL).size(label)[0]
        theme.draw_text(surface, label, (self.rect.right - PAD - lw, fy),
                        SIZE_SMALL, TEXT_MUTE)

        self.home_btn.draw(surface)
        self.stop_btn.draw(surface)

        # Home confirm flash: brief accent ring that fades back to the border.
        if self.motor.home_flash > 0.0:
            t = min(1.0, self.motor.home_flash / 0.6)
            flash_col = theme.lerp(border_color, acc, t)
            pygame.draw.rect(surface, flash_col, self.rect, width=2,
                             border_radius=RADIUS_CARD)


def _mode_label(mode):
    return {"angle": "Angle", "speed": "Speed", "steps": "Steps"}[mode]


def _tracked_width(text, size, tracking):
    f = theme.font(size)
    return sum(f.size(c)[0] for c in text) + tracking * max(0, len(text) - 1)
