import os
import cv2
import numpy as np
import pygame

from config.config import PHOTOS_DIR, THUMB_HEIGHT, PREVIEW_SCALE


def _gray_world_wb(frame_bgr):
    """Correct color cast via gray-world white balance: scale each channel so
    its mean matches the overall mean. This camera's auto-WB overcorrects
    when a large, uniformly-colored background (e.g. a plain wall) dominates
    the frame, giving skin tones a strong blue/purple cast - this runs in
    software on every frame instead, independent of the driver's own AWB."""
    frame = frame_bgr.astype(np.float32)
    b, g, r = cv2.split(frame)
    b_avg, g_avg, r_avg = b.mean(), g.mean(), r.mean()
    k = (b_avg + g_avg + r_avg) / 3.0
    b *= k / b_avg
    g *= k / g_avg
    r *= k / r_avg
    return np.clip(cv2.merge([b, g, r]), 0, 255).astype(np.uint8)


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
    frame = _gray_world_wb(frame)
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


def snap_photo(cap, session_id: str, photo_index: int, screen_w: int, screen_h: int):
    """Capture one frame, save to disk. Returns (path, thumbnail, preview) or None.
    `session_id` is shared by all photos (and the print) in one session, so the
    gallery can group them — capture timing means each shot lands in a
    different wall-clock second, so a fresh per-photo timestamp won't do."""
    ret, snap = cap.read()
    if not ret:
        return None
    snap = _gray_world_wb(snap)
    filename = f"photo_{session_id}_{photo_index + 1}.jpg"
    path = os.path.join(PHOTOS_DIR, filename)
    cv2.imwrite(path, snap)
    print(f"Saved: {path}")
    return path, make_thumbnail(snap, THUMB_HEIGHT), make_preview(snap, screen_w, screen_h)
