"""Reusable pygame widgets: Button, Segmented, Toggle, Slider, Dial.

Every widget exposes:
    handle_event(event) -> bool   # True if the event was consumed
    draw(surface)

Widgets are neutral by default; a per-motor accent color is passed in where a
saturated color is warranted (active segment, running button, dial arc, etc.).
Active controls are marked with a 2px accent border — never a fill-only state.
"""

import math
import pygame

from ui import theme
from ui.theme import (
    CARD, CARD_HOVER, BORDER, BORDER_MUTE, PANEL,
    TEXT_PRI, TEXT_SEC, TEXT_MUTE,
    RED_BG, RED_SOFT, BG,
    RADIUS_CTRL, RADIUS_SM,
    BORDER_W_DEFAULT, BORDER_W_ACTIVE,
    SIZE_BODY, SIZE_LABEL, SIZE_SMALL, SIZE_MONO,
)


def _left_click(event):
    return event.type == pygame.MOUSEBUTTONDOWN and event.button == 1


def _left_release(event):
    return event.type == pygame.MOUSEBUTTONUP and event.button == 1


class Button:
    """A clickable button. Variants: default / danger / accent / segment / ghost."""

    def __init__(self, rect, label, on_click, *, variant="default", accent=None,
                 size=SIZE_BODY, bold=False, enabled=True, active=False):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.on_click = on_click
        self.variant = variant
        self.accent = accent
        self.size = size
        self.bold = bold
        self.enabled = enabled
        self.active = active
        self.hover = False
        self.pressed = False
        self._hover_t = 0.0        # eased 0..1 hover progress
        self._press_t = 0.0        # eased 0..1 press progress

    def handle_event(self, event):
        if not self.enabled:
            return False
        if event.type == pygame.MOUSEMOTION:
            self.hover = self.rect.collidepoint(event.pos)
        elif _left_click(event) and self.rect.collidepoint(event.pos):
            self.pressed = True
            return True
        elif _left_release(event):
            was = self.pressed
            self.pressed = False
            if was and self.rect.collidepoint(event.pos):
                if self.on_click:
                    self.on_click()
                return True
        return False

    def _colors(self, hover):
        """Return (bg, border_color, border_w, text_color) for a hover state."""
        acc = self.accent or theme.TEXT_SEC
        if not self.enabled:
            return CARD, BORDER_MUTE, BORDER_W_DEFAULT, TEXT_MUTE

        if self.variant == "danger":
            bg = theme.lerp(RED_BG, (60, 34, 34), 0.5) if hover else RED_BG
            return bg, RED_SOFT, BORDER_W_DEFAULT, RED_SOFT

        if self.variant == "accent":
            if self.active:
                # Running / on: filled accent, dark text.
                bg = theme.lerp(acc, TEXT_PRI, 0.12) if hover else acc
                return bg, acc, BORDER_W_ACTIVE, BG

            bg = CARD_HOVER if hover else CARD
            return bg, acc, BORDER_W_DEFAULT, acc

        if self.variant == "segment":
            if self.active:
                return CARD_HOVER, acc, BORDER_W_ACTIVE, acc
            bg = CARD_HOVER if hover else PANEL
            return bg, BORDER_MUTE, BORDER_W_DEFAULT, TEXT_SEC

        if self.variant == "ghost":
            bg = CARD_HOVER if hover else CARD
            return bg, BORDER_MUTE, BORDER_W_DEFAULT, TEXT_SEC

        # default
        bg = CARD_HOVER if hover else CARD
        return bg, BORDER, BORDER_W_DEFAULT, TEXT_PRI

    def draw(self, surface):
        self._hover_t = theme.approach(
            self._hover_t, 1.0 if (self.hover and self.enabled) else 0.0)
        self._press_t = theme.approach(
            self._press_t, 1.0 if self.pressed else 0.0, rate=24.0)

        bg0, border0, border_w, text0 = self._colors(False)
        bg1, border1, _, text1 = self._colors(True)
        t = self._hover_t
        bg = theme.lerp(bg0, bg1, t)
        border_color = theme.lerp(border0, border1, t)
        text_color = theme.lerp(text0, text1, t)

        rect = self.rect
        if self._press_t > 0.02:
            inset = int(round(2 * self._press_t))
            rect = self.rect.inflate(-inset, -inset)

        theme.draw_rounded_rect(surface, bg, rect, RADIUS_CTRL,
                                border=border_w, border_color=border_color)
        theme.draw_text(surface, self.label, rect.center, self.size,
                        text_color, bold=self.bold, center=True)


