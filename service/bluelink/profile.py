"""Local user profile (display name). Stored on disk; never sent to a network."""

from __future__ import annotations

import json
from pathlib import Path

DEFAULT_NAME = "Anonymous"
MAX_NAME_LEN = 32


def _sanitize(name: str) -> str:
    name = (name or "").strip().replace("\n", " ")
    if not name:
        name = DEFAULT_NAME
    return name[:MAX_NAME_LEN]


def load_name(path: Path) -> str:
    try:
        obj = json.loads(Path(path).read_text(encoding="utf-8"))
        return _sanitize(obj.get("name", DEFAULT_NAME))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return DEFAULT_NAME


def save_name(path: Path, name: str) -> str:
    name = _sanitize(name)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"name": name}), encoding="utf-8")
    return name
