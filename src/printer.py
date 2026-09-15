import os
import re
import socket
import time
import struct
import http.client
import subprocess
import tempfile
from urllib.parse import urlsplit

# ── Print job constants ───────────────────────────────────────────────────────

_PRINTS_DIR         = os.path.join(os.path.dirname(__file__), "..", "prints")
_ARCHIVE_FMT        = "print_%Y%m%d_%H%M%S.jpg"
_JPEG_FORMAT        = "JPEG"
_JPEG_QUALITY       = 95
_PRINT_DPI          = (300, 300)

_LP_MEDIA           = "media=4x6"
_LP_MEDIA_TYPE      = "MediaType=photographic-glossy"
_LP_INPUT_SLOT      = "InputSlot=Photo"
_LP_ORIENTATION     = "landscape"
_LP_QUALITY         = "print-quality=5"

_CUPS_PORT          = 631
_CUPS_HOST          = "localhost"
_CUPS_CONTENT_TYPE  = "application/ipp"
_PRINTER_TIMEOUT    = 5
_PRINT_TIMEOUT      = 30
_PROBE_TIMEOUT      = 1.5   # live TCP reachability check for network printers

# Network-attached CUPS device URI schemes worth live-probing, with their
# default port when the URI doesn't specify one. usb:// and dnssd:// aren't
# probed here — CUPS's own backend already reflects their state promptly.
_NETWORK_SCHEMES = {"socket": 9100, "ipp": 631, "ipps": 631, "lpd": 515,
                    "http": 80, "https": 443}

_DEVICE_URI_RE = re.compile(r"^device for .*?:\s*(\S+)", re.IGNORECASE)


# ── Printer discovery ─────────────────────────────────────────────────────────

def _get_default_printer_name() -> str | None:
    try:
        r = subprocess.run(["lpstat", "-d"], capture_output=True, text=True, timeout=_PRINTER_TIMEOUT)
        if "no system default" in r.stdout.lower():
            return None
        parts = r.stdout.strip().split(":")
        return parts[-1].strip() or None if len(parts) >= 2 else None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def _reasons_indicate_offline(ipp: dict) -> bool:
    """True if CUPS's own printer-state-reasons already flags a backend
    failure (e.g. `offline-report`) — this is far fresher than the plain
    idle/processing text `lpstat -p` reports, which CUPS only updates after
    a job actually fails against the device."""
    reasons = ipp.get("printer-state-reasons")
    if reasons is None:
        return False
    if not isinstance(reasons, list):
        reasons = [reasons]
    return any(isinstance(r, str) and ("offline" in r or r.endswith("-error")) for r in reasons)


def _get_device_uri(name: str) -> str | None:
    try:
        r = subprocess.run(["lpstat", "-v", name], capture_output=True, text=True, timeout=_PRINTER_TIMEOUT)
        m = _DEVICE_URI_RE.match(r.stdout.strip())
        return m.group(1) if m else None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def _device_reachable(name: str) -> bool:
    """Live TCP reachability check for network-attached printers. CUPS won't
    notice a network printer went dark until a job is actually sent to it, so
    without this a powered-off network printer reads as "idle" indefinitely.
    usb:// / dnssd:// / unknown schemes are trusted as-is (nothing sane to
    probe from here, and CUPS's own backend already tracks their state)."""
    uri = _get_device_uri(name)
    if not uri:
        return True
    parsed = urlsplit(uri)
    default_port = _NETWORK_SCHEMES.get(parsed.scheme.lower())
    if default_port is None or not parsed.hostname:
        return True
    try:
        with socket.create_connection((parsed.hostname, parsed.port or default_port), timeout=_PROBE_TIMEOUT):
            return True
    except OSError:
        return False


def _get_printer_status(name: str, ipp: dict) -> str:
    if _reasons_indicate_offline(ipp) or not _device_reachable(name):
        return "offline"
    try:
        r = subprocess.run(["lpstat", "-p", name], capture_output=True, text=True, timeout=_PRINTER_TIMEOUT)
        out = r.stdout.lower()
        if "idle"       in out: return "idle"
        if "processing" in out: return "printing"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return "offline"


# ── IPP protocol (ink level query) ───────────────────────────────────────────

_IPP_REQUESTED_ATTRS = [
    "marker-levels", "marker-names", "marker-colors", "marker-types",
    "printer-state", "printer-state-reasons", "printer-name",
]

_IPP_CHARSET  = "utf-8"
_IPP_LANGUAGE = "en"


def _ipp_attr(tag: int, name: str, value: str | bytes) -> bytes:
    nb = name.encode()
    vb = value.encode() if isinstance(value, str) else value
    return bytes([tag]) + struct.pack("!H", len(nb)) + nb + struct.pack("!H", len(vb)) + vb


def _ipp_extra(tag: int, value: str | bytes) -> bytes:
    vb = value.encode() if isinstance(value, str) else value
    return bytes([tag]) + b"\x00\x00" + struct.pack("!H", len(vb)) + vb


