import os
import re
from datetime import datetime

_PHOTO_RE = re.compile(r"^photo_(\d{8}_\d{6})_(\d+)\.jpg$", re.IGNORECASE)
_PRINT_RE = re.compile(r"^print_(\d{8}_\d{6})\.jpg$", re.IGNORECASE)
_TS_FORMAT = "%Y%m%d_%H%M%S"


def _parse_ts(ts: str) -> datetime:
    return datetime.strptime(ts, _TS_FORMAT)


def list_sessions(photos_dir: str, prints_dir: str) -> list[dict]:
    """Group captured photos into sessions by their shared capture timestamp
    (encoded in the filenames: photo_YYYYMMDD_HHMMSS_N.jpg, print_YYYYMMDD_HHMMSS.jpg).
    Returns newest-first: [{"id", "time", "photos": [filename, ...], "strip": filename|None}]."""
    sessions: dict[str, dict] = {}

    if os.path.isdir(photos_dir):
        for fname in os.listdir(photos_dir):
            m = _PHOTO_RE.match(fname)
            if not m:
                continue
            ts, idx = m.group(1), int(m.group(2))
            sessions.setdefault(ts, {"photos": {}, "strip": None})["photos"][idx] = fname

    if os.path.isdir(prints_dir):
        for fname in os.listdir(prints_dir):
            m = _PRINT_RE.match(fname)
            if not m:
                continue
            sessions.setdefault(m.group(1), {"photos": {}, "strip": None})["strip"] = fname

    result = []
    for ts, data in sessions.items():
        photos = [data["photos"][i] for i in sorted(data["photos"])]
        if not photos:
            continue
        result.append({"id": ts, "time": _parse_ts(ts), "photos": photos, "strip": data["strip"]})

    result.sort(key=lambda entry: entry["time"], reverse=True)
    return result


def find_session(sessions: list[dict], session_id: str) -> dict | None:
    return next((s for s in sessions if s["id"] == session_id), None)


def total_photo_count(sessions: list[dict]) -> int:
    return sum(len(s["photos"]) for s in sessions)


def flatten(sessions: list[dict]) -> list[tuple[str, int]]:
    """Every (session_id, local_index) pair in gallery display order — newest
    session first, capture order within a session — for prev/next swipe nav."""
    return [(s["id"], i + 1) for s in sessions for i in range(len(s["photos"]))]
