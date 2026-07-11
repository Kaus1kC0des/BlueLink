"""Session manager: role/connection state machine and command handling.

Owns the current role (idle / host / member), constructs the right router and
transport, and turns UI commands into transport actions. Emits UI events via an
injected `emit` callback. See LLD.md section 7.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Callable

from ..constants import ADV_NAME_MAX, ADV_NAME_PREFIX, MAX_MEMBERS, PROTOCOL_VERSION
from ..ble.interface import (
    BleError,
    HostInfo,
    HostTransport,
    MemberTransport,
    ScanResult,
)
from .router import HostRouter, MemberRouter

log = logging.getLogger("bluelink.session")

Emit = Callable[[dict], None]
HostFactory = Callable[[], HostTransport]
MemberFactory = Callable[[], MemberTransport]


class Role(str, Enum):
    IDLE = "idle"
    HOST = "host"
    MEMBER = "member"


class State(str, Enum):
    IDLE = "idle"
    ADVERTISING = "advertising"
    HOSTING = "hosting"
    SCANNING = "scanning"
    CONNECTING = "connecting"
    CONNECTED = "connected"


class SessionManager:
    def __init__(
        self,
        name: str,
        emit: Emit,
        host_factory: HostFactory,
        member_factory: MemberFactory,
    ) -> None:
        self._name = name
        self._emit = emit
        self._host_factory = host_factory
        self._member_factory = member_factory

        self.role = Role.IDLE
        self.state = State.IDLE
        self._host_host_name: str | None = None

        self._host_t: HostTransport | None = None
        self._member_t: MemberTransport | None = None
        self._host_router: HostRouter | None = None
        self._member_router: MemberRouter | None = None
        self._peers: dict[str, ScanResult] = {}

    # --- helpers ---
    def name(self) -> str:
        return self._name

    def _adv_name(self) -> str:
        short = self._name[: ADV_NAME_MAX - len(ADV_NAME_PREFIX)]
        return ADV_NAME_PREFIX + short

    def _set_state(self, role: Role, state: State) -> None:
        self.role = role
        self.state = state
        self.emit_status()

    def emit_status(self) -> None:
        self._emit(
            {
                "t": "status",
                "role": self.role.value,
                "state": self.state.value,
                "host_name": self._host_host_name,
                "name": self._name,
            }
        )

    def host_info(self) -> HostInfo:
        members = len(self._host_t.members()) if self._host_t else 0
        return HostInfo(
            proto=PROTOCOL_VERSION,
            host_name=self._name,
            members=members,
            max_members=MAX_MEMBERS,
        )

    # --- commands ---
    def set_name(self, name: str) -> None:
        self._name = name
        self.emit_status()

    async def host(self) -> None:
        if self.role != Role.IDLE:
            await self._teardown()
        self._host_t = self._host_factory()
        self._host_router = HostRouter(self._host_t, self._emit, self.name)
        try:
            await self._host_t.start(
                adv_name=self._adv_name(),
                info_provider=self.host_info,
                on_uplink=self._host_router.on_uplink,
                on_member_change=self._host_router.on_member_change,
            )
        except BleError as exc:
            self._emit({"t": "error", "code": exc.code, "detail": exc.detail})
            await self._teardown()
            return
        self._set_state(Role.HOST, State.ADVERTISING)

    async def stop_host(self) -> None:
        await self._teardown()

    async def scan(self) -> None:
        if self.role == Role.HOST:
            await self._teardown()
        if self._member_t is None:
            self._member_t = self._member_factory()
        self._peers.clear()
        self._emit({"t": "peers", "peers": []})

        def on_result(r: ScanResult) -> None:
            self._peers[r.addr] = r
            self._emit(
                {
                    "t": "peers",
                    "peers": [
                        {"addr": p.addr, "name": p.name, "rssi": p.rssi}
                        for p in sorted(
                            self._peers.values(), key=lambda x: x.rssi, reverse=True
                        )
                    ],
                }
            )

        self._set_state(Role.MEMBER, State.SCANNING)
        try:
            await self._member_t.scan(on_result)
        except BleError as exc:
            self._emit({"t": "error", "code": exc.code, "detail": exc.detail})

    async def stop_scan(self) -> None:
        if self._member_t:
            await self._member_t.stop_scan()
        if self.state == State.SCANNING:
            self._set_state(Role.IDLE, State.IDLE)

    async def join(self, addr: str) -> None:
        if self._member_t is None:
            self._member_t = self._member_factory()
        await self._member_t.stop_scan()
        self._member_router = MemberRouter(self._member_t, self._emit, self.name)
        self._set_state(Role.MEMBER, State.CONNECTING)
        try:
            info = await self._member_t.join(
                addr,
                on_notify=self._member_router.on_notify,
                on_disconnect=self._on_member_disconnect,
            )
        except BleError as exc:
            self._emit({"t": "error", "code": exc.code, "detail": exc.detail})
            self._set_state(Role.IDLE, State.IDLE)
            return
        self._host_host_name = info.host_name
        self._set_state(Role.MEMBER, State.CONNECTED)
        await self._member_router.send_hello()

    async def leave(self) -> None:
        await self._teardown()

    async def send(self, body: str) -> None:
        if self.role == Role.HOST and self._host_router:
            await self._host_router.send_local(body)
        elif self.role == Role.MEMBER and self._member_router and self.state == State.CONNECTED:
            await self._member_router.send_local(body)
        else:
            self._emit(
                {"t": "error", "code": "not_connected", "detail": "no active chat"}
            )

    # --- transport callbacks ---
    def _on_member_disconnect(self) -> None:
        self._emit({"t": "error", "code": "peer_disconnected", "detail": "host lost"})
        self._host_host_name = None
        self.role = Role.IDLE
        self.state = State.IDLE
        self.emit_status()

    # --- teardown ---
    async def _teardown(self) -> None:
        try:
            if self._host_t:
                await self._host_t.stop()
            if self._member_t:
                await self._member_t.leave()
        except BleError as exc:
            log.warning("teardown error: %s", exc)
        finally:
            self._host_t = None
            self._member_t = None
            self._host_router = None
            self._member_router = None
            self._host_host_name = None
            self._set_state(Role.IDLE, State.IDLE)
