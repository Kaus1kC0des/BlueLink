"""Message routing: chunk/reassemble envelopes and move them across the link.

Two routers, one per role. Both share the framing layer; they differ only in
which direction chunks flow and whether they relay.

Host  = star hub: receives member uplinks, delivers locally, relays to others.
Member= spoke:    sends uplinks to host, receives host notifications.

1:1 chat is just the group-of-two case of the host/member code paths.

See LLD.md section 10.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Callable

from ..constants import PROTOCOL_VERSION
from ..ble.interface import HostTransport, MemberTransport
from . import envelope as env
from .framing import MsgIdCounter, Reassembler, FramingError, chunk

log = logging.getLogger("bluelink.router")

# emit(event: dict) pushes an event toward the UI (see web/protocol.py)
Emit = Callable[[dict], None]
# get_name() -> current local display name
GetName = Callable[[], str]


def _msg_event(e: env.Envelope, mine: bool) -> dict:
    d = e.data
    return {
        "t": "message",
        "id": d.get("id", ""),
        "sender": d.get("sender", "?"),
        "ts": d.get("ts", ""),
        "body": d.get("body", ""),
        "mine": mine,
        "system": False,
    }


def _system_event(text: str, ts: str = "") -> dict:
    return {
        "t": "message",
        "id": "",
        "sender": "system",
        "ts": ts,
        "body": text,
        "mine": False,
        "system": True,
    }


class HostRouter:
    """Runs on the peripheral. Fan-out hub for the group."""

    def __init__(self, transport: HostTransport, emit: Emit, get_name: GetName) -> None:
        self._t = transport
        self._emit = emit
        self._get_name = get_name
        self._reasm = Reassembler()
        self._out_id = MsgIdCounter()
        self._names: dict[str, str] = {}  # member_id -> display name

    # --- transport callbacks (sync) ---
    def on_uplink(self, member_id: str, chunk: bytes) -> None:
        try:
            payload = self._reasm.feed(member_id, chunk)
        except FramingError as exc:
            log.warning("dropping bad chunk from %s: %s", member_id, exc)
            return
        if payload is None:
            return
        self._handle_member_payload(member_id, payload)

    def on_member_change(self, member_id: str, connected: bool) -> None:
        if connected:
            self._names.setdefault(member_id, "…")
        else:
            name = self._names.pop(member_id, member_id)
            self._reasm.drop_source(member_id)
            self._emit(_system_event(f"{name} left"))
            self._broadcast_member_list()

    # --- local send (host user) ---
    async def send_local(self, body: str) -> None:
        e = env.make_msg(sender=self._get_name(), body=body)
        self._emit(_msg_event(e, mine=True))
        self._emit({"t": "sent", "id": e.data["id"]})
        await self._notify_all(e)

    # --- internals ---
    def _handle_member_payload(self, member_id: str, payload: bytes) -> None:
        try:
            e = env.Envelope.from_bytes(payload)
        except env.EnvelopeError as exc:
            log.warning("bad envelope from %s: %s", member_id, exc)
            return

        if e.type == env.T_HELLO:
            self._names[member_id] = str(e.data.get("name", "?"))[:32]
            self._emit(_system_event(f"{self._names[member_id]} joined"))
            self._broadcast_member_list()
        elif e.type == env.T_MSG:
            self._emit(_msg_event(e, mine=False))
            # relay original message to everyone except the origin
            asyncio.ensure_future(self._notify_all(e, exclude=member_id))
        else:
            log.debug("ignoring envelope type %s from member", e.type)

    async def _notify_all(self, e: env.Envelope, exclude: str | None = None) -> None:
        for c in chunk(e.to_bytes(), self._out_id.next(), self._t.mtu()):
            await self._t.notify_all(c, exclude=exclude)

    def _broadcast_member_list(self) -> None:
        members = [self._get_name()] + [
            n for n in self._names.values() if n not in ("…",)
        ]
        self._emit({"t": "member_list", "members": members, "count": len(members)})
        asyncio.ensure_future(self._notify_all(env.make_member_list(members)))


class MemberRouter:
    """Runs on the central. Talks only to the host."""

    def __init__(self, transport: MemberTransport, emit: Emit, get_name: GetName) -> None:
        self._t = transport
        self._emit = emit
        self._get_name = get_name
        self._reasm = Reassembler()
        self._out_id = MsgIdCounter()
        # Ids of messages this member originated. Real BLE notifications are
        # broadcast to every subscriber (the host cannot exclude the sender),
        # so we skip our own message when it comes back as a relay.
        self._my_ids: set[str] = set()
        self._my_id_order: list[str] = []

    # --- transport callback (sync) ---
    def on_notify(self, chunk_bytes: bytes) -> None:
        try:
            payload = self._reasm.feed("host", chunk_bytes)
        except FramingError as exc:
            log.warning("dropping bad chunk from host: %s", exc)
            return
        if payload is None:
            return
        try:
            e = env.Envelope.from_bytes(payload)
        except env.EnvelopeError as exc:
            log.warning("bad envelope from host: %s", exc)
            return

        if e.type == env.T_MSG:
            if e.data.get("id") in self._my_ids:
                return  # our own message echoed back by the host's relay
            self._emit(_msg_event(e, mine=False))
        elif e.type == env.T_MEMBER_LIST:
            members = list(e.data.get("members", []))
            self._emit({"t": "member_list", "members": members, "count": len(members)})
        elif e.type == env.T_SYSTEM:
            self._emit(_system_event(e.data.get("text", ""), e.data.get("ts", "")))

    # --- send paths ---
    async def send_hello(self) -> None:
        await self._send(env.make_hello(self._get_name(), PROTOCOL_VERSION))

    async def send_local(self, body: str) -> None:
        e = env.make_msg(sender=self._get_name(), body=body)
        self._remember_id(e.data["id"])
        self._emit(_msg_event(e, mine=True))
        self._emit({"t": "sent", "id": e.data["id"]})
        await self._send(e)

    def _remember_id(self, mid: str) -> None:
        self._my_ids.add(mid)
        self._my_id_order.append(mid)
        if len(self._my_id_order) > 256:  # bound memory
            self._my_ids.discard(self._my_id_order.pop(0))

    async def _send(self, e: env.Envelope) -> None:
        for c in chunk(e.to_bytes(), self._out_id.next(), self._t.mtu()):
            await self._t.send_uplink(c)
