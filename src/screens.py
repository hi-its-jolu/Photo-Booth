import math
import os
import pygame

from config.config import (
    ASSETS_DIR, TOTAL_PHOTOS,
    CAROUSEL_SCROLL_SPEED, CAROUSEL_PADDING, CAROUSEL_STRIP_HEIGHT, FLASH_DURATION,
    PRINT_QTY_MIN, PRINT_QTY_MAX, PREVIEW_URGENT_AT,
    THUMB_HEIGHT, THUMB_PADDING, THUMB_MARGIN_BOTTOM,
    GROUND, INK, ACCENT, ACCENT_DARK, NEUTRAL_200, NEUTRAL_400, NEUTRAL_500,
    NEUTRAL_600, NEUTRAL_700, GREEN, GREEN_DARK, WHITE,
)
from composite import REVIEW_GRID_W, REVIEW_GRID_H, REVIEW_GRID_Y, REVIEW_MAT_PAD

# ── UI text constants ─────────────────────────────────────────────────────────
_TXT_PRINTING     = "Printing…"
_TXT_PRINTING_N   = "Printing copy {done} of {total}…"
_TXT_INK          = "Ink"
_TXT_PAPER        = "Paper: {n} sheets"
_TXT_PRINTER_ICON = "\U0001f5a8  {name}"
_TXT_NO_PRINTER   = "No Printer Found."

# ── Printer status colours ────────────────────────────────────────────────────
_STATUS_COLOR = {
    "idle":     (80,  200,  80),
    "printing": (255, 165,   0),
    "offline":  (255,  80,  80),
}

_INK_NAMED: dict[str, tuple] = {
    "black":         ( 55,  55,  55),
    "photo black":   ( 65,  65,  65),
    "cyan":          (  0, 188, 212),
    "light cyan":    (100, 210, 230),
    "magenta":       (233,  30,  99),
    "light magenta": (230, 130, 180),
    "yellow":        (220, 180,   0),
    "white":         (210, 210, 210),
    "gray":          (140, 140, 140),
    "light gray":    (185, 185, 185),
    "matte black":   ( 80,  80,  80),
}

# ── Font cache (legacy SysFont, used by printer overlays only) ────────────────
_fonts: dict[int, pygame.font.Font] = {}

def _font(size: int) -> pygame.font.Font:
    if size not in _fonts:
        _fonts[size] = pygame.font.SysFont(None, size)
    return _fonts[size]


# ── Archivo font loader (2b / 1d screens) ─────────────────────────────────────
_FONT_DIR   = os.path.join(ASSETS_DIR, "fonts")
_FONT_FILES = {
    600: os.path.join(_FONT_DIR, "Archivo-SemiBold.ttf"),
    700: os.path.join(_FONT_DIR, "Archivo-Bold.ttf"),
    800: os.path.join(_FONT_DIR, "Archivo-ExtraBold.ttf"),
}
_archivo_cache: dict[tuple[int, int], pygame.font.Font] = {}

def _archivo(weight: int, size: int) -> pygame.font.Font:
    """Archivo TTF at `weight` (600/700/800) and pixel `size`; falls back to a
    bold system font if the TTF isn't present in assets/fonts/."""
    key = (weight, size)
    if key not in _archivo_cache:
        path = _FONT_FILES.get(weight)
        font = None
        if path and os.path.isfile(path):
            try:
                font = pygame.font.Font(path, size)
            except Exception:
                font = None
        _archivo_cache[key] = font or pygame.font.SysFont(None, size, bold=True)
    return _archivo_cache[key]


_tracked_cache: dict[tuple, pygame.Surface] = {}

def _tracked(weight: int, size: int, text: str, color, tracking_em: float = 0.0) -> pygame.Surface:
    """Render `text` with CSS-style letter-spacing (`tracking_em` × size), cached."""
    key = (weight, size, text, color, tracking_em)
    surf = _tracked_cache.get(key)
    if surf is not None:
        return surf
    font     = _archivo(weight, size)
    tracking = round(tracking_em * size)
    if tracking <= 0 or len(text) <= 1:
        surf = font.render(text, True, color)
    else:
        glyphs  = [font.render(ch, True, color) for ch in text]
        total_w = sum(g.get_width() for g in glyphs) + tracking * (len(glyphs) - 1)
        h       = max(g.get_height() for g in glyphs)
        surf    = pygame.Surface((total_w, h), pygame.SRCALPHA)
        x = 0
        for g in glyphs:
            surf.blit(g, (x, 0))
            x += g.get_width() + tracking
    _tracked_cache[key] = surf
    return surf


