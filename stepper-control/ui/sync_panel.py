"""ALL MOTORS panel: a Sync-mode toggle plus a combined control block that
mirrors the single-motor modes but applies to all five motors at once, and
the Home all / Stop all buttons.

Sync controls use a neutral accent (not a per-motor saturated color) because the
command targets every motor, not one."""

import pygame

from config import U, MIN_SPEED, MAX_SPEED, JOG_PRESETS
from ui import theme
from ui.theme import (
    CARD, BORDER, BORDER_MUTE, PANEL, TEXT_PRI, TEXT_SEC, TEXT_MUTE,
    SIZE_TINY, SIZE_H, SIZE_BODY, SIZE_SMALL, SIZE_MONO,
    RADIUS_CARD, BORDER_W_DEFAULT,
)
from ui.widgets import Button, Segmented, Slider, Toggle, TextInput

PAD = 2 * U
SYNC_ACCENT = (150, 152, 180)      # neutral — sync targets all motors
MODES = ["Angle", "Speed", "Steps"]


class SyncPanel:
    def __init__(self, rect, app_state):
        self.rect = pygame.Rect(rect)
        self.app = app_state
        self.mode = "angle"
        self.sync_speed = MIN_SPEED + (MAX_SPEED - MIN_SPEED) // 4
        self.sync_dir = 1
        self.running = False

        x = self.rect.x
        w = self.rect.width
        y = self.rect.y + 24

        # Sync-mode toggle row.
        self.toggle = Toggle((x + w - 44, y, 44, 24), self.app.sync_enabled,
                             self._on_toggle, SYNC_ACCENT)
        self.toggle_y = y

        # Mode switch (only interactive while sync is on).
        self.switch_y = y + 24 + PAD
        self.mode_switch = Segmented(
            (x, self.switch_y, w, 28), MODES, 0, self._on_mode, SYNC_ACCENT,
            enabled=self.app.sync_enabled,
        )

        self.body_top = self.switch_y + 28 + PAD

        # Home all / Stop all pinned near the bottom.
        btn_h = 34
        self.stop_all_btn = Button(
            (x, self.rect.bottom - btn_h, w, btn_h), "Stop all",
            self.app.stop_all, variant="danger", bold=True, size=SIZE_BODY)
        self.home_all_btn = Button(
            (x, self.rect.bottom - 2 * btn_h - U, w, btn_h), "Home all",
            self._home_all, variant="ghost", size=SIZE_SMALL)
        self.body_bottom = self.home_all_btn.rect.top - PAD

        self.body_widgets = []
        self._build_body()

    # ── callbacks ─────────────────────────────────────────────────────────
    def _on_toggle(self, value):
        self.app.sync_enabled = value
        self.mode_switch.enabled = value
        self._build_body()

    def _on_mode(self, index):
        self.mode = ["angle", "speed", "steps"][index]
        self._build_body()

    def _home_all(self):
        self.app.home_all()

    def _body_rect(self):
        return pygame.Rect(self.rect.x, self.body_top, self.rect.width,
                           self.body_bottom - self.body_top)

    # ── body ───────────────────────────────────────────────────────────────
    def _build_body(self):
        self.body_widgets = []
        self._slider = None
        self._run_btn = None
        self._dir_switch = None
        if not self.app.sync_enabled:
            return
        body = self._body_rect()
        if self.mode == "angle":
            self._build_angle(body)
        elif self.mode == "speed":
            self._build_speed(body)
        else:
            self._build_steps(body)

    def _build_angle(self, body):
        self._slider = Slider((body.x, body.top + 34, body.width, 10),
                              0, 360, 0, self._on_angle_slide, SYNC_ACCENT)
        entry_w = 88
        self._entry = TextInput(
            (body.x, body.top + 34 + 28, entry_w, 30),
            self._submit_angle, SYNC_ACCENT, placeholder="angle°", size=SIZE_MONO)
        self._go = Button((body.x + entry_w + U, body.top + 34 + 28,
                           body.width - entry_w - U, 30), "Move all",
                          self._go_angle, variant="accent", accent=SYNC_ACCENT,
                          size=SIZE_SMALL)
        self.body_widgets = [self._slider, self._entry, self._go]

    def _on_angle_slide(self, value):
        self._angle_value = value

    def _submit_angle(self, text):
        self._go_angle()

    def _go_angle(self):
        deg = None
        if getattr(self, "_entry", None) and self._entry.text:
            try:
                deg = float(self._entry.text)
            except ValueError:
                deg = None
        if deg is None and self._slider is not None:
            deg = self._slider.value
        if deg is not None:
            self.app.move_all_to_angle(max(0.0, min(360.0, deg)))

    def _build_speed(self, body):
        self._slider = Slider((body.x, body.top + 34, body.width, 10),
                              MIN_SPEED, MAX_SPEED, self.sync_speed,
                              self._on_speed, SYNC_ACCENT)
        self._dir_switch = Segmented(
            (body.x, body.top + 34 + 30, body.width, 30),
            ["CW", "CCW"], 0 if self.sync_dir > 0 else 1, self._on_dir, SYNC_ACCENT)
        run_h = 40
        self._run_btn = Button(
            (body.x, body.top + 34 + 30 + 30 + U, body.width, run_h),
            "Stop" if self.running else "Run", self._on_run,
            variant="accent", accent=SYNC_ACCENT, bold=True, active=self.running)
        self.body_widgets = [self._slider, self._dir_switch, self._run_btn]

    def _on_speed(self, value):
        self.sync_speed = value

    def _on_dir(self, index):
        self.sync_dir = 1 if index == 0 else -1
        if self.running:
            self.app.run_all(self.sync_dir, self.sync_speed)

    def _on_run(self):
        self.running = not self.running
        if self.running:
            self.app.run_all(self.sync_dir, self.sync_speed)
        else:
            self.app.stop_all()

    def _build_steps(self, body):
        presets = JOG_PRESETS
        n = len(presets)
        gap = U // 2
        bw = (body.width - (n - 1) * gap) // n
        bh = 30
        neg_y = body.top + 4
        pos_y = neg_y + bh + gap
        btns = []
        for i, p in enumerate(reversed(presets)):
            x = body.x + i * (bw + gap)
            btns.append(Button((x, neg_y, bw, bh), f"−{p}",
                               (lambda s=-p: self.app.jog_all(s)),
                               variant="ghost", size=SIZE_SMALL))
        for i, p in enumerate(presets):
            x = body.x + i * (bw + gap)
            btns.append(Button((x, pos_y, bw, bh), f"+{p}",
                               (lambda s=p: self.app.jog_all(s)),
                               variant="ghost", size=SIZE_SMALL))
        self.body_widgets = btns

    # ── events ───────────────────────────────────────────────────────────
    def handle_event(self, event):
        consumed = self.toggle.handle_event(event)
        if self.mode_switch.handle_event(event):
            consumed = True
        for w in self.body_widgets:
            if w.handle_event(event):
                consumed = True
        if self.home_all_btn.handle_event(event):
            consumed = True
        if self.stop_all_btn.handle_event(event):
            consumed = True
        return consumed

    def _sync_run_state(self):
        """Keep the Run/Stop label in step with reality (e.g. after Stop all)."""
        any_running = any(m.running for m in self.app.motors)
        if self.running != any_running:
            self.running = any_running
            if self.mode == "speed" and self._run_btn is not None:
                self._run_btn.label = "Stop" if self.running else "Run"
                self._run_btn.active = self.running

    # ── draw ─────────────────────────────────────────────────────────────
    def draw(self, surface):
        self._sync_run_state()
        x = self.rect.x
        theme.draw_text(surface, "ALL MOTORS", (x, self.rect.y), SIZE_TINY,
                        TEXT_SEC, tracking=2, upper=True)

        # Sync toggle row.
        theme.draw_text(surface, "Sync mode", (x, self.toggle_y + 4),
                        SIZE_BODY, TEXT_PRI)
        self.toggle.draw(surface)

        self.mode_switch.draw(surface)
        if not self.app.sync_enabled:
            theme.draw_text(surface, "Turn on to drive all motors together",
                            (x, self.body_top + 4), SIZE_SMALL, TEXT_MUTE)
        else:
            for w in self.body_widgets:
                w.draw(surface)
            if self.mode == "speed" and self._slider is not None:
                theme.draw_text(surface, f"{self.sync_speed} steps/s",
                                (self._slider.rect.x, self._slider.rect.y - 22),
                                SIZE_MONO, TEXT_PRI, mono=True)
            if self.mode == "angle" and self._slider is not None:
                theme.draw_text(surface, f"{self._slider.value:.0f}°",
                                (self._slider.rect.x, self._slider.rect.y - 22),
                                SIZE_MONO, TEXT_PRI, mono=True)

        self.home_all_btn.draw(surface)
        self.stop_all_btn.draw(surface)
