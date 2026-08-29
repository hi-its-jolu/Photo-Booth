import time
import os
import cv2
import pygame

from config.config import PHOTOS_DIR, THUMB_HEIGHT, PREVIEW_SCALE


def _to_rgb(frame_bgr, flip: bool = True):
    """Convert a BGR OpenCV frame to RGB, optionally mirroring horizontally."""
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    if flip:
        rgb = cv2.flip(rgb, 1)
    return rgb


def frame_to_surface(frame_bgr, flip: bool = True) -> pygame.Surface:
    return pygame.surfarray.make_surface(_to_rgb(frame_bgr, flip).swapaxes(0, 1))


def make_thumbnail(frame_bgr, height: int, flip: bool = True) -> pygame.Surface:
    rgb = _to_rgb(frame_bgr, flip)
    h, w = rgb.shape[:2]
    thumb = cv2.resize(rgb, (int(height * w / h), height))
    return pygame.surfarray.make_surface(thumb.swapaxes(0, 1))


def make_preview(frame_bgr, screen_w: int, screen_h: int, flip: bool = True) -> pygame.Surface:
    rgb = _to_rgb(frame_bgr, flip)
    h, w = rgb.shape[:2]
    scale = min(screen_w / w, screen_h / h) * PREVIEW_SCALE
    resized = cv2.resize(rgb, (int(w * scale), int(h * scale)))
    return pygame.surfarray.make_surface(resized.swapaxes(0, 1))


def grab_live_surface(cap, screen_w: int, screen_h: int) -> pygame.Surface | None:
    """Read one camera frame and return a fullscreen pygame Surface, or None on failure."""
    ret, frame = cap.read()
    if not ret:
        return None
    rgb = _to_rgb(frame)
    h, w = rgb.shape[:2]
    scale = max(screen_w / w, screen_h / h)
    new_w, new_h = int(w * scale), int(h * scale)
    rgb = cv2.resize(rgb, (new_w, new_h))
    rgb = rgb[
        (new_h - screen_h) // 2:(new_h + screen_h) // 2,
        (new_w - screen_w) // 2:(new_w + screen_w) // 2,
    ]
    return pygame.surfarray.make_surface(rgb.swapaxes(0, 1))


def snap_photo(cap, photo_index: int, screen_w: int, screen_h: int):
    """Capture one frame, save to disk. Returns (path, thumbnail, preview) or None."""
    ret, snap = cap.read()
    if not ret:
        return None
    filename = time.strftime(f"photo_%Y%m%d_%H%M%S_{photo_index + 1}.jpg")
    path = os.path.join(PHOTOS_DIR, filename)
    cv2.imwrite(path, snap)
    print(f"Saved: {path}")
    return path, make_thumbnail(snap, THUMB_HEIGHT), make_preview(snap, screen_w, screen_h)
