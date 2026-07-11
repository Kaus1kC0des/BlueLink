"""WebSocket command dispatch between the UI and the SessionManager.

Commands (UI -> service) are JSON objects with a `t` field. This module
validates them and calls the matching SessionManager coroutine. Events
(service -> UI) are produced by the core via its `emit` callback and are
forwarded verbatim by the server. See LLD.md section 5.
"""

from __future__ import annotations

import logging

from ..constants import MAX_BODY_BYTES
from ..core.session import SessionManager

log = logging.getLogger("bluelink.ws")


class ProtocolError(Exception):
    pass


async def dispatch(sm: SessionManager, msg: dict, save_name) -> None:
    """Execute one UI command against the session.

    *save_name* persists the display name locally when `set_name` arrives.
    """
    t = msg.get("t")
    if t == "set_name":
        name = save_name(str(msg.get("name", "")))
        sm.set_name(name)
    elif t == "host":
        await sm.host()
    elif t == "stop_host":
        await sm.stop_host()
    elif t == "scan":
        await sm.scan()
    elif t == "stop_scan":
        await sm.stop_scan()
    elif t == "join":
        addr = msg.get("addr")
        if not addr:
            raise ProtocolError("join requires 'addr'")
        await sm.join(str(addr))
    elif t == "leave":
        await sm.leave()
    elif t == "send":
        body = str(msg.get("body", ""))
        if len(body.encode("utf-8")) > MAX_BODY_BYTES:
            raise ProtocolError("message_too_large")
        await sm.send(body)
    elif t == "get_status":
        sm.emit_status()
    else:
        raise ProtocolError(f"unknown command {t!r}")