def _pulse_alpha(now: float, period: float) -> int:
    """0.775 + 0.225*sin(2*pi*t/period), mapped to 0-255 — the soft-pulse used
    for the live dot and the start/print caps."""
    return int(round(255 * (0.775 + 0.225 * math.sin(2 * math.pi * now / period))))


# ── Logo cache ────────────────────────────────────────────────────────────────
_logo_cache: dict[int, pygame.Surface | None] = {}

def _get_logo(width: int) -> pygame.Surface | None:
    if width not in _logo_cache:
        try:
            from composite import load_logo_surf
            _logo_cache[width] = load_logo_surf(width)
        except Exception:
            _logo_cache[width] = None
    return _logo_cache[width]


_logo_aspect: float | None = None

def _get_logo_by_height(height: int) -> pygame.Surface | None:
    """Like _get_logo, but sized by target height (aspect preserved)."""
    global _logo_aspect
    if _logo_aspect is None:
        probe = _get_logo(400)
        if probe is None:
            return None
        _logo_aspect = probe.get_width() / probe.get_height()
    return _get_logo(max(1, round(height * _logo_aspect)))


# ── Ink colour helper ─────────────────────────────────────────────────────────

def _ink_color(color_str: str) -> tuple:
    s = color_str.strip().lower()
    if s in _INK_NAMED:
        return _INK_NAMED[s]
    if s.startswith("#") and len(s) == 7:
        try:
            r, g, b = int(s[1:3], 16), int(s[3:5], 16), int(s[5:7], 16)
            if r < 40 and g < 40 and b < 40:
                return (60, 60, 60)
            if r > 200 and g > 200 and b < 60:
                return (220, 180, 0)
            return (r, g, b)
        except ValueError:
            pass
    return (160, 160, 160)


# ── Shared helpers ────────────────────────────────────────────────────────────

def _draw_shadow_composite(screen, surf, rect):
    pygame.draw.rect(screen, (0, 0, 0), (rect.x + 10, rect.y + 12, rect.w, rect.h))
    screen.blit(surf, rect)


# ── Idle screen ("2b" — ruled window) ──────────────────────────────────────────

_IDLE_MARGIN      = 56
_IDLE_HEADER_Y    = 40
_IDLE_LOGO_H      = 104
_IDLE_RULE_Y      = 170
_IDLE_VF_TOP      = 212
_IDLE_VF_W        = 996
_IDLE_VF_H        = 560
_IDLE_VF_BORDER   = 2
_IDLE_TICK_LEN    = 44
_IDLE_LABEL_Y     = 800
_IDLE_STRIP_Y     = 836
_IDLE_STRIP_INSET = 6
_IDLE_RAIL_H      = 92
_IDLE_START_D     = 58
_IDLE_START_DROP  = 4

# Interior size the live camera feed should be captured/cropped to for the
# viewfinder box (box size minus the 2px border on each side).
IDLE_VIEWFINDER_INNER = (_IDLE_VF_W - _IDLE_VF_BORDER * 2, _IDLE_VF_H - _IDLE_VF_BORDER * 2)

_TXT_LIVE    = "LIVE"
_TXT_EARLIER = "EARLIER TONIGHT"
_TXT_START   = "START"
_TXT_PRESS   = "PRESS THE GREEN BUTTON — {n} PHOTOS, ABOUT 30 SECONDS"