class Segmented:
    """A segmented control (e.g. Angle · Speed · Steps)."""

    def __init__(self, rect, options, index, on_change, accent, *, enabled=True,
                 size=SIZE_SMALL):
        self.rect = pygame.Rect(rect)
        self.options = options
        self.index = index
        self.on_change = on_change
        self.accent = accent
        self.enabled = enabled
        self.size = size
        self.hover_index = -1
        self._anim = float(index)   # eased indicator position (in segments)

    def _seg_rect(self, i):
        n = len(self.options)
        w = self.rect.width / n
        return pygame.Rect(int(self.rect.x + i * w), self.rect.y,
                           int(w) if i < n - 1 else self.rect.right - int(self.rect.x + i * w),
                           self.rect.height)

    def handle_event(self, event):
        if not self.enabled:
            return False
        if event.type == pygame.MOUSEMOTION:
            self.hover_index = -1
            for i in range(len(self.options)):
                if self._seg_rect(i).collidepoint(event.pos):
                    self.hover_index = i
        elif _left_click(event):
            for i in range(len(self.options)):
                if self._seg_rect(i).collidepoint(event.pos):
                    if i != self.index:
                        self.index = i
                        if self.on_change:
                            self.on_change(i)
                    return True
        return False

    def draw(self, surface):
        theme.draw_rounded_rect(surface, PANEL, self.rect, RADIUS_CTRL,
                                border=BORDER_W_DEFAULT, border_color=BORDER_MUTE)

        # Sliding active indicator: eased between the segment rects.
        self._anim = theme.approach(self._anim, float(self.index), rate=18.0)
        lo = max(0, min(len(self.options) - 1, int(self._anim)))
        hi = min(len(self.options) - 1, lo + 1)
        frac = self._anim - lo
        r_lo = self._seg_rect(lo).inflate(-4, -4)
        r_hi = self._seg_rect(hi).inflate(-4, -4)
        ind = pygame.Rect(
            round(theme.lerp(r_lo.x, r_hi.x, frac)),
            r_lo.y,
            round(theme.lerp(r_lo.w, r_hi.w, frac)),
            r_lo.h,
        )
        theme.draw_rounded_rect(surface, CARD_HOVER, ind, RADIUS_SM,
                                border=BORDER_W_ACTIVE, border_color=self.accent)

        for i, opt in enumerate(self.options):
            r = self._seg_rect(i).inflate(-4, -4)
            active = (i == self.index)
            if active:
                color = self.accent
            else:
                color = TEXT_SEC if self.hover_index == i else TEXT_MUTE
            theme.draw_text(surface, opt, r.center, self.size, color,
                            bold=active, center=True)


