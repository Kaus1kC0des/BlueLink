# Product Requirements Document — BlueLink (working title)

**A serverless, off-grid chat app for laptops: React web UI + a local Python service talking Bluetooth Low Energy (BLE), with no pairing required.**

| | |
|---|---|
| **Doc status** | Draft v0.3 |
| **Last updated** | 2026-07-11 |
| **Owner** | kausik.devanathan@qik.company |
| **Target release** | v1.0 (MVP) |

---

## 1. Summary

BlueLink lets two people — or a small group — on laptops exchange text messages directly over **Bluetooth Low Energy (BLE)** with **no internet, no cellular, no Wi-Fi, no server, and no pairing**. It targets situations where conventional infrastructure is unavailable or untrusted: outages, disasters, remote fieldwork, and dead zones.

The app is a **React web UI** running in the browser, backed by a **small Python companion service** on each laptop that owns the Bluetooth radio. The browser and the service talk over `localhost` (loopback) — this is *not* a network connection and needs no LAN. The split exists because browsers can't drive a BLE GATT server; a local service must (see §5).

A defining UX choice: **users never touch Windows Bluetooth settings and never see a pairing dialog.** Peers connect over an **open, unencrypted GATT characteristic**, so connecting is as simple as picking a name from a list.

v1 keeps scope tight: **direct connections only** (no multi-hop mesh), **no end-to-end encryption yet**, and a **basic but functional UI**. The goal of v1 is to prove the end-to-end path — two laptops chatting over BLE with zero infrastructure and zero setup friction.

## 2. Problem & motivation

When the internet goes down, ordinary messaging apps become useless — they all assume a reachable server. People meters apart still can't coordinate digitally. Laptops are good off-grid endpoints: big batteries, real keyboards, storage, and Bluetooth radios that are almost always present. There is no simple app that turns two laptops into a direct Bluetooth chat link with no infrastructure and no setup.

## 3. Goals & non-goals

### Goals (v1)
- Send/receive text messages **directly between two laptops over BLE**, with no network of any kind.
- **No pairing and no OS Bluetooth settings** — peers connect via an open GATT characteristic.
- Support a **small group** in one conversation (target up to **7** peers) via a star topology.
- Run **completely offline** — discovery, connection, and messaging all work with Wi-Fi and Ethernet disabled.
- **React web UI** for the interface; **Python local service** for BLE and browser communication.
- Fast, obvious discovery and connect: "app open" → "chatting" in under 60 seconds.
- Basic in-session message history (durable history is a stretch goal).

### Non-goals (v1)
- ❌ **End-to-end encryption** — explicitly deferred (see §8). Not in v1.
- ❌ **Pairing / bonding** — intentionally avoided; connections are open/unencrypted at the BLE layer.
- ❌ Multi-hop / relay mesh networking.
- ❌ Bluetooth Classic (RFCOMM/SPP) — v1 uses BLE only.
- ❌ Mobile clients (iOS/Android). Laptops only.
- ❌ Internet fallback, bridging, or cloud sync.
- ❌ Voice, video, or file transfer.
- ❌ Accounts, phone numbers, or centralized identity.
- ❌ Polished/production UI — a basic working UI is acceptable for v1.

## 4. Target users & scenarios

**Primary persona — "Prepared Priya":** keeps an off-grid comms plan; wants a tool that works when the grid doesn't, with essentially no setup.

**Scenarios:**
1. **Outage/disaster.** Internet and cell are down; two neighbors on laptops message to coordinate.
2. **Field team, no coverage.** A few laptops in a shelter/vehicle share status updates.
3. **Deliberately un-networked.** A user wants a physically-scoped channel that touches no network at all.

## 5. Architecture & technical reality (read this first)

### 5.1 Why web UI + local service, and why BLE
- **Browsers can't be a BLE peripheral.** The Web Bluetooth API is BLE-*central* only and cannot host a GATT server, so two browsers can never talk directly. A native process must own the radio → our **Python companion service**.
- **BLE, not Classic, because of the no-pairing requirement.** On Windows, Bluetooth Classic (RFCOMM) effectively requires bonding/pairing. BLE lets peers connect to an **unencrypted GATT characteristic with no pairing at all** — the exact "just connect" UX we want.
- **`localhost` is loopback, not LAN.** No Wi-Fi/Ethernet/router involved, so the off-grid requirement holds.

### 5.2 Roles
- The laptop that **hosts** a conversation runs a **BLE GATT server (peripheral role)** and advertises a fixed BlueLink service UUID.
- Laptops that **join** run as **BLE central (client role)**, scan for that UUID, connect, and write/subscribe to the message characteristic.
- For a 1:1 chat, one side hosts and one side joins. For a group, the host is the star hub and **relays** messages between members at the application layer.

