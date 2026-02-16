from __future__ import annotations

import re
from pathlib import Path


def sanitize_filename(name: str) -> str:
    sanitized = re.sub(r"[^0-9A-Za-zぁ-んァ-ヶ一-龠ー_\- ]+", "", name).strip()
    sanitized = re.sub(r"\s+", "_", sanitized)
    return sanitized[:64] or "clip"


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path
