import os
import cv2
import numpy as np
import pygame

from config.config import PHOTOS_DIR, THUMB_HEIGHT, PREVIEW_SCALE, CAMERA_SATURATION_BOOST


def _boost_saturation(frame_bgr):
    """Boost saturation in software, in HSV space, on an already-captured
    frame - this never touches the camera's own auto-exposure/white-balance,
    unlike setting the driver's saturation control directly (which caused a
    bad blue color cast on this camera)."""
    if not CAMERA_SATURATION_BOOST or CAMERA_SATURATION_BOOST == 1.0:
        return frame_bgr
    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[..., 1] = np.clip(hsv[..., 1] * CAMERA_SATURATION_BOOST, 0, 255)
    return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)


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
    """Read one camera frame and return a fullscreen pygame Surface, or None on failure
    (including when `cap` is None because no webcam was found at startup)."""
    if cap is None:
        return None
    ret, frame = cap.read()
    if not ret:
        return None
    frame = _boost_saturation(frame)
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
    if cap is None:
        return None
    ret, snap = cap.read()
    if not ret:
        return None
    snap = _boost_saturation(snap)
    filename = f"photo_{session_id}_{photo_index + 1}.jpg"
    path = os.path.join(PHOTOS_DIR, filename)
    cv2.imwrite(path, snap)
    print(f"Saved: {path}")
    return path, make_thumbnail(snap, THUMB_HEIGHT), make_preview(snap, screen_w, screen_h)
