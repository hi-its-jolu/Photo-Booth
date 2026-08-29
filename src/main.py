import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import random
import cv2
import pygame

from config.config import (
    PHOTOS_DIR, CAMERA_INDEX, COUNTDOWN_SECONDS, TOTAL_PHOTOS,
    PREVIEW_DURATION, TARGET_FPS,
    AUDIO_FREQ, AUDIO_SIZE, AUDIO_CHANNELS, AUDIO_BUFFER,
    CAROUSEL_SCROLL_SPEED, CAROUSEL_PADDING,
    PRINT_COMPOSE_DUR, PRINT_HOLD_DUR, PRINT_SLIDE_DUR,
    PRINT_QTY_DEFAULT, PRINT_QTY_MIN, PRINT_QTY_MAX,
    GPIO_BUTTON_START, GPIO_BUTTON_SNAP, GPIO_BUTTON_PRINT,
    GPIO_BUTTON_RETAKE, GPIO_BUTTON_QTY_P, GPIO_BUTTON_QTY_N,
    PRINTER_CHECK_INTERVAL,
)
from camera    import grab_live_surface, snap_photo
from composite import build_review_grid_surfs, build_composite_surf, build_print_image, fit_scale, scale_px
from carousel  import load_carousel_photos, count_photos
from qr        import make_qr_surf
from printer   import print_polaroid, get_printer_info
from server    import start_file_server
from screens   import (
    render_idle, render_countdown, render_preview, render_grid,
    render_printing_compose, render_printing_hold, render_printing_slide,
    draw_thumbnails, draw_printer_status_dot, idle_viewfinder_inner, IDLE_THUMB_H,
)

# ── Constants ─────────────────────────────────────────────────────────────────

_PRINTS_DIR     = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "prints")
_SFX_DIR        = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sfx")
_GRID_TIMEOUT   = 25.0
_QR_SIZE        = 124   # design-scale px; actual size is scaled to fit the real screen
_QR_ARCHIVE_FMT = "print_%Y%m%d_%H%M%S.jpg"
_SFX_BEEP       = "count_down_beep.mp3"
_SFX_SHUTTER    = "camera_shot.mp3"
_WINDOW_CAPTION = "Photo Booth"
_JPEG_FORMAT    = "JPEG"
_JPEG_QUALITY   = 95
_PRINT_DPI      = (300, 300)

_STATE_IDLE      = "idle"
_STATE_COUNTDOWN = "countdown"
_STATE_PREVIEW   = "preview"
_STATE_GRID      = "grid"
_STATE_PRINTING  = "printing"
_PHASE_COMPOSE   = "compose"
_PHASE_HOLD      = "hold"
_PHASE_SLIDE     = "slide"


# ── Mutable game state ────────────────────────────────────────────────────────

class GameState:
    def __init__(self):
        self.state             = _STATE_IDLE
        self.running           = True
        self.photo_index       = 0
        self.thumbnails: list  = []
        self.photo_paths: list = []
        self.grid_surfs: list  = []
        self.preview_surf      = None
        self.event_time        = 0.0
        self.countdown_start   = 0.0
        self.skip_countdown    = False
        self.last_beep_num     = -1
        self.composite_surf    = None
        self.composite_rect    = None
        self.print_phase       = None
        self.print_phase_start = 0.0
        self.print_qty         = PRINT_QTY_DEFAULT
        self.prints_done       = 0
        self.qr_surf           = None
        self.grid_enter_time   = 0.0
        self.printer_info: dict       = {}
        self.last_printer_check: float = 0.0
        self.carousel_photos: list    = []
        self.carousel_start: float    = 0.0
        self.photo_count: int         = 0
        self.screen_w: int            = 0
        self.screen_h: int            = 0

    def clear_session(self):
        self.thumbnails.clear()
        self.photo_paths.clear()
        self.grid_surfs.clear()

    def go_idle(self):
        self.state       = _STATE_IDLE
        self.photo_index = 0
        self.print_qty   = PRINT_QTY_DEFAULT
        self.qr_surf     = None
        self.clear_session()
        self.carousel_photos, self.carousel_start = _reset_carousel(self.screen_w, self.screen_h)
        self.photo_count = count_photos()


# ── Setup helpers ─────────────────────────────────────────────────────────────

