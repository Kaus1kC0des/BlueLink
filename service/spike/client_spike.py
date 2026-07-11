"""M0 spike (client side): scan for the spike host and exchange a string.

Run on laptop B AFTER starting spike/host_spike.py on laptop A:
    python -m spike.client_spike

Success = it finds 'BLK1-SpikeHost', connects with NO pairing prompt, writes a
message, and prints the echoed notification from the host.
"""

import asyncio
import logging

from bleak import BleakClient, BleakScanner

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("client_spike")

SERVICE_UUID = "6b1d0000-8f3a-4b2c-9c4e-1a2b3c4d5e6f"
CHAR_UUID = "6b1d0001-8f3a-4b2c-9c4e-1a2b3c4d5e6f"


def on_notify(_char, data: bytearray):
    print(f"\n<<< NOTIFY from host: {bytes(data).decode('utf-8', 'replace')!r}\n")


async def main():
    print("Scanning for 'BLK1-SpikeHost' (service UUID filter)…")
    device = await BleakScanner.find_device_by_filter(
        lambda d, adv: SERVICE_UUID.lower() in [s.lower() for s in (adv.service_uuids or [])]
        or (adv.local_name or "").startswith("BLK1-"),
        timeout=20.0,
    )
    if device is None:
        print("No host found. Is host_spike.py running and in range?")
        return

    print(f"Found {device.name or device.address}. Connecting (no pairing)…")
    async with BleakClient(device) as client:
        print(f"Connected. Negotiated MTU: {client.mtu_size}")
        await client.start_notify(CHAR_UUID, on_notify)

        msg = "hello from the client spike"
        print(f">>> Writing: {msg!r}")
        await client.write_gatt_char(CHAR_UUID, msg.encode("utf-8"), response=True)

        await asyncio.sleep(3)  # wait for the echo notification
        await client.stop_notify(CHAR_UUID)
    print("Done. If you saw a NOTIFY above with no pairing prompt, M0 passes. ✅")


if __name__ == "__main__":
    asyncio.run(main())
