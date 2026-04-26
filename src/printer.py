import pygame
import subprocess
import struct
import http.client


# ── Font cache ────────────────────────────────────────────────────────────────

_fonts: dict[int, pygame.font.Font] = {}


def _font(size: int) -> pygame.font.Font:
    if size not in _fonts:
        _fonts[size] = pygame.font.SysFont(None, size)
    return _fonts[size]


# ── Printer discovery ─────────────────────────────────────────────────────────

def _get_default_printer_name() -> str | None:
    """Return the default system printer name, or None."""
    try:
        r = subprocess.run(["lpstat", "-d"], capture_output=True, text=True, timeout=5)
        if "no system default" in r.stdout.lower():
            return None
        parts = r.stdout.strip().split(":")
        name = parts[-1].strip() if len(parts) >= 2 else None
        return name or None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def _get_printer_status(name: str) -> str:
    """Return 'idle', 'printing', or 'offline'."""
    try:
        r = subprocess.run(["lpstat", "-p", name], capture_output=True, text=True, timeout=5)
        out = r.stdout.lower()
        if "idle" in out:
            return "idle"
        if "processing" in out:
            return "printing"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return "offline"


# ── IPP protocol (ink level query) ───────────────────────────────────────────

def _ipp_attr(tag: int, name: str, value: str | bytes) -> bytes:
    nb = name.encode()
    vb = value.encode() if isinstance(value, str) else value
    return bytes([tag]) + struct.pack("!H", len(nb)) + nb + struct.pack("!H", len(vb)) + vb


def _ipp_extra(tag: int, value: str | bytes) -> bytes:
    vb = value.encode() if isinstance(value, str) else value
    return bytes([tag]) + b"\x00\x00" + struct.pack("!H", len(vb)) + vb


def _build_ipp_request(printer_uri: str) -> bytes:
    requested = [
        "marker-levels", "marker-names", "marker-colors", "marker-types",
        "printer-state", "printer-state-reasons", "printer-name",
    ]
    body = b"\x01\x01"
    body += struct.pack("!H", 0x000B)
    body += struct.pack("!I", 1)
    body += b"\x01"
    body += _ipp_attr(0x47, "attributes-charset", "utf-8")
    body += _ipp_attr(0x48, "attributes-natural-language", "en")
    body += _ipp_attr(0x45, "printer-uri", printer_uri)
    body += _ipp_attr(0x44, "requested-attributes", requested[0])
    for attr in requested[1:]:
        body += _ipp_extra(0x44, attr)
    body += b"\x03"
    return body


def _parse_ipp_response(data: bytes) -> dict:
    pos = 8
    attrs: dict = {}
    last_name: str | None = None

    while pos < len(data):
        tag = data[pos]; pos += 1
        if tag <= 0x0F:
            if tag == 0x03:
                break
            continue

        if pos + 2 > len(data):
            break
        nlen = struct.unpack_from("!H", data, pos)[0]; pos += 2
        name = data[pos:pos + nlen].decode("utf-8", errors="ignore"); pos += nlen

        if pos + 2 > len(data):
            break
        vlen = struct.unpack_from("!H", data, pos)[0]; pos += 2
        raw = data[pos:pos + vlen]; pos += vlen

        if tag in (0x21, 0x23):
            val = struct.unpack_from("!i", raw)[0] if len(raw) == 4 else 0
        elif tag == 0x22:
            val = bool(raw[0]) if raw else False
        elif 0x40 <= tag <= 0x5F:
            val = raw.decode("utf-8", errors="ignore")
        else:
            val = raw

        if nlen > 0:
            last_name = name

        if last_name:
            existing = attrs.get(last_name)
            if existing is None:
                attrs[last_name] = val
            elif isinstance(existing, list):
                existing.append(val)
            else:
                attrs[last_name] = [existing, val]

    return attrs


def _query_ipp_attrs(printer_name: str) -> dict:
    uri = f"ipp://localhost/printers/{printer_name}"
    try:
        payload = _build_ipp_request(uri)
        conn = http.client.HTTPConnection("localhost", 631, timeout=5)
        conn.request(
            "POST", f"/printers/{printer_name}", body=payload,
            headers={"Content-Type": "application/ipp",
                     "Content-Length": str(len(payload))},
        )
        resp = conn.getresponse()
        if resp.status != 200:
            return {}
        return _parse_ipp_response(resp.read())
    except Exception:
        return {}


# ── Ink colour helper ─────────────────────────────────────────────────────────

_INK_NAMED: dict[str, tuple[int, int, int]] = {
    "black":         (55,  55,  55),
    "photo black":   (65,  65,  65),
    "cyan":          (0,  188, 212),
    "light cyan":    (100, 210, 230),
    "magenta":       (233,  30,  99),
    "light magenta": (230, 130, 180),
    "yellow":        (220, 180,   0),
    "white":         (210, 210, 210),
    "gray":          (140, 140, 140),
    "light gray":    (185, 185, 185),
    "matte black":   (80,  80,  80),
}


def _ink_color(color_str: str) -> tuple[int, int, int]:
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


# ── Public API ────────────────────────────────────────────────────────────────

def get_printer_info() -> dict:
    name = _get_default_printer_name()
    if name is None:
        return {"ok": False, "name": None, "status": "offline", "ink": None, "paper": None}

    status = _get_printer_status(name)
    ok = status in ("idle", "printing")

    ink = None
    paper = None

    ipp = _query_ipp_attrs(name)
    if ipp:
        levels = ipp.get("marker-levels")
        names  = ipp.get("marker-names")
        colors = ipp.get("marker-colors")

        if levels is not None and names is not None:
            if not isinstance(levels, list): levels = [levels]
            if not isinstance(names,  list): names  = [names]
            if colors and not isinstance(colors, list): colors = [colors]
            else: colors = colors or []

            ink = []
            for i, (lvl, nm) in enumerate(zip(levels, names)):
                col = colors[i] if i < len(colors) else nm
                ink.append({"name": nm, "level": int(lvl), "color": col})

    return {"ok": ok, "name": name, "status": status, "ink": ink, "paper": paper}