def _setup_gpio():
    """Wire arcade buttons on Raspberry Pi. Returns a cleanup callable."""
    try:
        import RPi.GPIO as GPIO
        mapping = {pin: key for pin, key in [
            (GPIO_BUTTON_START,  pygame.K_SPACE),  (GPIO_BUTTON_SNAP,   pygame.K_SPACE),
            (GPIO_BUTTON_PRINT,  pygame.K_p),       (GPIO_BUTTON_RETAKE, pygame.K_DELETE),
            (GPIO_BUTTON_QTY_P,  pygame.K_RIGHT),   (GPIO_BUTTON_QTY_N,  pygame.K_LEFT),
        ] if pin is not None}
        GPIO.setmode(GPIO.BCM)
        for pin in mapping:
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        def _cb(pin):
            key = mapping.get(pin)
            if key:
                pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode=""))
        for pin in mapping:
            GPIO.add_event_detect(pin, GPIO.FALLING, callback=_cb, bouncetime=200)
        print(f"GPIO active on pins: {list(mapping.keys())}")
        return GPIO.cleanup
    except (ImportError, RuntimeError):
        print("GPIO not available")
        return lambda: None


def _build_overlays(screen_w: int, screen_h: int):
    vignette = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)
    vignette.fill((0, 0, 0, 90))
    flash = pygame.Surface((screen_w, screen_h))
    flash.fill((255, 255, 255))
    dim = pygame.Surface((screen_w, screen_h))
    dim.fill((0, 0, 0))
    dim.set_alpha(140)
    return vignette, flash, dim


def _build_text_assets(screen_w: int, screen_h: int):
    f320 = pygame.font.SysFont(None, 320)
    f72  = pygame.font.SysFont(None, 72)
    labels    = [f72.render(f"Photo {i+1} of {TOTAL_PHOTOS}", True, (255, 255, 255))
                 for i in range(TOTAL_PHOTOS)]
    cd_surfs  = {n: (f320.render(str(n), True, (0, 0, 0)),
                     f320.render(str(n), True, (255, 255, 255)))
                 for n in range(1, COUNTDOWN_SECONDS + 2)}
    return labels, cd_surfs


def _reset_carousel(screen_w: int, screen_h: int):
    s = fit_scale(screen_w, screen_h)
    photos = load_carousel_photos(scale_px(IDLE_THUMB_H, s))
    if photos:
        pad     = scale_px(CAROUSEL_PADDING, s)
        speed   = CAROUSEL_SCROLL_SPEED * s
        total_w = sum(p.get_width() + pad for p in photos)
        start   = time.monotonic() - random.uniform(0, total_w) / speed
    else:
        start = time.monotonic()
    return photos, start


def _generate_qr(photo_paths: list, server_base_url: str, screen_w: int, screen_h: int) -> pygame.Surface | None:
    try:
        os.makedirs(_PRINTS_DIR, exist_ok=True)
        pil_img = build_print_image(photo_paths)
        fname   = time.strftime(_QR_ARCHIVE_FMT)
        fpath   = os.path.join(_PRINTS_DIR, fname)
        pil_img.save(fpath, _JPEG_FORMAT, quality=_JPEG_QUALITY, dpi=_PRINT_DPI)
        qr_size = scale_px(_QR_SIZE, fit_scale(screen_w, screen_h))
        return make_qr_surf(f"{server_base_url}/{fname}", size=qr_size)
    except Exception as e:
        print(f"QR generation failed: {e}")
        return None


# ── Per-state tick functions ──────────────────────────────────────────────────

def _tick_printing(gs: GameState, screen, now: float) -> None:
    """Advance the printing animation one frame. Calls go_idle() when all copies done."""
    elapsed = now - gs.print_phase_start
    cs, cr  = gs.composite_surf, gs.composite_rect

    if gs.print_phase == _PHASE_COMPOSE:
        render_printing_compose(screen, gs.grid_surfs, cs, cr,
                                min(1.0, elapsed / PRINT_COMPOSE_DUR), gs.prints_done)
        if elapsed >= PRINT_COMPOSE_DUR:
            print_polaroid(gs.photo_paths, 1)
            gs.print_phase, gs.print_phase_start = _PHASE_HOLD, now

    elif gs.print_phase == _PHASE_HOLD:
        sw, sh = screen.get_size()
        render_printing_hold(screen, cs, cr, sw, sh, now, gs.prints_done, gs.print_qty)
        if elapsed >= PRINT_HOLD_DUR:
            gs.print_phase, gs.print_phase_start = _PHASE_SLIDE, now

    elif gs.print_phase == _PHASE_SLIDE:
        render_printing_slide(screen, cs, cr, min(1.0, elapsed / PRINT_SLIDE_DUR), screen.get_height())
        if elapsed >= PRINT_SLIDE_DUR:
            gs.prints_done += 1
            if gs.prints_done < gs.print_qty:
                gs.print_phase, gs.print_phase_start = _PHASE_COMPOSE, now
            else:
                gs.composite_surf, gs.prints_done = None, 0
                gs.go_idle()


