"""Central (client) transport using bleak. The 'join' side of a chat.

Scans for hosts advertising SERVICE_UUID, connects with no pairing, negotiates
MTU, reads+verifies the Info characteristic, and subscribes to notifications.
See LLD.md sections 3 and 7.2.
"""

from __future__ import annotations

import json
import logging

from bleak import BleakClient, BleakScanner

from ..constants import (
    CHAR_INFO_UUID,
    CHAR_MESSAGE_UUID,
    DEFAULT_MTU,
    PROTOCOL_VERSION,
    SERVICE_UUID,
)
from .interface import (
    BleError,
    HostInfo,
    MemberTransport,
    OnDisconnect,
    OnNotify,
    OnScanResult,
    ScanResult,
)

log = logging.getLogger("bluelink.central")


class MemberBleTransport(MemberTransport):
    def __init__(self) -> None:
        self._scanner: BleakScanner | None = None
        self._client: BleakClient | None = None
        self._on_notify: OnNotify | None = None

    async def scan(self, on_result: OnScanResult) -> None:
        def _cb(device, adv):
            name = adv.local_name or device.name or device.address
            on_result(ScanResult(addr=device.address, name=name, rssi=adv.rssi or -100))

        self._scanner = BleakScanner(
            detection_callback=_cb, service_uuids=[SERVICE_UUID]
        )
        try:
            await self._scanner.start()
        except Exception as exc:  # adapter off / unsupported
            raise BleError("adapter_unavailable", str(exc)) from exc

    async def stop_scan(self) -> None:
        if self._scanner:
            try:
                await self._scanner.stop()
            except Exception:
                pass
            self._scanner = None

    async def join(
        self, addr: str, on_notify: OnNotify, on_disconnect: OnDisconnect
    ) -> HostInfo:
        await self.stop_scan()
        self._on_notify = on_notify

        def _disc(_client):
            on_disconnect()

        self._client = BleakClient(addr, disconnected_callback=_disc)
        try:
            await self._client.connect()  # no pairing: chars are open
        except Exception as exc:
            self._client = None
            raise BleError("connect_failed", str(exc)) from exc

        # Read + verify protocol version before doing anything else.
        try:
            raw = await self._client.read_gatt_char(CHAR_INFO_UUID)
            info = json.loads(bytes(raw).decode("utf-8"))
        except Exception as exc:
            await self.leave()
            raise BleError("connect_failed", f"info read failed: {exc}") from exc

        if int(info.get("proto", -1)) != PROTOCOL_VERSION:
            await self.leave()
            raise BleError(
                "incompatible_protocol",
                f"host proto {info.get('proto')} != {PROTOCOL_VERSION}",
            )

        def _notify_cb(_char, data: bytearray):
            if self._on_notify:
                self._on_notify(bytes(data))

        await self._client.start_notify(CHAR_MESSAGE_UUID, _notify_cb)

        return HostInfo(
            proto=int(info["proto"]),
            host_name=str(info.get("host", "host")),
            members=int(info.get("members", 0)),
            max_members=int(info.get("max_members", 0)),
        )

    async def send_uplink(self, chunk: bytes) -> None:
        if not self._client or not self._client.is_connected:
            raise BleError("peer_disconnected", "not connected")
        try:
            # write-with-response for reliable, ordered chat delivery
            await self._client.write_gatt_char(CHAR_MESSAGE_UUID, chunk, response=True)
        except Exception as exc:
            raise BleError("peer_disconnected", str(exc)) from exc

    def mtu(self) -> int:
        if self._client is not None:
            try:
                return int(self._client.mtu_size)
            except Exception:
                pass
        return DEFAULT_MTU

    async def leave(self) -> None:
        client, self._client = self._client, None
        self._on_notify = None
        if client and client.is_connected:
            try:
                await client.disconnect()
            except Exception:
                pass
