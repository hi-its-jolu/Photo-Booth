import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import cv2
import pygame

from config.config import (
    PHOTOS_DIR,
    COUNTDOWN_SECONDS,
    TOTAL_PHOTOS,
    PREVIEW_DURATION,
    CAROUSEL_STRIP_HEIGHT,
)

from image import (
    grab_live_surface,
    snap_photo,
    build_grid_surfs,
    draw_thumbnails,
    load_carousel_photos,
)

from booth import render_idle, render_countdown, render_preview, render_grid


def main():
    os.makedirs(PHOTOS_DIR, exist_ok=True)

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise RuntimeError("Could not open webcam (index 0)")

    pygame.mixer.pre_init(44100, -16, 2, 512)
    pygame.init()
    pygame.mixer.init()

    SFX_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sfx")
    snd_beep    = pygame.mixer.Sound(os.path.join(SFX_DIR, "count_down_beep.mp3"))
    snd_shutter = pygame.mixer.Sound(os.path.join(SFX_DIR, "camera_shot.mp3"))

    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    pygame.display.set_caption("Photo Booth")
    pygame.mouse.set_visible(False)
    clock = pygame.time.Clock()

    screen_w, screen_h = screen.get_size()

    font_countdown = pygame.font.SysFont(None, 320)
    font_label     = pygame.font.SysFont(None, 72)
    font_hint      = pygame.font.SysFont(None, 48)

    idle_hint = font_hint.render("Press SPACE to start  ·  ESC to quit", True, (220, 220, 220))
    grid_hint = font_hint.render("P to print  ·  DEL to retake  ·  ESC to quit", True, (160, 160, 160))
    photo_labels = [
        font_label.render(f"Photo {i + 1} of {TOTAL_PHOTOS}", True, (255, 255, 255))
        for i in range(TOTAL_PHOTOS)
    ]
    countdown_surfs = {
        n: (font_countdown.render(str(n), True, (0, 0, 0)),
            font_countdown.render(str(n), True, (255, 255, 255)))
        for n in range(1, COUNTDOWN_SECONDS + 2)
    }

    vignette = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)
    vignette.fill((0, 0, 0, 90))
    flash_surf = pygame.Surface((screen_w, screen_h))
    flash_surf.fill((255, 255, 255))
    dim_surf = pygame.Surface((screen_w, screen_h))
    dim_surf.fill((0, 0, 0))
    dim_surf.set_alpha(140)
    carousel_bar = pygame.Surface((screen_w, CAROUSEL_STRIP_HEIGHT), pygame.SRCALPHA)
    carousel_bar.fill((0, 0, 0, 160))

    state = "idle"
    countdown_start = 0.0
    skip_countdown = False
    last_beep_num = -1
    photo_index = 0
    thumbnails = []
    photo_paths = []
    grid_surfs = []
    preview_surf = None
    event_time = 0.0

    carousel_photos = load_carousel_photos(CAROUSEL_STRIP_HEIGHT)
    carousel_start_time = time.monotonic()
    carousel_y = screen_h - CAROUSEL_STRIP_HEIGHT

    def clear_session():
        thumbnails.clear()
        photo_paths.clear()
        grid_surfs.clear()

    running = True
    while running:
        now = time.monotonic()

        if state == "grid":
            render_grid(screen, grid_surfs, grid_hint, screen_w, screen_h)
            pygame.display.flip()
            clock.tick(30)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_p:
                        print("Printing photos...")
                    elif event.key in (pygame.K_DELETE, pygame.K_BACKSPACE):
                        state = "idle"
                        photo_index = 0
                        clear_session()
                        carousel_photos = load_carousel_photos(CAROUSEL_STRIP_HEIGHT)
                        carousel_start_time = now
            continue

        live_surf = grab_live_surface(cap, screen_w, screen_h)
        if live_surf is None:
            break
        screen.blit(live_surf, (0, 0))

        if state == "idle":
            render_idle(screen, carousel_photos, carousel_bar, carousel_y, now,
                        carousel_start_time, idle_hint, screen_w)

        elif state == "countdown":
            elapsed = now - countdown_start
            remaining = COUNTDOWN_SECONDS - elapsed
            if remaining <= 0 or skip_countdown:
                skip_countdown = False
                last_beep_num = -1
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
                event_time = now
                state = "preview"
            else:
                num = max(1, min(COUNTDOWN_SECONDS + 1, int(remaining) + 1))
                if num != last_beep_num:
                    snd_beep.play()
                    last_beep_num = num
                render_countdown(screen, vignette, countdown_surfs, photo_labels,
                                 photo_index, screen_w, screen_h, num)

        elif state == "preview":
            age = now - event_time
            render_preview(screen, flash_surf, dim_surf, preview_surf, age, screen_w, screen_h)
            if age >= PREVIEW_DURATION:
                if photo_index < TOTAL_PHOTOS:
                    countdown_start = now
                    state = "countdown"
                else:
                    state = "grid"
                    grid_surfs = build_grid_surfs(photo_paths, screen_w, screen_h)

        draw_thumbnails(screen, thumbnails, screen_w, screen_h)
        pygame.display.flip()
        clock.tick(30)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE and state == "idle":
                    clear_session()
                    photo_index = 0
                    last_beep_num = -1
                    countdown_start = time.monotonic()
                    state = "countdown"
                elif event.key == pygame.K_SPACE and state == "countdown":
                    skip_countdown = True

    cap.release()
    pygame.quit()


if __name__ == "__main__":
    main()
