"""Bounded projections for a session handoff."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections.abc import Callable, Iterable, Iterator, Mapping
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory, TemporaryFile, mkdtemp
from typing import TYPE_CHECKING, Any, BinaryIO
from zipfile import ZIP_DEFLATED, ZipFile

if TYPE_CHECKING:
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


def _safe_path(name: str) -> bool:
    path = PurePosixPath(name)
    return (
        not path.is_absolute() and ".." not in path.parts and path.as_posix() == name
        and name != "." and not any(character in name for character in ("\\", ":", "\x00"))
    )


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
            if not _safe_path(member.path) or member.path in seen:
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


def import_handoff(source: Path, parent: Path, *, max_uncompressed_bytes: int) -> Path:
    """Verify all contents before publishing them in a new private directory."""
    with ZipFile(source) as archive:
        entries = archive.infolist()
        names = {entry.filename for entry in entries}
        if (len(names) != len(entries) or "manifest.json" not in names
                or any(not _safe_path(entry.filename) or entry.is_dir() for entry in entries)):
            raise ValueError("invalid package member paths")
        if sum(entry.file_size for entry in entries) > max_uncompressed_bytes:
            raise ValueError("package exceeds import size limit")
        if archive.getinfo("manifest.json").file_size > 16 * 1024 * 1024:
            raise ValueError("package manifest exceeds size limit")
        manifest_bytes = archive.read("manifest.json")
        manifest = json.loads(manifest_bytes)
        if not isinstance(manifest, dict) or manifest.get("schema") != "capstone-debug-session-handoff/1":
            raise ValueError("unsupported session handoff format")
        identity = manifest.pop("package_id", None)
        encoded = json.dumps(manifest, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()
        if hashlib.sha256(encoded).hexdigest() != identity:
            raise ValueError("package identity mismatch")
        members = manifest.get("members")
        if not isinstance(members, list) or any(
            not isinstance(row, dict) or set(row) != {"path", "size", "sha256"}
            or not isinstance(row["path"], str) or type(row["size"]) is not int
            or not isinstance(row["sha256"], str)
            for row in members
        ):
            raise ValueError("invalid package manifest members")
        paths = {row["path"] for row in members}
        if len(paths) != len(members) or paths != names - {"manifest.json"}:
            raise ValueError("package member list mismatch")

        with TemporaryDirectory(prefix=".capstone-import-", dir=parent) as staging:
            root = Path(staging) / "contents"
            root.mkdir(mode=0o700)
            for row in members:
                name = row["path"]
                if archive.getinfo(name).file_size != row["size"]:
                    raise ValueError("package member size mismatch")
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                digest = hashlib.sha256()
                with archive.open(name) as original, target.open("xb") as output:
                    while chunk := original.read(1024 * 1024):
                        digest.update(chunk)
                        output.write(chunk)
                if digest.hexdigest() != row["sha256"]:
                    raise ValueError("package member digest mismatch")
            (root / "manifest.json").write_bytes(manifest_bytes)
            destination = Path(mkdtemp(prefix="capstone-debug-", dir=parent))
            try:
                root.rename(destination / "contents")
            except OSError:
                destination.rmdir()
                raise
            return destination / "contents"


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


def latest_instruction_attempt(service, thread_id, through):
    """Select an initial lead from persisted session history."""
    before = through + 1
    while before > 1:
        page = service.read_history(thread_id, before=before)
        for event in reversed(page["events"]):
            payload = event["payload"]
            if (event.get("thread_id") == thread_id and event.get("visibility") == "public"
                    and 1 <= event["event_seq"] < before and event["event_type"] == "command_accepted"
                    and payload.get("kind") in _USER_COMMANDS and event.get("attempt_id")):
                return event["attempt_id"]
        if not page["has_more"]:
            return None
        cursor = page["next_before_event_seq"]
        if not 1 <= cursor < before:
            raise ValueError("session history cursor failed to advance")
        before = cursor
    return None


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


def _model_request_metadata(payload):
    usage = payload.get("model_context_usage")
    if not isinstance(usage, dict):
        return {}
    request_id = usage.get("request_id")
    if (not isinstance(request_id, str) or not re.fullmatch(r"ctx-[1-9][0-9]{0,8}", request_id)
            or usage.get("kind") not in ("main", "summary", "analysis")
            or usage.get("state") not in ("started", "completed", "failed")):
        return {}
    result = {key: usage[key] for key in ("request_id", "kind", "state")}
    for key, pattern in (("dispatch_id", r"request-[1-9][0-9]{0,8}"), ("prefix_fingerprint", r"[a-f0-9]{64}")):
        value = usage.get(key)
        if isinstance(value, str) and re.fullmatch(pattern, value):
            result[key] = value
    for key in ("window_tokens", "output_allowance_tokens", "encoding_allowance_tokens", "input_ceiling_tokens"):
        value = usage.get(key)
        if type(value) is int and 0 < value <= 100_000_000:
            result[key] = value
    groups = ("system", "tools", "messages", "tool_results")
    for key, fields in (("estimated_input", groups), ("estimated_input_before_projection", groups),
                        ("usage", ("input", "output", "cacheRead", "cacheWrite"))):
        values = usage.get(key)
        if isinstance(values, dict):
            result[key] = {field: values[field] for field in fields
                           if type(values.get(field)) is int and 0 <= values[field] <= 100_000_000}
    return result


def _model_request_timing(payload):
    event = payload.get("model_request_pool")
    if not isinstance(event, dict):
        return {}
    request_id, status = event.get("request_id"), event.get("status")
    if (not isinstance(request_id, str) or not re.fullmatch(r"request-[1-9][0-9]{0,8}", request_id)
            or status not in ("queued", "waiting_dependencies", "running", "cancelling",
                              "completed", "failed", "cancelled", "blocked")):
        return {}
    timing = ("queued_at_ms", "started_at_ms", "first_content_at_ms", "finished_at_ms")
    return {"request_id": request_id, "status": status, **{
        key: event[key] for key in timing if type(event.get(key)) is int and 0 <= event[key] <= 9007199254740991
    }}


def write_session_handoff(destination, service, thread_id, through_seq, *, uploads, capstone_revision,
                          objects=None, native_executor=None, supplements=None, read_gateway_calls=None):
    """Build the local session package after the application grants export."""
    gaps = []
    if supplements is None:
        gaps.append({"kind": "supplementary_evidence", "status": "export_unavailable"})
    attachments: dict[tuple[str, int], list[int]] = {}
    outputs = {}
    file_index = []
    settled_attempts = {}
    observed_attempts = set()
    operation_events = {}

    def conversation():
        for entry in read_conversation(service, thread_id, 1, through_seq, may_export_text=lambda _: True):
            versions = entry.get("attachment_versions", {})
            for ref in entry.get("attachment_refs", ()):
                attachments.setdefault((ref, versions.get(ref, 1)), []).append(entry["event_seq"])
            yield entry

    def execution_entry(event):
        kind = event["event_type"]
        attempt_id = event.get("attempt_id")
        payload = event["payload"]
        native_stage = payload.get("native_type")
        if attempt_id:
            observed_attempts.add(attempt_id)
            if kind in _ASSISTANT_STATES:
                settled_attempts[attempt_id] = None
            task, call = payload.get("task_id"), payload.get("tool_call_id")
            if (kind == "runtime_event" and native_stage in ("tool_execution_start", "tool_execution_end")
                    and isinstance(task, str) and isinstance(call, str)):
                key = (attempt_id, f"{task}:{call}")
                operation_events.setdefault(key, []).append(event["event_seq"])
        if kind in {"native_artifact_published", "delivery_published"}:
            field = "artifact" if kind == "native_artifact_published" else "delivery"
            descriptor = event["payload"].get(field)
            if isinstance(descriptor, dict):
                output = (kind, event.get("attempt_id"), descriptor.get("artifact_id"), descriptor.get("revision"))
                saved = outputs.get(output)
                if saved is None or event["event_seq"] > saved[0]:
                    outputs[output] = (event["event_seq"], descriptor)
        if event.get("attempt_id") or kind == "delivery_published":
            summary = {key: event[key] for key in (
                "event_seq", "event_id", "event_type", "occurred_at", "attempt_id", "turn_id",
            ) if key in event}
            if kind == "runtime_event" and native_stage in ("tool_execution_start", "tool_execution_end"):
                summary["native_stage"] = native_stage
                if type(payload.get("is_error")) is bool:
                    summary["is_error"] = payload["is_error"]
            if kind == "tool_completed" and type(payload.get("ok")) is bool:
                summary["ok"] = payload["ok"]
            if kind == "runtime_event" and native_stage == "model_context_usage":
                metadata = _model_request_metadata(payload)
                if metadata:
                    summary["model_context_usage"] = metadata
            if kind == "runtime_event" and native_stage == "model_request_pool":
                timing = _model_request_timing(payload)
                if timing:
                    summary["model_request_pool"] = timing
            if kind == "runtime_event" and native_stage == "model_context_snapshot":
                from .model_context_diagnostics import checked_history_selection
                snapshot = payload.get("model_context_snapshot_ref")
                if isinstance(snapshot, dict):
                    selection = checked_history_selection(snapshot.get("history_selection"))
                    request_id = snapshot.get("request_id")
                    if selection is not None and isinstance(request_id, str) and re.fullmatch(r"ctx-[1-9][0-9]{0,8}", request_id):
                        summary["history_selection"] = {"request_id": request_id, **selection}
            return summary
        return None

    def members():
        yield HandoffMember("conversation.jsonl", json_lines(conversation()))
        events = _read_public_history(service, thread_id, 1, through_seq, execution_entry)
        yield HandoffMember("execution/capstone/events.jsonl", json_lines(events))
        for (ref, version), event_seqs in attachments.items():
            if not isinstance(ref, str) or not re.fullmatch(r"resource_[a-f0-9]{32}", ref):
                gaps.append({"kind": "input_file", "status": "unsupported_reference"})
                continue
            with TemporaryFile(mode="w+b") as staged:
                try:
                    if uploads is None:
                        raise ValueError("resource storage unavailable")
                    resource = uploads.published(thread_id, ref, version=version)
                    digest = hashlib.sha256()
                    for chunk in uploads.read(thread_id, ref, version=version):
                        digest.update(chunk)
                        staged.write(chunk)
                    if staged.tell() != resource["size_bytes"] or digest.hexdigest() != resource["sha256"]:
                        raise ValueError("published resource bytes failed verification")
                except (KeyError, ValueError, OSError):
                    gaps.append({"kind": "input_file", "status": "unavailable", "resource_id": ref, "version": version})
                    continue
                staged.seek(0)
                path = f"files/inputs/{ref}/v{version}"
                file_index.append({"path": path, "file_name": resource.get("file_name"), "version": version,
                                   "resource_id": ref, "capstone_event_seqs": event_seqs})
                yield HandoffMember(path, iter(lambda: staged.read(1024 * 1024), b""))
        from .native_artifact_projection import read_native_artifact
        from .thread_deliveries import read_delivery_content

        for (kind, attempt_id, ref, version), (event_seq, descriptor) in sorted(
                outputs.items(), key=lambda item: str(item[0])):
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
            file_index.append({"path": path, "file_name": descriptor.get("file_name"), "revision": version,
                               "artifact_id": ref, "attempt_id": attempt_id, "capstone_event_seqs": [event_seq]})
            yield HandoffMember(path, [data])
        if file_index:
            yield HandoffMember("files/index.jsonl", json_lines(file_index))
        if supplements is not None:
            yield HandoffMember("execution/supplementary-evidence.jsonl", json_lines(supplements))
        if read_gateway_calls is None:
            gaps.append({"kind": "data_gateway_original_calls", "status": "capability_unavailable"})
        elif settled_attempts:
            try:
                selected = list(settled_attempts)[-32:]
                gateway = read_gateway_calls(selected)
                if len(settled_attempts) > len(selected):
                    gateway = {**gateway, "truncated": True}
                for row in gateway["events"]:
                    operation = row.pop("_operation", None)
                    refs = operation_events.get((row["attempt_id"], operation), ())
                    row["capstone_event_seqs"] = sorted(refs)
                    row["correlation_status"] = "linked" if refs else "unavailable"
                yield HandoffMember("execution/data-gateway/original-calls.json", [
                    json.dumps(gateway, ensure_ascii=False, allow_nan=False).encode(),
                ])
                if gateway["status"] != "available" or gateway["truncated"]:
                    gaps.append({"kind": "data_gateway_original_calls", "status": gateway["status"],
                                 "truncated": gateway["truncated"]})
                for row in gateway["events"]:
                    if row["status"] != "available":
                        gaps.append({"kind": "data_gateway_original_call", "status": row["status"], "entry": row["entry"]})
            except (KeyError, ValueError, RuntimeError, OSError):
                gaps.append({"kind": "data_gateway_original_calls", "status": "read_unavailable"})
        pending = len(observed_attempts.difference(settled_attempts))
        if pending:
            gaps.append({"kind": "data_gateway_original_calls", "status": "attempts_not_settled", "attempt_count": pending})
        yield HandoffMember("repro.md", [
            "# 会话复验\n\n打开 conversation.jsonl 定位指令。按事件编号查阅执行记录。"
            "如有附件或产出，打开 files/index.jsonl 查找原文件名和版本。"
            "核对 manifest.json 的版本、文件校验和与缺口。\n".encode()
        ])

    return write_handoff(
        destination, thread_id=thread_id, start_seq=1, through_seq=through_seq,
        members=members(), gaps=gaps, revisions={"capstone": capstone_revision},
    )
