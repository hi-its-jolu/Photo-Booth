import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import cv2
import pygame

from config.config import (
    PHOTOS_DIR,
    CAMERA_INDEX,
    COUNTDOWN_SECONDS,
    TOTAL_PHOTOS,
    PREVIEW_DURATION,
    TARGET_FPS,
    AUDIO_FREQ, AUDIO_SIZE, AUDIO_CHANNELS, AUDIO_BUFFER,
    CAROUSEL_STRIP_HEIGHT,
    PRINT_COMPOSE_DUR, PRINT_HOLD_DUR, PRINT_SLIDE_DUR,
    PRINT_QTY_DEFAULT, PRINT_QTY_MIN, PRINT_QTY_MAX,
    GPIO_BUTTON_START, GPIO_BUTTON_SNAP, GPIO_BUTTON_PRINT, GPIO_BUTTON_RETAKE,
    GPIO_BUTTON_QTY_P, GPIO_BUTTON_QTY_N,
)

from image import (
    grab_live_surface,
    snap_photo,
    build_grid_surfs,
    build_polaroid_surf,
    draw_thumbnails,
    load_carousel_photos,
)

from printer import print_composite

from booth import (
    render_idle,
    render_countdown,
    render_preview,
    render_grid,
    render_printing_compose,
    render_printing_hold,
    render_printing_slide,
)


