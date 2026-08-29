import io
import math
import os
import cv2
import pygame
from PIL import Image

from config.config import ASSETS_DIR, GRID_PAD, GRID_ACTION_BAR_H

# ── Constants ─────────────────────────────────────────────────────────────────

_LOGO_PATH    = os.path.join(ASSETS_DIR, "logo_wedding.png")
_IMG_FORMAT   = "PNG"
_JPEG_FORMAT  = "JPEG"
_JPEG_QUALITY = 95
_COLOR_MODE   = "RGBA"
_COLOR_RGB    = "RGB"

# Print paper dimensions at 300 DPI (landscape 4"×6")
PRINT_DPI    = 300
PRINT_WIDTH  = int(6 * PRINT_DPI)   # 1800 px
PRINT_HEIGHT = int(4 * PRINT_DPI)   # 1200 px
PRINT_BORDER = 50
PRINT_GAP    = 15

# On-screen composite proportions
_COMP_SCREEN_RATIO = 0.82
_COMP_BORDER_RATIO = 0.028
_COMP_GAP_RATIO    = 0.010
_LOGO_WIDTH_RATIO  = 0.44

_BG_COLOR = (252, 252, 248, 255)

# Design canvas the "2b"/"1d" screens (docs/design/README.md) were drawn at.
_DESIGN_W, _DESIGN_H = 1920, 1080


def fit_scale(screen_w: int, screen_h: int) -> float:
    """Uniform scale so the fixed 1920x1080 design fits screen_w x screen_h
    without clipping or overlap, preserving proportions on any real display."""
    return min(screen_w / _DESIGN_W, screen_h / _DESIGN_H)


def scale_px(v: float, s: float) -> int:
    return max(1, round(v * s))


# ── Logo loading ──────────────────────────────────────────────────────────────

def load_logo_pil(width: int) -> Image.Image | None:
    """Load the wedding logo as a PIL RGBA image scaled to `width` px."""
    try:
        logo = Image.open(_LOGO_PATH).convert(_COLOR_MODE)
        h = round(logo.height * width / logo.width)
        return logo.resize((width, h), Image.LANCZOS)
    except Exception:
        return None


def load_logo_surf(width: int) -> pygame.Surface | None:
    """Load the wedding logo as a pygame SRCALPHA Surface scaled to `width` px."""
    pil = load_logo_pil(width)
    if pil is None:
        return None
    buf = io.BytesIO()
    pil.save(buf, format=_IMG_FORMAT)
    buf.seek(0)
    return pygame.image.load(buf).convert_alpha()


# ── Shared photo crop helper ──────────────────────────────────────────────────

def _crop_photo_to_cell(bgr_img, cell_w: int, cell_h: int, flip: bool = True):
    """Scale-up and center-crop a BGR photo to exactly (cell_w × cell_h) RGB pixels."""
    rgb = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2RGB)
    if flip:
        rgb = cv2.flip(rgb, 1)
    ih, iw = rgb.shape[:2]
    scale = max(cell_w / iw, cell_h / ih)
    nw, nh = math.ceil(iw * scale), math.ceil(ih * scale)
    rgb = cv2.resize(rgb, (nw, nh), interpolation=cv2.INTER_LANCZOS4)
    cx, cy = (nw - cell_w) // 2, (nh - cell_h) // 2
    return rgb[cy:cy + cell_h, cx:cx + cell_w]


def _grid_cell_offsets(cell_w: int, cell_h: int, gap: int, border: int) -> list:
    return [
        (border,              border),
        (border + cell_w + gap, border),
        (border,              border + cell_h + gap),
        (border + cell_w + gap, border + cell_h + gap),
    ]


# ── Screen composite ──────────────────────────────────────────────────────────

def build_composite_surf(photo_paths: list, screen_w: int, screen_h: int) -> pygame.Surface:
    """Compose up to 4 photos into a landscape 2×2 pygame Surface for the screen."""
    target_w = int(screen_w * _COMP_SCREEN_RATIO)
    border   = max(int(target_w * _COMP_BORDER_RATIO), 14)
    gap      = max(int(target_w * _COMP_GAP_RATIO), 6)
    cell_w   = (target_w - border * 2 - gap) // 2
    cell_h   = round(cell_w * (PRINT_HEIGHT / PRINT_WIDTH))
    comp_w, comp_h = target_w, 2 * cell_h + gap + 2 * border
    offsets  = _grid_cell_offsets(cell_w, cell_h, gap, border)

    surf = pygame.Surface((comp_w, comp_h), pygame.SRCALPHA)
    surf.fill(_BG_COLOR)

    for i, path in enumerate(photo_paths[:4]):
        img = cv2.imread(path)
        if img is None:
            continue
        cell = _crop_photo_to_cell(img, cell_w, cell_h)
        surf.blit(pygame.surfarray.make_surface(cell.swapaxes(0, 1)), offsets[i])

    _blit_logo_surf(surf, comp_w, comp_h)
    return surf


