"""Right-side STATUS panel: one live row per motor."""

import math
import time

import pygame

from config import U
from ui import theme
from ui.theme import (
    BORDER_MUTE, TEXT_PRI, TEXT_SEC, TEXT_MUTE, GREEN_DOT, AMBER,
    SIZE_TINY, SIZE_SMALL, SIZE_MONO,
)

ROW_H = 40


class Sidebar:
    """Status list. Header height + one row per motor. Pure display, no input."""

    def __init__(self, rect, app_state):
        self.rect = pygame.Rect(rect)
        self.app = app_state

    def height(self):
        return 24 + len(self.app.motors) * ROW_H

    def draw(self, surface):
        x = self.rect.x
        theme.draw_text(surface, "STATUS", (x, self.rect.y), SIZE_TINY, TEXT_SEC,
                        tracking=2, upper=True)
        y = self.rect.y + 22
        for motor in self.app.motors:
            self._draw_row(surface, motor, x, y, self.rect.width)
            pygame.draw.line(surface, BORDER_MUTE, (x, y + ROW_H - 1),
                             (x + self.rect.width, y + ROW_H - 1), 1)
            y += ROW_H

    def _draw_row(self, surface, motor, x, y, w):
        cy = y + ROW_H // 2
        if motor.is_active():
            pulse = 0.5 + 0.5 * math.sin(time.time() * 6.0 + motor.index)
            dot_color = theme.lerp(AMBER, TEXT_PRI, 0.35 * pulse)
            pygame.draw.circle(surface, dot_color, (x + 4, cy),
                               4 + int(round(pulse)))
        else:
            pygame.draw.circle(surface, GREEN_DOT, (x + 4, cy), 4)
        theme.draw_text(surface, f"M{motor.index + 1}", (x + 16, cy - 8),
                        SIZE_SMALL, motor.color, bold=True)

        # State word, right-aligned.
        word = motor.state_word()
        ww = theme.font(SIZE_SMALL).size(word)[0]
        theme.draw_text(surface, word, (x + w - ww, cy - 8), SIZE_SMALL, TEXT_MUTE)

        # Angle readout, right-aligned before the state word.
        ang = f"{motor.current_angle():.0f}°"
        aw = theme.mono_font(SIZE_MONO).size(ang)[0]
        theme.draw_text(surface, ang, (x + w - ww - 2 * U - aw, cy - 8),
                        SIZE_MONO, TEXT_PRI, mono=True)
