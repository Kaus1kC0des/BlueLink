"""Wire framing: split logical messages into MTU-sized chunks and reassemble.

BLE payloads are tiny (MTU - 3 bytes), so every JSON envelope is chunked.
See LLD.md section 4 for the byte layout and algorithms.

Chunk layout on the Message characteristic:
    byte 0    : frame_version (uint8)
    bytes 1-2 : msg_id  (uint16, big-endian)  -- per-sender rolling id
    bytes 3-4 : seq     (uint16)              -- 0-based chunk index
    bytes 5-6 : count   (uint16)              -- total chunks for this msg_id
    bytes 7.. : payload (raw bytes slice)
"""

from __future__ import annotations

import struct
import time
from dataclasses import dataclass, field

from ..constants import (
    ATT_OVERHEAD,
    CHUNK_HEADER_FMT,
    CHUNK_HEADER_LEN,
    FRAME_VERSION,
    MAX_BODY_BYTES,
    MSG_ID_MODULO,
    REASSEMBLY_TIMEOUT_S,
)


class FramingError(Exception):
    """Raised for malformed chunks that cannot be trusted."""


def _usable_payload(mtu: int) -> int:
    body = mtu - ATT_OVERHEAD - CHUNK_HEADER_LEN
    if body < 1:
        raise FramingError(f"MTU {mtu} too small to carry any payload")
    return body


def chunk(payload: bytes, msg_id: int, mtu: int) -> list[bytes]:
    """Split *payload* into ordered chunks that each fit within *mtu*.

    An empty payload still yields exactly one (header-only) chunk so the
    receiver can reconstruct a zero-length message.
    """
    body = _usable_payload(mtu)
    parts = [payload[i : i + body] for i in range(0, len(payload), body)] or [b""]
    count = len(parts)
    if count >= MSG_ID_MODULO:
        raise FramingError("payload requires too many chunks")
    msg_id &= MSG_ID_MODULO - 1
    return [
        struct.pack(CHUNK_HEADER_FMT, FRAME_VERSION, msg_id, seq, count) + part
        for seq, part in enumerate(parts)
    ]


class MsgIdCounter:
    """Rolling uint16 message-id generator for a sender."""

    def __init__(self, start: int = 0) -> None:
        self._next = start & (MSG_ID_MODULO - 1)

    def next(self) -> int:
        value = self._next
        self._next = (self._next + 1) & (MSG_ID_MODULO - 1)
        return value


@dataclass
class _Partial:
    count: int
    parts: dict[int, bytes] = field(default_factory=dict)
    started: float = 0.0
    total_bytes: int = 0


class Reassembler:
    """Reassembles chunks into complete payloads, keyed by (source, msg_id).

    *now* is injectable so tests need not depend on the wall clock.
    """

    def __init__(self, now=time.monotonic) -> None:
        self._now = now
        self._buffers: dict[tuple[object, int], _Partial] = {}

    def _evict_stale(self) -> None:
        cutoff = self._now() - REASSEMBLY_TIMEOUT_S
        stale = [k for k, p in self._buffers.items() if p.started < cutoff]
        for key in stale:
            del self._buffers[key]

    def feed(self, source: object, data: bytes) -> bytes | None:
        """Feed one received chunk. Returns the full payload once complete.

        *source* identifies the sender (e.g. a connection handle) so concurrent
        senders reusing the same msg_id do not collide.
        """
        if len(data) < CHUNK_HEADER_LEN:
            raise FramingError("chunk shorter than header")
        ver, msg_id, seq, count = struct.unpack(
            CHUNK_HEADER_FMT, data[:CHUNK_HEADER_LEN]
        )
        if ver != FRAME_VERSION:
            raise FramingError(f"unsupported frame version {ver}")
        if count == 0 or seq >= count:
            raise FramingError(f"invalid seq/count {seq}/{count}")

        payload = data[CHUNK_HEADER_LEN:]
        key = (source, msg_id)
        self._evict_stale()

        partial = self._buffers.get(key)
        if partial is None:
            partial = _Partial(count=count, started=self._now())
            self._buffers[key] = partial
        elif partial.count != count:
            # Corrupt/stale reuse of msg_id — restart the buffer.
            partial = _Partial(count=count, started=self._now())
            self._buffers[key] = partial

        if seq not in partial.parts:
            partial.total_bytes += len(payload)
            if partial.total_bytes > MAX_BODY_BYTES + 512:
                del self._buffers[key]
                raise FramingError("reassembled message exceeds size limit")
            partial.parts[seq] = payload

        if len(partial.parts) == partial.count:
            del self._buffers[key]
            return b"".join(partial.parts[i] for i in range(partial.count))
        return None

    def drop_source(self, source: object) -> None:
        """Discard any in-flight buffers for a disconnected source."""
        for key in [k for k in self._buffers if k[0] == source]:
            del self._buffers[key]
