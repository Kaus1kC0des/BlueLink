"""Message envelopes carried inside reassembled chunks.

The envelope is the logical application message (JSON). `type` distinguishes
chat from control messages. See LLD.md section 6.

The schema intentionally leaves room for future `enc` (encryption metadata)
and `room` (access code) fields without changing the framing layer.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from ..constants import MAX_BODY_BYTES

# Envelope types
T_HELLO = "hello"  # member -> host: announce self on connect
T_MSG = "msg"  # any: chat message
T_MEMBER_LIST = "member_list"  # host -> members: current membership
T_SYSTEM = "system"  # host -> members: e.g. "Arun joined"


class EnvelopeError(Exception):
    """Raised when an envelope is malformed or oversized."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def new_id() -> str:
    return uuid.uuid4().hex


@dataclass
class Envelope:
    type: str
    data: dict

    def to_bytes(self) -> bytes:
        raw = json.dumps({"type": self.type, **self.data}, separators=(",", ":"))
        return raw.encode("utf-8")

    @staticmethod
    def from_bytes(raw: bytes) -> "Envelope":
        try:
            obj = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise EnvelopeError(f"invalid envelope JSON: {exc}") from exc
        if not isinstance(obj, dict) or "type" not in obj:
            raise EnvelopeError("envelope missing 'type'")
        etype = obj.pop("type")
        return Envelope(type=etype, data=obj)


# --- constructors -----------------------------------------------------------

def make_msg(sender: str, body: str, msg_id: str | None = None, ts: str | None = None) -> Envelope:
    if len(body.encode("utf-8")) > MAX_BODY_BYTES:
        raise EnvelopeError("message body exceeds MAX_BODY_BYTES")
    return Envelope(
        T_MSG,
        {"id": msg_id or new_id(), "sender": sender, "ts": ts or _now_iso(), "body": body},
    )


def make_hello(name: str, proto: int) -> Envelope:
    return Envelope(T_HELLO, {"name": name, "proto": proto})


def make_member_list(members: list[str]) -> Envelope:
    return Envelope(T_MEMBER_LIST, {"members": members})


def make_system(text: str) -> Envelope:
    return Envelope(T_SYSTEM, {"text": text, "ts": _now_iso()})
