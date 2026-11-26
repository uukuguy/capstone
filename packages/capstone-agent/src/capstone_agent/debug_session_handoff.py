"""Bounded projections for a session handoff."""

import hashlib
import json
import re
import sqlite3
from collections.abc import Callable, Iterable, Iterator, Mapping
from contextlib import closing
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, BinaryIO
from zipfile import ZIP_DEFLATED, ZipFile

from .thread_service import ThreadService

_USER_COMMANDS = {"send_auto", "send_ordinary", "send_professional", "send_message"}
_ASSISTANT_STATES = {
    "attempt_completed": "completed",
    "attempt_delivery_recovered": "completed",
    "attempt_failed": "failed",
    "attempt_cancelled": "cancelled",
    "attempt_interrupted": "interrupted",
}


@dataclass(frozen=True)
class HandoffMember:
    path: str
    chunks: Iterable[bytes]


def json_lines(rows: Iterable[Mapping[str, Any]]) -> Iterator[bytes]:
    for row in rows:
        yield (json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n").encode()


def write_handoff(
    destination: BinaryIO,
    *,
    thread_id: str,
    start_seq: int,
    through_seq: int,
    members: Iterable[HandoffMember],
    gaps: Iterable[Mapping[str, Any]],
    revisions: Mapping[str, Any],
) -> dict[str, Any]:
    """Write authorized members and hash the bytes actually delivered."""
    manifest: dict[str, Any] = {
        "schema": "capstone-debug-session-handoff/1",
        "thread_id": thread_id,
        "start_event_seq": start_seq,
        "through_event_seq": through_seq,
        "revisions": dict(revisions),
        "members": [],
    }
    seen = {"manifest.json"}
    with ZipFile(destination, "w", compression=ZIP_DEFLATED) as archive:
        for member in members:
            path = PurePosixPath(member.path)
            if (
                path.is_absolute()
                or ".." in path.parts
                or path.as_posix() != member.path
                or member.path == "."
                or any(character in member.path for character in ("\\", ":", "\x00"))
                or member.path in seen
            ):
                raise ValueError("invalid or duplicate handoff member path")
            seen.add(member.path)
            size = 0
            digest = hashlib.sha256()
            with archive.open(member.path, "w", force_zip64=True) as target:
                for chunk in member.chunks:
                    target.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
            manifest["members"].append({"path": member.path, "size": size, "sha256": digest.hexdigest()})
        manifest["gaps"] = list(gaps)
        identity = json.dumps(manifest, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()
        manifest["package_id"] = hashlib.sha256(identity).hexdigest()
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, allow_nan=False))
    return manifest


def _conversation_entry(
    event: dict[str, Any], may_export_text: Callable[[dict[str, Any]], bool]
) -> dict[str, Any] | None:
    payload = event["payload"]
    kind = event["event_type"]
    refs = None
    if kind == "command_accepted" and payload.get("kind") in _USER_COMMANDS:
        role = "user"
        status = "accepted"
        command = payload.get("payload")
        text = command.get("text") if isinstance(command, dict) else None
        if not isinstance(text, str):
            text = payload.get("text")
        refs = payload.get("attachment_refs")
    elif kind in _ASSISTANT_STATES:
        role = "assistant"
        status = _ASSISTANT_STATES[kind]
        text = payload.get("answer")
    else:
        return None

    entry = {key: event.get(key) for key in ("event_seq", "event_id", "attempt_id", "occurred_at")}
    entry.update(role=role, status=status)
    if not may_export_text(event):
        entry["text_status"] = "withheld"
        return entry
    entry["text_status"] = "included" if isinstance(text, str) else "unavailable"
    if isinstance(text, str):
        entry["text"] = text
    if isinstance(refs, list):
        entry["attachment_refs"] = [ref for ref in refs if isinstance(ref, str)]
        versions = payload.get("attachment_versions")
        if isinstance(versions, dict):
            entry["attachment_versions"] = {
                ref: versions[ref] for ref in entry["attachment_refs"]
                if type(versions.get(ref)) is int and versions[ref] > 0
            }
    return entry


def read_conversation(
    service: ThreadService,
    thread_id: str,
    start_seq: int,
    through_seq: int,
    *,
    may_export_text: Callable[[dict[str, Any]], bool],
) -> Iterator[dict[str, Any]]:
    """Project public history within an already authorized, frozen session range."""
    return _read_public_history(
        service, thread_id, start_seq, through_seq,
        lambda event: _conversation_entry(event, may_export_text),
    )


def read_session_observations(service, thread_id, through, *, before=None):
    """Read one bounded page across all attempts in the frozen session."""
    cursor = through + 1 if before is None else before
    if type(cursor) is not int or not 1 <= cursor <= through + 1:
        raise ValueError("invalid session observation cursor")
    page = service.read_history(thread_id, before=cursor, limit=12)
    if page["thread_id"] != thread_id:
        raise ValueError("history page belongs to a different session")
    observations = []
    for event in page["events"]:
        if (event.get("thread_id") != thread_id or event.get("visibility") != "public"
                or not 1 <= event["event_seq"] < cursor):
            continue
        summary = {key: event.get(key) for key in ("event_seq", "event_type", "attempt_id", "occurred_at")}
        payload = event["payload"]
        for field in ("native_type", "tool_name", "is_error", "ok"):
            value = payload.get(field)
            if isinstance(value, (str, bool)):
                summary[field] = value[:120] if isinstance(value, str) else value
        entry = _conversation_entry(event, lambda _: True)
        if entry is not None and "text" in entry:
            summary.update(role=entry["role"], text=entry["text"][:600], text_truncated=len(entry["text"]) > 600)
        observations.append(summary)
    next_before = page["next_before_event_seq"] if page["has_more"] else None
    if next_before is not None and not 1 <= next_before < cursor:
        raise ValueError("session observation cursor failed to advance")
    return {"events": observations, "through": through, "next_before": next_before}


