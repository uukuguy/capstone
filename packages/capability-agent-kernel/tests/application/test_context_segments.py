from __future__ import annotations

import json
import os
from hashlib import sha256
from pathlib import Path

import pytest

import capability_agent.application.context_segments as segments_module
from capability_agent.application.context_segments import (
    ContextSegment,
    MANIFEST_MAX_BYTES,
    MARKER_MAX_BYTES,
    SEGMENT_MAX_BYTES,
    SegmentManifest,
    SegmentStorageError,
    StorageMarker,
    decode_document,
    decode_segment,
    encode_segment,
    read_chain,
)
from capability_agent.application.context_models import ContextEvent, ContextEventDraft
from capability_agent.application.context_store import ApplicationContextStore
from capability_agent.application.workspace import ApplicationWorkspace
from capability_agent.trajectory.canonical import canonical_json_bytes


def test_strict_documents_require_canonical_bytes() -> None:
    assert decode_document(b'{"key":"value"}\n', max_bytes=16) == {"key": "value"}
    assert StorageMarker
    assert SegmentManifest
    assert ContextSegment


def test_internal_record_construction_rejects_non_schema_scalars() -> None:
    with pytest.raises(SegmentStorageError):
        StorageMarker("not portable")
    with pytest.raises(SegmentStorageError):
        SegmentManifest("run-a", True, 1, "0" * 64, "1" * 64)


@pytest.mark.parametrize(
    "raw",
    (
        b'{"nested":{"key":1,"key":2}}\n',
        b'{"key":"\\ud800"}\n',
    ),
)
def test_decode_document_sanitizes_parser_and_canonicalization_failures(raw: bytes) -> None:
    with pytest.raises(SegmentStorageError):
        decode_document(raw, max_bytes=len(raw))


@pytest.mark.parametrize("failure_stage", ["parse", "canonicalize"])
def test_decode_document_sanitizes_recursion_errors(
    monkeypatch: pytest.MonkeyPatch, failure_stage: str
) -> None:
    def fail_recursion(*args: object, **kwargs: object) -> object:
        raise RecursionError("internal recursion diagnostic")

    if failure_stage == "parse":
        monkeypatch.setattr(segments_module.json, "loads", fail_recursion)
    else:
        monkeypatch.setattr(segments_module, "canonical_json_bytes", fail_recursion)

    raw = b'{"key":0}\n'
    with pytest.raises(SegmentStorageError, match="^segmented document is invalid$"):
        decode_document(raw, max_bytes=len(raw))


def test_decode_document_sanitizes_deeply_nested_python_json_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The C accelerator has no fixed failure depth (CPython issue140125).
    # Exercise real recursive parsing with the standard library Python scanner.
    scanner_factory = getattr(json.scanner, "py_make_scanner", None)
    if scanner_factory is None:
        pytest.skip("stdlib Python JSON scanner is unavailable")

    def recursive_loads(text: str, **kwargs: object) -> object:
        decoder = json.JSONDecoder(**kwargs)  # type: ignore[arg-type]
        decoder.scan_once = scanner_factory(decoder)
        return decoder.decode(text)

    monkeypatch.setattr(segments_module.json, "loads", recursive_loads)
    depth = 100_000
    raw = b'{"key":' + b"[" * depth + b"0" + b"]" * depth + b"}\n"

    with pytest.raises(SegmentStorageError):
        decode_document(raw, max_bytes=len(raw))


def _event(sequence: int, previous_hash: str, next_hash: str) -> ContextEvent:
    return ContextEvent(
        run_id="run-a",
        sequence=sequence,
        event_type="diagnostic.recorded",
        payload={"message": f"event-{sequence}"},
        previous_revision=sequence - 1,
        previous_state_hash=previous_hash,
        next_revision=sequence,
        next_state_hash=next_hash,
    )


def _write_layout(tmp_path: Path, manifests: tuple[SegmentManifest, ...], raws: tuple[tuple[str, bytes], ...]) -> Path:
    core = tmp_path / "run-a" / "core"
    segments = core / "context-segments"
    segments.mkdir(parents=True)
    entry = core / "context-events.jsonl"
    entry.write_bytes(b"")
    (core / "context-storage.json").write_bytes(canonical_json_bytes(StorageMarker("run-a").document()))
    for digest, raw in raws:
        (segments / f"{digest}.json").write_bytes(raw)
    (core / "context-manifest.json").write_bytes(canonical_json_bytes(manifests[-1].document()))
    return entry


def _one_segment() -> tuple[ContextSegment, bytes, str, SegmentManifest]:
    segment, raw, digest = encode_segment((_event(1, "0" * 64, "1" * 64),), None)
    return segment, raw, digest, SegmentManifest("run-a", 1, 1, "1" * 64, digest)