class Toggle:
    """A pill switch. value is bool; on_change(value) fires on flip."""

    KNOB = 18

    def __init__(self, rect, value, on_change, accent, *, enabled=True):
        self.rect = pygame.Rect(rect)
        self.value = value
        self.on_change = on_change
        self.accent = accent
        self.enabled = enabled
        self._t = 1.0 if value else 0.0   # eased knob position

    def handle_event(self, event):
        if not self.enabled:
            return False
        if _left_click(event) and self.rect.collidepoint(event.pos):
            self.value = not self.value
            if self.on_change:
                self.on_change(self.value)
            return True
        return False

    def draw(self, surface):
        self._t = theme.approach(self._t, 1.0 if self.value else 0.0, rate=18.0)
        track = theme.lerp(BORDER, self.accent, self._t)
        theme.draw_rounded_rect(surface, track, self.rect, self.rect.height // 2)
        r = self.KNOB
        margin = (self.rect.height - r) // 2
        cx_off = self.rect.left + margin + r // 2
        cx_on = self.rect.right - margin - r // 2
        cx = theme.lerp(cx_off, cx_on, self._t)
        cy = self.rect.centery
        pygame.draw.circle(surface, theme.TEXT_PRI, (int(cx), int(cy)), r // 2)


class Slider:
    """Horizontal slider over [min_v, max_v]. on_change(value) fires on drag."""

    def __init__(self, rect, min_v, max_v, value, on_change, accent, *, enabled=True):
        self.rect = pygame.Rect(rect)
        self.min_v = min_v
        self.max_v = max_v
        self.value = value
        self.on_change = on_change
        self.accent = accent
        self.enabled = enabled
        self.dragging = False
        self.hover = False
        self._knob_t = 0.0        # eased knob-grow on hover/drag

    def _value_to_x(self, value):
        t = (value - self.min_v) / (self.max_v - self.min_v)
        t = max(0.0, min(1.0, t))
        return self.rect.x + t * self.rect.width

    def _x_to_value(self, x):
        t = (x - self.rect.x) / self.rect.width
        t = max(0.0, min(1.0, t))
        return round(self.min_v + t * (self.max_v - self.min_v))

    def _hit(self, pos):
        # Generous vertical hit area around the track.
        return self.rect.inflate(0, 24).collidepoint(pos)

    def handle_event(self, event):
        if not self.enabled:
            return False
        if _left_click(event) and self._hit(event.pos):
            self.dragging = True
            self._set(event.pos[0])
            return True
        elif _left_release(event):
            if self.dragging:
                self.dragging = False
                return True
        elif event.type == pygame.MOUSEMOTION:
            self.hover = self._hit(event.pos)
            if self.dragging:
                self._set(event.pos[0])
                return True
        return False

    def _set(self, x):
        v = self._x_to_value(x)
        if v != self.value:
            self.value = v
        if self.on_change:
            self.on_change(self.value)

    def draw(self, surface):
        self._knob_t = theme.approach(
            self._knob_t, 1.0 if (self.hover or self.dragging) else 0.0)
        cy = self.rect.centery
        # Track.
        pygame.draw.line(surface, BORDER, (self.rect.x, cy), (self.rect.right, cy), 4)
        # Filled portion.
        hx = self._value_to_x(self.value)
        pygame.draw.line(surface, self.accent, (self.rect.x, cy), (hx, cy), 4)
        # Knob grows slightly on hover/drag.
        r = 8 + int(round(2 * self._knob_t))
        pygame.draw.circle(surface, self.accent, (int(hx), cy), r)
        pygame.draw.circle(surface, BG, (int(hx), cy), max(3, r - 4))


class Dial:
    """Circular angle dial. Shows the live current angle as an arc; a draggable
    handle sets a target angle 0–360°. on_set(deg) fires on release."""

    def __init__(self, center, radius, get_current_angle, on_set, accent, *, enabled=True):
        self.center = center
        self.radius = radius
        self.get_current_angle = get_current_angle
        self.on_set = on_set
        self.accent = accent
        self.enabled = enabled
        self.target = get_current_angle()
        self.dragging = False
        self._draw_target = self.target   # eased handle position

    def _angle_from_pos(self, pos):
        dx = pos[0] - self.center[0]
        dy = pos[1] - self.center[1]
        deg = math.degrees(math.atan2(dy, dx)) + 90
        return deg % 360

    def _near_ring(self, pos):
        dx = pos[0] - self.center[0]
        dy = pos[1] - self.center[1]
        d = math.hypot(dx, dy)
        return abs(d - self.radius) <= 26 or d <= self.radius

    def sync_target(self):
        """Snap the handle to the live angle when not dragging (e.g. after Home)."""
        if not self.dragging:
            self.target = self.get_current_angle()

    def handle_event(self, event):
        if not self.enabled:
            return False
        if _left_click(event) and self._near_ring(event.pos):
            self.dragging = True
            self.target = self._angle_from_pos(event.pos)
            return True
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            self.target = self._angle_from_pos(event.pos)
            return True
        elif _left_release(event) and self.dragging:
            self.dragging = False
            if self.on_set:
                self.on_set(self.target)
            return True
        return False

    def draw(self, surface):
        cx, cy = self.center
        r = self.radius
        # Tick marks: minor every 30°, major every 90°.
        for deg in range(0, 360, 30):
            major = (deg % 90 == 0)
            inner = r - (12 if major else 7)
            outer = r - 2
            p1 = theme.angle_to_point((cx, cy), inner, deg)
            p2 = theme.angle_to_point((cx, cy), outer, deg)
            col = theme.lerp(BG, TEXT_MUTE, 0.9 if major else 0.5)
            pygame.draw.line(surface, col, p1, p2, 2 if major else 1)
        # Dim base ring.
        ring_col = theme.lerp(BG, self.accent, 0.22)
        pygame.draw.circle(surface, ring_col, (cx, cy), r, 6)
        # Live current-angle arc, with a bright leading tip.
        current = self.get_current_angle()
        if current > 0.5:
            theme.draw_arc_ring(surface, self.accent, (cx, cy), r, 0, current, 6)
            tip = theme.angle_to_point((cx, cy), r, current)
            tip_col = theme.lerp(self.accent, TEXT_PRI, 0.55)
            pygame.draw.circle(surface, tip_col, (int(tip[0]), int(tip[1])), 5)
        # Target handle eases toward its set position (snaps while dragging).
        if self.dragging:
            self._draw_target = self.target
        else:
            # Ease along the shortest arc so 350°→10° doesn't whip all the way around.
            delta = (self.target - self._draw_target + 180.0) % 360.0 - 180.0
            self._draw_target = (self._draw_target
                                 + delta * min(1.0, 16.0 * theme._dt)) % 360.0
        hx, hy = theme.angle_to_point((cx, cy), r, self._draw_target)
        grow = 2 if self.dragging else 0
        pygame.draw.circle(surface, self.accent, (int(hx), int(hy)), 9 + grow)
        pygame.draw.circle(surface, BG, (int(hx), int(hy)), 4)
        # Center readouts (angle + target) drawn by the card; leave center clear.


class TextInput:
    """A single-line text field. Click to focus, type, Enter submits.

    `numeric` restricts input to digits, sign and decimal point. `on_submit`
    receives the raw string on Enter."""

    def __init__(self, rect, on_submit, accent, *, placeholder="", numeric=True,
                 enabled=True, size=SIZE_MONO):
        self.rect = pygame.Rect(rect)
        self.on_submit = on_submit
        self.accent = accent
        self.placeholder = placeholder
        self.numeric = numeric
        self.enabled = enabled
        self.size = size
        self.text = ""
        self.focused = False

    def _accept(self, ch):
        if not self.numeric:
            return ch.isprintable()
        if ch.isdigit():
            return True
        if ch == "-" and len(self.text) == 0:
            return True
        if ch == "." and "." not in self.text:
            return True
        return False

    def handle_event(self, event):
        if not self.enabled:
            return False
        if _left_click(event):
            self.focused = self.rect.collidepoint(event.pos)
            return self.focused
        if not self.focused:
            return False
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                if self.on_submit:
                    self.on_submit(self.text)
                self.focused = False
                return True
            if event.key == pygame.K_ESCAPE:
                self.focused = False
                return True
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
                return True
            if event.unicode and self._accept(event.unicode):
                self.text += event.unicode
                return True
            return True  # swallow other keys while focused
        return False

    def draw(self, surface):
        border_color = self.accent if self.focused else BORDER_MUTE
        border_w = BORDER_W_ACTIVE if self.focused else BORDER_W_DEFAULT
        theme.draw_rounded_rect(surface, PANEL, self.rect, RADIUS_SM,
                                border=border_w, border_color=border_color)
        show = self.text if self.text else self.placeholder
        color = TEXT_PRI if self.text else TEXT_MUTE
        h = theme.mono_font(self.size).get_height()
        theme.draw_text(surface, show, (self.rect.x + 8, self.rect.centery - h // 2),
                        self.size, color, mono=True)
        if self.focused:
            tw = theme.mono_font(self.size).size(self.text)[0]
            caret_x = self.rect.x + 8 + tw + 1
            pygame.draw.line(surface, self.accent,
                             (caret_x, self.rect.y + 6),
                             (caret_x, self.rect.bottom - 6), 1)
