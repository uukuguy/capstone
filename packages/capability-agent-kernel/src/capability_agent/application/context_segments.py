"""Strict, immutable context-segment records and read-only chain replay.

This module intentionally owns only segmented-v1 encoding and integrity checks.
The public context store supplies reduction and writer dispatch in a later slice.
"""

from __future__ import annotations

import json
import math
import os
import stat
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from capability_agent._safe_files import open_bound_parent
from capability_agent.application.context_models import ContextEvent, PORTABLE_ID_PATTERN
from capability_agent.trajectory.canonical import canonical_json_bytes


MARKER_SCHEMA = "application-context-storage/1.0"
MARKER_MODE = "segmented-transactions/1.0"
MANIFEST_SCHEMA = "application-context-segment-manifest/1.0"
SEGMENT_SCHEMA = "application-context-segment/1.0"
MARKER_MAX_BYTES = 16 * 1024
MANIFEST_MAX_BYTES = 16 * 1024
SEGMENT_MAX_BYTES = 64 * 1024 * 1024
_HEX64 = frozenset("0123456789abcdef")
_READ_FLAGS = (
    os.O_RDONLY
    | getattr(os, "O_CLOEXEC", 0)
    | getattr(os, "O_NOFOLLOW", 0)
    | getattr(os, "O_NONBLOCK", 0)
)


class SegmentStorageError(RuntimeError):
    """Raised without filesystem details when segmented storage is invalid."""


@dataclass(frozen=True, slots=True)
class StorageMarker:
    run_id: str

    def __post_init__(self) -> None:
        _portable_id(self.run_id)

    def document(self) -> dict[str, object]:
        return {"schema": MARKER_SCHEMA, "mode": MARKER_MODE, "run_id": self.run_id}

    @classmethod
    def from_document(cls, document: dict[str, object]) -> "StorageMarker":
        _require_exact_keys(document, {"schema", "mode", "run_id"})
        run_id = _portable_id(document.get("run_id"))
        if document.get("schema") != MARKER_SCHEMA or document.get("mode") != MARKER_MODE:
            raise SegmentStorageError("segmented storage marker is invalid")
        return cls(run_id)


@dataclass(frozen=True, slots=True)
class SegmentManifest:
    run_id: str
    segment_count: int
    committed_revision: int
    committed_state_hash: str
    head_segment_sha256: str

    def __post_init__(self) -> None:
        _portable_id(self.run_id)
        _positive_int(self.segment_count)
        _positive_int(self.committed_revision)
        _hex64(self.committed_state_hash)
        _hex64(self.head_segment_sha256)

    def document(self) -> dict[str, object]:
        return {
            "schema": MANIFEST_SCHEMA,
            "run_id": self.run_id,
            "segment_count": self.segment_count,
            "committed_revision": self.committed_revision,
            "committed_state_hash": self.committed_state_hash,
            "head_segment_sha256": self.head_segment_sha256,
        }

    @classmethod
    def from_document(cls, document: dict[str, object]) -> "SegmentManifest":
        _require_exact_keys(document, {"schema", "run_id", "segment_count", "committed_revision", "committed_state_hash", "head_segment_sha256"})
        if document.get("schema") != MANIFEST_SCHEMA:
            raise SegmentStorageError("segmented manifest is invalid")
        count = _positive_int(document.get("segment_count"))
        revision = _positive_int(document.get("committed_revision"))
        return cls(
            run_id=_portable_id(document.get("run_id")),
            segment_count=count,
            committed_revision=revision,
            committed_state_hash=_hex64(document.get("committed_state_hash")),
            head_segment_sha256=_hex64(document.get("head_segment_sha256")),
        )