def test_encode_decode_and_read_chain_use_canonical_genesis_file(tmp_path: Path) -> None:
    segment, raw, digest, manifest = _one_segment()
    entry = _write_layout(tmp_path, (manifest,), ((digest, raw),))

    assert decode_segment(raw, expected_sha256=digest) == segment
    observed_manifest, events = read_chain(entry)

    assert observed_manifest == manifest
    assert events == segment.events


def test_codec_accepts_events_from_real_legacy_context_store(tmp_path: Path) -> None:
    legacy = ApplicationWorkspace.create(tmp_path / "legacy-runs", run_id="run-a")
    store = ApplicationContextStore.initialize(legacy)
    store.append(ContextEventDraft(event_type="diagnostic.recorded", payload={"message": "legal"}))
    _state, events = ApplicationContextStore.replay_events(legacy)
    segment, raw, digest = encode_segment(events, None)
    manifest = SegmentManifest("run-a", 1, events[-1].sequence, events[-1].next_state_hash, digest)
    entry = _write_layout(tmp_path / "segmented", (manifest,), ((digest, raw),))

    observed_manifest, observed_events = read_chain(entry)

    assert observed_manifest == manifest
    assert observed_events == events
    assert segment.start_revision == 1


@pytest.mark.parametrize(
    "raw",
    (
        b'{"key":"value","key":"other"}\n',
        b'{"key":NaN}\n',
        b'{"key":1e309}\n',
        b'{"key": "value"}\n',
        b'{"key":"value"}',
        b"\xff",
    ),
)
def test_decode_document_rejects_noncanonical_or_unsafe_json(raw: bytes) -> None:
    with pytest.raises(SegmentStorageError):
        decode_document(raw, max_bytes=128)


def test_decode_document_rejects_max_plus_one_before_parsing() -> None:
    raw = canonical_json_bytes({"key": "value"})

    with pytest.raises(SegmentStorageError):
        decode_document(raw, max_bytes=len(raw) - 1)


def test_decode_segment_rejects_wrong_digest_and_extra_field() -> None:
    _segment, raw, digest, _manifest = _one_segment()
    document = decode_document(raw, max_bytes=len(raw))
    document["extra"] = True
    malformed = canonical_json_bytes(document)

    with pytest.raises(SegmentStorageError):
        decode_segment(raw, expected_sha256="f" * 64)
    with pytest.raises(SegmentStorageError):
        decode_segment(malformed, expected_sha256=sha256(malformed).hexdigest())


def test_decode_segment_rejects_wrong_payload_digest() -> None:
    _segment, raw, _digest, _manifest = _one_segment()
    document = decode_document(raw, max_bytes=len(raw))
    document["payload_sha256"] = "0" * 64
    malformed = canonical_json_bytes(document)

    with pytest.raises(SegmentStorageError):
        decode_segment(malformed, expected_sha256=sha256(malformed).hexdigest())


def test_decode_segment_rejects_missing_required_field() -> None:
    _segment, raw, _digest, _manifest = _one_segment()
    document = decode_document(raw, max_bytes=len(raw))
    document.pop("payload_sha256")
    malformed = canonical_json_bytes(document)

    with pytest.raises(SegmentStorageError):
        decode_segment(malformed, expected_sha256=sha256(malformed).hexdigest())


def test_read_chain_returns_two_canonical_segments_in_revision_order(tmp_path: Path) -> None:
    first, first_raw, first_digest, first_manifest = _one_segment()
    second, second_raw, second_digest = encode_segment(
        (_event(2, "1" * 64, "2" * 64),), first_manifest
    )
    manifest = SegmentManifest("run-a", 2, 2, "2" * 64, second_digest)
    entry = _write_layout(
        tmp_path,
        (manifest,),
        ((first_digest, first_raw), (second_digest, second_raw)),
    )

    observed_manifest, events = read_chain(entry)

    assert observed_manifest == manifest
    assert events == (*first.events, *second.events)


def test_read_chain_rejects_segment_boundary_that_skips_revision(tmp_path: Path) -> None:
    _first, first_raw, first_digest, first_manifest = _one_segment()
    second, second_raw, second_digest = encode_segment(
        (_event(2, "1" * 64, "2" * 64),), first_manifest
    )
    document = decode_document(second_raw, max_bytes=len(second_raw))
    document["start_revision"] = 3
    malformed = canonical_json_bytes(document)
    malformed_digest = sha256(malformed).hexdigest()
    manifest = SegmentManifest("run-a", 2, 2, second.next_state_hash, malformed_digest)
    entry = _write_layout(
        tmp_path,
        (manifest,),
        ((first_digest, first_raw), (malformed_digest, malformed)),
    )

    with pytest.raises(SegmentStorageError):
        read_chain(entry)


