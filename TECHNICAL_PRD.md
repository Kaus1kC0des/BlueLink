# Technical PRD — BlueLink

**Engineering requirements, contracts, and acceptance criteria for the BLE off-grid chat app.**

| | |
|---|---|
| **Doc status** | Draft v0.1 |
| **Last updated** | 2026-07-11 |
| **Companion docs** | [PRD.md](PRD.md) (product), [HLD.md](HLD.md) (architecture), [LLD.md](LLD.md) (detailed design) |
| **Scope** | v1.0 MVP — Windows, BLE, no pairing, no E2E |

---

## 1. Purpose

This document translates the product PRD into concrete engineering requirements: the system boundaries, the technology stack, the **interoperability contract** that lets two independently set-up machines talk, the external/internal interfaces, and testable acceptance criteria. It is the source of truth for *what must be true* of the implementation; the HLD/LLD describe *how*.

## 2. System overview

BlueLink is a two-process desktop application, replicated identically on every participating laptop:

1. **Companion service** (Python) — owns the BLE radio (GATT server + client), owns session/message state, and exposes a local WebSocket API.
2. **Web UI** (React) — runs in the user's browser, connects to the service over `localhost`, and renders the chat.

Two laptops communicate **laptop-A-service ⇄ BLE ⇄ laptop-B-service**. Neither browser is ever on the air; browsers only ever talk to their own local service over loopback.

## 3. Technology stack (normative)

| Layer | Choice | Version floor | Notes |
|---|---|---|---|
| BLE client (central) | `bleak` | ≥ 0.21 | Windows WinRT backend |
| BLE server (peripheral) | `bless` | ≥ 0.2 | Windows WinRT backend |
| Service runtime | Python | ≥ 3.10 | async (`asyncio`) |
| Web server / WS | `FastAPI` + `uvicorn` | current | serves WS + static UI assets |
| UI framework | React (JSX, **no TypeScript**) | 18 | plain JavaScript `.jsx`/`.js`, built with Vite |
| UI ↔ service transport | WebSocket | — | `ws://127.0.0.1:<port>` |
| Packaging (later) | PyInstaller + static bundle | — | out of scope for M0–M3 |

No component may introduce a dependency that requires internet access at runtime.

## 4. Interoperability contract (CRITICAL)

> The following constants and formats are the **compatibility contract**. Two machines interoperate **if and only if** they agree on every item in this section. All values are compiled into the code as shared constants — never read from user config, environment, or a network source.

### 4.1 Protocol version
- `PROTOCOL_VERSION` is an integer, currently **`1`**.
- Exposed by the host via the Info characteristic (§6.2) and checked by the client on connect.
- **Mismatch behavior:** if `client.PROTOCOL_VERSION != host.PROTOCOL_VERSION`, the client MUST refuse to join and surface `error: incompatible_protocol` to the UI. No partial/best-effort messaging across versions.

### 4.2 Fixed BLE identifiers (128-bit UUIDs)
| Constant | UUID | Role |
|---|---|---|
| `SERVICE_UUID` | `6b1d0000-8f3a-4b2c-9c4e-1a2b3c4d5e6f` | Advertised by host; scan filter on client |
| `CHAR_MESSAGE_UUID` | `6b1d0001-8f3a-4b2c-9c4e-1a2b3c4d5e6f` | Client **writes** uplink; host **notifies** downlink |
| `CHAR_INFO_UUID` | `6b1d0002-8f3a-4b2c-9c4e-1a2b3c4d5e6f` | Client **reads** host name, proto version, member count |

These UUIDs are frozen for `PROTOCOL_VERSION = 1`. Changing any of them is a breaking change and MUST bump `PROTOCOL_VERSION`.

### 4.3 Wire framing (BLE payloads)
- Application messages are UTF-8 JSON objects (§7).
- Each JSON message is split into **chunks** with the binary chunk header defined in the LLD (`msg_id`, `seq`, `count`), sized to the negotiated MTU.
- The chunk header layout and reassembly rules are part of this contract; see [LLD §4](LLD.md).

### 4.4 What is explicitly NOT part of setup
To guarantee "replicate and it just works," none of the following may affect interoperability:
- ❌ No pre-shared keys, certificates, or accounts.
- ❌ No pairing/bonding at the OS level.
- ❌ No hardcoded peer addresses — peers are discovered by `SERVICE_UUID` at runtime.
- ❌ No machine-specific config file required for compatibility (display name and WS port are local-only and do not affect the wire).

