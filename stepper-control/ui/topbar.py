"""Top bar: title, motor count, connection badge, and the always-visible STOP ALL."""

import math
import time

import pygame

from config import U, NUM_MOTORS
from ui import theme
from ui.theme import (
    BG, BORDER, TEXT_PRI, TEXT_MUTE, TEXT_SEC, GREEN_DOT, AMBER,
    SIZE_TITLE, SIZE_SMALL, SIZE_BODY,
)
from ui.widgets import Button

BAR_H = 64


def _text_left_mid(surface, text, x, cy, size, color, bold=False):
    """Draw left-aligned text, vertically centered on cy. Returns right edge x."""
    h = theme.font(size, bold).get_height()
    rect = theme.draw_text(surface, text, (x, cy - h // 2), size, color, bold=bold)
    return rect.right


class TopBar:
    def __init__(self, width, app_state, on_stop_all):
        self.width = width
        self.app = app_state
        self.rect = pygame.Rect(0, 0, width, BAR_H)

        btn_w, btn_h = 120, 36
        self.stop_btn = Button(
            (width - 3 * U - btn_w, (BAR_H - btn_h) // 2, btn_w, btn_h),
            "STOP ALL", on_stop_all, variant="danger", bold=True, size=SIZE_BODY,
        )

    def handle_event(self, event):
        return self.stop_btn.handle_event(event)

    def draw(self, surface):
        surface.fill(BG, self.rect)
        cy = BAR_H // 2

        # Left: title + motor count.
        right = _text_left_mid(surface, "Stepper Control Panel", 3 * U, cy,
                               SIZE_TITLE, TEXT_PRI, bold=True)
        _text_left_mid(surface, f"{NUM_MOTORS} motors", right + 2 * U, cy,
                       SIZE_SMALL, TEXT_MUTE)

        # Right: connection badge, left of the STOP ALL button.
        status = self.app.controller.status_text()
        status_w = theme.font(SIZE_BODY).size(status)[0]
        badge_right = self.stop_btn.rect.left - 3 * U
        text_x = badge_right - status_w
        dot_x = text_x - 2 * U
        if status.startswith("Connecting"):
            pulse = 0.5 + 0.5 * math.sin(time.time() * 5.0)
            dot_color = theme.lerp(AMBER, BG, 0.5 * (1 - pulse))
        else:
            dot_color = GREEN_DOT
        pygame.draw.circle(surface, dot_color, (dot_x, cy), 4)
        _text_left_mid(surface, status, text_x, cy, SIZE_BODY, TEXT_SEC)

        self.stop_btn.draw(surface)

        # Divider beneath.
        pygame.draw.line(surface, BORDER, (0, BAR_H), (self.width, BAR_H), 1)
