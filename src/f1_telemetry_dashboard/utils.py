from __future__ import annotations

import base64
import os
from pathlib import Path

import numpy as np
import pandas as pd


def image_to_base64(image_path: str | os.PathLike[str]) -> str | None:
    p = Path(image_path)
    if not p.exists():
        return None
    encoded = base64.b64encode(p.read_bytes()).decode("ascii")
    ext = p.suffix.lower()
    mime = "image/jpeg" if ext in [".jpg", ".jpeg"] else "image/png"
    return f"data:{mime};base64,{encoded}"


def data_uri_to_bytes(src: str | None) -> bytes | None:
    if not src:
        return None
    if isinstance(src, str) and src.startswith("data:") and "base64," in src:
        b64 = src.split("base64,", 1)[1]
        try:
            return base64.b64decode(b64)
        except Exception:
            return None
    return None


def format_timedelta(td) -> str:
    if td is None or pd.isna(td):
        return "N/A"
    total_seconds = td.total_seconds()
    minutes = int(total_seconds // 60)
    seconds = int(total_seconds % 60)
    milliseconds = int((total_seconds - int(total_seconds)) * 1000)
    return f"{minutes}:{seconds:02d}.{milliseconds:03d}"


def safe_int(value, default: int = 1) -> int:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def sanitize_filename(name: str) -> str:
    if not name:
        return "report"
    safe = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in name)
    while "__" in safe:
        safe = safe.replace("__", "_")
    return safe.strip("_") or "report"


def is_valid_td(x) -> bool:
    if x is None:
        return False
    if isinstance(x, (pd.Series, pd.Index, np.ndarray)):
        return not pd.isna(x).all()
    return not pd.isna(x)

