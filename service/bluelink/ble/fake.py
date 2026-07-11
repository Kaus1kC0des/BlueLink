"""In-memory fake transport for testing the core without a BLE radio.

A FakeRadio is a shared bus. Fake hosts register on it; fake members scan and
connect through it. Chunks are delivered via asyncio callbacks, mimicking the
write (uplink) and notify (downlink) paths of real BLE.
"""

from __future__ import annotations

import itertools
from typing import Callable

from .interface import (
    BleError,
    HostInfo,
    HostTransport,
    MemberTransport,
    OnDisconnect,
    OnMemberChange,
    OnNotify,
    OnScanResult,
    OnUplink,
    ScanResult,
)

FAKE_MTU = 100


class FakeRadio:
    """Shared in-memory medium connecting fake hosts and members."""

    def __init__(self) -> None:
        self.hosts: dict[str, "FakeHostTransport"] = {}
        self._ids = itertools.count(1)

    def register_host(self, host: "FakeHostTransport") -> None:
        self.hosts[host.addr] = host

    def unregister_host(self, addr: str) -> None:
        self.hosts.pop(addr, None)

    def next_member_id(self) -> str:
        return f"m{next(self._ids)}"


class FakeHostTransport(HostTransport):
    def __init__(self, radio: FakeRadio, addr: str = "FAKE-HOST") -> None:
        self.radio = radio
        self.addr = addr
        self.adv_name = ""
        self._info_provider: Callable[[], HostInfo] | None = None
        self._on_uplink: OnUplink | None = None
        self._on_member_change: OnMemberChange | None = None
        # member_id -> that member's on_notify callback
        self._members: dict[str, OnNotify] = {}

    async def start(self, adv_name, info_provider, on_uplink, on_member_change) -> None:
        self.adv_name = adv_name
        self._info_provider = info_provider
        self._on_uplink = on_uplink
        self._on_member_change = on_member_change
        self.radio.register_host(self)

    # --- called by the fake member when joining/leaving ---
    def _attach_member(self, on_notify: OnNotify) -> tuple[str, HostInfo]:
        assert self._info_provider and self._on_member_change
        member_id = self.radio.next_member_id()
        self._members[member_id] = on_notify
        self._on_member_change(member_id, True)
        return member_id, self._info_provider()

    def _detach_member(self, member_id: str) -> None:
        if self._members.pop(member_id, None) is not None and self._on_member_change:
            self._on_member_change(member_id, False)

    def _receive_uplink(self, member_id: str, chunk: bytes) -> None:
        if self._on_uplink:
            self._on_uplink(member_id, chunk)

    # --- HostTransport API ---
    async def notify(self, member_id: str, chunk: bytes) -> None:
        cb = self._members.get(member_id)
        if cb:
            cb(chunk)

    async def notify_all(self, chunk: bytes, exclude: str | None = None) -> None:
        for mid, cb in list(self._members.items()):
            if mid != exclude:
                cb(chunk)

    def members(self) -> list[str]:
        return list(self._members)

    def mtu(self) -> int:
        return FAKE_MTU

    async def stop(self) -> None:
        self.radio.unregister_host(self.addr)
        for mid in list(self._members):
            self._detach_member(mid)


class FakeMemberTransport(MemberTransport):
    def __init__(self, radio: FakeRadio) -> None:
        self.radio = radio
        self._host: FakeHostTransport | None = None
        self._member_id: str | None = None
        self._scanning = False

    async def scan(self, on_result: OnScanResult) -> None:
        self._scanning = True
        for addr, host in list(self.radio.hosts.items()):
            on_result(ScanResult(addr=addr, name=host.adv_name, rssi=-50))

    async def stop_scan(self) -> None:
        self._scanning = False

    async def join(self, addr, on_notify: OnNotify, on_disconnect: OnDisconnect) -> HostInfo:
        host = self.radio.hosts.get(addr)
        if host is None:
            raise BleError("connect_failed", f"no fake host at {addr}")
        self._host = host
        self._on_disconnect = on_disconnect
        self._member_id, info = host._attach_member(on_notify)
        return info

    async def send_uplink(self, chunk: bytes) -> None:
        if not self._host or not self._member_id:
            raise BleError("peer_disconnected", "not connected")
        self._host._receive_uplink(self._member_id, chunk)

    def mtu(self) -> int:
        return FAKE_MTU

    async def leave(self) -> None:
        if self._host and self._member_id:
            self._host._detach_member(self._member_id)
        self._host = None
        self._member_id = None
