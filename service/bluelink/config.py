"""Local-only runtime configuration.

None of these values cross the BLE wire, so they can NEVER affect interop.
The interop contract lives in constants.py.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _default_data_dir() -> Path:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return Path(base) / "BlueLink"


@dataclass
class Config:
    ws_host: str = "127.0.0.1"  # MUST stay loopback (SEC-3); never bind 0.0.0.0
    ws_port: int = 8760  # if busy, launcher picks the next free port
    log_level: str = "INFO"
    data_dir: Path = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.data_dir is None:
            self.data_dir = _default_data_dir()
        self.data_dir = Path(self.data_dir)

    @property
    def profile_path(self) -> Path:
        return self.data_dir / "profile.json"

    @property
    def log_path(self) -> Path:
        return self.data_dir / "bluelink.log"

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)


def load() -> Config:
    """Load config from environment overrides (all optional, local-only)."""
    cfg = Config(
        ws_host=os.environ.get("BLUELINK_WS_HOST", "127.0.0.1"),
        ws_port=int(os.environ.get("BLUELINK_WS_PORT", "8760")),
        log_level=os.environ.get("BLUELINK_LOG_LEVEL", "INFO"),
    )
    # Safety rail: the service must never be reachable off-box.
    if cfg.ws_host not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError(
            f"ws_host must be loopback for the offline guarantee, got {cfg.ws_host!r}"
        )
    return cfg