### 4.5 Acceptance test for interop
Given two Windows laptops, each with a **fresh clone of the same commit** set up per the README, with **no shared configuration**: the machines MUST be able to discover, connect (no pairing), and exchange messages. This is the primary go/no-go for every release.

## 5. Functional requirements (engineering view)

Traceability: each maps to the product FR in [PRD.md §7](PRD.md).

| ID | Requirement | Source |
|---|---|---|
| T-1 | Service generates/loads a local profile (display name) from a local file; no network. | FR-1/2 |
| T-2 | Host mode: start GATT server, register service + characteristics, begin advertising `SERVICE_UUID` with the local name. | FR-3 |
| T-3 | Scan mode: BLE scan filtered by `SERVICE_UUID`; emit a de-duplicated peer list with name + RSSI to the UI. | FR-4 |
| T-4 | Join: connect as central with **no pairing**, negotiate MTU, read Info characteristic, verify `PROTOCOL_VERSION`, subscribe to notifications. | FR-5, §4.1 |
| T-5 | Send: chunk + write a message to `CHAR_MESSAGE_UUID`; report sent/failed to UI. | FR-7/9 |
| T-6 | Receive: reassemble chunks from notifications (client) or writes (host); deliver whole messages to UI. | FR-7/8 |
| T-7 | Group relay: host fans out each received message to all other connected centrals via notify. | FR-11/12 |
| T-8 | Membership: track connected centrals; emit join/leave events. | FR-13 |
| T-9 | Resilience: detect adapter off / disconnect; recover and reflect state truthfully. | FR-14/15 |
| T-10 | Offline guarantee: bind WS to `127.0.0.1` only; open no non-loopback sockets. | FR-14, SEC-3 |
| T-11 | Session history in memory, surfaced to UI; durable store is a stretch goal. | FR-16 |

## 6. External interfaces

### 6.1 UI ↔ service — WebSocket API
- Endpoint: `ws://127.0.0.1:<port>/ws` (default port in LLD; local-only, may be reconfigured without affecting interop).
- Full command/event schema in [LLD §5](LLD.md).

### 6.2 BLE GATT profile
- One primary service (`SERVICE_UUID`) with two characteristics (`CHAR_MESSAGE_UUID`, `CHAR_INFO_UUID`).
- Properties, permissions (no encryption required), and payload formats in [LLD §3](LLD.md).

## 7. Message model (logical)

A logical chat message, before chunking:
```json
{
  "type": "msg",
  "id": "<uuid4 string, generated by sender service>",
  "sender": "<display name>",
  "ts": "<ISO-8601 UTC, set by sender service>",
  "body": "<UTF-8 text, <= 4096 bytes>"
}
```
Control messages (`type` ∈ `hello`, `member_list`, `system`) share the envelope; see [LLD §6](LLD.md).

> Note: `ts` and `id` are generated by the sending **service**, not the UI, and not by any function unavailable in this environment — they are real runtime values on the machine that originates the message.

## 8. Non-functional / acceptance criteria

| ID | Criterion | Measurement |
|---|---|---|
| A-1 | 1:1 message round-trip < 2 s in range | Manual timing over 20 messages |
| A-2 | Host appears in scan list ≤ 10 s | Manual, both apps open |
| A-3 | Multi-chunk message (> 1 MTU, e.g. 2–4 KB) delivered intact | Automated checksum test |
| A-4 | No non-loopback sockets opened | `netstat`/Wireshark audit with Wi-Fi off |
| A-5 | Fresh-clone interop (see §4.5) | Two-laptop dry run each release |
| A-6 | Survives disconnect → reconnect without service restart | Manual: walk out of range and back |
| A-7 | Group of 3 relays correctly | Manual: 3 laptops, verify all see all |

## 9. Constraints & assumptions

- **Windows 10/11 only** for v1; foreground, lid-open use.
- Requires a working BLE adapter that supports the **peripheral role** (validated in M0).
- **No confidentiality and no access control** in v1 (open characteristic) — documented risk, not a defect.
- Single BLE adapter per machine; a machine is either hosting **or** joining at a time in v1 (simultaneous dual-role is out of scope).

## 10. Out of scope (v1)

E2E encryption, room codes/access control, Bluetooth Classic, mobile, mesh/relay-beyond-host, file/voice/video, cloud sync, cross-restart durable history (stretch), auto-update.

## 11. Open technical questions

Tracked in [PRD.md §12](PRD.md); the M0 spike must close #1 (`bless` reliability), #2 (MTU), and #4 (advertisement name limits) before M1 begins.