def _draw_idle_header(screen, now: float, screen_w: int):
    logo = _get_logo_by_height(_IDLE_LOGO_H)
    if logo is not None:
        screen.blit(logo, (_IDLE_MARGIN, _IDLE_HEADER_Y))
    row_cy = _IDLE_HEADER_Y + _IDLE_LOGO_H // 2

    live_label = _tracked(700, 19, _TXT_LIVE, NEUTRAL_600, 0.20)
    dot, gap   = 14, 14
    label_x    = (screen_w - _IDLE_MARGIN) - live_label.get_width()
    dot_x      = label_x - gap - dot

    dot_surf = pygame.Surface((dot, dot), pygame.SRCALPHA)
    dot_surf.fill((*ACCENT, _pulse_alpha(now, 1.8)))
    screen.blit(dot_surf, (dot_x, row_cy - dot // 2))
    screen.blit(live_label, (label_x, row_cy - live_label.get_height() // 2))


def _draw_idle_viewfinder(screen, live_surf, screen_w: int):
    box_x, box_y = (screen_w - _IDLE_VF_W) // 2, _IDLE_VF_TOP
    pygame.draw.rect(screen, (0, 0, 0), (box_x, box_y, _IDLE_VF_W, _IDLE_VF_H))
    if live_surf is not None:
        screen.blit(live_surf, (box_x + _IDLE_VF_BORDER, box_y + _IDLE_VF_BORDER))
    pygame.draw.rect(screen, INK, (box_x, box_y, _IDLE_VF_W, _IDLE_VF_H), _IDLE_VF_BORDER)

    L, T = _IDLE_TICK_LEN, _IDLE_VF_BORDER
    for corner_x, corner_y, sx, sy in [
        (box_x,               box_y,               1, 1),
        (box_x + _IDLE_VF_W,  box_y,              -1, 1),
        (box_x,               box_y + _IDLE_VF_H,  1, -1),
        (box_x + _IDLE_VF_W,  box_y + _IDLE_VF_H, -1, -1),
    ]:
        hx = corner_x if sx > 0 else corner_x - L
        hy = corner_y if sy > 0 else corner_y - T
        pygame.draw.rect(screen, (255, 255, 255), (hx, hy, L, T))
        vx = corner_x if sx > 0 else corner_x - T
        vy = corner_y if sy > 0 else corner_y - L
        pygame.draw.rect(screen, (255, 255, 255), (vx, vy, T, L))


def _draw_idle_labels(screen, photo_count: int, screen_w: int):
    left  = _tracked(700, 18, _TXT_EARLIER, NEUTRAL_600, 0.22)
    right = _tracked(700, 18, f"{photo_count} PHOTOS SO FAR", NEUTRAL_600, 0.22)
    screen.blit(left,  left.get_rect(left=_IDLE_MARGIN, bottom=_IDLE_LABEL_Y))
    screen.blit(right, right.get_rect(right=screen_w - _IDLE_MARGIN, bottom=_IDLE_LABEL_Y))


def _draw_idle_carousel(screen, carousel_photos, carousel_start: float, now: float, screen_w: int):
    left, right = _IDLE_MARGIN, screen_w - _IDLE_MARGIN
    strip_h = CAROUSEL_STRIP_HEIGHT
    pygame.draw.line(screen, INK, (left, _IDLE_STRIP_Y), (right, _IDLE_STRIP_Y), 2)
    pygame.draw.line(screen, INK, (left, _IDLE_STRIP_Y + strip_h), (right, _IDLE_STRIP_Y + strip_h), 2)
    if not carousel_photos:
        return

    thumb_y   = _IDLE_STRIP_Y + _IDLE_STRIP_INSET
    total_w   = sum(s.get_width() + CAROUSEL_PADDING for s in carousel_photos)
    offset    = (CAROUSEL_SCROLL_SPEED * (now - carousel_start)) % total_w
    prev_clip = screen.get_clip()
    screen.set_clip(pygame.Rect(left, _IDLE_STRIP_Y, right - left, strip_h))
    x = left - offset
    while x < right:
        for surf in carousel_photos:
            if x + surf.get_width() >= left:
                screen.blit(surf, (int(x), thumb_y))
            x += surf.get_width() + CAROUSEL_PADDING
            if x >= right:
                break
    screen.set_clip(prev_clip)


def _draw_idle_rail(screen, now: float, screen_w: int, screen_h: int):
    rail_y = screen_h - _IDLE_RAIL_H
    pygame.draw.rect(screen, NEUTRAL_200, (0, rail_y, screen_w, _IDLE_RAIL_H))
    pygame.draw.line(screen, INK, (0, rail_y), (screen_w, rail_y), 2)
    rail_cy = rail_y + _IDLE_RAIL_H // 2

    press = _archivo(800, 30).render(_TXT_PRESS.format(n=TOTAL_PHOTOS), True, INK)
    screen.blit(press, press.get_rect(left=_IDLE_MARGIN, centery=rail_cy))

    start_label   = _tracked(800, 22, _TXT_START, INK, 0.16)
    d, drop, gap  = _IDLE_START_D, _IDLE_START_DROP, 16
    cx = (screen_w - _IDLE_MARGIN) - start_label.get_width() - gap - d // 2

    pygame.draw.circle(screen, GREEN_DARK, (cx, rail_cy + drop), d // 2)
    alpha = _pulse_alpha(now, 1.6)
    cap   = pygame.Surface((d + 4, d + 4), pygame.SRCALPHA)
    c     = d // 2 + 2
    pygame.draw.circle(cap, (*GREEN, alpha), (c, c), d // 2)
    pygame.draw.circle(cap, (*INK, alpha),   (c, c), d // 2, 2)
    screen.blit(cap, (cx - c, rail_cy - c))
    screen.blit(start_label, start_label.get_rect(left=cx + d // 2 + gap, centery=rail_cy))


def render_idle(screen, live_surf, carousel_photos, carousel_start: float, now: float,
                photo_count: int, screen_w: int, screen_h: int):
    screen.fill(GROUND)
    _draw_idle_header(screen, now, screen_w)
    pygame.draw.line(screen, INK, (_IDLE_MARGIN, _IDLE_RULE_Y), (screen_w - _IDLE_MARGIN, _IDLE_RULE_Y), 2)
    _draw_idle_viewfinder(screen, live_surf, screen_w)
    _draw_idle_labels(screen, photo_count, screen_w)
    _draw_idle_carousel(screen, carousel_photos, carousel_start, now, screen_w)
    _draw_idle_rail(screen, now, screen_w, screen_h)


# ── Countdown screen ──────────────────────────────────────────────────────────

def render_countdown(screen, vignette, countdown_surfs, photo_labels,
                     photo_index: int, screen_w: int, screen_h: int, num: int):
    shadow, text = countdown_surfs[num]
    cx, cy = screen_w // 2, screen_h // 2 - 30
    screen.blit(vignette, (0, 0))
    screen.blit(shadow, shadow.get_rect(center=(cx + 5, cy + 5)))
    screen.blit(text,   text.get_rect(center=(cx, cy)))
    lbl = photo_labels[photo_index]
    screen.blit(lbl, lbl.get_rect(centerx=screen_w // 2, top=40))


# ── Photo flash preview screen ────────────────────────────────────────────────

def render_preview(screen, flash_surf, dim_surf, preview_surf, age: float,
                   screen_w: int, screen_h: int):
    if age < FLASH_DURATION:
        flash_surf.set_alpha(int(255 * (1.0 - age / FLASH_DURATION)))
        screen.blit(flash_surf, (0, 0))
    elif preview_surf is not None:
        screen.blit(dim_surf, (0, 0))
        pr = preview_surf.get_rect(center=(screen_w // 2, screen_h // 2 - 30))
        screen.blit(preview_surf, pr)
        pygame.draw.rect(screen, (255, 255, 255), pr.inflate(6, 6), 3)


# ── Preview / review screen ("1d" — hardware-mapped) ──────────────────────────

_REV_MARGIN       = 56
_REV_PLATE        = 112
_REV_HEADER_Y     = 44
_REV_RULE_Y       = 184
_REV_RAIL_TOP     = 836
_REV_FLASH_PERIOD = 0.7
_REV_FLASH_DIM    = 0.18

_TXT_SECONDS  = "SECONDS TO DECIDE"
_TXT_LET_GO   = "PRINT IT OR LET IT GO"
_TXT_FEWER    = "FEWER"
_TXT_MORE     = "MORE"
_TXT_COPIES2  = "COPIES"
_TXT_SCAN     = "SCAN TO DOWNLOAD"
_TXT_DISCARD  = "DISCARD"
_TXT_PRINT2   = "PRINT"


def _draw_review_header(screen, now: float, time_left: float, screen_w: int):
    secs   = max(0, math.ceil(time_left))
    urgent = time_left <= PREVIEW_URGENT_AT

    plate = pygame.Surface((_REV_PLATE, _REV_PLATE), pygame.SRCALPHA)
    plate.fill((*(ACCENT if urgent else INK), 255))
    num = _archivo(800, 60).render(f"{secs:02d}", True, GROUND)
    plate.blit(num, num.get_rect(center=(_REV_PLATE // 2, _REV_PLATE // 2)))
    if urgent and ((now % _REV_FLASH_PERIOD) / _REV_FLASH_PERIOD) >= 0.5:
        plate.set_alpha(round(255 * _REV_FLASH_DIM))
    screen.blit(plate, (_REV_MARGIN, _REV_HEADER_Y))

    line1 = _tracked(700, 19, _TXT_SECONDS, NEUTRAL_600, 0.20)
    line2 = _tracked(700, 19, _TXT_LET_GO, INK, 0.20)
    tx = _REV_MARGIN + _REV_PLATE + 18
    block_h = line1.get_height() + line2.get_height() + 4
    top = _REV_HEADER_Y + (_REV_PLATE - block_h) // 2
    screen.blit(line1, (tx, top))
    screen.blit(line2, (tx, top + line1.get_height() + 4))


def _draw_review_grid(screen, grid_surfs: list, screen_w: int):
    for item in grid_surfs:
        if item is None:
            continue
        surf, cx, cy, cw, ch = item
        pygame.draw.rect(screen, WHITE, (cx, cy, cw, ch))
        if surf is not None:
            screen.blit(surf, (cx + REVIEW_MAT_PAD, cy + REVIEW_MAT_PAD))
        pygame.draw.rect(screen, INK, (cx, cy, cw, ch), 2)

    grid_x = (screen_w - REVIEW_GRID_W) // 2
    logo = _get_logo(340)
    if logo is not None:
        screen.blit(logo, logo.get_rect(
            center=(grid_x + REVIEW_GRID_W // 2, REVIEW_GRID_Y + REVIEW_GRID_H // 2)))


def _draw_stepper_cap(screen, cx: int, cy: int, d: int, active: bool, glyph: str):
    alpha = 255 if active else round(255 * 0.45)
    pygame.draw.circle(screen, NEUTRAL_400, (cx, cy + 6), d // 2)
    cap = pygame.Surface((d + 4, d + 4), pygame.SRCALPHA)
    c   = d // 2 + 2
    pygame.draw.circle(cap, (*WHITE, alpha), (c, c), d // 2)
    pygame.draw.circle(cap, (*INK, alpha),   (c, c), d // 2, 2)
    pygame.draw.rect(cap, (*INK, alpha), (c - 19, c - 3, 38, 7))
    if glyph == "plus":
        pygame.draw.rect(cap, (*INK, alpha), (c - 3, c - 19, 7, 38))
    screen.blit(cap, (cx - c, cy - c))


def _draw_stepper(screen, x: int, rail_y: int, rail_h: int, print_qty: int):
    d, gap_lbl, cap_gap = 96, 10, 14
    fewer_on, more_on = print_qty > PRINT_QTY_MIN, print_qty < PRINT_QTY_MAX
    fewer_lbl = _tracked(700, 17, _TXT_FEWER, NEUTRAL_700, 0.16)
    more_lbl  = _tracked(700, 17, _TXT_MORE,  NEUTRAL_700, 0.16)
    copies_lbl = _tracked(700, 18, _TXT_COPIES2, NEUTRAL_600, 0.20)
    qty_num  = _archivo(800, 76).render(str(print_qty), True, INK)
    qty_word = _tracked(700, 24, "COPY" if print_qty == 1 else "COPIES", NEUTRAL_700, 0.12)

    cap_stack_h   = d + gap_lbl + max(fewer_lbl.get_height(), more_lbl.get_height())
    row_h         = max(qty_num.get_height(), qty_word.get_height())
    text_block_h  = copies_lbl.get_height() + row_h
    col_h         = max(cap_stack_h, text_block_h)
    col_bottom    = rail_y + rail_h // 2 + col_h // 2

    cap_top  = col_bottom - cap_stack_h
    cap_cy   = cap_top + d // 2
    fewer_cx = x + d // 2
    more_cx  = fewer_cx + d + cap_gap

    _draw_stepper_cap(screen, fewer_cx, cap_cy, d, fewer_on, "minus")
    screen.blit(fewer_lbl, fewer_lbl.get_rect(centerx=fewer_cx, top=cap_top + d + gap_lbl))
    _draw_stepper_cap(screen, more_cx, cap_cy, d, more_on, "plus")
    screen.blit(more_lbl, more_lbl.get_rect(centerx=more_cx, top=cap_top + d + gap_lbl))

    text_top   = col_bottom - text_block_h
    divider_x  = more_cx + d // 2 + 26
    pygame.draw.line(screen, INK, (divider_x, min(cap_top, text_top)), (divider_x, col_bottom), 2)

    tx = divider_x + 26
    screen.blit(copies_lbl, (tx, text_top))
    row_y = text_top + copies_lbl.get_height()
    screen.blit(qty_num,  (tx, row_y + row_h - qty_num.get_height()))
    screen.blit(qty_word, (tx + qty_num.get_width() + 10, row_y + row_h - qty_word.get_height()))


def _draw_review_qr(screen, qr_surf, screen_w: int, rail_y: int, rail_h: int):
    if qr_surf is None:
        return
    box, gap = 140, 10   # 8px inner padding is implicit: 140 - 2*8 = 124 = qr_surf size
    label = _tracked(700, 19, _TXT_SCAN, INK, 0.20)
    stack_h = box + gap + label.get_height()
    top = rail_y + (rail_h - stack_h) // 2

    box_rect = pygame.Rect(0, 0, box, box)
    box_rect.centerx, box_rect.top = screen_w // 2, top
    pygame.draw.rect(screen, WHITE, box_rect)
    pygame.draw.rect(screen, INK, box_rect, 2)
    screen.blit(qr_surf, qr_surf.get_rect(center=box_rect.center))
    screen.blit(label, label.get_rect(centerx=screen_w // 2, top=box_rect.bottom + gap))


def _draw_review_actions(screen, right_edge: int, rail_y: int, rail_h: int, print_qty: int):
    discard_lbl = _tracked(800, 19, _TXT_DISCARD, INK, 0.16)
    qty_word    = "COPY" if print_qty == 1 else "COPIES"
    print_lbl   = _tracked(800, 19, f"PRINT {print_qty} {qty_word}", INK, 0.16)

    d_disc, d_print, action_gap, lbl_gap = 112, 148, 28, 10
    disc_h  = d_disc  + lbl_gap + discard_lbl.get_height()
    print_h = d_print + lbl_gap + print_lbl.get_height()
    col_bottom = rail_y + rail_h // 2 + max(disc_h, print_h) // 2

    print_cx = right_edge - d_print // 2
    disc_cx  = print_cx - d_print // 2 - action_gap - d_disc // 2
    disc_cy  = col_bottom - discard_lbl.get_height() - lbl_gap - d_disc // 2
    print_cy = col_bottom - print_lbl.get_height()   - lbl_gap - d_print // 2

    # Discard
    pygame.draw.circle(screen, NEUTRAL_500, (disc_cx, disc_cy + 6), d_disc // 2)
    pygame.draw.circle(screen, INK, (disc_cx, disc_cy), d_disc // 2)
    pygame.draw.circle(screen, INK, (disc_cx, disc_cy), d_disc // 2, 2)
    half = 16
    pygame.draw.line(screen, WHITE, (disc_cx - half, disc_cy - half), (disc_cx + half, disc_cy + half), 6)
    pygame.draw.line(screen, WHITE, (disc_cx - half, disc_cy + half), (disc_cx + half, disc_cy - half), 6)
    screen.blit(discard_lbl, discard_lbl.get_rect(centerx=disc_cx, top=disc_cy + d_disc // 2 + lbl_gap))

    # Print
    pygame.draw.circle(screen, ACCENT_DARK, (print_cx, print_cy + 8), d_print // 2)
    pygame.draw.circle(screen, ACCENT, (print_cx, print_cy), d_print // 2)
    pygame.draw.circle(screen, ACCENT_DARK, (print_cx, print_cy), d_print // 2, 2)
    print_word = _tracked(800, 30, _TXT_PRINT2, WHITE, 0.06)
    screen.blit(print_word, print_word.get_rect(center=(print_cx, print_cy)))
    screen.blit(print_lbl, print_lbl.get_rect(centerx=print_cx, top=print_cy + d_print // 2 + lbl_gap))


def render_grid(screen, grid_surfs: list, screen_w: int, screen_h: int,
                now: float, time_left: float, print_qty: int = 1, qr_surf=None):
    screen.fill(GROUND)
    _draw_review_header(screen, now, time_left, screen_w)
    pygame.draw.line(screen, INK, (_REV_MARGIN, _REV_RULE_Y), (screen_w - _REV_MARGIN, _REV_RULE_Y), 2)
    _draw_review_grid(screen, grid_surfs, screen_w)

    rail_y, rail_h = _REV_RAIL_TOP, screen_h - _REV_RAIL_TOP
    pygame.draw.rect(screen, NEUTRAL_200, (0, rail_y, screen_w, rail_h))
    pygame.draw.line(screen, INK, (0, rail_y), (screen_w, rail_y), 2)

    _draw_stepper(screen, _REV_MARGIN, rail_y, rail_h, print_qty)
    _draw_review_qr(screen, qr_surf, screen_w, rail_y, rail_h)
    _draw_review_actions(screen, screen_w - _REV_MARGIN, rail_y, rail_h, print_qty)


# ── Printing animation ────────────────────────────────────────────────────────

def render_printing_compose(screen, grid_surfs: list, composite_surf, composite_rect,
                            t: float, prints_done: int = 0):
    """Phase 1: composite fades in over the grid (first copy) or black (subsequent)."""
    screen.fill((20, 20, 20))
    if prints_done == 0:
        for item in grid_surfs:
            if item is None:
                continue
            surf, x, y, nw, nh = item
            if surf is not None:
                screen.blit(surf, (x, y))
            pygame.draw.rect(screen, (255, 255, 255), (x, y, nw, nh), 2)
    composite_surf.set_alpha(int(255 * t))
    _draw_shadow_composite(screen, composite_surf, composite_rect)


def render_printing_hold(screen, composite_surf, composite_rect, screen_w: int,
                         screen_h: int, now: float, prints_done: int = 0, print_qty: int = 1):
    """Phase 2: composite fully visible with a pulsing status label."""
    screen.fill((20, 20, 20))
    composite_surf.set_alpha(255)
    _draw_shadow_composite(screen, composite_surf, composite_rect)
    label = (_TXT_PRINTING_N.format(done=prints_done + 1, total=print_qty)
             if print_qty > 1 else _TXT_PRINTING)
    pulse = int(160 + 95 * math.sin(now * 2.8))
    txt   = _font(64).render(label, True, (255, 255, 255))
    txt.set_alpha(pulse)
    screen.blit(txt, txt.get_rect(
        centerx=screen_w // 2,
        centery=composite_rect.bottom + (screen_h - composite_rect.bottom) // 2,
    ))


def render_printing_slide(screen, composite_surf, composite_rect, t: float, screen_h: int):
    """Phase 3: composite accelerates downward off-screen. t runs 0 → 1."""
    screen.fill((20, 20, 20))
    dy    = int((t * t) * (screen_h - composite_rect.top + 60))
    moved = composite_rect.move(0, dy)
    _draw_shadow_composite(screen, composite_surf, moved)


# ── Printer status widgets ────────────────────────────────────────────────────

def draw_printer_status_dot(surf: pygame.Surface, info: dict):
    """Single coloured dot in the top-right corner indicating printer state."""
    color = _STATUS_COLOR.get(info.get("status", "offline"), (255, 80, 80))
    pygame.draw.circle(surf, color, (surf.get_width() - 28, 28), 10)


def draw_printer_warning(surf: pygame.Surface):
    """Small red printer icon + label shown during countdown / preview."""
    ox, oy = 14, 14
    c = (255, 80, 80)
    pygame.draw.rect(surf, c, (ox + 8, oy,       14, 5))
    pygame.draw.rect(surf, c, (ox,     oy + 5,   30, 18))
    pygame.draw.rect(surf, (20, 20, 20), (ox + 5, oy + 13, 20, 4))
    pygame.draw.rect(surf, c, (ox + 8, oy + 23,  14, 7))
    txt = _font(36).render(_TXT_NO_PRINTER, True, c)
    surf.blit(txt, txt.get_rect(left=ox + 38, centery=oy + 16))


def _draw_ink_bars(surf, ink: list, card_x: int, cy: int, card_w: int, pad: int) -> int:
    """Draw one ink level bar per entry. Returns the new cy after all bars."""
    bar_x     = card_x + pad + 80
    bar_max_w = card_w - pad * 2 - 80 - 36
    low_ink   = 20
    for entry in ink:
        nm, level, col = entry["name"], entry["level"], _ink_color(entry.get("color", entry["name"]))
        surf.blit(_font(22).render(nm[:11], True, (155, 155, 155)), (card_x + pad, cy + 1))
        pygame.draw.rect(surf, (45, 45, 45), (bar_x, cy + 4, bar_max_w, 12), border_radius=4)
        if 0 <= level <= 100:
            bar_col = (220, 60, 60) if level <= low_ink else col
            pygame.draw.rect(surf, bar_col, (bar_x, cy + 4, max(1, int(bar_max_w * level / 100)), 12), border_radius=4)
            pct_col = (220, 60, 60) if level <= low_ink else (175, 175, 175)
            surf.blit(_font(20).render(f"{level}%", True, pct_col), (bar_x + bar_max_w + 4, cy))
        else:
            surf.blit(_font(20).render("N/A", True, (90, 90, 90)), (bar_x + bar_max_w + 4, cy))
        cy += 26
    return cy


def draw_printer_card(surf: pygame.Surface, info: dict):
    """Draw a printer status card in the top-right corner."""
    has_ink   = bool(info.get("ink"))
    has_paper = info.get("paper") is not None
    ink_rows  = len(info["ink"]) if has_ink else 0
    card_w, pad, margin = 280, 12, 18
    card_h = pad * 2 + 24 + 24 + ((24 + ink_rows * 26) if has_ink else 0) + (24 if has_paper else 0) + 6
    x, y   = surf.get_width() - card_w - margin, margin

    pygame.draw.rect(surf, (18, 18, 18), (x, y, card_w, card_h), border_radius=8)
    pygame.draw.rect(surf, (55, 55, 55), (x, y, card_w, card_h), 1, border_radius=8)
    cy = y + pad

    name = (info["name"] or "Unknown")[:22]
    surf.blit(_font(26).render(_TXT_PRINTER_ICON.format(name=name), True, (210, 210, 210)), (x + pad, cy))
    cy += 28

    status = info.get("status", "offline")
    sc     = _STATUS_COLOR.get(status, (160, 160, 160))
    pygame.draw.circle(surf, sc, (x + pad + 7, cy + 12), 5)
    surf.blit(_font(24).render(status.capitalize(), True, sc), (x + pad + 18, cy))
    cy += 30

    pygame.draw.line(surf, (45, 45, 45), (x + pad, cy), (x + card_w - pad, cy))
    cy += 8

    if has_ink:
        surf.blit(_font(22).render(_TXT_INK, True, (120, 120, 120)), (x + pad, cy))
        cy += 24
        cy = _draw_ink_bars(surf, info["ink"], x, cy, card_w, pad)
    if has_paper:
        surf.blit(_font(24).render(_TXT_PAPER.format(n=info["paper"]), True, (175, 175, 175)), (x + pad, cy))


# ── Thumbnail strip ───────────────────────────────────────────────────────────

def draw_thumbnails(screen, thumbnails: list, screen_w: int, screen_h: int):
    """Render the thumbnail strip at the bottom of the screen."""
    valid = [t for t in thumbnails if t is not None]
    if not valid:
        return
    total_w = sum(t.get_width() for t in valid) + THUMB_PADDING * (len(valid) - 1)
    x = (screen_w - total_w) // 2
    y = screen_h - THUMB_HEIGHT - THUMB_MARGIN_BOTTOM
    for thumb in valid:
        screen.blit(thumb, (x, y))
        pygame.draw.rect(screen, (255, 255, 255), (x, y, thumb.get_width(), THUMB_HEIGHT), 2)
        x += thumb.get_width() + THUMB_PADDING