def _tick_grid(gs: GameState, screen, screen_w: int, screen_h: int, now: float) -> None:
    """Render the grid/review screen and handle its keyboard events."""
    time_left = max(0.0, _GRID_TIMEOUT - (now - gs.grid_enter_time))
    render_grid(screen, gs.grid_surfs, screen_w, screen_h, now, time_left, gs.print_qty, gs.qr_surf)
    if time_left <= 0:
        gs.go_idle()
        return
    for event in pygame.event.get():
        if   event.type == pygame.QUIT:                        gs.running = False
        elif event.type == pygame.KEYDOWN: _handle_grid_key(gs, screen, screen_w, screen_h, now, event.key)


def _handle_grid_key(gs: GameState, screen, screen_w: int, screen_h: int, now: float, key) -> None:
    if   key == pygame.K_ESCAPE:                              gs.running = False
    elif key == pygame.K_RIGHT:                               gs.print_qty = min(PRINT_QTY_MAX, gs.print_qty + 1)
    elif key == pygame.K_LEFT:                                gs.print_qty = max(PRINT_QTY_MIN, gs.print_qty - 1)
    elif key in (pygame.K_DELETE, pygame.K_BACKSPACE):        gs.go_idle()
    elif key == pygame.K_p:
        gs.composite_surf    = build_composite_surf(gs.photo_paths, screen_w, screen_h)
        gs.composite_rect    = gs.composite_surf.get_rect(center=(screen_w // 2, screen_h // 2))
        gs.prints_done       = 0
        gs.print_phase       = _PHASE_COMPOSE
        gs.print_phase_start = now
        gs.qr_surf           = None
        gs.state             = _STATE_PRINTING


def _tick_countdown_frame(gs: GameState, screen, screen_w: int, screen_h: int, now: float,
                          vignette, countdown_surfs, photo_labels, snd_beep, snd_shutter, cap) -> None:
    remaining = COUNTDOWN_SECONDS - (now - gs.countdown_start)
    if remaining <= 0 or gs.skip_countdown:
        gs.skip_countdown = False
        gs.last_beep_num  = -1
        snd_shutter.play()
        result = snap_photo(cap, gs.photo_index, screen_w, screen_h)
        if result:
            path, thumb, gs.preview_surf = result
            gs.photo_paths.append(path)
            gs.thumbnails.append(thumb)
        else:
            gs.thumbnails.append(None)
            gs.preview_surf = None
        gs.photo_index += 1
        gs.event_time   = now
        gs.state        = _STATE_PREVIEW
    else:
        num = max(1, min(COUNTDOWN_SECONDS + 1, int(remaining) + 1))
        if num != gs.last_beep_num:
            snd_beep.play()
            gs.last_beep_num = num
        render_countdown(screen, vignette, countdown_surfs, photo_labels,
                         gs.photo_index, screen_w, screen_h, num)


def _advance_after_preview(gs: GameState, screen_w: int, screen_h: int,
                           now: float, server_base_url: str) -> None:
    if gs.photo_index < TOTAL_PHOTOS:
        gs.countdown_start = now
        gs.state           = _STATE_COUNTDOWN
    else:
        gs.state           = _STATE_GRID
        gs.grid_enter_time = now
        gs.grid_surfs      = build_review_grid_surfs(gs.photo_paths, screen_w, screen_h)
        gs.qr_surf         = _generate_qr(gs.photo_paths, server_base_url, screen_w, screen_h)


def _handle_live_key(gs: GameState, key, now: float) -> None:
    if   key == pygame.K_ESCAPE:                                          gs.running = False
    elif key == pygame.K_SPACE and gs.state == _STATE_IDLE:
        gs.clear_session()
        gs.photo_index, gs.last_beep_num = 0, -1
        gs.countdown_start = now
        gs.state           = _STATE_COUNTDOWN
    elif key == pygame.K_SPACE and gs.state == _STATE_COUNTDOWN:          gs.skip_countdown = True


def _render_idle_frame(gs: GameState, screen, cap, screen_w: int, screen_h: int, now: float) -> bool:
    """Render one frame of the idle screen. Returns False on camera failure."""
    vf_w, vf_h = idle_viewfinder_inner(screen_w, screen_h)
    live_box = grab_live_surface(cap, vf_w, vf_h)
    if live_box is None:
        return False
    render_idle(screen, live_box, gs.carousel_photos, gs.carousel_start, now,
                gs.photo_count, screen_w, screen_h)
    return True


def _render_live_frame(gs: GameState, screen, cap, screen_w: int, screen_h: int, now: float,
                       server_base_url: str, vignette, flash_surf, dim_surf,
                       photo_labels, countdown_surfs, snd_beep, snd_shutter) -> None:
    """Render one frame of idle / countdown / preview state."""
    if gs.state == _STATE_IDLE:
        if not _render_idle_frame(gs, screen, cap, screen_w, screen_h, now):
            gs.running = False
            return
    else:
        live_surf = grab_live_surface(cap, screen_w, screen_h)
        if live_surf is None:
            gs.running = False
            return
        screen.blit(live_surf, (0, 0))

        if gs.state == _STATE_COUNTDOWN:
            _tick_countdown_frame(gs, screen, screen_w, screen_h, now,
                                  vignette, countdown_surfs, photo_labels,
                                  snd_beep, snd_shutter, cap)
        elif gs.state == _STATE_PREVIEW:
            age = now - gs.event_time
            render_preview(screen, flash_surf, dim_surf, gs.preview_surf, age, screen_w, screen_h)
            if age >= PREVIEW_DURATION:
                _advance_after_preview(gs, screen_w, screen_h, now, server_base_url)

        draw_thumbnails(screen, gs.thumbnails, screen_w, screen_h)

    draw_printer_status_dot(screen, gs.printer_info)
    pygame.display.flip()
    for event in pygame.event.get():
        if event.type == pygame.QUIT:   gs.running = False
        elif event.type == pygame.KEYDOWN: _handle_live_key(gs, event.key, now)


# ── Main game loop ────────────────────────────────────────────────────────────

def _run_loop(gs: GameState, screen, cap, clock, screen_w: int, screen_h: int,
              server_base_url: str, vignette, flash_surf, dim_surf,
              photo_labels, countdown_surfs, snd_beep, snd_shutter) -> None:
    while gs.running:
        now = time.monotonic()
        if now - gs.last_printer_check >= PRINTER_CHECK_INTERVAL:
            gs.printer_info        = get_printer_info()
            gs.last_printer_check  = now

        if gs.state == _STATE_PRINTING:
            _tick_printing(gs, screen, now)
            draw_printer_status_dot(screen, gs.printer_info)
            pygame.display.flip()
            clock.tick(TARGET_FPS)
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (
                        event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                    gs.running = False
            continue

        if gs.state == _STATE_GRID:
            _tick_grid(gs, screen, screen_w, screen_h, now)
            draw_printer_status_dot(screen, gs.printer_info)
            pygame.display.flip()
            clock.tick(TARGET_FPS)
            continue

        _render_live_frame(gs, screen, cap, screen_w, screen_h, now, server_base_url,
                           vignette, flash_surf, dim_surf,
                           photo_labels, countdown_surfs, snd_beep, snd_shutter)
        clock.tick(TARGET_FPS)


def main():
    os.makedirs(PHOTOS_DIR,  exist_ok=True)
    os.makedirs(_PRINTS_DIR, exist_ok=True)
    server_base_url = start_file_server(_PRINTS_DIR)

    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open webcam (index {CAMERA_INDEX})")

    pygame.mixer.pre_init(AUDIO_FREQ, AUDIO_SIZE, AUDIO_CHANNELS, AUDIO_BUFFER)
    pygame.init()
    pygame.mixer.init()
    gpio_cleanup = _setup_gpio()

    snd_beep    = pygame.mixer.Sound(os.path.join(_SFX_DIR, _SFX_BEEP))
    snd_shutter = pygame.mixer.Sound(os.path.join(_SFX_DIR, _SFX_SHUTTER))
    screen      = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    pygame.display.set_caption(_WINDOW_CAPTION)
    pygame.mouse.set_visible(False)
    clock = pygame.time.Clock()
    screen_w, screen_h = screen.get_size()

    vignette, flash_surf, dim_surf   = _build_overlays(screen_w, screen_h)
    photo_labels, countdown_surfs    = _build_text_assets(screen_w, screen_h)

    gs = GameState()
    gs.screen_w, gs.screen_h               = screen_w, screen_h
    gs.carousel_photos, gs.carousel_start  = _reset_carousel(screen_w, screen_h)
    gs.photo_count                         = count_photos()
    gs.printer_info                        = get_printer_info()
    gs.last_printer_check                  = time.monotonic()

    _run_loop(gs, screen, cap, clock, screen_w, screen_h, server_base_url,
              vignette, flash_surf, dim_surf,
              photo_labels, countdown_surfs, snd_beep, snd_shutter)

    cap.release()
    pygame.quit()
    gpio_cleanup()


if __name__ == "__main__":
    main()