### 5.3 Component overview
```
┌─────────────────────┐        localhost         ┌───────────────────────────┐
│  React Web UI        │  WebSocket (ws://127...)  │  Python companion service  │
│  (browser)           │◄────────────────────────►│  - FastAPI + WebSocket     │
│  - chat window       │                           │  - bless  (GATT server)    │
│  - peer list         │                           │  - bleak  (GATT client)    │
│  - host / join / status│                         │  - chunking + msg routing  │
└─────────────────────┘                           └────────────┬──────────────┘
                                                                │ BLE (GATT)
                                                                │ open characteristic,
                                                                │ NO pairing
                                                   ┌────────────▼──────────────┐
                                                   │  Peer laptop (same stack)  │
                                                   └────────────────────────────┘
```

### 5.4 BLE characteristics we rely on
- **No pairing:** the message characteristic requires no encryption/authentication, so connecting triggers no OS pairing prompt.
- **Write + Notify:** clients **write** outgoing messages to the characteristic; the server pushes incoming messages via **notifications** so delivery is real-time.
- **Small MTU:** BLE payloads are small (~20 bytes default, up to ~185–512 after MTU negotiation). Messages **must be chunked and reassembled** — a modest, well-understood layer.
- **Low throughput** (~1–20 KB/s practical) is fine for text and is a reason media/files are non-goals.
- **Star topology:** one peripheral, multiple centrals — this is how the group host works.

### 5.5 Python BLE feasibility on Windows
- **`bleak`** — mature cross-platform BLE **central/client** (Windows via WinRT).
- **`bless`** — BLE **peripheral/GATT-server** (Windows via WinRT), built on bleak's backends.
- Both are pure-Python and use the Windows WinRT Bluetooth stack — no native helper or build toolchain required (a clear win over the earlier PyBluez/Classic plan).
- **Risk to validate in M0:** `bless` peripheral-role reliability and advertising on the specific Windows adapters we target; MTU negotiation behavior.

## 6. Platform scope

| OS | v1 target | Notes |
|---|---|---|
| Windows 10/11 | ✅ Primary | Dev environment; bleak + bless both support WinRT. |
| macOS | 🟡 Later | bleak + bless support it; not a v1 target. |
| Linux | 🟡 Later | bleak + bless via BlueZ/DBus; not a v1 target. |

## 7. Functional requirements

### 7.1 Setup & identity
- **FR-1** On first launch the user enters a **display name**, stored locally. No account, email, or network call.
- **FR-2** A peer is identified in the UI by display name (advertised by the host) plus its BLE address for disambiguation.

### 7.2 Discovery & connection (no pairing)
- **FR-3** A user can **start hosting** — the service runs the GATT server and advertises the BlueLink service UUID with the display name.
- **FR-4** A user can **scan** for nearby BlueLink hosts; discovered hosts appear in the React UI as a list with display name and signal strength (RSSI).
- **FR-5** The user joins a host with one action. **No pairing dialog and no Windows settings** are involved — the connection uses the open characteristic.
- **FR-6** The UI clearly shows state: **advertising / scanning → connecting → connected → disconnected**.

### 7.3 Messaging (1:1)
- **FR-7** Send/receive UTF-8 text messages. Outgoing messages are chunked to fit the negotiated MTU and reassembled on the other side; each logical message is length-framed.
- **FR-8** Messages appear in the chat window in order, with timestamps and sender label.
- **FR-9** Basic delivery feedback: **sent** once written/acknowledged at the BLE layer, **failed** if the link is down.
- **FR-10** When a peer disconnects, the UI reflects it; the user can rejoin/resume when back in range.

