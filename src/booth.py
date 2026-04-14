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
    FLASH_DURATION,
    PRINTER_CHECK_INTERVAL
)

from printer import (
    print_photos,
    check_printer_paper,
    check_printer_ink,
    check_printer_connection,
    draw_printer_warning,
)

from image import (
    grab_live_surface,
    snap_photo,
    build_grid_surfs,
    draw_thumbnails
)



# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    os.makedirs(PHOTOS_DIR, exist_ok=True)

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise RuntimeError("Could not open webcam (index 0)")

    pygame.init()
    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    pygame.display.set_caption("Photo Booth")
    pygame.mouse.set_visible(False)
    clock = pygame.time.Clock()

    screen_w, screen_h = screen.get_size()

    font_countdown = pygame.font.SysFont(None, 320)
    font_label     = pygame.font.SysFont(None, 72)
    font_hint      = pygame.font.SysFont(None, 48)

    # Pre-render text surfaces that are static or change at most once per photo
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

    # Pre-allocate overlay surfaces reused every frame
    vignette = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)
    vignette.fill((0, 0, 0, 90))
    flash_surf = pygame.Surface((screen_w, screen_h))
    flash_surf.fill((255, 255, 255))
    dim_surf = pygame.Surface((screen_w, screen_h))
    dim_surf.fill((0, 0, 0))
    dim_surf.set_alpha(140)

    # ── Printer status ─────────────────────────────────────────────
    printer_ok = check_printer_connection()
    printer_last_check = time.monotonic()

    # ── State machine ──────────────────────────────────────────────
    # "idle"      → waiting for SPACE
    # "countdown" → timer running, then snap photo
    # "preview"   → flash then brief photo preview
    # "grid"      → all photos taken, show grid for action selection
    state = "idle"
    countdown_start = 0.0
    skip_countdown = False
    photo_index = 0
    thumbnails = []
    photo_paths = []
    grid_surfs = []
    preview_surf = None
    event_time = 0.0

    def clear_session():
        thumbnails.clear()
        photo_paths.clear()
        grid_surfs.clear()

    running = True
    while running:
        now = time.monotonic()

        # ── Periodic printer check ─────────────────────────────────
        if now - printer_last_check >= PRINTER_CHECK_INTERVAL:
            printer_ok = check_printer_connection()
            printer_last_check = now

        # ── Grid state: no camera needed, render from cache ────────
        if state == "grid":
            screen.fill((20, 20, 20))
            for item in grid_surfs:
                if item is None:
                    continue

                surf, x, y, nw, nh = item
                screen.blit(surf, (x, y))

                pygame.draw.rect(screen, (255, 255, 255), (x, y, nw, nh), 2)

            screen.blit(grid_hint, grid_hint.get_rect(centerx=screen_w // 2, bottom=screen_h - 16))
            if not printer_ok:
                draw_printer_warning(screen)
            pygame.display.flip()
            clock.tick(30)
            
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_p:
                        print_photos(photo_paths)
                    elif event.key == pygame.K_DELETE or event.key == pygame.K_BACKSPACE:
                        state = "idle"
                        photo_index = 0
                        clear_session()
            continue

        # ── Live camera feed ───────────────────────────────────────
        live_surf = grab_live_surface(cap, screen_w, screen_h)
        if live_surf is None:
            break
        screen.blit(live_surf, (0, 0))

        # ── State rendering ────────────────────────────────────────
        if state == "idle":
            screen.blit(idle_hint, idle_hint.get_rect(centerx=screen_w // 2, bottom=screen_h - 20))

        elif state == "countdown":
            elapsed = now - countdown_start
            remaining = COUNTDOWN_SECONDS - elapsed

            if remaining <= 0 or skip_countdown:
                skip_countdown = False
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
                shadow, text = countdown_surfs[num]
                cx, cy = screen_w // 2, screen_h // 2 - 30
                screen.blit(vignette, (0, 0))
                screen.blit(shadow, shadow.get_rect(center=(cx + 5, cy + 5)))
                screen.blit(text,   text.get_rect(center=(cx, cy)))
                screen.blit(photo_labels[photo_index],
                            photo_labels[photo_index].get_rect(centerx=screen_w // 2, top=40))

        elif state == "preview":
            age = now - event_time
            if age < FLASH_DURATION:
                flash_surf.set_alpha(int(255 * (1.0 - age / FLASH_DURATION)))
                screen.blit(flash_surf, (0, 0))
            elif preview_surf is not None:
                screen.blit(dim_surf, (0, 0))
                pr = preview_surf.get_rect(center=(screen_w // 2, screen_h // 2 - 30))
                screen.blit(preview_surf, pr)
                pygame.draw.rect(screen, (255, 255, 255), pr.inflate(6, 6), 3)
            if age >= PREVIEW_DURATION:
                if photo_index < TOTAL_PHOTOS:
                    countdown_start = now
                    state = "countdown"
                else:
                    state = "grid"
                    grid_surfs = build_grid_surfs(photo_paths, screen_w, screen_h)

        # ── Thumbnails, flip, events ───────────────────────────────
        draw_thumbnails(screen, thumbnails, screen_w, screen_h)
        if not printer_ok:
            draw_printer_warning(screen)
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
                    countdown_start = time.monotonic()
                    state = "countdown"
                elif event.key == pygame.K_SPACE and state == "countdown":
                    skip_countdown = True

    cap.release()
    pygame.quit()


if __name__ == "__main__":
    main()