@dataclass(frozen=True, slots=True)
class ContextSegment:
    run_id: str
    start_revision: int
    end_revision: int
    previous_segment_sha256: str | None
    previous_state_hash: str
    next_state_hash: str
    payload_sha256: str
    events: tuple[ContextEvent, ...]

    def __post_init__(self) -> None:
        _portable_id(self.run_id)
        _positive_int(self.start_revision)
        _positive_int(self.end_revision)
        if self.previous_segment_sha256 is not None:
            _hex64(self.previous_segment_sha256)
        _hex64(self.previous_state_hash)
        _hex64(self.next_state_hash)
        _hex64(self.payload_sha256)
        if not isinstance(self.events, tuple) or not self.events or not all(
            isinstance(event, ContextEvent) for event in self.events
        ):
            raise SegmentStorageError("context segment is invalid")

    def document(self) -> dict[str, object]:
        return {
            "schema": SEGMENT_SCHEMA,
            "run_id": self.run_id,
            "start_revision": self.start_revision,
            "end_revision": self.end_revision,
            "previous_segment_sha256": self.previous_segment_sha256,
            "previous_state_hash": self.previous_state_hash,
            "next_state_hash": self.next_state_hash,
            "payload_sha256": self.payload_sha256,
            "events": [event.model_dump(mode="json") for event in self.events],
        }

    @classmethod
    def from_document(cls, document: dict[str, object]) -> "ContextSegment":
        _require_exact_keys(document, {"schema", "run_id", "start_revision", "end_revision", "previous_segment_sha256", "previous_state_hash", "next_state_hash", "payload_sha256", "events"})
        if document.get("schema") != SEGMENT_SCHEMA:
            raise SegmentStorageError("context segment is invalid")
        events_raw = document.get("events")
        if not isinstance(events_raw, list) or not events_raw:
            raise SegmentStorageError("context segment is invalid")
        try:
            events = tuple(ContextEvent.model_validate(value) for value in events_raw)
        except (TypeError, ValueError, ValidationError):
            raise SegmentStorageError("context segment is invalid") from None
        previous = document.get("previous_segment_sha256")
        if previous is not None:
            previous = _hex64(previous)
        segment = cls(
            run_id=_portable_id(document.get("run_id")),
            start_revision=_positive_int(document.get("start_revision")),
            end_revision=_positive_int(document.get("end_revision")),
            previous_segment_sha256=previous,
            previous_state_hash=_hex64(document.get("previous_state_hash")),
            next_state_hash=_hex64(document.get("next_state_hash")),
            payload_sha256=_hex64(document.get("payload_sha256")),
            events=events,
        )
        _validate_segment(segment)
        return segment


