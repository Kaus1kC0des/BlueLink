"""Property and edge-case tests for the chunking/reassembly layer."""

import os
import random

import pytest

from bluelink.constants import DEFAULT_MTU, MAX_BODY_BYTES
from bluelink.core.framing import (
    FramingError,
    MsgIdCounter,
    Reassembler,
    chunk,
)


def _roundtrip(payload: bytes, mtu: int, source="peer", msg_id=0) -> bytes | None:
    r = Reassembler()
    out = None
    for c in chunk(payload, msg_id, mtu):
        out = r.feed(source, c)
    return out


@pytest.mark.parametrize("mtu", [23, 27, 50, 185, 247, 512])
def test_roundtrip_random_sizes(mtu):
    for _ in range(50):
        size = random.randint(0, MAX_BODY_BYTES)
        payload = os.urandom(size)
        assert _roundtrip(payload, mtu) == payload


def test_empty_payload_roundtrips():
    assert _roundtrip(b"", DEFAULT_MTU) == b""


def test_single_chunk_when_small():
    chunks = chunk(b"hi", msg_id=1, mtu=247)
    assert len(chunks) == 1


def test_many_chunks_when_large():
    payload = os.urandom(4000)
    chunks = chunk(payload, msg_id=1, mtu=DEFAULT_MTU)
    assert len(chunks) > 1
    r = Reassembler()
    out = None
    for c in chunks:
        out = r.feed("peer", c)
    assert out == payload


def test_out_of_order_delivery():
    payload = os.urandom(500)
    chunks = chunk(payload, msg_id=7, mtu=DEFAULT_MTU)
    random.shuffle(chunks)
    r = Reassembler()
    out = None
    for c in chunks:
        out = r.feed("peer", c)
    assert out == payload


def test_duplicate_chunks_ignored():
    payload = os.urandom(300)
    chunks = chunk(payload, msg_id=3, mtu=DEFAULT_MTU)
    r = Reassembler()
    out = None
    for c in chunks + chunks:  # feed everything twice
        maybe = r.feed("peer", c)
        out = maybe or out
    assert out == payload


def test_concurrent_sources_do_not_collide():
    p1 = os.urandom(300)
    p2 = os.urandom(300)
    c1 = chunk(p1, msg_id=0, mtu=DEFAULT_MTU)  # same msg_id...
    c2 = chunk(p2, msg_id=0, mtu=DEFAULT_MTU)  # ...different source
    r = Reassembler()
    out1 = out2 = None
    # interleave
    for a, b in zip(c1, c2):
        out1 = r.feed("A", a) or out1
        out2 = r.feed("B", b) or out2
    assert out1 == p1
    assert out2 == p2


def test_bad_frame_version_rejected():
    payload = chunk(b"x", msg_id=1, mtu=DEFAULT_MTU)[0]
    corrupt = bytes([0xFF]) + payload[1:]
    r = Reassembler()
    with pytest.raises(FramingError):
        r.feed("peer", corrupt)


def test_short_chunk_rejected():
    r = Reassembler()
    with pytest.raises(FramingError):
        r.feed("peer", b"\x01\x00")


def test_mtu_too_small_rejected():
    with pytest.raises(FramingError):
        chunk(b"data", msg_id=1, mtu=9)  # 9 - 3 - 7 = -1


def test_msg_id_counter_wraps():
    c = MsgIdCounter(start=65535)
    assert c.next() == 65535
    assert c.next() == 0
    assert c.next() == 1


def test_drop_source_clears_partial():
    payload = os.urandom(300)
    chunks = chunk(payload, msg_id=1, mtu=DEFAULT_MTU)
    r = Reassembler()
    r.feed("peer", chunks[0])  # partial
    r.drop_source("peer")
    # feeding the rest should not complete (buffer was dropped)
    out = None
    for c in chunks[1:]:
        out = r.feed("peer", c) or out
    assert out is None
