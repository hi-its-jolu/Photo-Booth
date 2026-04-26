import math
import pygame
from config.config import CAROUSEL_SCROLL_SPEED, CAROUSEL_PADDING, FLASH_DURATION


def render_idle(screen, carousel_photos, carousel_bar, carousel_y, now,
                carousel_start_time, idle_hint, screen_w):
    if carousel_photos:
        total_w = sum(s.get_width() + CAROUSEL_PADDING for s in carousel_photos)
        offset = (CAROUSEL_SCROLL_SPEED * (now - carousel_start_time)) % total_w
        screen.blit(carousel_bar, (0, carousel_y))
        x = -offset
        while x < screen_w:
            for surf in carousel_photos:
                if x + surf.get_width() >= 0:
                    screen.blit(surf, (int(x), carousel_y))
                x += surf.get_width() + CAROUSEL_PADDING
                if x >= screen_w:
                    break
    screen.blit(idle_hint, idle_hint.get_rect(centerx=screen_w // 2, bottom=carousel_y - 12))


def render_countdown(screen, vignette, countdown_surfs, photo_labels,
                     photo_index, screen_w, screen_h, num):
    shadow, text = countdown_surfs[num]
    cx, cy = screen_w // 2, screen_h // 2 - 30
    screen.blit(vignette, (0, 0))
    screen.blit(shadow, shadow.get_rect(center=(cx + 5, cy + 5)))
    screen.blit(text,   text.get_rect(center=(cx, cy)))
    screen.blit(photo_labels[photo_index],
                photo_labels[photo_index].get_rect(centerx=screen_w // 2, top=40))


def render_preview(screen, flash_surf, dim_surf, preview_surf, age, screen_w, screen_h):
    if age < FLASH_DURATION:
        flash_surf.set_alpha(int(255 * (1.0 - age / FLASH_DURATION)))
        screen.blit(flash_surf, (0, 0))
    elif preview_surf is not None:
        screen.blit(dim_surf, (0, 0))
        pr = preview_surf.get_rect(center=(screen_w // 2, screen_h // 2 - 30))
        screen.blit(preview_surf, pr)
        pygame.draw.rect(screen, (255, 255, 255), pr.inflate(6, 6), 3)


def render_grid(screen, grid_surfs, grid_hint, screen_w, screen_h):
    screen.fill((20, 20, 20))
    for item in grid_surfs:
        if item is None:
            continue
        surf, x, y, nw, nh = item
        screen.blit(surf, (x, y))
        pygame.draw.rect(screen, (255, 255, 255), (x, y, nw, nh), 2)
    screen.blit(grid_hint, grid_hint.get_rect(centerx=screen_w // 2, bottom=screen_h - 16))


# ── Printing animation phases ─────────────────────────────────────────────────

def render_printing_compose(screen, grid_surfs, polaroid_surf, polaroid_rect, t):
    """Phase 1: polaroid fades in over the grid. t runs 0 → 1."""
    screen.fill((20, 20, 20))
    for item in grid_surfs:
        if item is None:
            continue
        surf, x, y, nw, nh = item
        screen.blit(surf, (x, y))
        pygame.draw.rect(screen, (255, 255, 255), (x, y, nw, nh), 2)

    # Drop shadow
    pygame.draw.rect(
        screen, (0, 0, 0),
        (polaroid_rect.x + 10, polaroid_rect.y + 12, polaroid_rect.w, polaroid_rect.h),
    )
    polaroid_surf.set_alpha(int(255 * t))
    screen.blit(polaroid_surf, polaroid_rect)


def render_printing_hold(screen, polaroid_surf, polaroid_rect, screen_w, screen_h, now):
    """Phase 2: polaroid is fully visible with a pulsing 'Printing…' label."""
    screen.fill((20, 20, 20))

    # Drop shadow
    pygame.draw.rect(
        screen, (0, 0, 0),
        (polaroid_rect.x + 10, polaroid_rect.y + 12, polaroid_rect.w, polaroid_rect.h),
    )
    polaroid_surf.set_alpha(255)
    screen.blit(polaroid_surf, polaroid_rect)

    # Pulsing "Printing…" text centred on screen
    font = pygame.font.SysFont(None, 64)
    pulse = int(160 + 95 * math.sin(now * 2.8))   # 55 → 255
    text_surf = font.render("Printing…", True, (255, 255, 255))
    text_surf.set_alpha(pulse)
    screen.blit(text_surf, text_surf.get_rect(
        centerx=screen_w // 2,
        centery=polaroid_rect.bottom + (screen_h - polaroid_rect.bottom) // 2,
    ))


def render_printing_slide(screen, polaroid_surf, polaroid_rect, t, screen_h):
    """Phase 3: polaroid accelerates down and off screen. t runs 0 → 1."""
    screen.fill((20, 20, 20))
    dy = int((t * t) * (screen_h - polaroid_rect.top + 60))   # ease-in
    moved = polaroid_rect.move(0, dy)
    pygame.draw.rect(
        screen, (0, 0, 0),
        (moved.x + 10, moved.y + 12, moved.w, moved.h),
    )
    screen.blit(polaroid_surf, moved)