def _read_public_history(service, thread_id, start_seq, through_seq, project):
    if start_seq < 1 or through_seq < start_seq - 1:
        raise ValueError("invalid session handoff range")
    before = through_seq + 1
    if before == start_seq:
        return

    # History pages run backwards. A private temporary database keeps memory
    # bounded and lets the caller stream the projected entries in order.
    with closing(sqlite3.connect("")) as spool:
        spool.execute("CREATE TABLE conversation (seq INTEGER PRIMARY KEY, entry TEXT NOT NULL)")
        while before > start_seq:
            page = service.read_history(thread_id, before=before)
            if page["thread_id"] != thread_id:
                raise ValueError("history page belongs to a different session")
            for event in page["events"]:
                seq = event["event_seq"]
                if (
                    event.get("thread_id") != thread_id
                    or event.get("visibility") != "public"
                    or not start_seq <= seq < before
                ):
                    continue
                entry = project(event)
                if entry is not None:
                    spool.execute(
                        "INSERT INTO conversation VALUES (?, ?)",
                        (seq, json.dumps(entry, ensure_ascii=False)),
                    )
            if not page["has_more"]:
                break
            cursor = page["next_before_event_seq"]
            if not 1 <= cursor < before:
                raise ValueError("session history cursor failed to advance")
            before = cursor

        for (entry_json,) in spool.execute("SELECT entry FROM conversation ORDER BY seq"):
            yield json.loads(entry_json)


def write_session_handoff(destination, service, thread_id, through_seq, *, uploads, capstone_revision,
                          objects=None, native_executor=None, supplements=None):
    """Build the local session package after the application grants export."""
    gaps = [
        {"kind": "data_gateway_original_calls", "status": "not_collected"},
    ]
    if supplements is None:
        gaps.append({"kind": "supplementary_evidence", "status": "export_unavailable"})
    attachments: dict[tuple[str, int], None] = {}
    outputs = {}

    def conversation():
        for entry in read_conversation(service, thread_id, 1, through_seq, may_export_text=lambda _: True):
            versions = entry.get("attachment_versions", {})
            for ref in entry.get("attachment_refs", ()):
                attachments[(ref, versions.get(ref, 1))] = None
            yield entry

    def execution_entry(event):
        kind = event["event_type"]
        if kind in {"native_artifact_published", "delivery_published"}:
            field = "artifact" if kind == "native_artifact_published" else "delivery"
            descriptor = event["payload"].get(field)
            if isinstance(descriptor, dict):
                output = (kind, event.get("attempt_id"), descriptor.get("artifact_id"), descriptor.get("revision"))
                outputs.setdefault(output, descriptor)
        if event.get("attempt_id") or kind == "delivery_published":
            return {key: event[key] for key in (
                "event_seq", "event_id", "event_type", "occurred_at", "attempt_id", "turn_id",
            ) if key in event}
        return None

    def members():
        yield HandoffMember("conversation.jsonl", json_lines(conversation()))
        events = _read_public_history(service, thread_id, 1, through_seq, execution_entry)
        yield HandoffMember("execution/capstone/events.jsonl", json_lines(events))
        for ref, version in attachments:
            if not isinstance(ref, str) or not re.fullmatch(r"resource_[a-f0-9]{32}", ref):
                gaps.append({"kind": "input_file", "status": "unsupported_reference"})
                continue
            try:
                if uploads is None:
                    raise ValueError("resource storage unavailable")
                uploads.published(thread_id, ref, version=version)
            except ValueError:
                gaps.append({"kind": "input_file", "status": "unavailable", "resource_id": ref, "version": version})
                continue
            yield HandoffMember(f"files/inputs/{ref}/v{version}", uploads.read(thread_id, ref, version=version))
        from .native_artifact_projection import read_native_artifact
        from .thread_deliveries import read_delivery_content

        for (kind, attempt_id, ref, version), descriptor in sorted(outputs.items(), key=lambda item: str(item[0])):
            try:
                if not isinstance(ref, str) or not re.fullmatch(r"[a-zA-Z0-9_-]+", ref):
                    raise ValueError("invalid artifact identity")
                if kind == "delivery_published":
                    if objects is None or type(version) is not int or version < 1:
                        raise ValueError("delivery storage or revision unavailable")
                    data = read_delivery_content(service, objects, thread_id, ref, version)
                    path = f"files/deliveries/{ref}/r{version}"
                else:
                    if not isinstance(attempt_id, str) or not re.fullmatch(r"[a-zA-Z0-9_-]+", attempt_id):
                        raise ValueError("invalid attempt identity")
                    _, data = read_native_artifact(service, native_executor, thread_id, attempt_id, ref,
                                                   objects=objects, expected_descriptor=descriptor)
                    path = f"files/outputs/{attempt_id}/{ref}"
            except (KeyError, ValueError, OSError):
                gaps.append({"kind": "produced_file", "status": "unavailable", "artifact_id": ref,
                             "attempt_id": attempt_id, "revision": version})
                continue
            yield HandoffMember(path, [data])
        if supplements is not None:
            yield HandoffMember("execution/supplementary-evidence.jsonl", json_lines(supplements))
        yield HandoffMember("repro.md", [
            "# 会话复验\n\n打开 conversation.jsonl 定位指令。按事件编号查阅执行记录。"
            "核对 manifest.json 的版本、文件校验和与缺口。\n".encode()
        ])

    return write_handoff(
        destination, thread_id=thread_id, start_seq=1, through_seq=through_seq,
        members=members(), gaps=gaps, revisions={"capstone": capstone_revision},
    )
