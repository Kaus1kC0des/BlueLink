"""End-to-end core tests using the in-memory fake transport (no BLE hardware)."""

import asyncio

import pytest

from bluelink.ble.fake import FakeHostTransport, FakeMemberTransport, FakeRadio
from bluelink.core.session import Role, SessionManager, State


class Collector:
    """Captures emitted UI events for a session."""

    def __init__(self):
        self.events = []

    def __call__(self, ev):
        self.events.append(ev)

    def of_type(self, t):
        return [e for e in self.events if e["t"] == t]

    def messages(self):
        return self.of_type("message")


def make_session(radio, host_addr="FAKE-HOST", name="anon"):
    emit = Collector()
    sm = SessionManager(
        name=name,
        emit=emit,
        host_factory=lambda: FakeHostTransport(radio, addr=host_addr),
        member_factory=lambda: FakeMemberTransport(radio),
    )
    return sm, emit


async def flush():
    # let ensure_future relay tasks run
    for _ in range(5):
        await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_one_to_one_chat():
    radio = FakeRadio()
    host, h_ev = make_session(radio, name="Priya")
    member, m_ev = make_session(radio, name="Arun")

    await host.host()
    assert host.role == Role.HOST and host.state == State.ADVERTISING

    await member.join("FAKE-HOST")
    await flush()
    assert member.state == State.CONNECTED

    # member sees the host name from the handshake
    status = member.state
    assert status == State.CONNECTED
    assert member._host_host_name == "Priya"

    # member -> host
    await member.send("hello from Arun")
    await flush()
    host_msgs = [m for m in h_ev.messages() if not m["system"]]
    assert any(m["body"] == "hello from Arun" and m["sender"] == "Arun" for m in host_msgs)

    # sender's own UI shows its message as mine=True
    my = [m for m in m_ev.messages() if m["body"] == "hello from Arun"]
    assert my and my[0]["mine"] is True

    # host -> member
    await host.send("hi Arun")
    await flush()
    got = [m for m in m_ev.messages() if m["body"] == "hi Arun" and not m["system"]]
    assert got and got[0]["sender"] == "Priya" and got[0]["mine"] is False


@pytest.mark.asyncio
async def test_group_relay_excludes_origin():
    radio = FakeRadio()
    host, h_ev = make_session(radio, name="Host")
    a, a_ev = make_session(radio, name="Alice")
    b, b_ev = make_session(radio, name="Bob")

    await host.host()
    await a.join("FAKE-HOST")
    await b.join("FAKE-HOST")
    await flush()

    # Alice sends; Bob and Host should receive; Alice should NOT get a relayed copy
    await a.send("group hi")
    await flush()

    # Bob receives the relayed message
    bob_got = [m for m in b_ev.messages() if m["body"] == "group hi" and not m["system"]]
    assert bob_got and bob_got[0]["sender"] == "Alice"

    # Host receives it locally
    host_got = [m for m in h_ev.messages() if m["body"] == "group hi" and not m["system"]]
    assert host_got

    # Alice sees exactly one copy (her own mine=True echo), not a relayed duplicate
    alice_copies = [m for m in a_ev.messages() if m["body"] == "group hi" and not m["system"]]
    assert len(alice_copies) == 1
    assert alice_copies[0]["mine"] is True


@pytest.mark.asyncio
async def test_join_leave_membership_events():
    radio = FakeRadio()
    host, h_ev = make_session(radio, name="Host")
    a, a_ev = make_session(radio, name="Alice")

    await host.host()
    await a.join("FAKE-HOST")
    await flush()

    # host announced Alice joined + broadcast a member_list
    sys_msgs = [m for m in h_ev.messages() if m["system"]]
    assert any("Alice" in m["body"] and "joined" in m["body"] for m in sys_msgs)
    mls = h_ev.of_type("member_list")
    assert mls and "Alice" in mls[-1]["members"] and "Host" in mls[-1]["members"]

    # Alice leaves -> host sees a "left" system message
    await a.leave()
    await flush()
    sys_after = [m for m in h_ev.messages() if m["system"]]
    assert any("left" in m["body"] for m in sys_after)


@pytest.mark.asyncio
async def test_multichunk_message_over_small_mtu():
    # FAKE_MTU=100 -> payload chunk ~90 bytes; a 1KB body spans many chunks
    radio = FakeRadio()
    host, h_ev = make_session(radio, name="Host")
    a, _ = make_session(radio, name="Alice")

    await host.host()
    await a.join("FAKE-HOST")
    await flush()

    big = "x" * 1000
    await a.send(big)
    await flush()

    got = [m for m in h_ev.messages() if m["body"] == big]
    assert got, "large multi-chunk message must reassemble intact"


@pytest.mark.asyncio
async def test_send_without_connection_errors():
    radio = FakeRadio()
    sm, ev = make_session(radio, name="Nobody")
    await sm.send("into the void")
    errs = ev.of_type("error")
    assert errs and errs[0]["code"] == "not_connected"
