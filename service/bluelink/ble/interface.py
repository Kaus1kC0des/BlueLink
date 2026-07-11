"""Transport abstraction the core depends on.

The core (session/router) talks only to these interfaces, never to bleak/bless
directly. This keeps the core testable with a fake transport and lets a future
native WinRT helper slot in without touching the core (HLD section 11).

Two concrete roles:
  * HostTransport   (peripheral / GATT server, bless)   -- see peripheral.py
  * MemberTransport (central / GATT client, bleak)       -- see central.py
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Awaitable, Callable


class BleError(Exception):
    """Base class for transport failures, carrying a typed error code."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class ScanResult:
    addr: str
    name: str
    rssi: int


@dataclass(frozen=True)
class HostInfo:
    proto: int
    host_name: str
    members: int
    max_members: int


# Callback signatures
OnScanResult = Callable[[ScanResult], None]
# host side: (member_id, chunk_bytes)
OnUplink = Callable[[str, bytes], None]
# host side: (member_id, connected: bool)
OnMemberChange = Callable[[str, bool], None]
# member side: (chunk_bytes)
OnNotify = Callable[[bytes], None]
# member/host: connection lost
OnDisconnect = Callable[[], None]


class HostTransport(ABC):
    """Peripheral role: advertise, accept centrals, notify (downlink)."""

    @abstractmethod
    async def start(
        self,
        adv_name: str,
        info_provider: Callable[[], HostInfo],
        on_uplink: OnUplink,
        on_member_change: OnMemberChange,
    ) -> None:
        """Start the GATT server and begin advertising."""

    @abstractmethod
    async def notify(self, member_id: str, chunk: bytes) -> None:
        """Send one chunk to a single connected member."""

    @abstractmethod
    async def notify_all(self, chunk: bytes, exclude: str | None = None) -> None:
        """Send one chunk to all connected members except *exclude*."""

    @abstractmethod
    def members(self) -> list[str]:
        """Currently connected member ids."""

    @abstractmethod
    def mtu(self) -> int:
        """Safe chunking MTU for notifications (min across connected members).

        Conservative: a value that fits every current member's negotiated MTU.
        """

    @abstractmethod
    async def stop(self) -> None:
        """Stop advertising and disconnect all members."""


class MemberTransport(ABC):
    """Central role: scan, connect, subscribe, write (uplink)."""

    @abstractmethod
    async def scan(self, on_result: OnScanResult) -> None:
        """Start scanning; call *on_result* for each discovered host."""

    @abstractmethod
    async def stop_scan(self) -> None: ...

    @abstractmethod
    async def join(
        self, addr: str, on_notify: OnNotify, on_disconnect: OnDisconnect
    ) -> HostInfo:
        """Connect (no pairing), negotiate MTU, read+verify Info, subscribe.

        Raises BleError('incompatible_protocol') on version mismatch.
        """

    @abstractmethod
    async def send_uplink(self, chunk: bytes) -> None:
        """Write one chunk to the host's Message characteristic."""

    @abstractmethod
    def mtu(self) -> int:
        """Negotiated ATT MTU for the active connection."""

    @abstractmethod
    async def leave(self) -> None:
        """Disconnect from the host."""
