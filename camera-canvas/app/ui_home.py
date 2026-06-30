"""Home screen - choose Live Style Transfer or Create from Photo."""

import math

import pygame

from app.ui import (BG, BAR_BG, BORDER, TEXT, TEXT_DIM, ACCENT, GOOD, WARN,
                    bgr_to_surface, update_cursor)

CARD_W, CARD_H = 420, 320
CARD_GAP = 40


class HomeScreen:
    def __init__(self, screen, capture, raw_slot, device_name, num_styles):
        self.screen = screen
        self.capture = capture
        self.raw_slot = raw_slot
        self.device_name = device_name
        self.num_styles = num_styles
        self.selected = 0
        self._card_rects = []

        self.fonts = {
            "title": pygame.font.SysFont("helveticaneue,arial", 42, bold=True),
            "subtitle": pygame.font.SysFont("helveticaneue,arial", 17),
            "card_title": pygame.font.SysFont("helveticaneue,arial", 25, bold=True),
            "card_body": pygame.font.SysFont("helveticaneue,arial", 15),
            "small": pygame.font.SysFont("helveticaneue,arial", 13),
            "mono": pygame.font.SysFont("menlo,monaco,monospace", 14, bold=True),
        }

    def run(self):
        """Blocking loop until a mode is chosen. Returns 'live', 'snapshot', or 'quit'."""
        clock = pygame.time.Clock()
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
        self.screen.fill(BG)
        w, h = self.screen.get_size()

        title = self.fonts["title"].render("Neural Style Transfer", True, TEXT)
        self.screen.blit(title, (w // 2 - title.get_width() // 2, int(h * 0.12)))
        sub = self.fonts["subtitle"].render(
            f"Live webcam styling, {self.num_styles} styles, and still-image art generation",
            True, TEXT_DIM)
        self.screen.blit(sub, (w // 2 - sub.get_width() // 2, int(h * 0.12) + 52))

        total_w = CARD_W * 2 + CARD_GAP
        x0 = w // 2 - total_w // 2
        y0 = int(h * 0.28)
        self._card_rects = []
        self._draw_live_card(pygame.Rect(x0, y0, CARD_W, CARD_H), self.selected == 0)
        self._draw_snapshot_card(pygame.Rect(x0 + CARD_W + CARD_GAP, y0, CARD_W, CARD_H),
                                 self.selected == 1)

        status = f"Device: {self.device_name.upper()}   ·   "
        status += "Camera connected" if self.capture.connected else (self.capture.error or "Camera not found")
        col = GOOD if self.capture.connected else WARN
        txt = self.fonts["small"].render(status, True, col)
        self.screen.blit(txt, (w // 2 - txt.get_width() // 2, h - 52))
        hint = self.fonts["small"].render(
            "Left/Right select  ·  Enter choose  ·  1 / 2 jump  ·  Esc quit", True, TEXT_DIM)
        self.screen.blit(hint, (w // 2 - hint.get_width() // 2, h - 30))

        update_cursor((r for r, _action in self._card_rects), pygame.mouse.get_pos())

    def _card_base(self, rect, selected, accent):
        bg = (30, 32, 53) if selected else (22, 24, 36)
        pygame.draw.rect(self.screen, bg, rect, border_radius=16)
        pygame.draw.rect(self.screen, accent if selected else BORDER, rect,
                         width=2 if selected else 1, border_radius=16)

    def _draw_live_card(self, rect, selected):
        self._card_base(rect, selected, ACCENT)
        pad = 24
        self.screen.blit(self.fonts["card_title"].render("Live Style Transfer", True, TEXT),
                         (rect.x + pad, rect.y + pad))
        self.screen.blit(self.fonts["card_body"].render(
            "Real-time webcam styling. Cycle styles, tweak", True, TEXT_DIM),
            (rect.x + pad, rect.y + pad + 38))
        self.screen.blit(self.fonts["card_body"].render(
            "strength, watch the FPS HUD, record or screenshot.", True, TEXT_DIM),
            (rect.x + pad, rect.y + pad + 58))

        preview = pygame.Rect(rect.x + pad, rect.y + pad + 88,
                              rect.w - pad * 2, rect.h - pad * 2 - 88 - 28)
        frame = self.raw_slot.get()
        if self.capture.connected and frame is not None:
            self._blit_fit(frame, preview)
        else:
            pygame.draw.rect(self.screen, (16, 17, 26), preview, border_radius=8)
            msg = self.fonts["small"].render(
                self.capture.error or "Waiting for camera...", True, TEXT_DIM)
            self.screen.blit(msg, (preview.centerx - msg.get_width() // 2,
                                   preview.centery - msg.get_height() // 2))
        pygame.draw.rect(self.screen, BORDER, preview, 1, border_radius=8)

        key = self.fonts["mono"].render("1", True, ACCENT)
        self.screen.blit(key, (rect.right - pad - key.get_width(), rect.y + pad))
        self._card_rects.append((rect, "live"))

    def _draw_snapshot_card(self, rect, selected):
        self._card_base(rect, selected, GOOD)
        pad = 24
        self.screen.blit(self.fonts["card_title"].render("Create from Photo", True, TEXT),
                         (rect.x + pad, rect.y + pad))
        self.screen.blit(self.fonts["card_body"].render(
            "Capture a still frame or upload an image, pick", True, TEXT_DIM),
            (rect.x + pad, rect.y + pad + 38))
        self.screen.blit(self.fonts["card_body"].render(
            "a style, and generate full-quality art to save.", True, TEXT_DIM),
            (rect.x + pad, rect.y + pad + 58))

        icon_rect = pygame.Rect(rect.x + pad, rect.y + pad + 88,
                                rect.w - pad * 2, rect.h - pad * 2 - 88 - 28)
        pygame.draw.rect(self.screen, (16, 17, 26), icon_rect, border_radius=8)
        pygame.draw.rect(self.screen, BORDER, icon_rect, 1, border_radius=8)
        self._draw_palette_glyph(icon_rect)

        key = self.fonts["mono"].render("2", True, GOOD)
        self.screen.blit(key, (rect.right - pad - key.get_width(), rect.y + pad))
        self._card_rects.append((rect, "snapshot"))

    def _draw_palette_glyph(self, rect):
        colors = [(129, 140, 248), (52, 211, 153), (244, 114, 182), (251, 146, 60), (56, 189, 248)]
        cx, cy = rect.centerx, rect.centery
        r = min(rect.w, rect.h) * 0.28
        for i, col in enumerate(colors):
            ang = -math.pi / 2 + i * (2 * math.pi / len(colors))
            x = cx + int(math.cos(ang) * r)
            y = cy + int(math.sin(ang) * r * 0.7)
            pygame.draw.circle(self.screen, col, (x, y), 14)

    def _blit_fit(self, frame_bgr, rect):
        surf = bgr_to_surface(frame_bgr)
        fw, fh = surf.get_size()
        scale = min(rect.w / fw, rect.h / fh)
        nw, nh = max(1, int(fw * scale)), max(1, int(fh * scale))
        surf = pygame.transform.smoothscale(surf, (nw, nh))
        self.screen.blit(surf, (rect.centerx - nw // 2, rect.centery - nh // 2))