def _blit_logo_surf(surf: pygame.Surface, canvas_w: int, canvas_h: int) -> None:
    logo_w = max(int(canvas_w * _LOGO_WIDTH_RATIO), 80)
    logo   = load_logo_surf(logo_w)
    if logo is not None:
        surf.blit(logo, ((canvas_w - logo.get_width()) // 2,
                         (canvas_h - logo.get_height()) // 2))


# ── Print image ───────────────────────────────────────────────────────────────

def build_print_image(photo_paths: list) -> Image.Image:
    """Build a 4"×6" landscape PIL Image (1800×1200 px @ 300 DPI) with 4 photos."""
    cell_w  = (PRINT_WIDTH  - PRINT_BORDER * 2 - PRINT_GAP) // 2
    cell_h  = (PRINT_HEIGHT - PRINT_BORDER * 2 - PRINT_GAP) // 2
    offsets = _grid_cell_offsets(cell_w, cell_h, PRINT_GAP, PRINT_BORDER)

    img = Image.new(_COLOR_RGB, (PRINT_WIDTH, PRINT_HEIGHT), (252, 252, 248))
    for i, path in enumerate(photo_paths[:4]):
        frame = cv2.imread(path)
        if frame is None:
            continue
        cell = _crop_photo_to_cell(frame, cell_w, cell_h)
        img.paste(Image.fromarray(cell), offsets[i])

    _paste_logo_pil(img, PRINT_WIDTH, PRINT_HEIGHT)
    return img


def _paste_logo_pil(img: Image.Image, canvas_w: int, canvas_h: int) -> None:
    logo_w = max(int(canvas_w * _LOGO_WIDTH_RATIO), 80)
    logo   = load_logo_pil(logo_w)
    if logo is not None:
        img.paste(logo, ((canvas_w - logo.width) // 2,
                         (canvas_h - logo.height) // 2), mask=logo)


# ── Review grid (preview screen "1d") ─────────────────────────────────────────

REVIEW_GRID_W, REVIEW_GRID_H = 1000, 568
REVIEW_GRID_GAP              = 22
REVIEW_MAT_PAD               = 10
REVIEW_GRID_Y                = 228   # fixed y per the 1920x1080 design (docs/design/README.md)


def build_review_grid_surfs(photo_paths: list, screen_w: int, screen_h: int) -> list:
    """Build the fixed 2x2 review-screen grid: 4 (photo_surf, x, y, cell_w, cell_h)
    tuples in absolute screen coordinates, scaled to fit screen_w x screen_h.
    photo_surf is already cropped to fill the cell's inner mat; None where a
    photo is missing."""
    s = fit_scale(screen_w, screen_h)
    grid_w  = scale_px(REVIEW_GRID_W, s)
    grid_h  = scale_px(REVIEW_GRID_H, s)
    gap     = scale_px(REVIEW_GRID_GAP, s)
    mat_pad = scale_px(REVIEW_MAT_PAD, s)
    grid_x  = (screen_w - grid_w) // 2
    grid_y  = scale_px(REVIEW_GRID_Y, s)

    cell_w = (grid_w - gap) // 2
    cell_h = (grid_h - gap) // 2
    photo_w, photo_h = cell_w - mat_pad * 2, cell_h - mat_pad * 2
    offsets = _grid_cell_offsets(cell_w, cell_h, gap, 0)

    cells = []
    for i in range(4):
        path = photo_paths[i] if i < len(photo_paths) else None
        img  = cv2.imread(path) if path else None
        surf = None
        if img is not None:
            cell = _crop_photo_to_cell(img, photo_w, photo_h)
            surf = pygame.surfarray.make_surface(cell.swapaxes(0, 1))
        ox, oy = offsets[i]
        cells.append((surf, grid_x + ox, grid_y + oy, cell_w, cell_h))
    return cells


# ── Grid layout surfaces ──────────────────────────────────────────────────────

def build_grid_surfs(photo_paths: list, screen_w: int, screen_h: int) -> list:
    """Load saved photos from disk and return (surf, x, y, w, h) tuples for the grid."""
    n = len(photo_paths)
    if not n:
        return []
    cols   = math.ceil(math.sqrt(n))
    rows   = math.ceil(n / cols)
    cell_w = (screen_w - GRID_PAD * (cols + 1)) // cols
    cell_h = (screen_h - GRID_PAD * (rows + 1) - GRID_ACTION_BAR_H) // rows
    surfs  = []
    for i, fpath in enumerate(photo_paths):
        img = cv2.imread(fpath)
        if img is None:
            surfs.append(None)
            continue
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        ih, iw = rgb.shape[:2]
        scale  = min(cell_w / iw, cell_h / ih)
        nw, nh = int(iw * scale), int(ih * scale)
        rgb    = cv2.resize(rgb, (nw, nh))
        surf   = pygame.surfarray.make_surface(rgb.swapaxes(0, 1))
        col    = i % cols
        row    = i // cols
        x = GRID_PAD + col * (cell_w + GRID_PAD) + (cell_w - nw) // 2
        y = GRID_PAD + row * (cell_h + GRID_PAD) + (cell_h - nh) // 2
        surfs.append((surf, x, y, nw, nh))
    return surfs
