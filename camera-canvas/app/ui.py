"""pygame rendering, overlay HUD, and input handling for the Live screen."""

import time
import math

import cv2
import numpy as np
import pygame

from app.dialogs import open_file_dialog

BG = (16, 18, 24)
BAR_BG = (24, 27, 36)
BORDER = (44, 48, 62)
TEXT = (235, 237, 242)
TEXT_DIM = (140, 146, 162)
ACCENT = (96, 165, 250)
GOOD = (74, 222, 128)
WARN = (251, 146, 60)
REC = (248, 113, 113)
SLIDER_TRACK = (52, 56, 72)
DARK_ON_LIGHT = (18, 19, 26)

CATEGORY_COLOR = {
    "filter": (96, 165, 250),
    "neural": (167, 139, 250),
    "arbitrary": (52, 211, 153),
}

BAR_H = 136
TOP_ACCENT_H = 3
SWITCH_FLASH_S = 0.22
SHOT_FLASH_S = 0.16
SHOT_TOAST_S = 1.1


def _ease_out_cubic(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def bgr_to_surface(frame_bgr):
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    return pygame.image.frombuffer(np.ascontiguousarray(rgb).tobytes(),
                                   (rgb.shape[1], rgb.shape[0]), "RGB")


def update_cursor(clickable_rects, mouse_pos):
    """Hand cursor over anything clickable, arrow otherwise."""
    hovering = any(r.collidepoint(mouse_pos) for r in clickable_rects)
    try:
        pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND if hovering
                                else pygame.SYSTEM_CURSOR_ARROW)
    except Exception:
        pass


