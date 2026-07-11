"""Home screen - choose Live Style Transfer or Create from Photo.

Art-studio personality: drifting color blobs in the background, a rainbow
paint-stripe under the title, cards that lift and glow as you hover, and a
gently bobbing palette glyph. All motion is cheap pre-rendered blits and is
disabled when reduce_motion is set.
"""

import math
import time

import pygame

from app.ui import (BG, BAR_BG, BORDER, TEXT, TEXT_DIM, ACCENT, GOOD, WARN,
                    PALETTE, bgr_to_surface, update_cursor, _ease_out_cubic)

CARD_W, CARD_H = 420, 320
CARD_GAP = 40
FADE_IN_S = 0.35


def _make_blob(color, radius):
    """Pre-render one soft glowing blob (fake radial gradient)."""
    surf = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
    steps = 20
    for i in range(steps, 0, -1):
        r = int(radius * i / steps)
        pygame.draw.circle(surf, (*color, 4), (radius, radius), r)
    return surf


class HomeScreen:
    def __init__(self, screen, capture, raw_slot, device_name, num_styles,
                 reduce_motion=False):
        self.screen = screen
        self.capture = capture
        self.raw_slot = raw_slot
        self.device_name = device_name
        self.num_styles = num_styles
        self.reduce_motion = reduce_motion
        self.selected = 0
        self._card_rects = []
        self._sel_t = [1.0, 0.0]      # eased selection progress per card
        self._t0 = time.time()
        self._last_t = self._t0

        self.fonts = {
            "title": pygame.font.SysFont("helveticaneue,arial", 46, bold=True),
            "subtitle": pygame.font.SysFont("helveticaneue,arial", 17),
            "card_title": pygame.font.SysFont("helveticaneue,arial", 25, bold=True),
            "card_body": pygame.font.SysFont("helveticaneue,arial", 15),
            "small": pygame.font.SysFont("helveticaneue,arial", 13),
            "mono": pygame.font.SysFont("menlo,monaco,monospace", 14, bold=True),
        }

        h = max(1, screen.get_height())
        blob_r = max(180, int(h * 0.32))
        self._blobs = [
            (_make_blob(PALETTE[0], blob_r), 0.16, 0.20, 0.11, 0.0),
            (_make_blob(PALETTE[3], blob_r), 0.84, 0.24, 0.09, 2.1),
            (_make_blob(PALETTE[4], int(blob_r * 0.8)), 0.30, 0.85, 0.13, 4.2),
            (_make_blob(PALETTE[2], int(blob_r * 0.7)), 0.74, 0.80, 0.10, 1.3),
        ]

    def run(self):
        """Blocking loop until a mode is chosen. Returns 'live', 'snapshot', or 'quit'."""
        clock = pygame.time.Clock()
        self._t0 = time.time()
        while True:
            for event in pygame.event.get():
                action = self._handle_event(event)
                if action:
                    return action
            self.draw()
            pygame.display.flip()
            clock.tick(60)

    def _handle_event(self, event):
        if event.type == pygame.QUIT:
            return "quit"
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return "quit"
            if event.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_TAB):
                self.selected = 1 - self.selected
            elif event.key == pygame.K_1:
                return "live"
            elif event.key == pygame.K_2:
                return "snapshot"
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                return "live" if self.selected == 0 else "snapshot"
        elif event.type == pygame.MOUSEMOTION:
            for i, (rect, _action) in enumerate(self._card_rects):
                if rect.collidepoint(event.pos):
                    self.selected = i
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for rect, action in self._card_rects:
                if rect.collidepoint(event.pos):
                    return action
        return None

    def draw(self):
        now = time.time()
        dt = min(0.1, now - self._last_t)
        self._last_t = now

        self.screen.fill(BG)
        w, h = self.screen.get_size()

        self._draw_blobs(now, w, h)

        # Ease selection progress toward the selected card.
        for i in range(2):
            target = 1.0 if i == self.selected else 0.0
            if self.reduce_motion:
                self._sel_t[i] = target
            else:
                self._sel_t[i] += (target - self._sel_t[i]) * min(1.0, 12.0 * dt)

        title = self.fonts["title"].render("Camera Canvas", True, TEXT)
        ty = int(h * 0.10)
        self.screen.blit(title, (w // 2 - title.get_width() // 2, ty))
        self._draw_paint_stripe(w // 2, ty + title.get_height() + 10, now)

        sub = self.fonts["subtitle"].render(
            f"Live webcam styling, {self.num_styles} styles, motion paint trails, "
            "and still-image art generation", True, TEXT_DIM)
        self.screen.blit(sub, (w // 2 - sub.get_width() // 2,
                               ty + title.get_height() + 30))

        total_w = CARD_W * 2 + CARD_GAP
        x0 = w // 2 - total_w // 2
        y0 = int(h * 0.28)
        self._card_rects = []
        self._draw_live_card(pygame.Rect(x0, y0, CARD_W, CARD_H), 0, now)
        self._draw_snapshot_card(pygame.Rect(x0 + CARD_W + CARD_GAP, y0, CARD_W, CARD_H),
                                 1, now)

        status = f"Device: {self.device_name.upper()}   ·   "
        status += "Camera connected" if self.capture.connected else (self.capture.error or "Camera not found")
        col = GOOD if self.capture.connected else WARN
        txt = self.fonts["small"].render(status, True, col)
        self.screen.blit(txt, (w // 2 - txt.get_width() // 2, h - 52))
        hint = self.fonts["small"].render(
            "Left/Right select  ·  Enter choose  ·  1 / 2 jump  ·  Esc quit", True, TEXT_DIM)
        self.screen.blit(hint, (w // 2 - hint.get_width() // 2, h - 30))

        self._draw_fade_in(now, w, h)
        update_cursor((r for r, _action in self._card_rects), pygame.mouse.get_pos())

    def _draw_blobs(self, now, w, h):
        t = 0.0 if self.reduce_motion else now
        for surf, fx, fy, speed, phase in self._blobs:
            x = fx * w + math.sin(t * speed + phase) * w * 0.04
            y = fy * h + math.cos(t * speed * 1.3 + phase) * h * 0.05
            self.screen.blit(surf, (int(x - surf.get_width() / 2),
                                    int(y - surf.get_height() / 2)))

    def _draw_paint_stripe(self, cx, y, now):
        """A little rainbow paint stripe under the title, gently waving."""
        seg_w, seg_h, gap = 46, 6, 6
        total = len(PALETTE) * seg_w + (len(PALETTE) - 1) * gap
        x = cx - total // 2
        for i, col in enumerate(PALETTE):
            dy = 0 if self.reduce_motion else int(math.sin(now * 2.2 + i * 0.9) * 2)
            pygame.draw.rect(self.screen, col, (x, y + dy, seg_w, seg_h),
                             border_radius=3)
            x += seg_w + gap

    def _draw_fade_in(self, now, w, h):
        if self.reduce_motion:
            return
        elapsed = now - self._t0
        if elapsed >= FADE_IN_S:
            return
        alpha = int(255 * (1 - _ease_out_cubic(elapsed / FADE_IN_S)))
        if alpha <= 0:
            return
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((*BG, alpha))
        self.screen.blit(overlay, (0, 0))

    def _card_base(self, rect, idx, accent):
        """Card background with eased hover lift + glow. Returns the drawn rect."""
        t = self._sel_t[idx]
        grow = int(8 * t)
        lift = int(6 * t)
        r = rect.inflate(grow, grow).move(0, -lift)

        if t > 0.05:
            glow = pygame.Surface((r.w + 24, r.h + 24), pygame.SRCALPHA)
            pygame.draw.rect(glow, (*accent, int(34 * t)), glow.get_rect(),
                             border_radius=22)
            self.screen.blit(glow, (r.x - 12, r.y - 12))

        bg = tuple(int(a + (b - a) * t) for a, b in zip((34, 26, 43), (44, 33, 56)))
        pygame.draw.rect(self.screen, bg, r, border_radius=16)
        border = tuple(int(a + (b - a) * t) for a, b in zip(BORDER, accent))
        pygame.draw.rect(self.screen, border, r, width=1 + int(round(t)),
                         border_radius=16)
        return r

    def _draw_live_card(self, rect, idx, now):
        accent = PALETTE[3]
        r = self._card_base(rect, idx, accent)
        pad = 24
        self.screen.blit(self.fonts["card_title"].render("Live Style Transfer", True, TEXT),
                         (r.x + pad, r.y + pad))
        self.screen.blit(self.fonts["card_body"].render(
            "Real-time webcam styling with motion paint trails.", True, TEXT_DIM),
            (r.x + pad, r.y + pad + 38))
        self.screen.blit(self.fonts["card_body"].render(
            "Cycle styles, wave to paint, record or screenshot.", True, TEXT_DIM),
            (r.x + pad, r.y + pad + 58))

        preview = pygame.Rect(r.x + pad, r.y + pad + 88,
                              r.w - pad * 2, r.h - pad * 2 - 88 - 28)
        frame = self.raw_slot.get()
        if self.capture.connected and frame is not None:
            self._blit_fit(frame, preview)
        else:
            pygame.draw.rect(self.screen, (22, 16, 28), preview, border_radius=8)
            msg = self.fonts["small"].render(
                self.capture.error or "Waiting for camera...", True, TEXT_DIM)
            self.screen.blit(msg, (preview.centerx - msg.get_width() // 2,
                                   preview.centery - msg.get_height() // 2))
        pygame.draw.rect(self.screen, BORDER, preview, 1, border_radius=8)

        key = self.fonts["mono"].render("1", True, accent)
        self.screen.blit(key, (r.right - pad - key.get_width(), r.y + pad))
        self._card_rects.append((r, "live"))

    def _draw_snapshot_card(self, rect, idx, now):
        accent = PALETTE[2]
        r = self._card_base(rect, idx, accent)
        pad = 24
        self.screen.blit(self.fonts["card_title"].render("Create from Photo", True, TEXT),
                         (r.x + pad, r.y + pad))
        self.screen.blit(self.fonts["card_body"].render(
            "Capture a still frame or upload an image, pick", True, TEXT_DIM),
            (r.x + pad, r.y + pad + 38))
        self.screen.blit(self.fonts["card_body"].render(
            "a style, and generate full-quality art to save.", True, TEXT_DIM),
            (r.x + pad, r.y + pad + 58))

        icon_rect = pygame.Rect(r.x + pad, r.y + pad + 88,
                                r.w - pad * 2, r.h - pad * 2 - 88 - 28)
        pygame.draw.rect(self.screen, (22, 16, 28), icon_rect, border_radius=8)
        pygame.draw.rect(self.screen, BORDER, icon_rect, 1, border_radius=8)
        self._draw_palette_glyph(icon_rect, now)

        key = self.fonts["mono"].render("2", True, accent)
        self.screen.blit(key, (r.right - pad - key.get_width(), r.y + pad))
        self._card_rects.append((r, "snapshot"))

    def _draw_palette_glyph(self, rect, now):
        cx, cy = rect.centerx, rect.centery
        radius = min(rect.w, rect.h) * 0.28
        t = 0.0 if self.reduce_motion else now
        for i, col in enumerate(PALETTE):
            ang = -math.pi / 2 + i * (2 * math.pi / len(PALETTE)) + t * 0.35
            bob = math.sin(t * 2.0 + i * 1.4) * 5
            x = cx + int(math.cos(ang) * radius)
            y = cy + int(math.sin(ang) * radius * 0.7 + bob)
            size = 14 + int(math.sin(t * 2.6 + i) * 2)
            pygame.draw.circle(self.screen, col, (x, y), size)

    def _blit_fit(self, frame_bgr, rect):
        surf = bgr_to_surface(frame_bgr)
        fw, fh = surf.get_size()
        scale = min(rect.w / fw, rect.h / fh)
        nw, nh = max(1, int(fw * scale)), max(1, int(fh * scale))
        surf = pygame.transform.smoothscale(surf, (nw, nh))
        self.screen.blit(surf, (rect.centerx - nw // 2, rect.centery - nh // 2))