def main():
    os.makedirs(PHOTOS_DIR, exist_ok=True)

    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open webcam (index {CAMERA_INDEX})")

    pygame.mixer.pre_init(AUDIO_FREQ, AUDIO_SIZE, AUDIO_CHANNELS, AUDIO_BUFFER)
    pygame.init()
    pygame.mixer.init()

    # ── GPIO setup (Raspberry Pi only) ────────────────────────────
    _gpio_cleanup = lambda: None   # no-op on non-Pi
    try:
        import RPi.GPIO as GPIO

        _button_map = {
            pin: key
            for pin, key in [
                (GPIO_BUTTON_START,  pygame.K_SPACE),
                (GPIO_BUTTON_SNAP,   pygame.K_SPACE),
                (GPIO_BUTTON_PRINT,  pygame.K_p),
                (GPIO_BUTTON_RETAKE, pygame.K_DELETE),
                (GPIO_BUTTON_QTY_P,  pygame.K_RIGHT),
                (GPIO_BUTTON_QTY_N,  pygame.K_LEFT),
            ]
            if pin is not None
        }

        GPIO.setmode(GPIO.BCM)
        for pin in _button_map:
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        def _gpio_callback(pin):
            key = _button_map.get(pin)
            if key is not None:
                pygame.event.post(
                    pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode="")
                )

        for pin in _button_map:
            GPIO.add_event_detect(
                pin, GPIO.FALLING, callback=_gpio_callback, bouncetime=200
            )

        _gpio_cleanup = GPIO.cleanup
        print(f"GPIO buttons active on pins: {list(_button_map.keys())}")

    except (ImportError, RuntimeError):
        print("GPIO not available — running without arcade buttons")

    # ── Sound effects ──────────────────────────────────────────────
    SFX_DIR     = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sfx")
    snd_beep    = pygame.mixer.Sound(os.path.join(SFX_DIR, "count_down_beep.mp3"))
    snd_shutter = pygame.mixer.Sound(os.path.join(SFX_DIR, "camera_shot.mp3"))

    # ── Display ────────────────────────────────────────────────────
    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    pygame.display.set_caption("Photo Booth")
    pygame.mouse.set_visible(False)
    clock = pygame.time.Clock()
    screen_w, screen_h = screen.get_size()

    # ── Fonts & pre-rendered text ──────────────────────────────────
    font_countdown = pygame.font.SysFont(None, 320)
    font_label     = pygame.font.SysFont(None, 72)
    font_hint      = pygame.font.SysFont(None, 48)

    idle_hint = font_hint.render("Press SPACE to start  ·  ESC to quit", True, (220, 220, 220))
    grid_hint = font_hint.render("← → copies  ·  P to print  ·  DEL to retake  ·  ESC to quit", True, (160, 160, 160))
    photo_labels = [
        font_label.render(f"Photo {i + 1} of {TOTAL_PHOTOS}", True, (255, 255, 255))
        for i in range(TOTAL_PHOTOS)
    ]
    countdown_surfs = {
        n: (font_countdown.render(str(n), True, (0, 0, 0)),
            font_countdown.render(str(n), True, (255, 255, 255)))
        for n in range(1, COUNTDOWN_SECONDS + 2)
    }

    # ── Overlay surfaces ───────────────────────────────────────────
    vignette = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)
    vignette.fill((0, 0, 0, 90))
    flash_surf = pygame.Surface((screen_w, screen_h))
    flash_surf.fill((255, 255, 255))
    dim_surf = pygame.Surface((screen_w, screen_h))
    dim_surf.fill((0, 0, 0))
    dim_surf.set_alpha(140)
    carousel_bar = pygame.Surface((screen_w, CAROUSEL_STRIP_HEIGHT), pygame.SRCALPHA)
    carousel_bar.fill((0, 0, 0, 160))

    # ── State machine ──────────────────────────────────────────────
    state           = "idle"
    countdown_start = 0.0
    skip_countdown  = False
    last_beep_num   = -1
    photo_index     = 0
    thumbnails      = []
    photo_paths     = []
    grid_surfs      = []
    preview_surf    = None
    event_time      = 0.0

    polaroid_surf     = None
    polaroid_rect     = None
    print_phase       = None   # "compose" | "hold" | "slide"
    print_phase_start = 0.0
    print_qty         = PRINT_QTY_DEFAULT   # copies selected by user (1-4)
    prints_done       = 0                   # copies animated so far this session

    carousel_photos    = load_carousel_photos(CAROUSEL_STRIP_HEIGHT)
    carousel_start_time = time.monotonic()
    carousel_y         = screen_h - CAROUSEL_STRIP_HEIGHT

    def clear_session():
        thumbnails.clear()
        photo_paths.clear()
        grid_surfs.clear()

    # ── Main loop ──────────────────────────────────────────────────
    running = True
    while running:
        now = time.monotonic()

        # ── Printing animation ─────────────────────────────────────
        if state == "printing":
            elapsed = now - print_phase_start

            if print_phase == "compose":
                t = min(1.0, elapsed / PRINT_COMPOSE_DUR)
                render_printing_compose(
                    screen, grid_surfs, polaroid_surf, polaroid_rect, t, prints_done
                )
                if elapsed >= PRINT_COMPOSE_DUR:
                    # Send the full print job on the very first copy
                    if prints_done == 0:
                        print_composite(polaroid_surf, print_qty)
                    print_phase = "hold"
                    print_phase_start = now

            elif print_phase == "hold":
                render_printing_hold(
                    screen, polaroid_surf, polaroid_rect, screen_w, screen_h, now,
                    prints_done, print_qty,
                )
                if elapsed >= PRINT_HOLD_DUR:
                    print_phase = "slide"
                    print_phase_start = now

            elif print_phase == "slide":
                t = min(1.0, elapsed / PRINT_SLIDE_DUR)
                render_printing_slide(screen, polaroid_surf, polaroid_rect, t, screen_h)
                if elapsed >= PRINT_SLIDE_DUR:
                    prints_done += 1
                    if prints_done < print_qty:
                        # Another copy to animate — fade in from black
                        print_phase = "compose"
                        print_phase_start = now
                    else:
                        # All done → back to idle
                        state = "idle"
                        print_phase = None
                        polaroid_surf = None
                        prints_done = 0
                        print_qty = PRINT_QTY_DEFAULT
                        photo_index = 0
                        clear_session()
                        carousel_photos = load_carousel_photos(CAROUSEL_STRIP_HEIGHT)
                        carousel_start_time = now

            pygame.display.flip()
            clock.tick(TARGET_FPS)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    running = False
            continue

        # ── Grid ───────────────────────────────────────────────────
        if state == "grid":
            render_grid(screen, grid_surfs, grid_hint, screen_w, screen_h, print_qty)
            pygame.display.flip()
            clock.tick(TARGET_FPS)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_RIGHT:
                        print_qty = min(PRINT_QTY_MAX, print_qty + 1)
                    elif event.key == pygame.K_LEFT:
                        print_qty = max(PRINT_QTY_MIN, print_qty - 1)
                    elif event.key == pygame.K_p:
                        polaroid_surf = build_polaroid_surf(photo_paths, screen_w, screen_h)
                        polaroid_rect = polaroid_surf.get_rect(
                            center=(screen_w // 2, screen_h // 2)
                        )
                        prints_done = 0
                        print_phase = "compose"
                        print_phase_start = now
                        state = "printing"
                    elif event.key in (pygame.K_DELETE, pygame.K_BACKSPACE):
                        state = "idle"
                        photo_index = 0
                        print_qty = PRINT_QTY_DEFAULT
                        clear_session()
                        carousel_photos = load_carousel_photos(CAROUSEL_STRIP_HEIGHT)
                        carousel_start_time = now
            continue

        # ── Live camera feed ───────────────────────────────────────
        live_surf = grab_live_surface(cap, screen_w, screen_h)
        if live_surf is None:
            break
        screen.blit(live_surf, (0, 0))

        # ── Idle ───────────────────────────────────────────────────
        if state == "idle":
            render_idle(screen, carousel_photos, carousel_bar, carousel_y, now,
                        carousel_start_time, idle_hint, screen_w)

        # ── Countdown ──────────────────────────────────────────────
        elif state == "countdown":
            elapsed   = now - countdown_start
            remaining = COUNTDOWN_SECONDS - elapsed

            if remaining <= 0 or skip_countdown:
                skip_countdown = False
                last_beep_num  = -1
                snd_shutter.play()
                result = snap_photo(cap, photo_index, screen_w, screen_h)
                if result:
                    path, thumb, preview_surf = result
                    photo_paths.append(path)
                    thumbnails.append(thumb)
                else:
                    thumbnails.append(None)
                    preview_surf = None
                photo_index += 1
                event_time   = now
                state        = "preview"
            else:
                num = max(1, min(COUNTDOWN_SECONDS + 1, int(remaining) + 1))
                if num != last_beep_num:
                    snd_beep.play()
                    last_beep_num = num
                render_countdown(screen, vignette, countdown_surfs, photo_labels,
                                 photo_index, screen_w, screen_h, num)

        # ── Preview ────────────────────────────────────────────────
        elif state == "preview":
            age = now - event_time
            render_preview(screen, flash_surf, dim_surf, preview_surf, age, screen_w, screen_h)
            if age >= PREVIEW_DURATION:
                if photo_index < TOTAL_PHOTOS:
                    countdown_start = now
                    state = "countdown"
                else:
                    state      = "grid"
                    grid_surfs = build_grid_surfs(photo_paths, screen_w, screen_h)

        draw_thumbnails(screen, thumbnails, screen_w, screen_h)
        pygame.display.flip()
        clock.tick(TARGET_FPS)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE and state == "idle":
                    clear_session()
                    photo_index     = 0
                    last_beep_num   = -1
                    countdown_start = time.monotonic()
                    state           = "countdown"
                elif event.key == pygame.K_SPACE and state == "countdown":
                    skip_countdown = True

    cap.release()
    pygame.quit()
    _gpio_cleanup()


if __name__ == "__main__":
    main()
