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
from composite import (
    REVIEW_GRID_W, REVIEW_GRID_H, REVIEW_GRID_Y, REVIEW_MAT_PAD,
    fit_scale, scale_px,
)

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

# Carousel thumbnail height at design scale: strip height minus the top inset,
# flush to the strip's bottom rule (132 - 6 = 126).
IDLE_THUMB_H = CAROUSEL_STRIP_HEIGHT - _IDLE_STRIP_INSET

_TXT_LIVE    = "LIVE"
_TXT_EARLIER = "EARLIER TONIGHT"
_TXT_START   = "START"
_TXT_PRESS   = "PRESS THE GREEN BUTTON — {n} PHOTOS, ABOUT 30 SECONDS"


def idle_viewfinder_inner(screen_w: int, screen_h: int) -> tuple[int, int]:
    """Interior size (mirror/cover-crop target) for the idle viewfinder box,
    scaled to fit screen_w x screen_h."""
    s = fit_scale(screen_w, screen_h)
    border = scale_px(_IDLE_VF_BORDER, s)
    return scale_px(_IDLE_VF_W, s) - border * 2, scale_px(_IDLE_VF_H, s) - border * 2


def _draw_idle_header(screen, now: float, screen_w: int, s: float):
    margin, header_y, logo_h = scale_px(_IDLE_MARGIN, s), scale_px(_IDLE_HEADER_Y, s), scale_px(_IDLE_LOGO_H, s)
    logo = _get_logo_by_height(logo_h)
    if logo is not None:
        screen.blit(logo, (margin, header_y))
    row_cy = header_y + logo_h // 2

    live_label = _tracked(700, scale_px(19, s), _TXT_LIVE, NEUTRAL_600, 0.20)
    dot, gap   = scale_px(14, s), scale_px(14, s)
    label_x    = (screen_w - margin) - live_label.get_width()
    dot_x      = label_x - gap - dot

    dot_surf = pygame.Surface((dot, dot), pygame.SRCALPHA)
    dot_surf.fill((*ACCENT, _pulse_alpha(now, 1.8)))
    screen.blit(dot_surf, (dot_x, row_cy - dot // 2))
    screen.blit(live_label, (label_x, row_cy - live_label.get_height() // 2))


def _draw_idle_viewfinder(screen, live_surf, screen_w: int, s: float):
    box_w, box_h = scale_px(_IDLE_VF_W, s), scale_px(_IDLE_VF_H, s)
    border       = scale_px(_IDLE_VF_BORDER, s)
    box_x, box_y = (screen_w - box_w) // 2, scale_px(_IDLE_VF_TOP, s)

    pygame.draw.rect(screen, (0, 0, 0), (box_x, box_y, box_w, box_h))
    if live_surf is not None:
        screen.blit(live_surf, (box_x + border, box_y + border))
    pygame.draw.rect(screen, INK, (box_x, box_y, box_w, box_h), border)

    L, T = scale_px(_IDLE_TICK_LEN, s), border
    for corner_x, corner_y, sx, sy in [
        (box_x,          box_y,          1, 1),
        (box_x + box_w,  box_y,         -1, 1),
        (box_x,          box_y + box_h,  1, -1),
        (box_x + box_w,  box_y + box_h, -1, -1),
    ]:
        hx = corner_x if sx > 0 else corner_x - L
        hy = corner_y if sy > 0 else corner_y - T
        pygame.draw.rect(screen, (255, 255, 255), (hx, hy, L, T))
        vx = corner_x if sx > 0 else corner_x - T
        vy = corner_y if sy > 0 else corner_y - L
        pygame.draw.rect(screen, (255, 255, 255), (vx, vy, T, L))


def _draw_idle_labels(screen, photo_count: int, screen_w: int, s: float):
    margin = scale_px(_IDLE_MARGIN, s)
    y      = scale_px(_IDLE_LABEL_Y, s)
    size   = scale_px(18, s)
    left   = _tracked(700, size, _TXT_EARLIER, NEUTRAL_600, 0.22)
    right  = _tracked(700, size, f"{photo_count} PHOTOS SO FAR", NEUTRAL_600, 0.22)
    screen.blit(left,  left.get_rect(left=margin, bottom=y))
    screen.blit(right, right.get_rect(right=screen_w - margin, bottom=y))


def _draw_idle_carousel(screen, carousel_photos, carousel_start: float, now: float, screen_w: int, s: float):
    margin      = scale_px(_IDLE_MARGIN, s)
    left, right = margin, screen_w - margin
    strip_y     = scale_px(_IDLE_STRIP_Y, s)
    strip_h     = scale_px(CAROUSEL_STRIP_HEIGHT, s)
    rule_w      = scale_px(2, s)
    pygame.draw.line(screen, INK, (left, strip_y), (right, strip_y), rule_w)
    pygame.draw.line(screen, INK, (left, strip_y + strip_h), (right, strip_y + strip_h), rule_w)
    if not carousel_photos:
        return

    thumb_y = strip_y + scale_px(_IDLE_STRIP_INSET, s)
    pad     = scale_px(CAROUSEL_PADDING, s)
    speed   = CAROUSEL_SCROLL_SPEED * s
    total_w = sum(surf.get_width() + pad for surf in carousel_photos)
    offset  = (speed * (now - carousel_start)) % total_w

    prev_clip = screen.get_clip()
    screen.set_clip(pygame.Rect(left, strip_y, right - left, strip_h))
    x = left - offset
    while x < right:
        for surf in carousel_photos:
            if x + surf.get_width() >= left:
                screen.blit(surf, (int(x), thumb_y))
            x += surf.get_width() + pad
            if x >= right:
                break
    screen.set_clip(prev_clip)


def _draw_idle_rail(screen, now: float, screen_w: int, screen_h: int, s: float):
    rail_h = scale_px(_IDLE_RAIL_H, s)
    rail_y = screen_h - rail_h
    margin = scale_px(_IDLE_MARGIN, s)
    pygame.draw.rect(screen, NEUTRAL_200, (0, rail_y, screen_w, rail_h))
    pygame.draw.line(screen, INK, (0, rail_y), (screen_w, rail_y), scale_px(2, s))
    rail_cy = rail_y + rail_h // 2

    press = _archivo(800, scale_px(30, s)).render(_TXT_PRESS.format(n=TOTAL_PHOTOS), True, INK)
    screen.blit(press, press.get_rect(left=margin, centery=rail_cy))

    start_label  = _tracked(800, scale_px(22, s), _TXT_START, INK, 0.16)
    d, drop, gap = scale_px(_IDLE_START_D, s), scale_px(_IDLE_START_DROP, s), scale_px(16, s)
    cx = (screen_w - margin) - start_label.get_width() - gap - d // 2

    pygame.draw.circle(screen, GREEN_DARK, (cx, rail_cy + drop), d // 2)
    alpha = _pulse_alpha(now, 1.6)
    pad2  = scale_px(4, s)
    cap   = pygame.Surface((d + pad2, d + pad2), pygame.SRCALPHA)
    c     = d // 2 + pad2 // 2
    pygame.draw.circle(cap, (*GREEN, alpha), (c, c), d // 2)
    pygame.draw.circle(cap, (*INK, alpha),   (c, c), d // 2, scale_px(2, s))
    screen.blit(cap, (cx - c, rail_cy - c))
    screen.blit(start_label, start_label.get_rect(left=cx + d // 2 + gap, centery=rail_cy))


def render_idle(screen, live_surf, carousel_photos, carousel_start: float, now: float,
                photo_count: int, screen_w: int, screen_h: int):
    s = fit_scale(screen_w, screen_h)
    screen.fill(GROUND)
    _draw_idle_header(screen, now, screen_w, s)
    margin, rule_y = scale_px(_IDLE_MARGIN, s), scale_px(_IDLE_RULE_Y, s)
    pygame.draw.line(screen, INK, (margin, rule_y), (screen_w - margin, rule_y), scale_px(2, s))
    _draw_idle_viewfinder(screen, live_surf, screen_w, s)
    _draw_idle_labels(screen, photo_count, screen_w, s)
    _draw_idle_carousel(screen, carousel_photos, carousel_start, now, screen_w, s)
    _draw_idle_rail(screen, now, screen_w, screen_h, s)


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
_REV_RAIL_H       = 244
_REV_GRID_BOTTOM_GAP = 40   # gap between grid bottom and the rail, at design scale
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


def _draw_review_header(screen, now: float, time_left: float, screen_w: int, s: float):
    plate_sz = scale_px(_REV_PLATE, s)
    secs     = max(0, math.ceil(time_left))
    urgent   = time_left <= PREVIEW_URGENT_AT

    plate = pygame.Surface((plate_sz, plate_sz), pygame.SRCALPHA)
    plate.fill((*(ACCENT if urgent else INK), 255))
    num = _archivo(800, scale_px(60, s)).render(f"{secs:02d}", True, GROUND)
    plate.blit(num, num.get_rect(center=(plate_sz // 2, plate_sz // 2)))
    if urgent and ((now % _REV_FLASH_PERIOD) / _REV_FLASH_PERIOD) >= 0.5:
        plate.set_alpha(round(255 * _REV_FLASH_DIM))
    margin, header_y = scale_px(_REV_MARGIN, s), scale_px(_REV_HEADER_Y, s)
    screen.blit(plate, (margin, header_y))

    size  = scale_px(19, s)
    line1 = _tracked(700, size, _TXT_SECONDS, NEUTRAL_600, 0.20)
    line2 = _tracked(700, size, _TXT_LET_GO, INK, 0.20)
    tx = margin + plate_sz + scale_px(18, s)
    line_gap = scale_px(4, s)
    block_h = line1.get_height() + line2.get_height() + line_gap
    top = header_y + (plate_sz - block_h) // 2
    screen.blit(line1, (tx, top))
    screen.blit(line2, (tx, top + line1.get_height() + line_gap))


def review_grid_rect(screen_w: int, screen_h: int) -> tuple[int, int, int, int]:
    """Grid x, y, w, h. Grown to fill the available space between the header
    rule and the bottom rail — preserving the design's aspect ratio — so the
    photos use as much of the screen as the layout allows, rather than being
    stuck at a fixed size when there's slack (e.g. a non-16:9 display)."""
    s = fit_scale(screen_w, screen_h)
    margin = scale_px(_REV_MARGIN, s)
    grid_y = scale_px(REVIEW_GRID_Y, s)
    rail_y = screen_h - scale_px(_REV_RAIL_H, s)
    bottom_gap = scale_px(_REV_GRID_BOTTOM_GAP, s)

    available_w  = screen_w - margin * 2
    available_h  = rail_y - bottom_gap - grid_y
    design_ratio = REVIEW_GRID_W / REVIEW_GRID_H

    if available_w / design_ratio <= available_h:
        grid_w, grid_h = available_w, round(available_w / design_ratio)
    else:
        grid_h, grid_w = available_h, round(available_h * design_ratio)

    return (screen_w - grid_w) // 2, grid_y, grid_w, grid_h


def _draw_review_grid(screen, grid_surfs: list, screen_w: int, screen_h: int):
    grid_x, grid_y, grid_w, grid_h = review_grid_rect(screen_w, screen_h)
    grid_scale = grid_w / REVIEW_GRID_W
    mat_pad = scale_px(REVIEW_MAT_PAD, grid_scale)
    border  = scale_px(2, grid_scale)
    for item in grid_surfs:
        if item is None:
            continue
        surf, cx, cy, cw, ch = item
        pygame.draw.rect(screen, WHITE, (cx, cy, cw, ch))
        if surf is not None:
            screen.blit(surf, (cx + mat_pad, cy + mat_pad))
        pygame.draw.rect(screen, INK, (cx, cy, cw, ch), border)

    logo = _get_logo(scale_px(340, grid_scale))
    if logo is not None:
        screen.blit(logo, logo.get_rect(
            center=(grid_x + grid_w // 2, grid_y + grid_h // 2)))


def _draw_stepper_cap(screen, cx: int, cy: int, d: int, active: bool, glyph: str, s: float):
    alpha = 255 if active else round(255 * 0.45)
    drop  = scale_px(6, s)
    pygame.draw.circle(screen, NEUTRAL_400, (cx, cy + drop), d // 2)
    pad = scale_px(4, s)
    cap = pygame.Surface((d + pad, d + pad), pygame.SRCALPHA)
    c   = d // 2 + pad // 2
    border = scale_px(2, s)
    pygame.draw.circle(cap, (*WHITE, alpha), (c, c), d // 2)
    pygame.draw.circle(cap, (*INK, alpha),   (c, c), d // 2, border)
    bar_w, bar_h = scale_px(38, s), scale_px(7, s)
    pygame.draw.rect(cap, (*INK, alpha), (c - bar_w // 2, c - bar_h // 2, bar_w, bar_h))
    if glyph == "plus":
        pygame.draw.rect(cap, (*INK, alpha), (c - bar_h // 2, c - bar_w // 2, bar_h, bar_w))
    screen.blit(cap, (cx - c, cy - c))


def _draw_stepper(screen, x: int, rail_y: int, rail_h: int, print_qty: int, s: float):
    d, gap_lbl, cap_gap = scale_px(96, s), scale_px(10, s), scale_px(14, s)
    fewer_on, more_on = print_qty > PRINT_QTY_MIN, print_qty < PRINT_QTY_MAX
    lbl_sz     = scale_px(17, s)
    fewer_lbl  = _tracked(700, lbl_sz, _TXT_FEWER, NEUTRAL_700, 0.16)
    more_lbl   = _tracked(700, lbl_sz, _TXT_MORE,  NEUTRAL_700, 0.16)
    copies_lbl = _tracked(700, scale_px(18, s), _TXT_COPIES2, NEUTRAL_600, 0.20)
    qty_num    = _archivo(800, scale_px(76, s)).render(str(print_qty), True, INK)
    qty_word   = _tracked(700, scale_px(24, s), "COPY" if print_qty == 1 else "COPIES", NEUTRAL_700, 0.12)

    cap_stack_h   = d + gap_lbl + max(fewer_lbl.get_height(), more_lbl.get_height())
    row_h         = max(qty_num.get_height(), qty_word.get_height())
    text_block_h  = copies_lbl.get_height() + row_h
    col_h         = max(cap_stack_h, text_block_h)
    col_bottom    = rail_y + rail_h // 2 + col_h // 2

    cap_top  = col_bottom - cap_stack_h
    cap_cy   = cap_top + d // 2
    fewer_cx = x + d // 2
    more_cx  = fewer_cx + d + cap_gap

    _draw_stepper_cap(screen, fewer_cx, cap_cy, d, fewer_on, "minus", s)
    screen.blit(fewer_lbl, fewer_lbl.get_rect(centerx=fewer_cx, top=cap_top + d + gap_lbl))
    _draw_stepper_cap(screen, more_cx, cap_cy, d, more_on, "plus", s)
    screen.blit(more_lbl, more_lbl.get_rect(centerx=more_cx, top=cap_top + d + gap_lbl))

    text_top   = col_bottom - text_block_h
    gap_div    = scale_px(26, s)
    divider_x  = more_cx + d // 2 + gap_div
    pygame.draw.line(screen, INK, (divider_x, min(cap_top, text_top)), (divider_x, col_bottom), scale_px(2, s))

    tx = divider_x + gap_div
    screen.blit(copies_lbl, (tx, text_top))
    row_y = text_top + copies_lbl.get_height()
    gap_num = scale_px(10, s)
    screen.blit(qty_num,  (tx, row_y + row_h - qty_num.get_height()))
    screen.blit(qty_word, (tx + qty_num.get_width() + gap_num, row_y + row_h - qty_word.get_height()))


def _draw_review_qr(screen, qr_surf, screen_w: int, rail_y: int, rail_h: int, s: float):
    if qr_surf is None:
        return
    box = scale_px(140, s)
    gap = scale_px(10, s)   # 8px inner padding is implicit: qr_surf is generated pre-scaled to fit
    label = _tracked(700, scale_px(19, s), _TXT_SCAN, INK, 0.20)
    stack_h = box + gap + label.get_height()
    top = rail_y + (rail_h - stack_h) // 2

    box_rect = pygame.Rect(0, 0, box, box)
    box_rect.centerx, box_rect.top = screen_w // 2, top
    pygame.draw.rect(screen, WHITE, box_rect)
    pygame.draw.rect(screen, INK, box_rect, scale_px(2, s))
    screen.blit(qr_surf, qr_surf.get_rect(center=box_rect.center))
    screen.blit(label, label.get_rect(centerx=screen_w // 2, top=box_rect.bottom + gap))


def _draw_review_actions(screen, right_edge: int, rail_y: int, rail_h: int, print_qty: int, s: float):
    lbl_sz = scale_px(19, s)
    discard_lbl = _tracked(800, lbl_sz, _TXT_DISCARD, INK, 0.16)
    qty_word    = "COPY" if print_qty == 1 else "COPIES"
    print_lbl   = _tracked(800, lbl_sz, f"PRINT {print_qty} {qty_word}", INK, 0.16)

    d_disc, d_print   = scale_px(112, s), scale_px(148, s)
    action_gap, lbl_gap = scale_px(28, s), scale_px(10, s)
    disc_h  = d_disc  + lbl_gap + discard_lbl.get_height()
    print_h = d_print + lbl_gap + print_lbl.get_height()
    col_bottom = rail_y + rail_h // 2 + max(disc_h, print_h) // 2

    print_cx = right_edge - d_print // 2
    disc_cx  = print_cx - d_print // 2 - action_gap - d_disc // 2
    disc_cy  = col_bottom - discard_lbl.get_height() - lbl_gap - d_disc // 2
    print_cy = col_bottom - print_lbl.get_height()   - lbl_gap - d_print // 2

    border = scale_px(2, s)

    # Discard
    disc_drop = scale_px(6, s)
    pygame.draw.circle(screen, NEUTRAL_500, (disc_cx, disc_cy + disc_drop), d_disc // 2)
    pygame.draw.circle(screen, INK, (disc_cx, disc_cy), d_disc // 2)
    pygame.draw.circle(screen, INK, (disc_cx, disc_cy), d_disc // 2, border)
    half   = scale_px(16, s)
    line_w = scale_px(6, s)
    pygame.draw.line(screen, WHITE, (disc_cx - half, disc_cy - half), (disc_cx + half, disc_cy + half), line_w)
    pygame.draw.line(screen, WHITE, (disc_cx - half, disc_cy + half), (disc_cx + half, disc_cy - half), line_w)
    screen.blit(discard_lbl, discard_lbl.get_rect(centerx=disc_cx, top=disc_cy + d_disc // 2 + lbl_gap))

    # Print
    print_drop = scale_px(8, s)
    pygame.draw.circle(screen, ACCENT_DARK, (print_cx, print_cy + print_drop), d_print // 2)
    pygame.draw.circle(screen, ACCENT, (print_cx, print_cy), d_print // 2)
    pygame.draw.circle(screen, ACCENT_DARK, (print_cx, print_cy), d_print // 2, border)
    print_word = _tracked(800, scale_px(30, s), _TXT_PRINT2, WHITE, 0.06)
    screen.blit(print_word, print_word.get_rect(center=(print_cx, print_cy)))
    screen.blit(print_lbl, print_lbl.get_rect(centerx=print_cx, top=print_cy + d_print // 2 + lbl_gap))


def render_grid(screen, grid_surfs: list, screen_w: int, screen_h: int,
                now: float, time_left: float, print_qty: int = 1, qr_surf=None):
    s = fit_scale(screen_w, screen_h)
    screen.fill(GROUND)
    _draw_review_header(screen, now, time_left, screen_w, s)
    margin, rule_y = scale_px(_REV_MARGIN, s), scale_px(_REV_RULE_Y, s)
    pygame.draw.line(screen, INK, (margin, rule_y), (screen_w - margin, rule_y), scale_px(2, s))
    _draw_review_grid(screen, grid_surfs, screen_w, screen_h)

    rail_h = scale_px(_REV_RAIL_H, s)
    rail_y = screen_h - rail_h
    pygame.draw.rect(screen, NEUTRAL_200, (0, rail_y, screen_w, rail_h))
    pygame.draw.line(screen, INK, (0, rail_y), (screen_w, rail_y), scale_px(2, s))

    _draw_stepper(screen, margin, rail_y, rail_h, print_qty, s)
    _draw_review_qr(screen, qr_surf, screen_w, rail_y, rail_h, s)
    _draw_review_actions(screen, screen_w - margin, rail_y, rail_h, print_qty, s)


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
