"""Entrypoint: start the BlueLink service and open the UI.

    python -m bluelink            # normal (real BLE)
    BLUELINK_FAKE=1 python -m bluelink   # in-memory transport (UI dev only)
"""

from __future__ import annotations

import socket
import threading
import webbrowser

import uvicorn

from . import config as config_mod
from . import logging_setup, profile
from .web.server import build_app


def _find_free_port(host: str, preferred: int, tries: int = 20) -> int:
    for port in range(preferred, preferred + tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((host, port))
                return port
            except OSError:
                continue
    return preferred  # fall back; uvicorn will surface the bind error


def main() -> None:
    cfg = config_mod.load()
    cfg.ensure_dirs()
    log = logging_setup.setup(cfg.log_level, cfg.log_path)

    name = profile.load_name(cfg.profile_path)

    def save_name(new: str) -> str:
        return profile.save_name(cfg.profile_path, new)

    port = _find_free_port(cfg.ws_host, cfg.ws_port)
    url = f"http://{cfg.ws_host}:{port}/"

    app = build_app(cfg, save_name, initial_name=name)

    log.info("BlueLink starting as %r at %s", name, url)
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    uvicorn.run(app, host=cfg.ws_host, port=port, log_level=cfg.log_level.lower())


if __name__ == "__main__":
    main()
