"""Peripheral (GATT server) transport using bless. The 'host' side of a chat.

Advertises SERVICE_UUID, exposes the Message (write + notify) and Info (read)
characteristics with open permissions (no pairing), and relays via notifications.

Limitations of the bless GATT-server abstraction (validated in M0/M3, see
PRD.md section 12):
  * Writes do not identify which central sent them, so all uplinks are attributed
    to a single logical source. Membership is instead driven by `hello` envelopes
    at the app layer (router), which works without transport-level connect events.
  * Notifications are broadcast to every subscriber; the origin cannot be excluded
    at the transport. The MemberRouter dedupes its own echoed messages by id.
  * The negotiated MTU is not readily exposed; notification chunk size is kept
    conservative (override with BLUELINK_HOST_MTU once measured).
"""

from __future__ import annotations

import json
import logging
import os

from bless import (
    BlessServer,
    GATTAttributePermissions,
    GATTCharacteristicProperties,
)

from ..constants import (
    CHAR_INFO_UUID,
    CHAR_MESSAGE_UUID,
    DEFAULT_MTU,
    SERVICE_UUID,
)
from .interface import BleError, HostInfo, HostTransport, OnMemberChange, OnUplink

log = logging.getLogger("bluelink.peripheral")

# Conservative notification payload sizing. MTU 23 -> 20-byte payloads works on
# every adapter; raise via env once real MTU is measured (M2).
HOST_MTU = int(os.environ.get("BLUELINK_HOST_MTU", str(DEFAULT_MTU)))

# One synthetic member id, since bless writes don't identify the central.
_SINGLE_SOURCE = "peer"


class HostBleTransport(HostTransport):
    def __init__(self) -> None:
        self._server: BlessServer | None = None
        self._info_provider = None
        self._on_uplink: OnUplink | None = None
        self._on_member_change: OnMemberChange | None = None

    async def start(self, adv_name, info_provider, on_uplink, on_member_change) -> None:
        self._info_provider = info_provider
        self._on_uplink = on_uplink
        self._on_member_change = on_member_change

        server = BlessServer(name=adv_name)
        server.read_request_func = self._on_read
        server.write_request_func = self._on_write

        try:
            await server.add_new_service(SERVICE_UUID)

            msg_flags = (
                GATTCharacteristicProperties.read
                | GATTCharacteristicProperties.write
                | GATTCharacteristicProperties.write_without_response
                | GATTCharacteristicProperties.notify
            )
            msg_perms = (
                GATTAttributePermissions.readable | GATTAttributePermissions.writeable
            )
            await server.add_new_characteristic(
                SERVICE_UUID, CHAR_MESSAGE_UUID, msg_flags, None, msg_perms
            )

            await server.add_new_characteristic(
                SERVICE_UUID,
                CHAR_INFO_UUID,
                GATTCharacteristicProperties.read,
                self._info_bytes(),
                GATTAttributePermissions.readable,
            )

            await server.start()
        except BleError:
            raise
        except Exception as exc:
            raise BleError("peripheral_unsupported", str(exc)) from exc

        self._server = server
        log.info("GATT server advertising as %r", adv_name)

    def _info_bytes(self) -> bytearray:
        info = self._info_provider() if self._info_provider else None
        obj = {
            "proto": info.proto if info else 1,
            "host": info.host_name if info else "host",
            "members": info.members if info else 0,
            "max_members": info.max_members if info else 0,
        }
        return bytearray(json.dumps(obj, separators=(",", ":")).encode("utf-8"))

    # --- bless callbacks (sync) ---
    def _on_read(self, characteristic, **kwargs) -> bytearray:
        if _same_uuid(characteristic.uuid, CHAR_INFO_UUID):
            return self._info_bytes()
        return characteristic.value or bytearray()

    def _on_write(self, characteristic, value, **kwargs) -> None:
        if _same_uuid(characteristic.uuid, CHAR_MESSAGE_UUID):
            if self._on_uplink:
                self._on_uplink(_SINGLE_SOURCE, bytes(value))

    # --- HostTransport API ---
    async def notify(self, member_id: str, chunk: bytes) -> None:
        # bless cannot target a single subscriber; broadcast to all.
        await self.notify_all(chunk)

    async def notify_all(self, chunk: bytes, exclude: str | None = None) -> None:
        if not self._server:
            return
        char = self._server.get_characteristic(CHAR_MESSAGE_UUID)
        if char is None:
            return
        char.value = bytearray(chunk)
        self._server.update_value(SERVICE_UUID, CHAR_MESSAGE_UUID)

    def members(self) -> list[str]:
        # Transport can't enumerate centrals; membership is tracked in the router.
        return []

    def mtu(self) -> int:
        return HOST_MTU

    async def stop(self) -> None:
        server, self._server = self._server, None
        if server:
            try:
                await server.stop()
            except Exception as exc:
                log.warning("server stop error: %s", exc)


def _same_uuid(a: str, b: str) -> bool:
    return str(a).lower() == str(b).lower()