def _build_ipp_request(printer_uri: str) -> bytes:
    body = b"\x01\x01" + struct.pack("!H", 0x000B) + struct.pack("!I", 1) + b"\x01"
    body += _ipp_attr(0x47, "attributes-charset",      _IPP_CHARSET)
    body += _ipp_attr(0x48, "attributes-natural-language", _IPP_LANGUAGE)
    body += _ipp_attr(0x45, "printer-uri",             printer_uri)
    body += _ipp_attr(0x44, "requested-attributes",    _IPP_REQUESTED_ATTRS[0])
    for attr in _IPP_REQUESTED_ATTRS[1:]:
        body += _ipp_extra(0x44, attr)
    return body + b"\x03"


def _parse_ipp_response(data: bytes) -> dict:
    pos, attrs, last_name = 8, {}, None
    while pos < len(data):
        tag = data[pos]; pos += 1
        if tag <= 0x0F:
            if tag == 0x03: break
            continue
        if pos + 2 > len(data): break
        nlen = struct.unpack_from("!H", data, pos)[0]; pos += 2
        name = data[pos:pos + nlen].decode("utf-8", errors="ignore"); pos += nlen
        if pos + 2 > len(data): break
        vlen = struct.unpack_from("!H", data, pos)[0]; pos += 2
        raw  = data[pos:pos + vlen]; pos += vlen
        if   tag in (0x21, 0x23): val = struct.unpack_from("!i", raw)[0] if len(raw) == 4 else 0
        elif tag == 0x22:          val = bool(raw[0]) if raw else False
        elif 0x40 <= tag <= 0x5F:  val = raw.decode("utf-8", errors="ignore")
        else:                      val = raw
        if nlen > 0: last_name = name
        if last_name:
            existing = attrs.get(last_name)
            if   existing is None:             attrs[last_name] = val
            elif isinstance(existing, list):   existing.append(val)
            else:                              attrs[last_name] = [existing, val]
    return attrs


def _query_ipp_attrs(printer_name: str) -> dict:
    uri = f"ipp://{_CUPS_HOST}/printers/{printer_name}"
    try:
        payload = _build_ipp_request(uri)
        conn    = http.client.HTTPConnection(_CUPS_HOST, _CUPS_PORT, timeout=_PRINTER_TIMEOUT)
        conn.request("POST", f"/printers/{printer_name}", body=payload,
                     headers={"Content-Type": _CUPS_CONTENT_TYPE,
                               "Content-Length": str(len(payload))})
        resp = conn.getresponse()
        return _parse_ipp_response(resp.read()) if resp.status == 200 else {}
    except Exception:
        return {}


# ── Public status API ─────────────────────────────────────────────────────────

def get_printer_info() -> dict:
    name = _get_default_printer_name()
    if name is None:
        return {"ok": False, "name": None, "status": "offline", "ink": None, "paper": None}

    ipp    = _query_ipp_attrs(name)
    status = _get_printer_status(name, ipp)
    ink    = None

    if ipp:
        levels = ipp.get("marker-levels")
        names  = ipp.get("marker-names")
        colors = ipp.get("marker-colors")
        if levels is not None and names is not None:
            if not isinstance(levels, list): levels = [levels]
            if not isinstance(names,  list): names  = [names]
            if colors and not isinstance(colors, list): colors = [colors]
            else: colors = colors or []
            ink = [{"name": nm, "level": int(lvl), "color": colors[i] if i < len(colors) else nm}
                   for i, (lvl, nm) in enumerate(zip(levels, names))]

    return {"ok": status in ("idle", "printing"), "name": name,
            "status": status, "ink": ink, "paper": None}


def check_printer_connection() -> bool:
    return get_printer_info()["ok"]


# ── Printing ──────────────────────────────────────────────────────────────────

def _save_archive(pil_img) -> str:
    os.makedirs(_PRINTS_DIR, exist_ok=True)
    path = os.path.join(_PRINTS_DIR, time.strftime(_ARCHIVE_FMT))
    pil_img.save(path, _JPEG_FORMAT, dpi=_PRINT_DPI, quality=_JPEG_QUALITY)
    print(f"Saved print: {path}")
    return path


def _send_to_cups(tmp_path: str, copies: int) -> None:
    try:
        subprocess.run(
            ["lp", "-n", str(max(1, copies)),
             "-o", _LP_MEDIA, "-o", _LP_MEDIA_TYPE, "-o", _LP_INPUT_SLOT,
             "-o", _LP_ORIENTATION, "-o", _LP_QUALITY, tmp_path],
            capture_output=True, timeout=_PRINT_TIMEOUT,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass


def _build_composite(photo_paths: list):
    from composite import build_print_image
    return build_print_image(photo_paths)


def save_polaroid(photo_paths: list) -> None:
    """Build the 4"×6" composite and archive it locally — no printer involved."""
    _save_archive(_build_composite(photo_paths))


def print_polaroid(photo_paths: list, copies: int = 1) -> None:
    """Build a 4"×6" composite, archive it, and send `copies` to the printer."""
    pil_img = _build_composite(photo_paths)
    _save_archive(pil_img)

    tmp = tempfile.NamedTemporaryFile(suffix=".png", prefix="photobooth_print_", delete=False)
    tmp.close()
    pil_img.save(tmp.name, "PNG", dpi=_PRINT_DPI)
    _send_to_cups(tmp.name, copies)
