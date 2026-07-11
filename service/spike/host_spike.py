"""M0 spike (host side): advertise an open BLE GATT characteristic and echo.

This is the load-bearing validation from PRD.md section 13 (M0): prove that a
Windows laptop can advertise a GATT server and exchange bytes over an OPEN
(unencrypted, no-pairing) characteristic using bless.

Run this on laptop A:
    python -m spike.host_spike
Then run spike/client_spike.py on laptop B. Success = the string written by the
client appears here, with NO Windows pairing prompt.

This deliberately does NOT use the bluelink package — it is a minimal,
dependency-only smoke test so a failure points squarely at bless/BLE, not our
code. The real transports live in bluelink/ble/.
"""

import asyncio
import logging

from bless import (
    BlessServer,
    GATTAttributePermissions,
    GATTCharacteristicProperties,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("host_spike")

SERVICE_UUID = "6b1d0000-8f3a-4b2c-9c4e-1a2b3c4d5e6f"
CHAR_UUID = "6b1d0001-8f3a-4b2c-9c4e-1a2b3c4d5e6f"

server: BlessServer | None = None


def on_write(characteristic, value, **kwargs):
    text = bytes(value).decode("utf-8", "replace")
    print(f"\n>>> RECEIVED over BLE (no pairing): {text!r}\n")
    # Echo back via notify so the client sees a round-trip.
    if server is not None:
        char = server.get_characteristic(CHAR_UUID)
        char.value = bytearray(f"echo:{text}".encode("utf-8"))
        server.update_value(SERVICE_UUID, CHAR_UUID)


def on_read(characteristic, **kwargs):
    return characteristic.value or bytearray(b"hello")


async def main():
    global server
    server = BlessServer(name="BLK1-SpikeHost")
    server.read_request_func = on_read
    server.write_request_func = on_write

    await server.add_new_service(SERVICE_UUID)
    flags = (
        GATTCharacteristicProperties.read
        | GATTCharacteristicProperties.write
        | GATTCharacteristicProperties.write_without_response
        | GATTCharacteristicProperties.notify
    )
    perms = GATTAttributePermissions.readable | GATTAttributePermissions.writeable
    await server.add_new_characteristic(
        SERVICE_UUID, CHAR_UUID, flags, bytearray(b"hello"), perms
    )

    await server.start()
    print("Host advertising as 'BLK1-SpikeHost'. Waiting for a client to write…")
    print("Press Ctrl+C to stop.")
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())
