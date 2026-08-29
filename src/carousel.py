import os
import cv2
import pygame

from config.config import PHOTOS_DIR

_SUPPORTED_EXTS = (".jpg", ".jpeg", ".png")


def count_photos() -> int:
    """Count saved photos in PHOTOS_DIR, for the idle screen's 'N PHOTOS SO FAR'."""
    if not os.path.isdir(PHOTOS_DIR):
        return 0
    return sum(1 for f in os.listdir(PHOTOS_DIR) if f.lower().endswith(_SUPPORTED_EXTS))


def load_carousel_photos(target_h: int) -> list[pygame.Surface]:
    """Load all saved photos scaled to `target_h` px for the idle carousel strip."""
    if not os.path.isdir(PHOTOS_DIR):
        return []
    files = sorted(
        os.path.join(PHOTOS_DIR, f)
        for f in os.listdir(PHOTOS_DIR)
        if f.lower().endswith(_SUPPORTED_EXTS)
    )
    surfs = []
    for fpath in files:
        img = cv2.imread(fpath)
        if img is None:
            continue
        h, w = img.shape[:2]
        rgb  = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        rgb  = cv2.resize(rgb, (int(w * target_h / h), target_h))
        surfs.append(pygame.surfarray.make_surface(rgb.swapaxes(0, 1)))
    return surfs
