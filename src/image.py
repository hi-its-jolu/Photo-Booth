import math
import time
import cv2
import pygame
import os


from config.config import (
    PHOTOS_DIR,
    THUMB_HEIGHT,
    THUMB_PADDING,
    THUMB_MARGIN_BOTTOM,
    GRID_PAD,
    GRID_ACTION_BAR_H,
    PREVIEW_SCALE,
)


def _to_rgb(frame_bgr, flip=True):
    """Convert a BGR OpenCV frame to RGB, optionally mirroring horizontally."""
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    if flip:
        rgb = cv2.flip(rgb, 1)
    return rgb


def frame_to_surface(frame_bgr, flip=True):
    """Convert an OpenCV BGR frame to a pygame Surface."""
    return pygame.surfarray.make_surface(_to_rgb(frame_bgr, flip).swapaxes(0, 1))


def make_thumbnail(frame_bgr, height, flip=True):
    rgb = _to_rgb(frame_bgr, flip)
    h, w = rgb.shape[:2]
    thumb = cv2.resize(rgb, (int(height * w / h), height))
    return pygame.surfarray.make_surface(thumb.swapaxes(0, 1))


def make_preview(frame_bgr, screen_w, screen_h, flip=True):
    rgb = _to_rgb(frame_bgr, flip)
    h, w = rgb.shape[:2]
    scale = min(screen_w / w, screen_h / h) * PREVIEW_SCALE
    resized = cv2.resize(rgb, (int(w * scale), int(h * scale)))
    return pygame.surfarray.make_surface(resized.swapaxes(0, 1))


def grab_live_surface(cap, screen_w, screen_h):
    """Read one camera frame and return a fullscreen pygame Surface, or None on failure."""
    ret, frame = cap.read()
    if not ret:
        return None
    frame_rgb = _to_rgb(frame)
    h, w = frame_rgb.shape[:2]
    scale = max(screen_w / w, screen_h / h)
    new_w, new_h = int(w * scale), int(h * scale)
    frame_rgb = cv2.resize(frame_rgb, (new_w, new_h))
    frame_rgb = frame_rgb[
        (new_h - screen_h) // 2:(new_h + screen_h) // 2,
        (new_w - screen_w) // 2:(new_w + screen_w) // 2,
    ]
    return pygame.surfarray.make_surface(frame_rgb.swapaxes(0, 1))


def snap_photo(cap, photo_index, screen_w, screen_h):
    """Capture one frame and save to disk. Returns (path, thumbnail, preview_surf) or None."""
    ret, snap = cap.read()
    if not ret:
        return None
    filename = time.strftime(f"photo_%Y%m%d_%H%M%S_{photo_index + 1}.jpg")
    path = os.path.join(PHOTOS_DIR, filename)
    cv2.imwrite(path, snap)
    print(f"Saved: {path}")
    return path, make_thumbnail(snap, THUMB_HEIGHT), make_preview(snap, screen_w, screen_h)


def build_grid_surfs(photo_paths, screen_w, screen_h):
    """Load saved photos from disk once and return cached (surf, x, y, w, h) tuples."""
    n = len(photo_paths)
    if not n:
        return []
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)
    cell_w = (screen_w - GRID_PAD * (cols + 1)) // cols
    cell_h = (screen_h - GRID_PAD * (rows + 1) - GRID_ACTION_BAR_H) // rows
    surfs = []
    for i, fpath in enumerate(photo_paths):
        img = cv2.imread(fpath)
        if img is None:
            surfs.append(None)
            continue
        img_rgb = _to_rgb(img)
        ih, iw = img_rgb.shape[:2]
        scale = min(cell_w / iw, cell_h / ih)
        nw, nh = int(iw * scale), int(ih * scale)
        img_rgb = cv2.resize(img_rgb, (nw, nh))
        surf = pygame.surfarray.make_surface(img_rgb.swapaxes(0, 1))
        col = i % cols
        row = i // cols
        x = GRID_PAD + col * (cell_w + GRID_PAD) + (cell_w - nw) // 2
        y = GRID_PAD + row * (cell_h + GRID_PAD) + (cell_h - nh) // 2
        surfs.append((surf, x, y, nw, nh))
    return surfs

def build_polaroid_surf(photo_paths: list, screen_w: int, screen_h: int) -> pygame.Surface:
    """Compose up to 4 photos into a single polaroid-style pygame Surface (2×2 grid)."""
    target_h = int(screen_h * 0.74)
    border   = max(int(target_h * 0.042), 18)   # equal border top/left/right
    bottom   = max(int(target_h * 0.13),  55)   # thicker bottom (classic polaroid)
    gap      = max(int(target_h * 0.014),  7)   # gap between the two photos

    cell_h = (target_h - border - bottom - gap) // 2
    cell_w = cell_h                              # square cells
    pol_w  = 2 * cell_w + gap + 2 * border
    pol_h  = target_h

    surf = pygame.Surface((pol_w, pol_h))
    surf.fill((252, 252, 248))                   # slightly warm white

    offsets = [
        (border,                border),
        (border + cell_w + gap, border),
        (border,                border + cell_h + gap),
        (border + cell_w + gap, border + cell_h + gap),
    ]

    for i, path in enumerate(photo_paths[:4]):
        img = cv2.imread(path)
        if img is None:
            continue
        img_rgb = _to_rgb(img, flip=True)          # match grid/preview orientation
        ih, iw  = img_rgb.shape[:2]
        scale   = max(cell_w / iw, cell_h / ih)   # fill cell, then center-crop
        nw, nh  = int(iw * scale), int(ih * scale)
        img_rgb = cv2.resize(img_rgb, (nw, nh))
        cx, cy  = (nw - cell_w) // 2, (nh - cell_h) // 2
        cell_img = img_rgb[cy:cy + cell_h, cx:cx + cell_w]
        surf.blit(pygame.surfarray.make_surface(cell_img.swapaxes(0, 1)), offsets[i])

    return surf


def load_carousel_photos(target_h):
    """Load all past photos from PHOTOS_DIR scaled to target_h for strip carousel display."""
    if not os.path.isdir(PHOTOS_DIR):
        return []
    files = sorted([
        os.path.join(PHOTOS_DIR, f) for f in os.listdir(PHOTOS_DIR)
        if f.lower().endswith(('.jpg', '.jpeg', '.png'))
    ])
    surfs = []
    for fpath in files:
        img = cv2.imread(fpath)
        if img is None:
            continue
        h, w = img.shape[:2]
        new_w = int(w * target_h / h)
        rgb = _to_rgb(img)
        rgb = cv2.resize(rgb, (new_w, target_h))
        surfs.append(pygame.surfarray.make_surface(rgb.swapaxes(0, 1)))
    return surfs


def draw_thumbnails(screen, thumbnails, screen_w, screen_h):
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
