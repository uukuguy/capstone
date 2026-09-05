from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import sqlite3
import sys
import tempfile
import tracemalloc
from pathlib import Path

import pytest

_PATH = Path(__file__).parents[1] / "experiments/op08_semantic/document.py"
_SPEC = importlib.util.spec_from_file_location("op08_document", _PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MODULE
sys.path.insert(0, str(Path(__file__).parents[2]))
try:
    _SPEC.loader.exec_module(_MODULE)
finally:
    sys.path.pop(0)
canonicalize_document = _MODULE.canonicalize_document
DocumentDecodeError = _MODULE.DocumentDecodeError
DocumentShapeError = _MODULE.DocumentShapeError
DocumentCanonicalError = _MODULE.DocumentCanonicalError
DocumentResourceError = _MODULE.DocumentResourceError


@pytest.mark.parametrize("component", ["blob_bytes", "integer_bytes", "database_bytes"])
def test_scratch_component_limit_rejects_and_cleans(tmp_path: Path, component: str) -> None:
    limits = _MODULE.ScratchLimits(**{component: 1})
    source, sink = io.BytesIO(b'{"a":12345}'), io.BytesIO()
    with pytest.raises(DocumentResourceError):
        canonicalize_document(source, sink, scratch_parent=tmp_path, limits=limits)
    assert list(tmp_path.iterdir()) == []
    assert not source.closed and not sink.closed
    assert sink.getvalue() == b''


def test_small_document_fits_explicit_scratch_limits(tmp_path: Path) -> None:
    limits = _MODULE.ScratchLimits(blob_bytes=8, integer_bytes=5, database_bytes=65536)
    sink = io.BytesIO()
    canonicalize_document(io.BytesIO(b'{"a":12345}'), sink, scratch_parent=tmp_path, limits=limits)
    assert sink.getvalue() == b'{"a":12345}'
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("value", [0, -1, True, 1.5])
def test_scratch_limits_require_positive_integer_configuration(value) -> None:
    with pytest.raises(ValueError):
        _MODULE.ScratchLimits(blob_bytes=value)


def test_scratch_file_limit_checks_before_extending(tmp_path: Path) -> None:
    path = tmp_path / "bounded"
    with _MODULE.LimitedFile(path, 4) as stream:
        assert stream.write(b'abcd') == 4
        with pytest.raises(OSError):
            stream.write(b'e')
        assert path.stat().st_size == 4


def test_database_growth_reaches_limit_and_cleans(tmp_path: Path) -> None:
    limits = _MODULE.ScratchLimits(database_bytes=32768)
    raw = b'{"a":[' + b','.join([b'0'] * 300) + b']}'
    sink = io.BytesIO()
    with pytest.raises(DocumentResourceError) as error:
        canonicalize_document(io.BytesIO(raw), sink, scratch_parent=tmp_path, limits=limits)
    cause = error.value
    while cause.__cause__ is not None:
        cause = cause.__cause__
    assert isinstance(cause, sqlite3.OperationalError)
    assert cause.sqlite_errorcode == sqlite3.SQLITE_FULL
    assert sink.getvalue() == b'' and list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("raw", [
    b'{}', b' {"a": [1, -0.0, true, false, null, {"x":"y"}]} ',
    b'{"a":1,"b":2,"a":3}', b'{"a":1,"\\u0061":2}',
    b'{"a":NaN,"a":0}', b'{"a":Infinity,"a":0}',
    b'{"a":"\\ud800","a":0}', b'{"a":{"x":NaN},"a":0}',
    b'{"a":{"\\ud800":0},"a":0}', b'{"a":[NaN,"\\ud800"],"a":0}',
])
def test_mapping_matches_current_canonical_oracle(tmp_path: Path, raw: bytes) -> None:
    expected = json.dumps(json.loads(raw), ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf8")
    source, sink = io.BytesIO(raw), io.BytesIO()
    info = canonicalize_document(source, sink, scratch_parent=tmp_path)
    assert sink.getvalue() == expected
    assert info.byte_count == len(expected)
    assert info.digest == hashlib.sha256(expected).hexdigest()
    assert not source.closed and not sink.closed
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("raw", [
    b'{"a":NaN}', b'{"a":Infinity}', b'{"a":-Infinity}', b'{"a":1e99999}',
    b'{"a":"\\ud800"}', b'{"\\ud800":0,"\\ud800":1}',
])
def test_reachable_uncanonical_values_and_keys_reject(tmp_path: Path, raw: bytes) -> None:
    source, sink = io.BytesIO(raw), io.BytesIO()
    with pytest.raises(DocumentCanonicalError):
        canonicalize_document(source, sink, scratch_parent=tmp_path)
    assert not source.closed and not sink.closed
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("raw", [
    b'', b'{', b'{"a":}', b'{"a":1,}', b'{"a":1} {}',
    b'{"a":[1,]}', b'{"a":01,"a":0}', b'{"a":"\\x","a":0}',
    b'{"a":"\xff","a":0}', b'{"a":"\xed\xa0\x80","a":0}',
])
def test_syntax_errors_are_not_hidden_by_overwrite(tmp_path: Path, raw: bytes) -> None:
    with pytest.raises(DocumentDecodeError):
        canonicalize_document(io.BytesIO(raw), io.BytesIO(), scratch_parent=tmp_path)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("raw", [b'[]', b'1', b'null', b'"text"'])
def test_root_shape_matches_domain_mapping_contract(tmp_path: Path, raw: bytes) -> None:
    with pytest.raises(DocumentShapeError):
        canonicalize_document(io.BytesIO(raw), io.BytesIO(), scratch_parent=tmp_path)


def test_top_level_omission_after_duplicate_resolution(tmp_path: Path) -> None:
    raw = b'{"result_ref":NaN,"a":{"result_ref":2},"result_ref":"\\ud800","b":3}'
    expected_document = json.loads(raw)
    del expected_document["result_ref"]
    expected = json.dumps(expected_document, separators=(",", ":")).encode()
    sink = io.BytesIO()
    info = canonicalize_document(io.BytesIO(raw), sink, scratch_parent=tmp_path, omit_top_level_key="result_ref")
    assert sink.getvalue() == expected
    assert info.digest == hashlib.sha256(expected).hexdigest()


def test_omission_cannot_hide_parse_time_integer_limit(tmp_path: Path) -> None:
    previous = sys.get_int_max_str_digits()
    try:
        sys.set_int_max_str_digits(640)
        raw = b'{"result_ref":' + b'1' * 641 + b'}'
        with pytest.raises(DocumentDecodeError):
            canonicalize_document(io.BytesIO(raw), io.BytesIO(), scratch_parent=tmp_path, omit_top_level_key="result_ref")
    finally:
        sys.set_int_max_str_digits(previous)


def test_partial_schema_failure_discards_owned_scratch(tmp_path: Path, monkeypatch) -> None:
    original = sqlite3.connect

    class FailedSchema(sqlite3.Connection):
        def execute(self, sql, parameters=()):
            if sql.startswith("CREATE TABLE array_edges"):
                raise sqlite3.OperationalError("injected initialization failure")
            return super().execute(sql, parameters)

    monkeypatch.setattr(sqlite3, "connect", lambda *a, **kw: original(*a, factory=FailedSchema, **kw))
    source, sink = io.BytesIO(b'{}'), io.BytesIO()
    with pytest.raises(DocumentResourceError) as error:
        canonicalize_document(source, sink, scratch_parent=tmp_path)
    assert isinstance(error.value.__cause__, sqlite3.OperationalError)
    assert list(tmp_path.iterdir()) == []
    assert sink.getvalue() == b''
    assert not source.closed and not sink.closed


def test_integer_spool_cleanup_does_not_replace_decode_failure(tmp_path: Path, monkeypatch) -> None:
    original = tempfile.TemporaryFile

    class CloseFailure:
        def __init__(self, wrapped):
            self.wrapped = wrapped

        def __getattr__(self, name):
            return getattr(self.wrapped, name)

        def close(self):
            self.wrapped.close()
            raise OSError("cleanup failure")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.close()

    monkeypatch.setattr(tempfile, "TemporaryFile", lambda *a, **kw: CloseFailure(original(*a, **kw)))
    with pytest.raises(DocumentDecodeError):
        canonicalize_document(io.BytesIO(b'{"a":01}'), io.BytesIO(), scratch_parent=tmp_path)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("operation", ["read", "write"])
@pytest.mark.parametrize("fault", [OSError("private data"), UnicodeDecodeError("utf8", b"x", 0, 1, "private data")])
def test_caller_io_failure_retains_cause_and_cleans_scratch(tmp_path: Path, operation: str, fault: Exception) -> None:

    class Broken(io.BytesIO):
        def read(self, size=-1):
            if operation == "read":
                raise fault
            return super().read(size)

        def write(self, chunk):
            if operation == "write":
                raise fault
            return super().write(chunk)

    source, sink = Broken(b'{"a":1}'), Broken()
    with pytest.raises(DocumentResourceError) as error:
        canonicalize_document(source, sink, scratch_parent=tmp_path)
    cause = error.value
    while cause.__cause__ is not None:
        cause = cause.__cause__
    assert cause is fault
    assert "private data" not in str(error.value)
    assert not source.closed and not sink.closed
    assert list(tmp_path.iterdir()) == []


def test_deep_document_uses_disk_traversal_without_new_depth_cap(tmp_path: Path) -> None:
    raw = b'{"a":' + b'[' * 12000 + b'0' + b']' * 12000 + b'}'
    try:
        expected = json.dumps(json.loads(raw), separators=(",", ":")).encode()
    except (RecursionError, MemoryError):
        pytest.skip("reference_unavailable: not a semantic comparison PASS")
    tracemalloc.start()
    before = tracemalloc.get_traced_memory()[0]
    try:
        with tempfile.TemporaryFile() as sink:
            info = canonicalize_document(io.BytesIO(raw), sink, scratch_parent=tmp_path)
            _, peak = tracemalloc.get_traced_memory()
            sink.seek(0)
            assert sink.read() == expected
    finally:
        tracemalloc.stop()
    assert info.digest == hashlib.sha256(expected).hexdigest()
    assert peak - before < 4 * 1024 * 1024
    print({"depth": 12000, "peak_bytes": peak - before})


@pytest.mark.parametrize("size", [8 * 1024 * 1024, 64 * 1024 * 1024])
@pytest.mark.parametrize("shape", ["string", "duplicate_key", "number", "discarded"])
def test_large_document_end_to_end_fixed_python_memory(tmp_path: Path, size: int, shape: str) -> None:
    block = (b"0" if shape == "number" else b"a") * 65536
    with tempfile.TemporaryFile() as source, tempfile.TemporaryFile() as sink:
        def run_block():
            for _ in range(size // len(block)):
                source.write(block)

        if shape == "string":
            source.write(b'{"v":"'); run_block(); source.write(b'"}')
            expected_prefix, expected_suffix = b'{"v":"', b'"}'
        elif shape == "duplicate_key":
            source.write(b'{"'); run_block(); source.write(b'":1,"'); run_block(); source.write(b'":2}')
            expected_prefix, expected_suffix = b'{"', b'":2}'
        elif shape == "number":
            source.write(b'{"n":0.'); run_block(); source.write(b'1e' + str(size + 1).encode() + b'}')
            expected_prefix, expected_suffix = b'{"n":1.0}', b""
        else:
            source.write(b'{"n":"\\ud800'); run_block(); source.write(b'","n":0}')
            expected_prefix, expected_suffix = b'{"n":0}', b""
        expected_hash = hashlib.sha256(expected_prefix)
        expected_size = len(expected_prefix) + len(expected_suffix)
        if shape in {"string", "duplicate_key"}:
            for _ in range(size // len(block)):
                expected_hash.update(block)
            expected_size += size
        expected_hash.update(expected_suffix)
        source.seek(0)
        tracemalloc.start()
        before = tracemalloc.get_traced_memory()[0]
        try:
            info = canonicalize_document(source, sink, scratch_parent=tmp_path)
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        assert peak - before < 4 * 1024 * 1024
        assert info.digest == expected_hash.hexdigest()
        assert info.byte_count == expected_size == sink.tell()
        sink.seek(0)
        actual = hashlib.sha256()
        while chunk := sink.read(65536):
            actual.update(chunk)
        assert actual.hexdigest() == expected_hash.hexdigest()
        assert not source.closed and not sink.closed
        assert list(tmp_path.iterdir()) == []
        print({"shape": shape, "body_bytes": size, "peak_bytes": peak - before,
               "output_bytes": info.byte_count, "sha256": info.digest})
