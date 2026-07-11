# BlueLink

**Serverless, off-grid chat for laptops over Bluetooth Low Energy — no internet, no server, no pairing.**

Two laptops running BlueLink can chat directly over BLE with nothing in between:
no Wi-Fi, no cellular, no router, no accounts, no OS Bluetooth pairing. A React
web UI runs in your browser and talks over `localhost` to a small Python service
that owns the BLE radio.

See [PRD.md](PRD.md), [TECHNICAL_PRD.md](TECHNICAL_PRD.md), [HLD.md](HLD.md), and
[LLD.md](LLD.md) for the full design.

> **Status:** v0.1 prototype. Core, WebSocket API, and UI are built and tested.
> Live two-laptop BLE messaging depends on the **M0 hardware spike** passing
> (see below). v1 has **no encryption and no access control** — anyone in range
> can connect and sniff. Do not use it for anything confidential.

---

## Requirements

- **Windows 10/11** with a working Bluetooth LE adapter (that supports the
  peripheral/GATT-server role — validated by the M0 spike).
- **Python 3.11** — *required*, not 3.12+. The BLE peripheral library (`bless`)
  depends on `bleak` 0.20.x and the `bleak_winrt` wheels, which stop at CP311.
- **Node.js 18+** and npm (to build the UI once).

You can get Python 3.11 via [python.org](https://www.python.org/downloads/) or conda:
```bash
conda create -n bl311 python=3.11
```

## One-time setup (do this while online)

```bash
# 1. Backend service
cd service
py -3.11 -m venv .venv            # or: <path-to-python3.11> -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 2. Frontend (build once; the service then serves it offline)
cd ../ui
npm install
npm run build                     # emits ui/dist, served by the service
```

## Run

```bash
cd service
.venv\Scripts\activate
python -m bluelink
```

This starts the local service and opens your browser to the UI
(`http://127.0.0.1:8760/`). Do this on **both** laptops.

To chat:
1. On both laptops, enter a display name.
2. On one laptop, click **Host a chat**.
3. On the other, click **Scan for hosts**, then **Join** the host.
4. Type and send. For a group, more laptops just **Join** the same host.

Everything works with Wi-Fi and Ethernet **off**.

## How two independent machines can talk (interop)

Interoperability is a **build-time contract**, not configuration. Both machines
run the same repo, so they share the same BLE UUIDs, wire framing, and
`PROTOCOL_VERSION` (all in [`service/bluelink/constants.py`](service/bluelink/constants.py)).
There is nothing per-machine to configure — no keys, no addresses, no pairing.
If two machines run mismatched versions, the join handshake fails cleanly with a
clear error instead of misbehaving. See [TECHNICAL_PRD.md §4](TECHNICAL_PRD.md).

## M0 spike — validate BLE on your hardware first

Before relying on live messaging, prove BLE peripheral+central works on your two
Windows laptops with **no pairing prompt**:

```bash
# Laptop A:
cd service && .venv\Scripts\activate
python -m spike.host_spike

# Laptop B:
cd service && .venv\Scripts\activate
python -m spike.client_spike
```

Success = the client's string appears on the host and the host's echo appears on
the client, with **no Windows pairing dialog**. If this fails, hosting via
`bless` isn't viable on that adapter (see PRD.md risk #1 and its fallback).

## Development

```bash
# Run the service against an in-memory fake transport (no BLE, UI dev):
cd service && BLUELINK_FAKE=1 python -m bluelink

# Live-reload UI dev server (proxies /ws to the service on :8760):
cd ui && npm run dev

# Tests (framing, core/router, protocol, server):
cd service && .venv\Scripts\activate && pytest -q
```

## Project layout

```
service/            Python companion service (BLE + WebSocket API)
  bluelink/
    constants.py    ★ interop contract (UUIDs, PROTOCOL_VERSION, framing)
    core/           framing, envelopes, router, session state machine
    ble/            interface + bleak (central) + bless (peripheral) + fake
    web/            FastAPI WebSocket server + command dispatch
  spike/            M0 hardware validation scripts
  tests/            pytest suite (runs without hardware via the fake transport)
ui/                 React (JSX) + Vite web UI; builds to ui/dist
```

## Security posture (v1)

No end-to-end encryption and no access control. The BLE characteristic is open
and unencrypted; privacy in v1 comes only from being fully offline. The message
framing reserves room to add encryption and a room code later without a rewrite.
The service binds to `127.0.0.1` only and makes no network connections.
