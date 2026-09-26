"""Bounded, closed JSON-lines contract for one application worker session."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any


SCHEMA = "capstone-worker/1.0"
MAX_FRAME_BYTES = 1_000_000
_SESSION_ID = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
_FIELDS = frozenset({"schema", "session_id", "sequence", "kind", "payload"})
_PAYLOAD_FIELDS = {
    "open": frozenset({"application_id", "mode", "case_id", "provider", "model", "run_id"}),
    "turn": frozenset({"instruction"}),
    "close": frozenset(),
    "evidence": frozenset({"ref"}),
    "ready": frozenset({"run_id"}),
    "progress": frozenset({"event", "message", "ordinal", "total", "capability", "run_id"}),
    "answer_committed": frozenset({"ordinal", "turn_id", "answer_output", "answer_ref", "result_refs", "evidence_refs"}),
    "completed": frozenset({"run_id", "result"}),
    "failed": frozenset({"code"}),
    "evidence_result": frozenset({"ref", "value"}),
}
_REQUIRED_PAYLOAD_FIELDS = {
    "open": frozenset({"application_id", "mode"}),
    "turn": _PAYLOAD_FIELDS["turn"],
    "evidence": _PAYLOAD_FIELDS["evidence"],
    "ready": _PAYLOAD_FIELDS["ready"],
    "progress": frozenset({"event", "message"}),
    "answer_committed": _PAYLOAD_FIELDS["answer_committed"],
    "completed": _PAYLOAD_FIELDS["completed"],
    "failed": _PAYLOAD_FIELDS["failed"],
    "evidence_result": _PAYLOAD_FIELDS["evidence_result"],
}


class ProtocolError(ValueError):
    """A worker frame violates the fixed local process contract."""


@dataclass(frozen=True, slots=True)
class Frame:
    session_id: str
    sequence: int
    kind: str
    payload: dict[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.session_id, str) or not _SESSION_ID.fullmatch(self.session_id):
            raise ProtocolError("session ID is invalid")
        if type(self.sequence) is not int or self.sequence < 1:
            raise ProtocolError("frame sequence is invalid")
        fields = _PAYLOAD_FIELDS.get(self.kind) if isinstance(self.kind, str) else None
        if fields is None or not isinstance(self.payload, dict) or set(self.payload) - fields:
            raise ProtocolError("frame kind or payload is invalid")
        if _REQUIRED_PAYLOAD_FIELDS.get(self.kind, frozenset()) - self.payload.keys():
            raise ProtocolError("frame payload is incomplete")
        if self.kind == "answer_committed" and (
            type(self.payload["ordinal"]) is not int or self.payload["ordinal"] < 1
            or not isinstance(self.payload["turn_id"], str)
            or not isinstance(self.payload["answer_output"], str)
            or not isinstance(self.payload["answer_ref"], str)
            or any(not isinstance(self.payload[key], list)
                   or any(not isinstance(ref, str) for ref in self.payload[key])
                   for key in ("result_refs", "evidence_refs"))
        ):
            raise ProtocolError("committed answer payload is invalid")
        try:
            json.dumps(self.payload, ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError):
            raise ProtocolError("frame payload is not JSON") from None

    def to_line(self) -> bytes:
        document = {
            "schema": SCHEMA, "session_id": self.session_id,
            "sequence": self.sequence, "kind": self.kind, "payload": self.payload,
        }
        encoded = (json.dumps(document, ensure_ascii=False, allow_nan=False,
                              separators=(",", ":")) + "\n").encode("utf-8")
        if len(encoded) > MAX_FRAME_BYTES:
            raise ProtocolError("frame exceeds size limit")
        return encoded

    @classmethod
    def from_line(cls, raw: bytes, *, expected_sequence: int | None = None) -> Frame:
        if len(raw) > MAX_FRAME_BYTES:
            raise ProtocolError("frame exceeds size limit")
        if not raw.endswith(b"\n"):
            raise ProtocolError("frame must end with newline")
        try:
            document = json.loads(raw)
        except (UnicodeDecodeError, ValueError):
            raise ProtocolError("frame is not JSON") from None
        if not isinstance(document, dict) or set(document) != _FIELDS or document["schema"] != SCHEMA:
            raise ProtocolError("frame schema is invalid")
        frame = cls(
            session_id=document["session_id"], sequence=document["sequence"],
            kind=document["kind"], payload=document["payload"],
        )
        if expected_sequence is not None and frame.sequence != expected_sequence:
            raise ProtocolError("frame sequence is out of order")
        return frame
