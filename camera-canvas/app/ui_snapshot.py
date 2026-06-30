"""Snapshot screen - generate still-image art from a captured or uploaded photo."""

import os
import time
import math
import threading

import cv2
import pygame

from app.ui import (BG, BAR_BG, BORDER, TEXT, TEXT_DIM, ACCENT, GOOD, WARN,
                    DARK_ON_LIGHT, CATEGORY_COLOR, bgr_to_surface, update_cursor)
from app.dialogs import open_file_dialog
from app.pipeline import cap_long_edge

BAR_H = 110
HEADER_H = 64
SNAPSHOT_RES_CAP = 1024


class SnapshotScreen:
    def __init__(self, screen, registry, raw_slot, capture, recorder):
        self.screen = screen
        self.registry = registry
        self.ids = list(registry.keys())
        self.raw_slot = raw_slot
        self.capture = capture
        self.recorder = recorder

        self.style_idx = 0
        self.source_img = None
        self.result_img = None
        self.busy = False
        self.job_id = 0
        self.error = None
        self.toast_until = 0.0
        self.toast_text = ""

        self.fonts = {
            "h1": pygame.font.SysFont("helveticaneue,arial", 26, bold=True),
            "body": pygame.font.SysFont("helveticaneue,arial", 16),
            "small": pygame.font.SysFont("helveticaneue,arial", 13),
            "mono": pygame.font.SysFont("menlo,monaco,monospace", 17, bold=True),
        }
        self.want_quit = False
        self.want_back = False
        self._button_rects = {}

    def entry(self):
        return self.registry[self.ids[self.style_idx]]

    def run(self):
        """Blocking loop until back/quit. Returns 'home' or 'quit'."""
        clock = pygame.time.Clock()
        while not self.want_quit and not self.want_back:
            for event in pygame.event.get():
                self._handle_event(event)
            self.draw()
            pygame.display.flip()
            clock.tick(60)
        return "quit" if self.want_quit else "home"

    def _new_source(self, img):
        self.job_id += 1
        self.busy = False
        self.source_img = img
        self.result_img = None
        self.error = None

    def _capture_from_camera(self):
        frame = self.raw_slot.get()
        if frame is None:
            self.error = "No camera frame available yet"
            return
        self._new_source(frame.copy())

    def _load_from_file(self, path):
        img = cv2.imread(path)
        if img is None:
            self.error = f"Could not open image: {os.path.basename(path)}"
            return
        self._new_source(img)

    def _generate(self):
        if self.source_img is None or self.busy:
            return
        self.job_id += 1
        job_id = self.job_id
        self.busy = True
        proc = self.entry().processor
        src = self.source_img

        def worker():
            try:
                small = cap_long_edge(src, SNAPSHOT_RES_CAP)
                result = proc.process(small)
            except Exception as exc:
                print(f"[snapshot] generation failed: {exc}")
                result = None
            if job_id == self.job_id:
                self.result_img = result
                self.busy = False

        threading.Thread(target=worker, daemon=True).start()

    def _save(self):
        if self.result_img is None:
            return
        self.recorder.screenshot(self.result_img, suffix="_art")
        self.toast_text = "Saved"
        self.toast_until = time.time() + 1.5

    def _handle_event(self, event):
        if event.type == pygame.QUIT:
            self.want_quit = True
        elif event.type == pygame.DROPFILE:
            self._load_from_file(event.file)
        elif event.type == pygame.KEYDOWN:
            self._on_key(event)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._on_click(event.pos)

    def _on_key(self, event):
        k = event.key
        if k == pygame.K_ESCAPE:
            self.want_back = True
        elif k == pygame.K_c:
            self._capture_from_camera()
        elif k == pygame.K_o:
            path = open_file_dialog("Choose a photo")
            if path:
                self._load_from_file(path)
        elif k in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            self._generate()
        elif k == pygame.K_s:
            self._save()
        elif k == pygame.K_LEFT:
            self.style_idx = (self.style_idx - 1) % len(self.ids)
        elif k == pygame.K_RIGHT:
            self.style_idx = (self.style_idx + 1) % len(self.ids)
        elif pygame.K_1 <= k <= pygame.K_9:
            idx = k - pygame.K_1
            if idx < len(self.ids):
                self.style_idx = idx
        elif k == pygame.K_UP:
            self._change_strength(0.05)
        elif k == pygame.K_DOWN:
            self._change_strength(-0.05)

    def _change_strength(self, d):
        p = self.entry().processor
        if p.has_strength:
            p.set_strength(max(0.0, min(1.0, p.get_strength() + d)))

    def _on_click(self, pos):
        for name, rect in self._button_rects.items():
            if not rect.collidepoint(pos):
                continue
            if name == "capture":
                self._capture_from_camera()
            elif name == "load":
                path = open_file_dialog("Choose a photo")
                if path:
                    self._load_from_file(path)
            elif name == "generate":
                self._generate()
            elif name == "save":
                self._save()
            return

    def draw(self):
        self.screen.fill(BG)
        w, h = self.screen.get_size()
        view = pygame.Rect(0, HEADER_H, w, h - HEADER_H - BAR_H)

        self._draw_header(pygame.Rect(0, 0, w, HEADER_H))
        self._draw_main(view)
        self._draw_bottom_bar(pygame.Rect(0, h - BAR_H, w, BAR_H))
        update_cursor(self._button_rects.values(), pygame.mouse.get_pos())

    def _draw_header(self, rect):
        pygame.draw.rect(self.screen, BAR_BG, rect)
        pygame.draw.line(self.screen, BORDER, (0, rect.bottom - 1), (rect.right, rect.bottom - 1))
        title = self.fonts["h1"].render("Create from Photo", True, TEXT)
        self.screen.blit(title, (24, rect.centery - title.get_height() // 2))
        hint = self.fonts["small"].render("Esc: back to home", True, TEXT_DIM)
        self.screen.blit(hint, (rect.right - 24 - hint.get_width(),
                                rect.centery - hint.get_height() // 2))

    def _draw_main(self, view):
        pad = 24
        inner = view.inflate(-pad * 2, -pad * 2)
        if self.source_img is None:
            self._draw_empty_state(inner)
            return
        if self.result_img is not None and not self.busy:
            gap = 16
            half_w = (inner.w - gap) // 2
            left = pygame.Rect(inner.x, inner.y, half_w, inner.h)
            right = pygame.Rect(inner.x + half_w + gap, inner.y, half_w, inner.h)
            self._blit_fit(self.source_img, left)
            self._blit_fit(self.result_img, right)
            self._tag(left, "ORIGINAL")
            self._tag(right, "ART")
        else:
            self._blit_fit(self.source_img, inner)
            if self.busy:
                self._draw_busy_overlay(inner)

    def _draw_empty_state(self, rect):
        self._draw_dashed_rect(rect, BORDER, 10, 8)
        cam_ok = self.capture.connected
        cam_line = "Press C to capture from the camera" if cam_ok else "Camera not connected - use Upload instead"
        lines = [("No photo yet", "h1", TEXT),
                 (cam_line, "body", TEXT_DIM if cam_ok else WARN),
                 ("Press O, or drop an image file onto the window, to upload", "body", TEXT_DIM)]
        cy = rect.centery - 44
        for i, (txt, fk, col) in enumerate(lines):
            surf = self.fonts[fk].render(txt, True, col)
            self.screen.blit(surf, (rect.centerx - surf.get_width() // 2, cy + i * 34))
        if self.error:
            err = self.fonts["small"].render(self.error, True, WARN)
            self.screen.blit(err, (rect.centerx - err.get_width() // 2, cy + 3 * 34 + 10))

    def _draw_dashed_rect(self, rect, color, dash, gap):
        x, y, w, h = rect
        for edge_y in (y, y + h - 2):
            xx = x
            while xx < x + w:
                pygame.draw.line(self.screen, color, (xx, edge_y), (min(xx + dash, x + w), edge_y), 2)
                xx += dash + gap
        for edge_x in (x, x + w - 2):
            yy = y
            while yy < y + h:
                pygame.draw.line(self.screen, color, (edge_x, yy), (edge_x, min(yy + dash, y + h)), 2)
                yy += dash + gap

    def _draw_busy_overlay(self, rect):
        overlay = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 130))
        self.screen.blit(overlay, rect.topleft)
        t = time.time()
        label = self.fonts["h1"].render("Generating" + "." * (int(t * 2) % 4), True, TEXT)
        self.screen.blit(label, (rect.centerx - label.get_width() // 2, rect.centery - 26))
        cx, cy = rect.centerx, rect.centery + 26
        for i in range(8):
            ang = t * 4 + i * (math.pi / 4)
            x = cx + int(math.cos(ang) * 16)
            y = cy + int(math.sin(ang) * 16)
            fade = (i / 8.0)
            color = tuple(int(c * fade + 20 * (1 - fade)) for c in ACCENT)
            pygame.draw.circle(self.screen, color, (x, y), 3)

    def _tag(self, rect, text):
        label = self.fonts["small"].render(text, True, TEXT)
        pad = 6
        bg = pygame.Surface((label.get_width() + pad * 2, label.get_height() + pad), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 150))
        self.screen.blit(bg, (rect.x + 10, rect.y + 10))
        self.screen.blit(label, (rect.x + 10 + pad, rect.y + 10 + pad // 2))

    def _blit_fit(self, frame_bgr, rect):
        surf = bgr_to_surface(frame_bgr)
        fw, fh = surf.get_size()
        scale = min(rect.w / fw, rect.h / fh)
        nw, nh = max(1, int(fw * scale)), max(1, int(fh * scale))
        surf = pygame.transform.smoothscale(surf, (nw, nh))
        self.screen.blit(surf, (rect.centerx - nw // 2, rect.centery - nh // 2))

    def _draw_bottom_bar(self, bar):
        self._button_rects = {}
        pygame.draw.rect(self.screen, BAR_BG, bar)
        pygame.draw.line(self.screen, BORDER, (bar.x, bar.y), (bar.right, bar.y))
        entry = self.entry()
        cat_col = CATEGORY_COLOR.get(entry.category, ACCENT)
        pad = 20

        x = bar.x + pad
        pygame.draw.circle(self.screen, cat_col, (x + 5, bar.y + 26), 6)
        self._text(entry.name, (x + 20, bar.y + 14), "mono", TEXT)
        self._text(f"{self.style_idx + 1}/{len(self.ids)}  ·  Left/Right or 1-9 to pick a style",
                   (x + 20, bar.y + 40), "small", TEXT_DIM)
        if entry.has_strength:
            val = entry.processor.get_strength()
            self._text(f"strength {val:.2f}  (Up/Down)", (x + 20, bar.y + 60), "small", TEXT_DIM)

        btn_w, btn_h, gap = 150, 40, 10
        right_x = bar.right - pad
        actions = [("load", "Upload (O)", None, False)]
        actions.append(("capture", "Capture (C)", None, not self.capture.connected))
        gen_label = "Generating…" if self.busy else "Generate (Enter)"
        actions.append(("generate", gen_label, ACCENT, self.source_img is None or self.busy))
        if self.result_img is not None:
            actions.append(("save", "Save (S)", GOOD, False))

        bx = right_x
        for key, label, accent, disabled in reversed(actions):
            bx -= btn_w
            rect = pygame.Rect(bx, bar.centery - btn_h // 2, btn_w, btn_h)
            self._draw_button(rect, label, None if disabled else accent, disabled)
            self._button_rects[key] = rect
            bx -= gap

        if time.time() < self.toast_until:
            toast = self.fonts["small"].render(self.toast_text, True, GOOD)
            self.screen.blit(toast, (right_x - toast.get_width(), bar.y + 8))

        if self.error:
            err = self.fonts["small"].render(self.error, True, WARN)
            self.screen.blit(err, (x, bar.bottom - 22))

    def _draw_button(self, rect, label, fill, disabled):
        bg = fill if fill is not None else (40, 44, 58) if not disabled else (26, 28, 38)
        pygame.draw.rect(self.screen, bg, rect, border_radius=8)
        pygame.draw.rect(self.screen, BORDER, rect, 1, border_radius=8)
        text_color = DARK_ON_LIGHT if fill is not None else (TEXT_DIM if disabled else TEXT)
        surf = self.fonts["small"].render(label, True, text_color)
        self.screen.blit(surf, (rect.centerx - surf.get_width() // 2,
                                rect.centery - surf.get_height() // 2))

    def _text(self, text, pos, font_key, color):
        surf = self.fonts[font_key].render(text, True, color)
        self.screen.blit(surf, pos)
