"""Tests for the WebSocket command dispatch layer."""

import pytest

from bluelink.ble.fake import FakeHostTransport, FakeMemberTransport, FakeRadio
from bluelink.constants import MAX_BODY_BYTES
from bluelink.core.session import Role, SessionManager
from bluelink.web.protocol import ProtocolError, dispatch


def make_sm():
    radio = FakeRadio()
    events = []
    saved = {}

    def save_name(n):
        saved["name"] = n
        return n

    sm = SessionManager(
        name="anon",
        emit=events.append,
        host_factory=lambda: FakeHostTransport(radio),
        member_factory=lambda: FakeMemberTransport(radio),
    )
    return sm, events, save_name, saved


@pytest.mark.asyncio
async def test_set_name_persists_and_updates():
    sm, events, save_name, saved = make_sm()
    await dispatch(sm, {"t": "set_name", "name": "Priya"}, save_name)
    assert saved["name"] == "Priya"
    assert sm.name() == "Priya"


@pytest.mark.asyncio
async def test_host_command_enters_host_role():
    sm, events, save_name, _ = make_sm()
    await dispatch(sm, {"t": "host"}, save_name)
    assert sm.role == Role.HOST
    assert any(e["t"] == "status" and e["role"] == "host" for e in events)


@pytest.mark.asyncio
async def test_unknown_command_raises():
    sm, _, save_name, _ = make_sm()
    with pytest.raises(ProtocolError):
        await dispatch(sm, {"t": "frobnicate"}, save_name)


@pytest.mark.asyncio
async def test_join_requires_addr():
    sm, _, save_name, _ = make_sm()
    with pytest.raises(ProtocolError):
        await dispatch(sm, {"t": "join"}, save_name)


@pytest.mark.asyncio
async def test_oversize_message_rejected():
    sm, _, save_name, _ = make_sm()
    big = "x" * (MAX_BODY_BYTES + 1)
    with pytest.raises(ProtocolError):
        await dispatch(sm, {"t": "send", "body": big}, save_name)


@pytest.mark.asyncio
async def test_send_without_connection_emits_error():
    sm, events, save_name, _ = make_sm()
    await dispatch(sm, {"t": "send", "body": "hi"}, save_name)
    assert any(e["t"] == "error" and e["code"] == "not_connected" for e in events)