def test_read_chain_rejects_partial_sentinels_and_nonempty_logical_entry(tmp_path: Path) -> None:
    core = tmp_path / "run-a" / "core"
    core.mkdir(parents=True)
    entry = core / "context-events.jsonl"
    entry.write_bytes(b"{}\n")
    (core / "context-storage.json").write_bytes(canonical_json_bytes(StorageMarker("run-a").document()))

    with pytest.raises(SegmentStorageError):
        read_chain(entry)


def test_read_chain_rejects_oversize_marker_before_document_parse(tmp_path: Path) -> None:
    _segment, raw, digest, manifest = _one_segment()
    entry = _write_layout(tmp_path, (manifest,), ((digest, raw),))
    marker = entry.parent / "context-storage.json"
    marker.write_bytes(b"x" * (16 * 1024 + 1))

    with pytest.raises(SegmentStorageError):
        read_chain(entry)


def test_read_chain_reads_marker_at_exact_max_plus_one_bound(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _segment, raw, digest, manifest = _one_segment()
    entry = _write_layout(tmp_path, (manifest,), ((digest, raw),))
    real_open = segments_module.os.open
    real_read = segments_module.os.read
    marker_fd: int | None = None
    marker_reads: list[int] = []

    def recording_open(name: str | bytes, flags: int, *args: int, **kwargs: int) -> int:
        nonlocal marker_fd
        descriptor = real_open(name, flags, *args, **kwargs)
        if name == "context-storage.json":
            marker_fd = descriptor
        return descriptor

    def recording_read(descriptor: int, count: int) -> bytes:
        if descriptor == marker_fd:
            marker_reads.append(count)
        return real_read(descriptor, count)

    monkeypatch.setattr(segments_module.os, "open", recording_open)
    monkeypatch.setattr(segments_module.os, "read", recording_read)

    read_chain(entry)

    assert marker_reads[0] == MARKER_MAX_BYTES + 1


def test_read_chain_rejects_oversize_manifest_and_segment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _segment, raw, digest, manifest = _one_segment()
    entry = _write_layout(tmp_path / "manifest", (manifest,), ((digest, raw),))
    (entry.parent / "context-manifest.json").write_bytes(b"x" * (MANIFEST_MAX_BYTES + 1))
    with pytest.raises(SegmentStorageError):
        read_chain(entry)

    entry = _write_layout(tmp_path / "segment", (manifest,), ((digest, raw),))
    monkeypatch.setattr(segments_module, "SEGMENT_MAX_BYTES", len(raw) - 1)
    with pytest.raises(SegmentStorageError):
        read_chain(entry)


def test_read_chain_rejects_marker_manifest_run_mismatch(tmp_path: Path) -> None:
    _segment, raw, digest, manifest = _one_segment()
    entry = _write_layout(tmp_path, (manifest,), ((digest, raw),))
    mismatched = SegmentManifest("run-b", 1, 1, "1" * 64, digest)
    (entry.parent / "context-manifest.json").write_bytes(canonical_json_bytes(mismatched.document()))

    with pytest.raises(SegmentStorageError):
        read_chain(entry)


def test_read_chain_accepts_relative_entry_and_rejects_symlinked_parent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _segment, raw, digest, manifest = _one_segment()
    entry = _write_layout(tmp_path / "relative", (manifest,), ((digest, raw),))
    monkeypatch.chdir(tmp_path)
    assert read_chain(entry.relative_to(tmp_path))[0] == manifest

    core = entry.parent
    original = core.with_name("core-original")
    core.rename(original)
    core.symlink_to(original, target_is_directory=True)
    with pytest.raises(SegmentStorageError):
        read_chain(entry)

    _segment, raw, digest, manifest = _one_segment()
    entry = _write_layout(tmp_path / "complete", (manifest,), ((digest, raw),))
    entry.write_bytes(b"{}\n")
    with pytest.raises(SegmentStorageError):
        read_chain(entry)


def test_read_chain_rejects_fifo_segment_without_blocking(tmp_path: Path) -> None:
    _segment, raw, digest, manifest = _one_segment()
    entry = _write_layout(tmp_path, (manifest,), ((digest, raw),))
    target = entry.parent / "context-segments" / f"{digest}.json"
    target.unlink()
    os.mkfifo(target)

    with pytest.raises(SegmentStorageError):
        read_chain(entry)


def test_read_chain_accepts_old_opened_manifest_during_atomic_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, first_raw, first_digest, first_manifest = _one_segment()
    second, second_raw, second_digest = encode_segment(
        (_event(2, "1" * 64, "2" * 64),), first_manifest
    )
    current_manifest = SegmentManifest("run-a", 2, 2, "2" * 64, second_digest)
    entry = _write_layout(
        tmp_path,
        (first_manifest,),
        ((first_digest, first_raw), (second_digest, second_raw)),
    )
    manifest_path = entry.parent / "context-manifest.json"
    replacement = entry.parent / "replacement.json"
    replacement.write_bytes(canonical_json_bytes(current_manifest.document()))
    real_open = segments_module.os.open
    real_read = segments_module.os.read
    manifest_fd: int | None = None
    replaced = False

    def recording_open(name: str | bytes, flags: int, *args: int, **kwargs: int) -> int:
        nonlocal manifest_fd
        descriptor = real_open(name, flags, *args, **kwargs)
        if name == "context-manifest.json":
            manifest_fd = descriptor
        return descriptor

    def replace_after_manifest_read(descriptor: int, count: int) -> bytes:
        nonlocal replaced
        result = real_read(descriptor, count)
        if descriptor == manifest_fd and not replaced:
            replaced = True
            replacement.replace(manifest_path)
        return result

    monkeypatch.setattr(segments_module.os, "open", recording_open)
    monkeypatch.setattr(segments_module.os, "read", replace_after_manifest_read)

    observed_manifest, events = read_chain(entry)

    assert replaced
    assert observed_manifest == first_manifest
    assert events == first.events
    assert second.end_revision == 2


def test_read_chain_rejects_mutable_manifest_changed_in_place_after_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, first_raw, first_digest, first_manifest = _one_segment()
    _second, second_raw, second_digest = encode_segment(
        (_event(2, "1" * 64, "2" * 64),), first_manifest
    )
    current_manifest = SegmentManifest("run-a", 2, 2, "2" * 64, second_digest)
    entry = _write_layout(
        tmp_path,
        (first_manifest,),
        ((first_digest, first_raw), (second_digest, second_raw)),
    )
    manifest_path = entry.parent / "context-manifest.json"
    replacement_raw = canonical_json_bytes(current_manifest.document())
    assert len(replacement_raw) == manifest_path.stat().st_size
    fixed_mtime_ns = 1_700_000_000_000_000_000
    os.utime(manifest_path, ns=(fixed_mtime_ns, fixed_mtime_ns))
    real_open = segments_module.os.open
    real_read = segments_module.os.read
    real_fstat = segments_module.os.fstat
    manifest_fd: int | None = None
    changed = False
    observed_metadata: list[os.stat_result] = []

    def recording_open(name: str | bytes, flags: int, *args: int, **kwargs: int) -> int:
        nonlocal manifest_fd
        descriptor = real_open(name, flags, *args, **kwargs)
        if name == "context-manifest.json":
            manifest_fd = descriptor
        return descriptor

    def rewrite_after_manifest_read(descriptor: int, count: int) -> bytes:
        nonlocal changed
        result = real_read(descriptor, count)
        if descriptor == manifest_fd and not changed:
            changed = True
            observed_metadata.append(real_fstat(descriptor))
            manifest_path.write_bytes(replacement_raw)
            os.utime(manifest_path, ns=(fixed_mtime_ns, fixed_mtime_ns))
            observed_metadata.append(real_fstat(descriptor))
        return result

    monkeypatch.setattr(segments_module.os, "open", recording_open)
    monkeypatch.setattr(segments_module.os, "read", rewrite_after_manifest_read)

    with pytest.raises(SegmentStorageError):
        read_chain(entry)

    assert changed
    before, after = observed_metadata
    assert before.st_ino == after.st_ino
    assert before.st_size == after.st_size
    assert before.st_mtime_ns == after.st_mtime_ns == fixed_mtime_ns
    assert before.st_nlink == after.st_nlink == 1
    assert before.st_ctime_ns != after.st_ctime_ns


def test_read_chain_rejects_immutable_segment_replaced_after_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _segment, raw, digest, manifest = _one_segment()
    entry = _write_layout(tmp_path, (manifest,), ((digest, raw),))
    target = entry.parent / "context-segments" / f"{digest}.json"
    replacement = entry.parent / "context-segments" / "replacement.json"
    replacement.write_bytes(raw)
    real_open = segments_module.os.open
    real_fstat = segments_module.os.fstat
    segment_fd: int | None = None

    def recording_open(name: str | bytes, flags: int, *args: int, **kwargs: int) -> int:
        nonlocal segment_fd
        descriptor = real_open(name, flags, *args, **kwargs)
        if name == target.name:
            segment_fd = descriptor
        return descriptor

    def replace_after_segment_open(descriptor: int):
        if descriptor == segment_fd and replacement.exists():
            replacement.replace(target)
        return real_fstat(descriptor)

    monkeypatch.setattr(segments_module.os, "open", recording_open)
    monkeypatch.setattr(segments_module.os, "fstat", replace_after_segment_open)

    with pytest.raises(SegmentStorageError):
        read_chain(entry)