def decode_document(raw: bytes, *, max_bytes: int) -> dict[str, object]:
    """Strictly decode one canonical, bounded JSON object."""

    if not isinstance(max_bytes, int) or isinstance(max_bytes, bool) or max_bytes < 1:
        raise SegmentStorageError("segmented document limit is invalid")
    if not isinstance(raw, bytes) or len(raw) > max_bytes:
        raise SegmentStorageError("segmented document is invalid")
    try:
        text = raw.decode("utf-8", errors="strict")
        value = json.loads(text, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
        _reject_nonfinite(value)
        if not isinstance(value, dict) or any(type(key) is not str for key in value):
            raise ValueError("document must be an object")
        canonical = canonical_json_bytes(value)
    except SegmentStorageError:
        raise
    except (
        UnicodeDecodeError,
        UnicodeEncodeError,
        json.JSONDecodeError,
        TypeError,
        ValueError,
        OverflowError,
        RecursionError,
    ):
        raise SegmentStorageError("segmented document is invalid") from None
    if raw != canonical:
        raise SegmentStorageError("segmented document is invalid")
    return value


def encode_segment(
    events: tuple[ContextEvent, ...], previous: SegmentManifest | None,
) -> tuple[ContextSegment, bytes, str]:
    """Encode one immutable canonical segment from already validated events."""

    if not isinstance(events, tuple) or not events:
        raise SegmentStorageError("context segment is invalid")
    first = events[0]
    if not all(isinstance(event, ContextEvent) for event in events):
        raise SegmentStorageError("context segment is invalid")
    previous_digest: str | None = None
    if previous is not None:
        if not isinstance(previous, SegmentManifest):
            raise SegmentStorageError("segmented manifest is invalid")
        previous_digest = previous.head_segment_sha256
        if first.run_id != previous.run_id or first.previous_revision != previous.committed_revision or first.previous_state_hash != previous.committed_state_hash:
            raise SegmentStorageError("context segment is invalid")
    segment = ContextSegment(
        run_id=first.run_id,
        start_revision=first.sequence,
        end_revision=events[-1].sequence,
        previous_segment_sha256=previous_digest,
        previous_state_hash=first.previous_state_hash,
        next_state_hash=events[-1].next_state_hash,
        payload_sha256=sha256(canonical_json_bytes([event.model_dump(mode="json") for event in events])).hexdigest(),
        events=events,
    )
    _validate_segment(segment)
    if previous is None and (segment.start_revision != 1 or segment.previous_segment_sha256 is not None):
        raise SegmentStorageError("context segment is invalid")
    raw = canonical_json_bytes(segment.document())
    if len(raw) > SEGMENT_MAX_BYTES:
        raise SegmentStorageError("context segment is invalid")
    return segment, raw, sha256(raw).hexdigest()


def decode_segment(raw: bytes, *, expected_sha256: str) -> ContextSegment:
    """Decode a canonical segment whose bytes match its content-address name."""

    expected = _hex64(expected_sha256)
    document = decode_document(raw, max_bytes=SEGMENT_MAX_BYTES)
    if sha256(raw).hexdigest() != expected:
        raise SegmentStorageError("context segment is invalid")
    return ContextSegment.from_document(document)


def read_chain(entry_path: Path) -> tuple[SegmentManifest, tuple[ContextEvent, ...]]:
    """Read one fail-closed segmented layout from its logical replay entry."""

    entry = Path(entry_path)
    if entry.name != "context-events.jsonl":
        raise SegmentStorageError("segmented storage entry is invalid")
    core = entry.parent
    marker_path = core / "context-storage.json"
    manifest_path = core / "context-manifest.json"
    segments_path = core / "context-segments"
    marker_exists = _exists(marker_path)
    manifest_exists = _exists(manifest_path)
    segments_exists = _exists(segments_path)
    if not marker_exists and not manifest_exists and not segments_exists:
        raise SegmentStorageError("segmented storage is absent")
    if not (marker_exists and manifest_exists and segments_exists):
        raise SegmentStorageError("segmented storage is inconsistent")
    _require_directory(segments_path)
    if _read_path(entry, max_bytes=MARKER_MAX_BYTES, mutable=False) != b"":
        raise SegmentStorageError("segmented storage is inconsistent")
    marker = StorageMarker.from_document(_read_document(marker_path, MARKER_MAX_BYTES, mutable=False))
    manifest = SegmentManifest.from_document(_read_document(manifest_path, MANIFEST_MAX_BYTES, mutable=True))
    if marker.run_id != manifest.run_id:
        raise SegmentStorageError("segmented storage is inconsistent")
    current = manifest.head_segment_sha256
    records: list[tuple[str, ContextSegment]] = []
    seen: set[str] = set()
    for _ in range(manifest.segment_count):
        if current in seen:
            raise SegmentStorageError("context segment chain is invalid")
        seen.add(current)
        raw = _read_path(segments_path / f"{current}.json", max_bytes=SEGMENT_MAX_BYTES, mutable=False)
        segment = decode_segment(raw, expected_sha256=current)
        records.append((current, segment))
        if segment.run_id != manifest.run_id:
            raise SegmentStorageError("context segment chain is invalid")
        if segment.previous_segment_sha256 is None:
            break
        current = segment.previous_segment_sha256
    if len(records) != manifest.segment_count or records[-1][1].previous_segment_sha256 is not None:
        raise SegmentStorageError("context segment chain is invalid")
    records.reverse()
    first = records[0][1]
    if first.start_revision != 1:
        raise SegmentStorageError("context segment chain is invalid")
    for (left_digest, left), (right_digest, right) in zip(records, records[1:]):
        if right.previous_segment_sha256 != left_digest or right.start_revision != left.end_revision + 1 or right.previous_state_hash != left.next_state_hash:
            raise SegmentStorageError("context segment chain is invalid")
    head = records[-1][1]
    if head.end_revision != manifest.committed_revision or head.next_state_hash != manifest.committed_state_hash:
        raise SegmentStorageError("context segment chain is invalid")
    return manifest, tuple(event for _digest, segment in records for event in segment.events)


def _validate_segment(segment: ContextSegment) -> None:
    if segment.end_revision < segment.start_revision or len(segment.events) != segment.end_revision - segment.start_revision + 1:
        raise SegmentStorageError("context segment is invalid")
    if sha256(canonical_json_bytes([event.model_dump(mode="json") for event in segment.events])).hexdigest() != segment.payload_sha256:
        raise SegmentStorageError("context segment is invalid")
    previous_revision = segment.start_revision - 1
    previous_hash = segment.previous_state_hash
    for event in segment.events:
        if event.run_id != segment.run_id or event.sequence != previous_revision + 1 or event.previous_revision != previous_revision or event.previous_state_hash != previous_hash:
            raise SegmentStorageError("context segment is invalid")
        previous_revision = event.next_revision
        previous_hash = event.next_state_hash
    if previous_revision != segment.end_revision or previous_hash != segment.next_state_hash:
        raise SegmentStorageError("context segment is invalid")


def _read_document(path: Path, max_bytes: int, *, mutable: bool) -> dict[str, object]:
    return decode_document(_read_path(path, max_bytes=max_bytes, mutable=mutable), max_bytes=max_bytes)


def _read_path(path: Path, *, max_bytes: int, mutable: bool) -> bytes:
    try:
        with open_bound_parent(path) as (parent, name):
            descriptor = os.open(name, _READ_FLAGS, dir_fd=parent)
            try:
                before = os.fstat(descriptor)
                if not stat.S_ISREG(before.st_mode):
                    raise OSError("not regular")
                chunks: list[bytes] = []
                remaining = max_bytes + 1
                while remaining:
                    chunk = os.read(descriptor, min(64 * 1024, remaining))
                    if not chunk:
                        break
                    chunks.append(chunk)
                    remaining -= len(chunk)
                raw = b"".join(chunks)
                after = os.fstat(descriptor)
                if len(raw) > max_bytes:
                    raise OSError("changed")
                named = os.stat(name, dir_fd=parent, follow_symlinks=False)
                if mutable:
                    if _same_inode(named, after):
                        if _identity(before) != _identity(after) or _identity(named) != _identity(after):
                            raise OSError("changed")
                    elif not stat.S_ISREG(named.st_mode):
                        raise OSError("changed")
                    elif _identity(before) == _identity(after):
                        # The atomic replacement occurred after the final
                        # descriptor sample. The descriptor is still the full
                        # old snapshot and the current leaf is a new regular
                        # manifest inode.
                        pass
                    elif (
                        _mutable_identity(before) != _mutable_identity(after)
                        or after.st_nlink >= before.st_nlink
                    ):
                        raise OSError("changed")
                else:
                    if _identity(before) != _identity(after):
                        raise OSError("changed")
                    if _identity(named) != _identity(after):
                        raise OSError("replaced")
                return raw
            finally:
                os.close(descriptor)
    except (OSError, ValueError, TypeError):
        raise SegmentStorageError("segmented storage cannot be read") from None


def _exists(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    except OSError:
        raise SegmentStorageError("segmented storage cannot be inspected") from None
    return True


def _require_directory(path: Path) -> None:
    try:
        metadata = path.lstat()
    except OSError:
        raise SegmentStorageError("segmented storage cannot be inspected") from None
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise SegmentStorageError("segmented storage is inconsistent")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value: str) -> object:
    raise ValueError(f"non-finite JSON value: {value}")


def _reject_nonfinite(value: object) -> None:
    pending = [value]
    while pending:
        current = pending.pop()
        if type(current) is float and not math.isfinite(current):
            raise SegmentStorageError("segmented document is invalid")
        if isinstance(current, dict):
            pending.extend(current.values())
        elif isinstance(current, list):
            pending.extend(current)


def _require_exact_keys(document: dict[str, object], expected: set[str]) -> None:
    if set(document) != expected:
        raise SegmentStorageError("segmented document is invalid")


def _portable_id(value: object) -> str:
    if not isinstance(value, str) or not PORTABLE_ID_PATTERN.fullmatch(value):
        raise SegmentStorageError("segmented document is invalid")
    return value


def _positive_int(value: object) -> int:
    if type(value) is not int or value < 1:
        raise SegmentStorageError("segmented document is invalid")
    return value


def _hex64(value: object) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(character not in _HEX64 for character in value):
        raise SegmentStorageError("segmented document is invalid")
    return value


def _identity(metadata: os.stat_result) -> tuple[int, int, int, int, int, int, int]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
        metadata.st_nlink,
    )


def _mutable_identity(metadata: os.stat_result) -> tuple[int, int, int, int, int]:
    """Descriptor attributes stable across unlink of an old manifest inode.

    This is not an independent integrity proof: callers may use it only after
    the current named leaf is confirmed to be a different regular inode and
    the opened descriptor's link count has fallen. ``st_ctime`` and
    ``st_nlink`` change on that unlink, while inode, mode, size, and mtime
    still detect an in-place edit of the opened snapshot.
    """

    return (metadata.st_dev, metadata.st_ino, metadata.st_mode, metadata.st_size, metadata.st_mtime_ns)


def _same_inode(left: os.stat_result, right: os.stat_result) -> bool:
    return left.st_dev == right.st_dev and left.st_ino == right.st_ino


__all__ = [
    "ContextSegment",
    "MARKER_MAX_BYTES",
    "MANIFEST_MAX_BYTES",
    "SEGMENT_MAX_BYTES",
    "SegmentManifest",
    "SegmentStorageError",
    "StorageMarker",
    "decode_document",
    "decode_segment",
    "encode_segment",
    "read_chain",
]
