"""FastAPI app: the /ws endpoint and static UI serving.

Everything is loopback-only. The core's `emit` pushes events onto an asyncio
queue; a broadcaster task fans them out to all connected browser clients.
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from ..config import Config
from ..core.session import SessionManager
from .protocol import ProtocolError, dispatch

log = logging.getLogger("bluelink.server")

_PLACEHOLDER = """<!doctype html><meta charset=utf-8>
<title>BlueLink</title>
<body style="font-family:system-ui;max-width:40rem;margin:3rem auto;padding:0 1rem">
<h1>BlueLink service is running</h1>
<p>The web UI has not been built yet. Build it with:</p>
<pre>cd ui &amp;&amp; npm install &amp;&amp; npm run build</pre>
<p>Then reload this page. The WebSocket API is live at <code>/ws</code>.</p>
</body>"""


def make_factories(cfg: Config):
    """Return (host_factory, member_factory).

    Set BLUELINK_FAKE=1 to use the in-memory transport (single-process UI dev,
    no real BLE and no cross-machine comms).
    """
    if os.environ.get("BLUELINK_FAKE"):
        from ..ble.fake import FakeHostTransport, FakeMemberTransport, FakeRadio

        radio = FakeRadio()
        return (lambda: FakeHostTransport(radio), lambda: FakeMemberTransport(radio))

    from ..ble.central import MemberBleTransport
    from ..ble.peripheral import HostBleTransport

    return (lambda: HostBleTransport(), lambda: MemberBleTransport())


def build_app(cfg: Config, save_name, initial_name: str) -> FastAPI:
    app = FastAPI(title="BlueLink")

    clients: set[WebSocket] = set()
    out_queue: asyncio.Queue = asyncio.Queue()
    loop_holder: dict[str, asyncio.AbstractEventLoop] = {}

    def emit(ev: dict) -> None:
        loop = loop_holder.get("loop")
        if loop is None:
            return
        try:
            loop.call_soon_threadsafe(out_queue.put_nowait, ev)
        except RuntimeError:
            pass

    host_factory, member_factory = make_factories(cfg)
    sm = SessionManager(
        name=initial_name,
        emit=emit,
        host_factory=host_factory,
        member_factory=member_factory,
    )
    app.state.session = sm

    async def _broadcast() -> None:
        while True:
            ev = await out_queue.get()
            dead = []
            for ws in list(clients):
                try:
                    await ws.send_json(ev)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                clients.discard(ws)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        loop_holder["loop"] = asyncio.get_running_loop()
        task = asyncio.create_task(_broadcast())
        try:
            yield
        finally:
            task.cancel()

    app.router.lifespan_context = lifespan

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket) -> None:
        await ws.accept()
        clients.add(ws)
        sm.emit_status()  # tell the newly connected UI the current state
        try:
            while True:
                msg = await ws.receive_json()
                try:
                    await dispatch(sm, msg, save_name)
                except ProtocolError as exc:
                    await ws.send_json(
                        {"t": "error", "code": "bad_command", "detail": str(exc)}
                    )
                except Exception as exc:  # never let one bad command kill the socket
                    log.exception("command failed")
                    await ws.send_json(
                        {"t": "error", "code": "internal", "detail": str(exc)}
                    )
        except WebSocketDisconnect:
            pass
        finally:
            clients.discard(ws)

    # Serve the built UI if present; otherwise a placeholder page.
    dist = Path(__file__).resolve().parents[3] / "ui" / "dist"
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=str(dist), html=True), name="ui")
    else:

        @app.get("/")
        async def _placeholder() -> HTMLResponse:
            return HTMLResponse(_PLACEHOLDER)

    return app
