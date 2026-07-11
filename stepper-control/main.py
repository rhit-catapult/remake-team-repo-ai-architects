"""Stepper Control Panel — entry point, main loop, layout router.

Drives five 28BYJ-48 stepper motors (Arduino Mega + ULN2003) by angle, speed,
or step jogs. Runs fully in mock mode when no Arduino is attached.

    python main.py

Global keys:
    SPACE / Esc   STOP ALL (safety)
    1 – 5         focus that motor card
    F             toggle fullscreen
"""

import os
import sys

# Make the app launchable from any working directory: ensure this folder (which
# holds config.py and the ui/ motor/ serial_io/ packages) is importable.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pygame

import config
from ui import theme
from ui.theme import BG, PANEL, BORDER
from ui.topbar import TopBar, BAR_H
from ui.motor_card import MotorCard
from ui.sidebar import Sidebar
from ui.sync_panel import SyncPanel
from serial_io.controller import SerialController
from motor.motor_state import build_app_state

SIDEBAR_W = 260
PAD = 3 * config.U
GAP = 2 * config.U
COLS = 3
ROWS = 2

# Windowed-mode size, captured before fullscreen overwrites config.WINDOW_W/H.
WINDOWED_SIZE = (config.WINDOW_W, config.WINDOW_H)


def build_card_rects():
    """Compute the 5 motor-card rects in the main (left) area, 3 columns × 2 rows."""
    main_w = config.WINDOW_W - SIDEBAR_W
    area_x = PAD
    area_y = BAR_H + PAD
    area_w = main_w - 2 * PAD
    area_h = config.WINDOW_H - area_y - PAD

    card_w = (area_w - (COLS - 1) * GAP) // COLS
    card_h = (area_h - (ROWS - 1) * GAP) // ROWS

    rects = []
    for i in range(config.NUM_MOTORS):
        r, c = divmod(i, COLS)
        x = area_x + c * (card_w + GAP)
        y = area_y + r * (card_h + GAP)
        rects.append(pygame.Rect(x, y, card_w, card_h))
    return rects


def _set_display(fullscreen):
    """(Re)create the window and sync config.WINDOW_W/H to its real size."""
    if fullscreen:
        screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    else:
        screen = pygame.display.set_mode(WINDOWED_SIZE)
    config.WINDOW_W, config.WINDOW_H = screen.get_size()
    return screen


def build_ui(app):
    """Build the full widget tree for the current window size. Called at launch
    and again whenever fullscreen is toggled."""
    topbar = TopBar(config.WINDOW_W, app, app.stop_all)
    cards = [MotorCard(rect, app.motors[i], app)
             for i, rect in enumerate(build_card_rects())]

    # Right column: STATUS (top) + ALL MOTORS / sync (bottom).
    side_x = config.WINDOW_W - SIDEBAR_W + PAD
    side_w = SIDEBAR_W - PAD - PAD // 2
    side_y = BAR_H + PAD
    sidebar = Sidebar((side_x, side_y, side_w,
                       config.WINDOW_H - side_y - PAD), app)
    sync_top = side_y + sidebar.height() + 2 * config.U
    sync_panel = SyncPanel((side_x, sync_top, side_w,
                            config.WINDOW_H - sync_top - PAD), app)
    return topbar, cards, sidebar, sync_panel


def _draw_stop_flash(screen, app):
    """Brief red edge flash after STOP ALL — unmissable, even from across a room."""
    if app.stop_flash <= 0.0:
        return
    t = min(1.0, app.stop_flash / 0.45)
    alpha = int(150 * t)
    w, h = screen.get_size()
    edge = 8
    overlay = pygame.Surface((w, h), pygame.SRCALPHA)
    color = (*theme.RED_SOFT, alpha)
    pygame.draw.rect(overlay, color, (0, 0, w, edge))
    pygame.draw.rect(overlay, color, (0, h - edge, w, edge))
    pygame.draw.rect(overlay, color, (0, 0, edge, h))
    pygame.draw.rect(overlay, color, (w - edge, 0, edge, h))
    screen.blit(overlay, (0, 0))


def main():
    pygame.init()
    pygame.display.set_caption(config.WINDOW_TITLE)
    fullscreen = config.FULLSCREEN
    screen = _set_display(fullscreen)
    clock = pygame.time.Clock()

    controller = SerialController()
    controller.connect_async()    # auto-detect on a bg thread → real serial, else mock
                                  # (never blocks the window on the serial handshake)

    app = build_app_state(controller, theme.MOTOR_COLORS)
    topbar, cards, sidebar, sync_panel = build_ui(app)

    running = True
    while running:
        dt = clock.tick(config.FPS) / 1000.0
        theme.set_dt(dt)          # drives all widget easing this frame

        # 1. serial completions → clear moving flags.
        for m in controller.poll():
            app.on_move_done(m)

        # 2. events.
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if _typing(cards, sync_panel):
                    # A text field is focused; only let it and Esc through.
                    if event.key == pygame.K_ESCAPE:
                        app.stop_all()
                    _route_event(event, topbar, cards, sync_panel, app)
                    continue
                if event.key in (pygame.K_SPACE, pygame.K_ESCAPE):
                    app.stop_all()
                    sync_panel.running = False
                elif pygame.K_1 <= event.key <= pygame.K_5:
                    app.focused = event.key - pygame.K_1
                elif event.key == pygame.K_f:
                    fullscreen = not fullscreen
                    screen = _set_display(fullscreen)
                    topbar, cards, sidebar, sync_panel = build_ui(app)
                else:
                    _route_event(event, topbar, cards, sync_panel, app)
            else:
                _route_event(event, topbar, cards, sync_panel, app)

        # 3. update: sync card enabled state + integrate motor positions.
        for card in cards:
            card.enabled = not app.sync_enabled
        app.update(dt)
        for card in cards:
            if card._dial is not None:
                card._dial.sync_target()

        # 4. draw.
        screen.fill(BG)
        _draw_sidebar_bg(screen)
        topbar.draw(screen)
        for card in cards:
            card.draw(screen)
        sidebar.draw(screen)
        sync_panel.draw(screen)
        _draw_stop_flash(screen, app)
        pygame.display.flip()

    controller.stop_all()
    controller.close()
    pygame.quit()
    sys.exit(0)


def _typing(cards, sync_panel):
    for card in cards:
        for w in card.body_widgets:
            if getattr(w, "focused", False):
                return True
    for w in sync_panel.body_widgets:
        if getattr(w, "focused", False):
            return True
    return False


def _route_event(event, topbar, cards, sync_panel, app):
    if topbar.handle_event(event):
        return
    if sync_panel.handle_event(event):
        return
    for card in cards:
        if card.handle_event(event):
            return


def _draw_sidebar_bg(screen):
    x = config.WINDOW_W - SIDEBAR_W
    pygame.draw.rect(screen, PANEL, (x, BAR_H + 1, SIDEBAR_W, config.WINDOW_H - BAR_H))
    pygame.draw.line(screen, BORDER, (x, BAR_H + 1), (x, config.WINDOW_H), 1)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        # Never let the window vanish silently — surface the full traceback.
        import traceback
        print("\n" + "=" * 60, file=sys.stderr)
        print("[stepper-control] crashed — traceback below:", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        traceback.print_exc()
        try:
            pygame.quit()
        except Exception:
            pass
        sys.exit(1)