def check_printer_connection() -> bool:
    return get_printer_info()["ok"]


# ── Printing ──────────────────────────────────────────────────────────────────

def print_composite(surface: pygame.Surface, copies: int = 1) -> None:
    """Save the polaroid composite surface to a temp file and send it to the printer."""
    import tempfile
    tmp = tempfile.NamedTemporaryFile(
        suffix=".png", prefix="photobooth_", delete=False
    )
    tmp_path = tmp.name
    tmp.close()

    pygame.image.save(surface, tmp_path)

    try:
        subprocess.run(
            ["lp", "-n", str(max(1, copies)), tmp_path],
            capture_output=True, timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass


def print_photos(photo_paths):
    """Send all photos to the system printer."""
    pass


# ── Drawing ───────────────────────────────────────────────────────────────────

_STATUS_COLOR = {
    "idle":     (80, 200, 80),
    "printing": (255, 165, 0),
    "offline":  (255, 80, 80),
}

_CARD_W  = 280
_CARD_PAD = 12
_MARGIN  = 18
_LINE_H  = 24
_BAR_H   = 12


def draw_printer_card(surf: pygame.Surface, info: dict) -> None:
    """Draw a printer status info card in the top-right corner."""
    has_ink   = bool(info.get("ink"))
    has_paper = info.get("paper") is not None

    ink_rows  = len(info["ink"]) if has_ink else 0
    card_h    = (_CARD_PAD * 2
                 + _LINE_H
                 + _LINE_H
                 + ((_LINE_H + ink_rows * (_LINE_H + 2)) if has_ink else 0)
                 + (_LINE_H if has_paper else 0)
                 + 6)

    x = surf.get_width() - _CARD_W - _MARGIN
    y = _MARGIN

    pygame.draw.rect(surf, (18, 18, 18), (x, y, _CARD_W, card_h), border_radius=8)
    pygame.draw.rect(surf, (55, 55, 55), (x, y, _CARD_W, card_h), 1, border_radius=8)

    cy = y + _CARD_PAD

    display_name = info["name"] or "Unknown"
    if len(display_name) > 22:
        display_name = display_name[:21] + "…"
    name_surf = _font(26).render(f"🖨  {display_name}", True, (210, 210, 210))
    surf.blit(name_surf, (x + _CARD_PAD, cy))
    cy += _LINE_H + 4

    status    = info.get("status", "offline")
    sc        = _STATUS_COLOR.get(status, (160, 160, 160))
    pygame.draw.circle(surf, sc, (x + _CARD_PAD + 7, cy + _LINE_H // 2), 5)
    st_surf = _font(24).render(status.capitalize(), True, sc)
    surf.blit(st_surf, (x + _CARD_PAD + 18, cy))
    cy += _LINE_H + 6

    pygame.draw.line(surf, (45, 45, 45), (x + _CARD_PAD, cy), (x + _CARD_W - _CARD_PAD, cy))
    cy += 8

    if has_ink:
        hdr = _font(22).render("Ink", True, (120, 120, 120))
        surf.blit(hdr, (x + _CARD_PAD, cy))
        cy += _LINE_H

        bar_x     = x + _CARD_PAD + 80
        bar_max_w = _CARD_W - _CARD_PAD * 2 - 80 - 36

        LOW_INK = 20  # percent threshold for warning

        for entry in info["ink"]:
            nm    = entry["name"]
            level = entry["level"]
            col   = _ink_color(entry.get("color", nm))

            label = _font(22).render(nm[:11], True, (155, 155, 155))
            surf.blit(label, (x + _CARD_PAD, cy + 1))

            pygame.draw.rect(surf, (45, 45, 45), (bar_x, cy + 4, bar_max_w, _BAR_H), border_radius=4)

            if 0 <= level <= 100:
                bar_col = (220, 60, 60) if level <= LOW_INK else col
                fill = max(1, int(bar_max_w * level / 100))
                pygame.draw.rect(surf, bar_col, (bar_x, cy + 4, fill, _BAR_H), border_radius=4)
                pct_col = (220, 60, 60) if level <= LOW_INK else (175, 175, 175)
                pct = _font(20).render(f"{level}%", True, pct_col)
                surf.blit(pct, (bar_x + bar_max_w + 4, cy))
            else:
                na = _font(20).render("N/A", True, (90, 90, 90))
                surf.blit(na, (bar_x + bar_max_w + 4, cy))

            cy += _LINE_H + 2

    if has_paper:
        paper_surf = _font(24).render(f"Paper: {info['paper']} sheets", True, (175, 175, 175))
        surf.blit(paper_surf, (x + _CARD_PAD, cy))


def draw_printer_warning(surf: pygame.Surface) -> None:
    """Small red printer icon + label – shown during countdown / preview."""
    ox, oy = 14, 14
    c = (255, 80, 80)
    pygame.draw.rect(surf, c, (ox + 8, oy,      14, 5))
    pygame.draw.rect(surf, c, (ox,     oy + 5,  30, 18))
    pygame.draw.rect(surf, (20, 20, 20), (ox + 5, oy + 13, 20, 4))
    pygame.draw.rect(surf, c, (ox + 8, oy + 23, 14, 7))
    text = _font(36).render("No Printer Found.", True, c)
    surf.blit(text, text.get_rect(left=ox + 38, centery=oy + 16))


def check_printer_ink():
    pass


def check_printer_paper():
    pass
