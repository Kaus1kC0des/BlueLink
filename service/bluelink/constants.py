"""Interop contract for BlueLink.

★ THIS FILE IS THE COMPATIBILITY CONTRACT ★

Two machines interoperate if and only if they agree on every value here.
NEVER read these from config, environment, or the network. Changing any BLE
identifier or the framing layout is a breaking change and MUST bump
PROTOCOL_VERSION.

See TECHNICAL_PRD.md section 4 and LLD.md section 2.
"""

import struct

# --- Protocol version -------------------------------------------------------
# Checked during the join handshake (member reads the host Info characteristic).
# A mismatch fails closed with error code `incompatible_protocol`.
PROTOCOL_VERSION = 1

# --- Fixed BLE identifiers (128-bit UUIDs), frozen for PROTOCOL_VERSION 1 ----
SERVICE_UUID = "6b1d0000-8f3a-4b2c-9c4e-1a2b3c4d5e6f"
CHAR_MESSAGE_UUID = "6b1d0001-8f3a-4b2c-9c4e-1a2b3c4d5e6f"  # write (uplink) + notify (downlink)
CHAR_INFO_UUID = "6b1d0002-8f3a-4b2c-9c4e-1a2b3c4d5e6f"  # read (host metadata)

# --- Advertising ------------------------------------------------------------
ADV_NAME_PREFIX = "BLK1-"  # advertised local name = prefix + short display name
ADV_NAME_MAX = 20  # keep prefix+name within the ~26-byte adv name budget

# --- Limits -----------------------------------------------------------------
MAX_MEMBERS = 7  # BLE piconet-ish ceiling; real limit validated in M3
MAX_BODY_BYTES = 4096  # per logical chat message body

# --- Wire framing (chunking) ------------------------------------------------
# Chunk header: ver(1) msg_id(2) seq(2) count(2) => 7 bytes, big-endian.
FRAME_VERSION = 1  # framing format version (independent of PROTOCOL_VERSION)
CHUNK_HEADER_FMT = ">BHHH"
CHUNK_HEADER_LEN = struct.calcsize(CHUNK_HEADER_FMT)  # == 7
assert CHUNK_HEADER_LEN == 7, "chunk header must be exactly 7 bytes"

DEFAULT_MTU = 23  # ATT default; the real value comes from MTU negotiation
ATT_OVERHEAD = 3  # ATT opcode + handle bytes deducted from MTU for payload

# msg_id wraps in this range (uint16). Reassembly timeout keeps collisions safe.
MSG_ID_MODULO = 1 << 16
REASSEMBLY_TIMEOUT_S = 10.0