class UI:
    def __init__(self, screen, state, out_slot, raw_slot, recorder, capture,
                 display_fps_counter, infer_fps_getter):
        self.screen = screen
        self.state = state
        self.out_slot = out_slot
        self.raw_slot = raw_slot
        self.recorder = recorder
        self.capture = capture
        self.display_fps = display_fps_counter
        self.infer_fps_getter = infer_fps_getter

        self.fonts = {
            "hero": pygame.font.SysFont("menlo,monaco,monospace", 40, bold=True),
            "hero_sm": pygame.font.SysFont("menlo,monaco,monospace", 26, bold=True),
            "big": pygame.font.SysFont("helveticaneue,arial", 28, bold=True),
            "h": pygame.font.SysFont("helveticaneue,arial", 18, bold=True),
            "body": pygame.font.SysFont("helveticaneue,arial", 16),
            "small": pygame.font.SysFont("helveticaneue,arial", 13),
            "mono": pygame.font.SysFont("menlo,monaco,monospace", 17, bold=True),
        }
        self.want_quit = False
        self.want_back = False
        self.want_benchmark = False
        self._button_rects = {}

        self._last_style_id = None
        self._switch_flash_t = -10.0
        self._shot_flash_t = -10.0
        self._shot_toast_until = 0.0

    @property
    def reduce_motion(self):
        return getattr(self.state, "reduce_motion", False)

    def handle_events(self):
        self.want_benchmark = False
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.want_quit = True
            elif event.type == pygame.DROPFILE:
                self.state.use_style_image(event.file)
            elif event.type == pygame.KEYDOWN:
                self._on_key(event)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._on_click(event.pos)

    def _on_key(self, event):
        k = event.key
        s = self.state
        if k == pygame.K_ESCAPE:
            self.want_back = True
        elif k in (pygame.K_RIGHT,):
            s.cycle_style(1)
        elif k in (pygame.K_LEFT,):
            s.cycle_style(-1)
        elif pygame.K_1 <= k <= pygame.K_9:
            s.jump_style(k - pygame.K_1)
        elif k == pygame.K_UP:
            s.change_strength(+0.05)
        elif k == pygame.K_DOWN:
            s.change_strength(-0.05)
        elif k == pygame.K_LEFTBRACKET:
            s.cycle_res(-1)
        elif k == pygame.K_RIGHTBRACKET:
            s.cycle_res(+1)
        elif k == pygame.K_TAB:
            s.side_by_side = not s.side_by_side
        elif k == pygame.K_s:
            self._screenshot()
        elif k == pygame.K_r:
            self._toggle_record()
        elif k == pygame.K_o:
            path = open_file_dialog("Choose style image")
            if path:
                s.use_style_image(path)
        elif k == pygame.K_p:
            s.next_preset()
        elif k == pygame.K_f:
            self._toggle_fullscreen()
        elif k == pygame.K_b:
            self.want_benchmark = True

    def _on_click(self, pos):
        for name, rect in self._button_rects.items():
            if rect.collidepoint(pos):
                if name == "shot":
                    self._screenshot()
                elif name == "rec":
                    self._toggle_record()
                elif name == "thumb":
                    self.state.next_preset()
                elif name == "sbs":
                    self.state.side_by_side = not self.state.side_by_side
                elif name == "slider":
                    entry = self.state.entry()
                    if entry.has_strength and rect.w:
                        val = (pos[0] - rect.x) / rect.w
                        entry.processor.set_strength(max(0.0, min(1.0, val)))
                return

    def _screenshot(self):
        styled = self.out_slot.get()
        if styled is not None:
            self.recorder.screenshot(styled)
            now = time.time()
            self._shot_toast_until = now + SHOT_TOAST_S
            if not self.reduce_motion:
                self._shot_flash_t = now

    def _toggle_record(self):
        styled = self.out_slot.get()
        if styled is not None:
            self.recorder.toggle_recording(max(1.0, self.display_fps.value()), styled)

    def _toggle_fullscreen(self):
        self.state.fullscreen = not self.state.fullscreen
        flags = pygame.FULLSCREEN if self.state.fullscreen else 0
        size = (0, 0) if self.state.fullscreen else (self.state.window_w, self.state.window_h)
        self.screen = pygame.display.set_mode(size, flags)

    def draw(self):
        self.display_fps.tick()
        now = time.time()

        if self.state.style_id != self._last_style_id:
            if self._last_style_id is not None and not self.reduce_motion:
                self._switch_flash_t = now
            self._last_style_id = self.state.style_id

        self.screen.fill(BG)
        w, h = self.screen.get_size()
        view = pygame.Rect(0, 0, w, h - BAR_H)

        styled = self.out_slot.get()
        raw = self.raw_slot.get()

        if styled is None:
            self._draw_camera_message(view)
        elif self.state.side_by_side and raw is not None:
            half = pygame.Rect(view.x, view.y, view.w // 2, view.h)
            self._blit_fit(raw, half)
            self._blit_fit(styled, pygame.Rect(view.centerx, view.y, view.w // 2, view.h))
            pygame.draw.line(self.screen, BORDER, (view.centerx, view.y),
                             (view.centerx, view.bottom), 1)
            self._tag(half, "ORIGINAL")
            self._tag(pygame.Rect(view.centerx, view.y, view.w // 2, view.h), "STYLED")
        else:
            self._blit_fit(styled, view)

        self._draw_bottom_bar(pygame.Rect(0, h - BAR_H, w, BAR_H), now)

        if not self.reduce_motion:
            self._draw_shot_flash(now, w, h)

        update_cursor(self._button_rects.values(), pygame.mouse.get_pos())
        pygame.display.flip()

    def _blit_fit(self, frame_bgr, rect):
        fh, fw = frame_bgr.shape[:2]
        scale = min(rect.w / fw, rect.h / fh)
        nw, nh = max(1, int(fw * scale)), max(1, int(fh * scale))
        surf = pygame.transform.smoothscale(bgr_to_surface(frame_bgr), (nw, nh))
        self.screen.blit(surf, (rect.centerx - nw // 2, rect.centery - nh // 2))

    def _tag(self, rect, text):
        label = self.fonts["small"].render(text, True, TEXT)
        pad = 6
        bg = pygame.Surface((label.get_width() + pad * 2, label.get_height() + pad), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 150))
        self.screen.blit(bg, (rect.x + 10, rect.y + 10))
        self.screen.blit(label, (rect.x + 10 + pad, rect.y + 10 + pad // 2))

    def _draw_camera_message(self, view):
        err = self.capture.error or "Waiting for camera..."
        lines = ["Camera", err, "Press Esc to go back"]
        cy = view.centery - 30
        for i, (txt, font, col) in enumerate([
                (lines[0], self.fonts["big"], TEXT),
                (lines[1], self.fonts["body"], WARN),
                (lines[2], self.fonts["small"], TEXT_DIM)]):
            surf = font.render(txt, True, col)
            self.screen.blit(surf, (view.centerx - surf.get_width() // 2, cy + i * 34))

    def _draw_shot_flash(self, now, w, h):
        elapsed = now - self._shot_flash_t
        if elapsed >= SHOT_FLASH_S:
            return
        alpha = int(210 * (1 - _ease_out_cubic(elapsed / SHOT_FLASH_S)))
        if alpha <= 0:
            return
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((255, 255, 255, alpha))
        self.screen.blit(overlay, (0, 0))

    def _draw_bottom_bar(self, bar, now):
        self._button_rects = {}
        pygame.draw.rect(self.screen, BAR_BG, bar)

        entry = self.state.entry()
        cat_col = CATEGORY_COLOR.get(entry.category, ACCENT)
        cam_ok = self.capture.connected

        accent_color = REC if not cam_ok else cat_col
        accent_h = TOP_ACCENT_H
        if not self.reduce_motion:
            flash_elapsed = now - self._switch_flash_t
            if cam_ok and flash_elapsed < SWITCH_FLASH_S:
                k = 1 - _ease_out_cubic(flash_elapsed / SWITCH_FLASH_S)
                accent_h = int(TOP_ACCENT_H + k * 9)
            elif not cam_ok:
                pulse = 0.5 + 0.5 * math.sin(now * 3.0)
                accent_h = int(TOP_ACCENT_H + pulse * 5)
        pygame.draw.rect(self.screen, accent_color, (bar.x, bar.y, bar.w, accent_h))
        pygame.draw.line(self.screen, BORDER, (bar.x, bar.y + accent_h),
                         (bar.right, bar.y + accent_h), 1)

        pad = 20
        row_y = bar.y + accent_h

        x = bar.x + pad
        right_x = bar.right - pad
        btn_w = 116
        name_w = 230
        gap = 24

        has_thumb_asset = bool(self.state.adain and self.state.adain.style_thumb is not None)
        slider_w = 150
        slider_zone_w = slider_w + 10 + 41 + gap
        res_zone_w = 90 + gap
        dev_zone_w = 130 + gap
        thumb_zone_w = (96 + gap) if has_thumb_asset else 0

        MIN_HERO_W = 170
        available = (right_x - btn_w - gap) - (x + name_w) - MIN_HERO_W
        show_slider = available >= slider_zone_w
        if show_slider:
            available -= slider_zone_w
        show_res = available >= res_zone_w
        if show_res:
            available -= res_zone_w
        show_device = available >= dev_zone_w
        if show_device:
            available -= dev_zone_w
        show_thumb = has_thumb_asset and available >= thumb_zone_w

        pygame.draw.circle(self.screen, cat_col, (x + 5, row_y + 24), 6)
        self._text(entry.name, (x + 20, row_y + 14), "big", TEXT)
        self._text(f"{entry.category} · {self.state.idx + 1}/{len(self.state.ids)}",
                   (x + 20, row_y + 66), "small", TEXT_DIM)
        if entry.category == "arbitrary" and self.state.adain and self.state.adain.style_name:
            self._text(f"image: {self.state.adain.style_name}", (x + 20, row_y + 92),
                       "small", cat_col)
        cursor = x + name_w

        if show_slider:
            self._draw_slider(cursor, row_y + 38, slider_w, entry)
            cursor += slider_zone_w

        if show_res:
            self._text("RES", (cursor, row_y + 14), "small", TEXT_DIM)
            self._text(f"{self.state.infer_res}px", (cursor, row_y + 30), "mono", TEXT)
            self._text("[ / ]", (cursor, row_y + 58), "small", TEXT_DIM)
            cursor += res_zone_w

        buttons_x = right_x - btn_w
        cursor_right = buttons_x

        thumb_x = None
        if show_thumb:
            cursor_right -= (96 + gap)
            thumb_x = cursor_right

        if show_device:
            cursor_right -= (130 + gap)
            self._draw_device_cluster(cursor_right, row_y, 130, cam_ok, now)

        hero_w = max(MIN_HERO_W, cursor_right - gap - cursor)
        self._draw_fps_hero(cursor, row_y, hero_w)

        if show_thumb:
            thumb_rect = pygame.Rect(thumb_x, bar.y + accent_h + 10, 96, BAR_H - accent_h - 20)
            self._blit_fit(self.state.adain.style_thumb, thumb_rect)
            pygame.draw.rect(self.screen, BORDER, thumb_rect, 1)
            self._button_rects["thumb"] = thumb_rect

        self._draw_record_button(pygame.Rect(buttons_x, row_y + 8, btn_w, 40), now)
        shot_rect = pygame.Rect(buttons_x, row_y + 52, btn_w, 40)
        self._draw_button(shot_rect, "Screenshot (S)", None)
        self._button_rects["shot"] = shot_rect

        if now < self._shot_toast_until:
            self._text("Saved", (shot_rect.x, shot_rect.bottom + 6), "small", GOOD)

    def _draw_fps_hero(self, x, row_y, zone_w):
        inf = self.infer_fps_getter()
        disp = self.display_fps.value()
        label = "FPS · INFERENCE / DISPLAY" if zone_w >= 230 else "FPS"
        self._text(label, (x, row_y + 10), "small", TEXT_DIM, tracking=1)

        inf_color = GOOD if inf >= 15 else WARN
        disp_color = GOOD if disp >= 30 else WARN

        hero_font = self.fonts["hero"]
        slash_font = self.fonts["big"]
        probe_w = (hero_font.size("888")[0] * 2 + slash_font.size("/")[0] + 28)
        if probe_w > zone_w:
            hero_font = self.fonts["hero_sm"]
            slash_font = self.fonts["body"]

        inf_surf = hero_font.render(f"{inf:3.0f}", True, inf_color)
        slash_surf = slash_font.render("/", True, TEXT_DIM)
        disp_surf = hero_font.render(f"{disp:3.0f}", True, disp_color)

        ty = row_y + 32
        self.screen.blit(inf_surf, (x, ty))
        sx = x + inf_surf.get_width() + 14
        self.screen.blit(slash_surf, (sx, ty + (inf_surf.get_height() - slash_surf.get_height()) // 2))
        dx = sx + slash_surf.get_width() + 14
        self.screen.blit(disp_surf, (dx, ty))

    def _draw_device_cluster(self, x, row_y, w, cam_ok, now):
        self._text("DEVICE", (x, row_y + 14), "small", TEXT_DIM)
        self._text(self.state.device_name.upper(), (x, row_y + 30), "mono", ACCENT)

        chip_y = row_y + 58
        chip = pygame.Rect(x, chip_y, w - 4, 26)
        if cam_ok:
            self._text("camera ok", (x, chip_y + 5), "small", GOOD)
        else:
            alpha = 255
            if not self.reduce_motion:
                alpha = int(160 + 95 * (0.5 + 0.5 * math.sin(now * 3.0)))
            bg = pygame.Surface((chip.w, chip.h), pygame.SRCALPHA)
            pygame.draw.rect(bg, (*REC, min(255, alpha // 2)), (0, 0, chip.w, chip.h), border_radius=6)
            self.screen.blit(bg, chip.topleft)
            self._text("NO CAMERA", (x + 6, chip_y + 5), "small", REC)

    def _draw_record_button(self, rect, now):
        recording = self.recorder.recording
        if recording and not self.reduce_motion:
            pulse = 0.5 + 0.5 * math.sin(now * 6.0)
            fill = tuple(int(c * (0.7 + 0.3 * pulse)) for c in REC)
        else:
            fill = REC if recording else None
        label = "● REC" if recording else "Record (R)"
        self._draw_button(rect, label, fill)
        self._button_rects["rec"] = rect

    def _draw_slider(self, x, y, w, entry):
        self._text("STRENGTH", (x, y - 14), "small", TEXT_DIM)
        track = pygame.Rect(x, y + 6, w, 6)
        pygame.draw.rect(self.screen, SLIDER_TRACK, track, border_radius=3)
        if entry.has_strength:
            val = entry.processor.get_strength()
            fill = pygame.Rect(x, y + 6, int(w * val), 6)
            pygame.draw.rect(self.screen, ACCENT, fill, border_radius=3)
            knob_x = x + int(w * val)
            pygame.draw.circle(self.screen, TEXT, (knob_x, y + 9), 8)
            self._text(f"{val:.2f}", (x + w + 10, y), "mono", TEXT)
            self._button_rects["slider"] = pygame.Rect(x, y - 4, w, 22)
        else:
            self._text("n/a", (x + w + 10, y), "small", TEXT_DIM)

    def _draw_button(self, rect, label, fill):
        pygame.draw.rect(self.screen, fill or (40, 44, 58), rect, border_radius=8)
        pygame.draw.rect(self.screen, BORDER, rect, 1, border_radius=8)
        text_color = DARK_ON_LIGHT if fill is not None else TEXT
        surf = self.fonts["small"].render(label, True, text_color)
        self.screen.blit(surf, (rect.centerx - surf.get_width() // 2,
                                rect.centery - surf.get_height() // 2))

    def _text(self, text, pos, font_key, color, tracking=0):
        if tracking == 0:
            surf = self.fonts[font_key].render(text, True, color)
            self.screen.blit(surf, pos)
            return surf
        f = self.fonts[font_key]
        x, y = pos
        for ch in text:
            glyph = f.render(ch, True, color)
            self.screen.blit(glyph, (x, y))
            x += glyph.get_width() + tracking
        return None
