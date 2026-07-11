"""Design system: dark navy control panel. No gradients, no shadows, no emoji.

Per-motor accent colors are the only saturated colors in the UI. Everything
else is neutral. Hierarchy comes from size / weight / color, not decoration.
"""

import math
import pygame

# ─── COLORS ──────────────────────────────────────────────────────────────────
BG          = ( 19,  20,  31)   # #13141f
PANEL       = ( 14,  15,  26)   # #0e0f1a
CARD        = ( 26,  27,  46)   # #1a1b2e
CARD_HOVER  = ( 30,  32,  53)   # #1e2035
BORDER      = ( 42,  43,  61)   # #2a2b3d
BORDER_MUTE = ( 30,  31,  48)   # #1e1f30

TEXT_PRI    = (240, 240, 245)
TEXT_SEC    = (102, 104, 128)
TEXT_MUTE   = ( 68,  69,  96)
TEXT_FAINT  = ( 51,  52,  80)

# Per-motor accent colors — the only saturated colors in the UI.
MOTOR_COLORS = [
    (129, 140, 248),   # M1  indigo
    ( 52, 211, 153),   # M2  green
    (244, 114, 182),   # M3  pink
    (251, 146,  60),   # M4  orange
    ( 56, 189, 248),   # M5  sky blue
]

GREEN_DOT = ( 34, 197,  94)     # connected/mock indicator, "idle" ok state
AMBER     = (251, 191,  36)     # "moving" indicator
RED_SOFT  = (248, 113, 113)     # stop / emergency
RED_BG    = ( 42,  26,  26)

# ─── TYPE ────────────────────────────────────────────────────────────────────
FONT_NAME  = None
SIZE_TITLE = 26
SIZE_H     = 15
SIZE_BODY  = 14
SIZE_LABEL = 13
SIZE_SMALL = 12
SIZE_TINY  = 10                 # uppercase tracked section labels
SIZE_MONO  = 14                 # numeric readouts (angle, steps, speed)

# ─── GEOMETRY ────────────────────────────────────────────────────────────────
RADIUS_CARD = 12
RADIUS_CTRL = 8
RADIUS_SM   = 5

BORDER_W_DEFAULT = 1
BORDER_W_ACTIVE  = 2            # active = border 1px→2px in motor color


# ─── FONT CACHE ──────────────────────────────────────────────────────────────
_font_cache: dict = {}
_mono_cache: dict = {}


def font(size, bold=False):
    key = (size, bold)
    f = _font_cache.get(key)
    if f is None:
        f = pygame.font.SysFont(FONT_NAME, size, bold=bold)
        _font_cache[key] = f
    return f


def mono_font(size, bold=False):
    """Tabular-ish numeric font for readouts (angle / steps / speed)."""
    key = (size, bold)
    f = _mono_cache.get(key)
    if f is None:
        f = pygame.font.SysFont("menlo,consolas,dejavusansmono,monospace", size, bold=bold)
        _mono_cache[key] = f
    return f


# ─── ANIMATION CLOCK ─────────────────────────────────────────────────────────
# Widgets are drawn immediate-mode, so they read the frame delta from here
# rather than each carrying its own clock. main.py calls set_dt() once per
# frame; approach() gives frame-rate-independent easing toward a target.
_dt = 1.0 / 60.0


def set_dt(dt):
    global _dt
    _dt = max(1e-4, min(0.1, dt))


def approach(current, target, rate=14.0):
    """Ease `current` toward `target`; `rate` ~ how many times per second the
    remaining gap shrinks by ~63%. Frame-rate independent."""
    return current + (target - current) * min(1.0, rate * _dt)


# ─── HELPERS ─────────────────────────────────────────────────────────────────
def lerp(a, b, t):
    """Scalar or per-channel linear interpolation (t in 0..1)."""
    if isinstance(a, (tuple, list)):
        return tuple(int(round(av + (bv - av) * t)) for av, bv in zip(a, b))
    return a + (b - a) * t


def draw_rounded_rect(surface, color, rect, radius, border=0, border_color=None):
    rect = pygame.Rect(rect)
    if border and border_color is not None:
        # Fill first (if a fill color is given), then stroke the border.
        if color is not None:
            pygame.draw.rect(surface, color, rect, border_radius=radius)
        pygame.draw.rect(surface, border_color, rect, width=border, border_radius=radius)
    else:
        pygame.draw.rect(surface, color, rect, border_radius=radius)


def draw_text(surface, text, pos, size, color, bold=False, center=False,
              tracking=0, upper=False, mono=False):
    """Draw text and return the blitted rect. Supports letter-spacing (tracking)."""
    if upper:
        text = text.upper()
    f = (mono_font if mono else font)(size, bold)

    if tracking == 0:
        surf = f.render(text, True, color)
        rect = surf.get_rect()
        if center:
            rect.center = pos
        else:
            rect.topleft = pos
        surface.blit(surf, rect)
        return rect

    # Render character by character with extra spacing between glyphs.
    glyphs = [f.render(ch, True, color) for ch in text]
    widths = [g.get_width() for g in glyphs]
    total_w = sum(widths) + tracking * max(0, len(glyphs) - 1)
    height = f.get_height()

    if center:
        x = pos[0] - total_w // 2
        y = pos[1] - height // 2
    else:
        x, y = pos

    start_x = x
    for g, w in zip(glyphs, widths):
        surface.blit(g, (x, y))
        x += w + tracking
    return pygame.Rect(start_x, y, total_w, height)


def draw_arc_ring(surface, color, center, radius, start_deg, end_deg, width):
    """Draw a stroked arc. Angles are degrees, 0° at top, increasing clockwise."""
    cx, cy = center
    span = end_deg - start_deg
    n = max(2, int(abs(span) / 3))
    pts = []
    for i in range(n + 1):
        t = i / n
        a = math.radians((start_deg + span * t) - 90)
        pts.append((cx + radius * math.cos(a), cy + radius * math.sin(a)))
    if len(pts) >= 2:
        pygame.draw.lines(surface, color, False, pts, width)
    # Rounded caps.
    r = max(1, width // 2)
    for p in (pts[0], pts[-1]):
        pygame.draw.circle(surface, color, (int(round(p[0])), int(round(p[1]))), r)


def angle_to_point(center, radius, deg):
    """Point on a circle for a given angle (0° top, clockwise)."""
    a = math.radians(deg - 90)
    return (center[0] + radius * math.cos(a), center[1] + radius * math.sin(a))
