import io
import pygame
from PIL import Image

_IMG_FORMAT  = "PNG"
_FILL_COLOR  = (230, 230, 230)
_BACK_COLOR  = (24, 24, 24)
_ERROR_LEVEL = "M"   # qrcode.constants.ERROR_CORRECT_M
_BOX_SIZE    = 5
_BORDER      = 2
_LABEL_TEXT  = "Scan to download"


def make_qr_surf(url: str, size: int = 110) -> pygame.Surface | None:
    """Return a pygame Surface containing a QR code for `url` scaled to `size` px.
    Returns None if the qrcode package is not installed."""
    try:
        import qrcode
        import qrcode.constants
        qr = qrcode.QRCode(
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=_BOX_SIZE,
            border=_BORDER,
        )
        qr.add_data(url)
        qr.make(fit=True)
        pil_img = qr.make_image(fill_color=_FILL_COLOR, back_color=_BACK_COLOR).convert("RGB")
        pil_img = pil_img.resize((size, size), Image.LANCZOS)
        buf = io.BytesIO()
        pil_img.save(buf, format=_IMG_FORMAT)
        buf.seek(0)
        return pygame.image.load(buf).convert()
    except Exception:
        return None
