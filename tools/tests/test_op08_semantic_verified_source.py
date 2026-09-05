from __future__ import annotations

import hashlib
import importlib
import io
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2]))
try:
    document = importlib.import_module("tools.experiments.op08_semantic.document")
    source_module = importlib.import_module("tools.experiments.op08_semantic.verified_source")
finally:
    sys.path.pop(0)


def test_same_descriptor_input_matches_digest_without_moving_caller_cursor(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "input.json"
    raw = b'{"a":1,"a":2}'
    path.write_bytes(raw)
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    requests = []
    original = os.pread

    def bounded_read(fd, size, offset):
        requests.append(size)
        return original(fd, size, offset)

    monkeypatch.setattr(os, "pread", bounded_read)
    with path.open("rb") as source:
        source.seek(3)
        reader = source_module.VerifiedSource(source.fileno(), hashlib.sha256(raw).hexdigest(), len(raw))
        sink = io.BytesIO()
        result = document.canonicalize_document(reader, sink, scratch_parent=scratch)
        assert sink.getvalue() == b'{"a":2}'
        assert result.digest == hashlib.sha256(sink.getvalue()).hexdigest()
        assert source.tell() == 3 and not source.closed
        assert reader.read(1) == b''
    assert max(requests) <= 65536
    assert list(scratch.iterdir()) == []


@pytest.mark.parametrize("mismatch", ["digest", "size", "mutation"])
def test_invalid_binding_rejects_before_document_output(tmp_path: Path, monkeypatch, mismatch: str) -> None:
    raw = b'{"a":1}'
    path = tmp_path / "input.json"
    path.write_bytes(raw)
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    digest = "0" * 64 if mismatch == "digest" else hashlib.sha256(raw).hexdigest()
    size = len(raw) + 1 if mismatch == "size" else len(raw)
    original = os.pread
    mutated = False

    def read_then_modify(fd, count, offset):
        nonlocal mutated
        chunk = original(fd, count, offset)
        if mismatch == "mutation" and not mutated:
            mutated = True
            with path.open("r+b") as writer:
                writer.seek(5)
                writer.write(b'2')
            details = path.stat()
            os.utime(path, ns=(details.st_atime_ns, details.st_mtime_ns + 1000000))
        return chunk

    monkeypatch.setattr(os, "pread", read_then_modify)
    with path.open("rb") as source:
        sink = io.BytesIO()
        with pytest.raises(OSError):
            reader = source_module.VerifiedSource(source.fileno(), digest, size)
            document.canonicalize_document(reader, sink, scratch_parent=scratch)
        assert not source.closed and sink.getvalue() == b''
    assert list(scratch.iterdir()) == []
