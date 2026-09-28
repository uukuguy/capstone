"""Bounded, closed JSON-lines contract for one application worker session."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any


SCHEMA = "capstone-worker/1.0"
MAX_FRAME_BYTES = 2 * 1024 * 1024 + 65_536
_SESSION_ID = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
_FIELDS = frozenset({"schema", "session_id", "sequence", "kind", "payload"})
_PAYLOAD_FIELDS = {
    "open": frozenset({"application_id", "mode", "case_id", "provider", "model", "run_id"}),
    "turn": frozenset({"instruction"}),
    "close": frozenset(),
    "evidence": frozenset({"ref"}),
    "ready": frozenset({"run_id"}),
    "progress": frozenset({"event", "message", "ordinal", "total", "capability", "run_id"}),
    "answer_committed": frozenset({"ordinal", "turn_id", "answer_output", "answer_summary", "answer_ref", "result_refs", "evidence_refs", "duration_ms"}),
    "completed": frozenset({"run_id", "result", "report_path"}),
    "failed": frozenset({"code"}),
    "evidence_result": frozenset({"ref", "value"}),
    "network_view": frozenset({"ordinal", "view"}),
    "network_view_unavailable": frozenset({"ordinal"}),
    "network_diagram": frozenset({"diagram"}),
    "network_layer": frozenset({"ordinal", "layer"}),
    "network_layer_unavailable": frozenset({"ordinal"}),
    "network_story": frozenset({"story"}),
    "network_story_unavailable": frozenset({"code"}),
}
_REQUIRED_PAYLOAD_FIELDS = {
    "open": frozenset({"application_id", "mode"}),
    "turn": _PAYLOAD_FIELDS["turn"],
    "evidence": _PAYLOAD_FIELDS["evidence"],
    "ready": _PAYLOAD_FIELDS["ready"],
    "progress": frozenset({"event", "message"}),
    # Duration was added after the worker protocol shipped. Keep it optional so
    # older workers and persisted sessions remain readable.
    "answer_committed": frozenset({"ordinal", "turn_id", "answer_output", "answer_ref", "result_refs", "evidence_refs"}),
    "completed": frozenset({"run_id", "result"}),
    "failed": _PAYLOAD_FIELDS["failed"],
    "evidence_result": _PAYLOAD_FIELDS["evidence_result"],
    "network_view": _PAYLOAD_FIELDS["network_view"],
    "network_view_unavailable": _PAYLOAD_FIELDS["network_view_unavailable"],
    "network_diagram": _PAYLOAD_FIELDS["network_diagram"],
    "network_layer": _PAYLOAD_FIELDS["network_layer"],
    "network_layer_unavailable": _PAYLOAD_FIELDS["network_layer_unavailable"],
    "network_story": _PAYLOAD_FIELDS["network_story"],
    "network_story_unavailable": _PAYLOAD_FIELDS["network_story_unavailable"],
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
            or ("answer_summary" in self.payload and not isinstance(self.payload["answer_summary"], str))
            or not isinstance(self.payload["answer_ref"], str)
            or any(not isinstance(self.payload[key], list)
                   or any(not isinstance(ref, str) for ref in self.payload[key])
                   for key in ("result_refs", "evidence_refs"))
        ):
            raise ProtocolError("committed answer payload is invalid")
        if self.kind == "answer_committed" and (
            "duration_ms" in self.payload
            and (type(self.payload["duration_ms"]) is not int or self.payload["duration_ms"] < 0)
        ):
            raise ProtocolError("committed answer duration is invalid")
        if self.kind == "network_view":
            from capstone_agent.network_view import normalize_network_view

            try:
                normalized = normalize_network_view(self.payload["view"])
            except ValueError:
                raise ProtocolError("network view payload is invalid") from None
            if self.payload["ordinal"] != normalized["ordinal"]:
                raise ProtocolError("network view ordinal is invalid")
        if self.kind == "network_view_unavailable" and (
            type(self.payload["ordinal"]) is not int or not 1 <= self.payload["ordinal"] <= 3
        ):
            raise ProtocolError("network view unavailable ordinal is invalid")
        if self.kind == "network_diagram":
            from capstone_agent.network_diagram import normalize_network_diagram

            try:
                normalize_network_diagram(self.payload["diagram"])
            except ValueError:
                raise ProtocolError("network diagram payload is invalid") from None
        if self.kind == "network_layer" and (
            type(self.payload["ordinal"]) is not int
            or not 1 <= self.payload["ordinal"] <= 3
            or not isinstance(self.payload["layer"], dict)
            or set(self.payload["layer"]) != {
                "schema", "ordinal", "diagram_ref", "model_revision",
                "focus_ids", "next_focus_ids", "overlay",
            }
            or self.payload["layer"].get("schema") != "capstone-network-layer/1.0"
            or self.payload["layer"].get("ordinal") != self.payload["ordinal"]
            or not isinstance(self.payload["layer"].get("diagram_ref"), str)
            or not isinstance(self.payload["layer"].get("model_revision"), str)
        ):
            raise ProtocolError("network layer payload is invalid")
        if self.kind == "network_layer_unavailable" and (
            type(self.payload["ordinal"]) is not int or not 1 <= self.payload["ordinal"] <= 3
        ):
            raise ProtocolError("network layer unavailable ordinal is invalid")
        if self.kind == "network_story":
            from capstone_agent.network_story import normalize_network_story

            story = self.payload["story"]
            if not isinstance(story, dict):
                raise ProtocolError("network story payload is invalid")
            refs = {
                ordinal: tuple(
                    step["overlay"]["source_ref"]
                    for step in story.get("steps", [])
                    if isinstance(step, dict) and step.get("ordinal") == ordinal
                    and isinstance(step.get("overlay"), dict)
                    and isinstance(step["overlay"].get("source_ref"), str)
                )
                for ordinal in range(1, 4)
            }
            try:
                normalize_network_story(story, admitted_refs_by_ordinal=refs)
            except ValueError:
                raise ProtocolError("network story payload is invalid") from None
        if self.kind == "network_story_unavailable" and (
            not isinstance(self.payload.get("code"), str) or not self.payload["code"]
        ):
            raise ProtocolError("network story unavailable payload is invalid")
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
