import math
import pygame
from config.config import (
    CAROUSEL_SCROLL_SPEED, CAROUSEL_PADDING, FLASH_DURATION,
    PRINT_QTY_MIN, PRINT_QTY_MAX,
)

# ── Font cache ────────────────────────────────────────────────────────────────
_fonts: dict = {}

def _font(size: int) -> pygame.font.Font:
    if size not in _fonts:
        _fonts[size] = pygame.font.SysFont(None, size)
    return _fonts[size]


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


def render_grid(screen, grid_surfs, grid_hint, screen_w, screen_h, print_qty=1):
    _BAR_H   = 90
    _MARGIN  = 28
    _BTN_H   = 58
    _CIRC_R  = 27
    _GAP     = 12

    screen.fill((18, 18, 18))

    # ── Photos with drop shadow ────────────────────────────────────
    for item in grid_surfs:
        if item is None:
            continue
        surf, x, y, nw, nh = item
        pygame.draw.rect(screen, (0, 0, 0), (x + 5, y + 5, nw, nh))   # shadow
        screen.blit(surf, (x, y))
        pygame.draw.rect(screen, (210, 210, 210), (x, y, nw, nh), 2)

    # ── Action bar ────────────────────────────────────────────────
    bar_y  = screen_h - _BAR_H
    btn_cy = bar_y + _BAR_H // 2
    btn_top = btn_cy - _BTN_H // 2

    pygame.draw.rect(screen, (24, 24, 24), (0, bar_y, screen_w, _BAR_H))
    pygame.draw.line(screen, (52, 52, 52), (0, bar_y), (screen_w, bar_y), 1)

    # ── PRINT button — blue, right ─────────────────────────────────
    PRINT_W    = 190
    print_rect = pygame.Rect(screen_w - _MARGIN - PRINT_W, btn_top, PRINT_W, _BTN_H)
    pygame.draw.rect(screen, (28, 98, 195), print_rect, border_radius=10)
    pygame.draw.rect(screen, (60, 135, 235), print_rect, 2, border_radius=10)
    screen.blit(
        _font(40).render("PRINT", True, (255, 255, 255)),
        _font(40).render("PRINT", True, (255, 255, 255)).get_rect(center=print_rect.center),
    )
    pk = _font(21).render("P", True, (140, 190, 255))
    screen.blit(pk, (print_rect.left + 8, print_rect.top + 6))

    # ── RETAKE button — red ────────────────────────────────────────
    RETAKE_W    = 172
    retake_rect = pygame.Rect(print_rect.left - _GAP - RETAKE_W, btn_top, RETAKE_W, _BTN_H)
    pygame.draw.rect(screen, (175, 35, 35), retake_rect, border_radius=10)
    pygame.draw.rect(screen, (215, 68, 68), retake_rect, 2, border_radius=10)
    screen.blit(
        _font(40).render("RETAKE", True, (255, 255, 255)),
        _font(40).render("RETAKE", True, (255, 255, 255)).get_rect(center=retake_rect.center),
    )
    rk = _font(21).render("DEL", True, (255, 160, 160))
    screen.blit(rk, (retake_rect.left + 8, retake_rect.top + 6))

    # ── Qty selector — grey circles, left ─────────────────────────
    qty_num_s = _font(54).render(str(print_qty), True, (255, 255, 255))
    qty_lbl_s = _font(27).render("copy" if print_qty == 1 else "copies", True, (120, 120, 120))

    minus_cx = _MARGIN + _CIRC_R
    num_x    = minus_cx + _CIRC_R + 14
    lbl_x    = num_x + qty_num_s.get_width() + 8
    plus_cx  = lbl_x + qty_lbl_s.get_width() + 14 + _CIRC_R

    for cx, active, arrow in [
        (minus_cx, print_qty > PRINT_QTY_MIN, "◀"),
        (plus_cx,  print_qty < PRINT_QTY_MAX, "▶"),
    ]:
        bg  = (68, 68, 68) if active else (36, 36, 36)
        fg  = (205, 205, 205) if active else (62, 62, 62)
        pygame.draw.circle(screen, bg, (cx, btn_cy), _CIRC_R)
        pygame.draw.circle(screen, (100, 100, 100), (cx, btn_cy), _CIRC_R, 2)
        a_s = _font(44).render(arrow, True, fg)
        screen.blit(a_s, a_s.get_rect(center=(cx, btn_cy)))

    screen.blit(qty_num_s, qty_num_s.get_rect(left=num_x, centery=btn_cy))
    screen.blit(qty_lbl_s, qty_lbl_s.get_rect(left=lbl_x, centery=btn_cy + 2))

    # ── Keyboard hints for qty (← →) ──────────────────────────────
    kl = _font(19).render("←", True, (58, 58, 58))
    kr = _font(19).render("→", True, (58, 58, 58))
    screen.blit(kl, kl.get_rect(centerx=minus_cx, top=btn_cy + _CIRC_R + 3))
    screen.blit(kr, kr.get_rect(centerx=plus_cx,  top=btn_cy + _CIRC_R + 3))

    # ── ESC hint — very subtle ─────────────────────────────────────
    esc = _font(20).render("ESC  quit", True, (46, 46, 46))
    screen.blit(esc, esc.get_rect(right=screen_w - 10, bottom=screen_h - 5))


# ── Printing animation phases ─────────────────────────────────────────────────

def render_printing_compose(screen, grid_surfs, polaroid_surf, polaroid_rect, t,
                            prints_done=0):
    """Phase 1: polaroid fades in. Copy 1 fades over the grid; subsequent copies
    fade over a plain dark background."""
    screen.fill((20, 20, 20))
    if prints_done == 0:
        for item in grid_surfs:
            if item is None:
                continue
            surf, x, y, nw, nh = item
            screen.blit(surf, (x, y))
            pygame.draw.rect(screen, (255, 255, 255), (x, y, nw, nh), 2)

    pygame.draw.rect(
        screen, (0, 0, 0),
        (polaroid_rect.x + 10, polaroid_rect.y + 12, polaroid_rect.w, polaroid_rect.h),
    )
    polaroid_surf.set_alpha(int(255 * t))
    screen.blit(polaroid_surf, polaroid_rect)


def render_printing_hold(screen, polaroid_surf, polaroid_rect, screen_w, screen_h, now,
                         prints_done=0, print_qty=1):
    """Phase 2: polaroid fully visible with a pulsing label.
    Shows copy progress when printing multiple copies."""
    screen.fill((20, 20, 20))

    pygame.draw.rect(
        screen, (0, 0, 0),
        (polaroid_rect.x + 10, polaroid_rect.y + 12, polaroid_rect.w, polaroid_rect.h),
    )
    polaroid_surf.set_alpha(255)
    screen.blit(polaroid_surf, polaroid_rect)

    # Label: plain when qty=1, shows progress when qty>1
    if print_qty > 1:
        label = f"Printing copy {prints_done + 1} of {print_qty}…"
    else:
        label = "Printing…"

    pulse     = int(160 + 95 * math.sin(now * 2.8))
    text_surf = _font(64).render(label, True, (255, 255, 255))
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