### 7.4 Small group chat
- **FR-11** A host accepts up to **7** connected centrals (subject to the adapter's real limit, validated in M3).
- **FR-12** The host **relays** each incoming message to all other connected members via notifications (application-layer fan-out). Messages are plaintext in v1 (no E2E — see §8).
- **FR-13** All members see the current member list; joins and leaves appear as system messages.

### 7.5 Resilience & offline
- **FR-14** All features function with Wi-Fi and Ethernet **disabled**. The only socket to the browser is `localhost` loopback; the app makes **zero non-loopback network connections**.
- **FR-15** Graceful handling of the Bluetooth adapter being off/unavailable: clear UI error and recovery when it returns.

### 7.6 History (basic)
- **FR-16** Messages for the current session are visible in the chat window. Durable, cross-restart history is a **stretch goal** (simple local file/SQLite if time permits).

## 8. Security & privacy — v1 stance

> **v1 has NO end-to-end encryption AND NO pairing.** Both are deliberate, documented scoping decisions to reach a working, frictionless prototype.

- **SEC-1 (v1)** The BLE characteristic is **open and unencrypted**. Anyone in radio range with a BLE sniffer could read traffic, and any BLE client could connect. Treat v1 as **not confidential and not access-controlled**.
- **SEC-2 (v1)** No telemetry, analytics, or network calls — privacy comes from being fully offline, not from crypto.
- **SEC-3 (v1)** The `localhost` service must **bind to `127.0.0.1` only** (never `0.0.0.0`) so it is never reachable from any network.
- **SEC-4 (future)** Application-layer encryption (e.g. a Noise-protocol handshake over the characteristic, or libsodium key exchange) and a simple access model (e.g. a shared room code) are planned for a later version. Design the message framing so this can layer on **without a rewrite**.

## 9. Non-functional requirements

- **NFR-1 Performance:** Message round-trip within BLE range < 2 s under normal conditions.
- **NFR-2 Discovery latency:** A nearby host appears in the scan list within ~5–10 s (BLE scanning is fast).
- **NFR-3 Reliability:** The service handles disconnects and MTU/chunking edge cases without crashing; UI reflects state truthfully.
- **NFR-4 Startup:** Service + UI reach a usable state within a few seconds of launch.
- **NFR-5 Verifiable offline:** Document/demonstrate that the app opens no non-loopback sockets.
- **NFR-6 Simplicity:** A basic, clean UI is sufficient; no design-system investment required for v1.

## 10. UX principles

- **Zero setup.** No pairing, no Windows settings — pick a name, connect, chat.
- **Honest status.** Connection and delivery state are always visible and truthful — never show "sent" when the link is closed.
- **Basic but clear.** Function over polish for v1; the interface just needs to be legible and usable.

## 11. Technical approach (recommended)

- **Frontend:** **React** (Vite), minimal styling. Talks to the service via a **WebSocket** on `ws://127.0.0.1:<port>`.
- **Local service:** **Python** with **FastAPI** (WebSocket + static assets), **`bless`** for the GATT server (host role) and **`bleak`** for the GATT client (join role).
- **BLE design:** one fixed **service UUID**; a **message characteristic** (write + notify) that is unencrypted (no pairing); display name carried in the advertisement or an info characteristic.
- **Wire protocol (BLE):** length-prefixed frames carrying compact JSON `{type, sender, ts, body}`, split into MTU-sized chunks with a small chunk header (message id, index, count) for reassembly.
- **Browser↔service protocol:** small JSON message set over WebSocket — e.g. `host`, `scan`, `peers`, `join`, `send`, `message`, `status`.
- **Packaging (later):** bundle the Python service (PyInstaller) + built React assets into a one-click launcher; out of scope for the first prototype, which can run from a dev command.

## 12. Open questions

1. **`bless` reliability on target Windows adapters** — does the GATT server advertise and accept connections reliably? Top spike (M0).
2. **MTU negotiation** — what MTU do target adapters settle on, and does it hold across the connection? Drives chunk size.
3. **Concurrent centrals on one peripheral** — can a single Windows adapter hold up to 7 BLE connections? Validate the real ceiling in M3.
4. **Advertisement payload limits** — does the display name fit in the advertisement, or do we need an info characteristic clients read after connecting?
5. **No access control in v1** — is "anyone in range can join" acceptable for the prototype, or do we want a lightweight room code sooner rather than later?
6. **Port/asset serving** — load the UI from a bundled static server on `localhost`; confirm it stays fully offline.

## 13. Milestones

| Phase | Scope | Exit criteria |
|---|---|---|
| **M0 — BLE spike (P0)** | Prove bless + bleak on Windows: one laptop advertises a GATT server, another connects (no pairing) and exchanges a string via write + notify | Two Windows laptops exchange a plaintext string over an open BLE characteristic, with no pairing prompt |
| **M1 — 1:1 chat, end to end** | React UI ↔ WebSocket ↔ Python ↔ BLE; host/scan/join, chunked send/receive, status | Two laptops hold a real-time 1:1 text chat through the full stack, fully offline, no pairing |
| **M2 — Robustness** | Reconnect handling, adapter-off handling, chunk/reassembly hardening, loopback-only binding | Chat survives disconnect/reconnect and message sizes above one MTU; passes an offline-network check |
| **M3 — Small group** | Host accepts multiple centrals, application-layer relay, member list | 3+ laptops chat in one group via a host relay |
| **M4 — Basic polish + packaging** | Session history stretch goal, simple packaging/launcher, docs | A non-developer can launch and use it on Windows |

## 14. Success metrics

Gathered from hands-on testing (no telemetry):
- Two Windows laptops reach a working 1:1 chat, unassisted, within ~60 s, **with no pairing or settings steps**.
- ≥ 95% message delivery success within BLE range during test sessions, including multi-chunk messages.
- Zero non-loopback network connections observed in an audit.
- A 3-person group chat runs through a host relay in a test session.

## 15. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| **`bless` GATT-server unreliable on some Windows adapters** | High — blocks hosting | M0 spike first; test on target hardware; fallback to a native WinRT helper if needed |
| Small MTU / chunking bugs corrupt or drop messages | Medium | Robust framing + reassembly with ids and length checks; test messages spanning many chunks |
| Single adapter can't hold 7 BLE connections | Medium | Validate real ceiling in M3; cap group size to what works |
| Open characteristic → no privacy/access control | Medium | Clearly label v1 as not confidential; design framing so encryption + room code layer on later |
| BLE discovery misses a host intermittently | Low | Continuous scanning, manual rescan, show RSSI |
| Sleep/lid-close drops connections | Low | Scope v1 to foreground, lid-open use |
