from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import sys
import tracemalloc
from pathlib import Path
from typing import BinaryIO

import pytest

_MODULE_PATH = Path(__file__).parents[1] / "experiments/op08_semantic/strings.py"
_SPEC = importlib.util.spec_from_file_location("op08_semantic_strings", _MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)
StringDecodeError = _MODULE.StringDecodeError
StringIOError = _MODULE.StringIOError
UTF8Cursor = _MODULE.UTF8Cursor
read_json_string = _MODULE.read_json_string


class _SplitSource:
    def __init__(self, value: bytes, split: int) -> None:
        self.value = value
        self.split = split
        self.offset = 0
        self.closed = False
        self.requests: list[int] = []

    def read(self, size: int) -> bytes:
        self.requests.append(size)
        if self.offset >= len(self.value):
            return b""
        end = min(len(self.value), self.offset + size)
        if self.offset < self.split:
            end = min(end, self.split)
        value = self.value[self.offset : end]
        self.offset = end
        return value


class _ShortSink(io.BytesIO):
    def write(self, value: bytes) -> int:
        super().write(value[:2])
        return min(2, len(value))


@pytest.mark.parametrize(
    "raw, expected_surrogate",
    [
        (b'"ordinary"', False),
        (b'"slash\\/quote\\\"backslash\\\\"', False),
        (b'"\\b\\f\\n\\r\\t"', False),
        ('"snowman ☃ nonbmp 😀"'.encode(), False),
        (b'"\\ud83d\\ude00"', False),
        (b'"\\ud800"', True),
        (b'"\\ud800x\\udc00"', True),
    ],
)
def test_string_matches_json_canonical_oracle_for_every_source_split(
    raw: bytes, expected_surrogate: bool
) -> None:
    expected = json.dumps(
        json.loads(raw), ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode("utf8", "surrogatepass")
    for split in range(1, len(raw) + 1):
        source = _SplitSource(raw + b",", split)
        sink = io.BytesIO()
        cursor = UTF8Cursor(source, chunk_size=7)
        info = read_json_string(cursor, sink)
        assert sink.getvalue() == expected
        assert info.byte_count == len(expected)
        assert info.digest == hashlib.sha256(expected).hexdigest()
        assert info.has_unpaired_surrogate is expected_surrogate
        assert cursor.read_char() == ","
        assert not source.closed and not sink.closed


def test_string_leaves_following_token_readable() -> None:
    cursor = UTF8Cursor(_SplitSource(b'"key":', 1), chunk_size=3)
    read_json_string(cursor, io.BytesIO())
    assert cursor.read_char() == ":"


def test_document_cursor_spans_leave_delimiters_and_skip_only_json_space() -> None:
    cursor = UTF8Cursor(io.BytesIO(b" \t\r\n-12.3e+4, 0]"), chunk_size=3)
    cursor.skip_whitespace()
    pieces = []
    while piece := cursor.read_number_span():
        assert len(piece) <= 3
        pieces.append(piece)
    assert "".join(pieces) == "-12.3e+4"
    assert cursor.read_char() == ","
    cursor.skip_whitespace()
    assert cursor.read_number_span() == "0"
    assert cursor.read_char() == "]"
    cursor.skip_whitespace()
    assert cursor.peek_char() == ""


def test_document_cursor_does_not_accept_non_json_whitespace() -> None:
    cursor = UTF8Cursor(io.BytesIO("\u00a01".encode()))
    cursor.skip_whitespace()
    assert cursor.peek_char() == "\u00a0"


@pytest.mark.parametrize("following", [b",", b":", b"]"])
def test_string_preserves_each_common_following_token(following: bytes) -> None:
    cursor = UTF8Cursor(_SplitSource(b'"value"' + following, 2))
    read_json_string(cursor, io.BytesIO())
    assert cursor.read_char() == following.decode()


class _ProgressSink:
    def __init__(self, progress: object) -> None:
        self.progress = progress
    def write(self, _: object) -> object:
        return self.progress


@pytest.mark.parametrize("progress", [None, 0, -1, 100, True])
def test_invalid_sink_progress_is_io_error(progress: object) -> None:
    with pytest.raises(StringIOError):
        read_json_string(UTF8Cursor(_SplitSource(b'"x"', 1)), _ProgressSink(progress))  # type: ignore[arg-type]


@pytest.mark.parametrize("operation", ["read", "write"])
def test_io_fault_preserves_cause_and_stream_ownership(operation: str) -> None:
    fault = OSError("private source content")

    class Broken(io.BytesIO):
        def read(self, size: int = -1) -> bytes:
            if operation == "read":
                raise fault
            return super().read(size)

        def write(self, value: bytes) -> int:
            if operation == "write":
                raise fault
            return super().write(value)

    source = Broken(b'"x"')
    sink = Broken()
    with pytest.raises(StringIOError) as error:
        read_json_string(UTF8Cursor(source), sink)
    assert error.value.__cause__ is fault
    assert "private source content" not in str(error.value)
    assert not source.closed and not sink.closed


@pytest.mark.parametrize("value", [None, "text", bytearray(b'"x"'), 1])
def test_nonbytes_source_is_io_protocol_failure(value: object) -> None:
    class InvalidSource:
        closed = False

        def read(self, size: int) -> object:
            return value

    source = InvalidSource()
    sink = io.BytesIO()
    with pytest.raises(StringIOError):
        read_json_string(UTF8Cursor(source), sink)
    assert not source.closed and not sink.closed


@pytest.mark.parametrize("codepoint", [*range(32), 34, 92])
def test_every_escaped_control_matches_oracle(codepoint: int) -> None:
    raw = f'"\\u{codepoint:04x}"'.encode()
    expected = json.dumps(chr(codepoint), ensure_ascii=False).encode()
    sink = io.BytesIO()
    info = read_json_string(UTF8Cursor(_SplitSource(raw, 1)), sink)
    assert sink.getvalue() == expected
    assert info.digest == hashlib.sha256(expected).hexdigest()
    assert not info.has_unpaired_surrogate


@pytest.mark.parametrize(
    "raw",
    [b"", b"plain", b'"\\x"', b'"\x01"', b'"unterminated', b'"\xff"',
     b'"\xf0\x9f', b'"\\u12"', b'"\\uXXXX"', b'"\\', b'"\xed\xa0\x80"'],
)
def test_invalid_strings_raise_decode_error(raw: bytes) -> None:
    with pytest.raises(StringDecodeError):
        read_json_string(UTF8Cursor(_SplitSource(raw, 1)), io.BytesIO())


def test_short_sink_writes_all_bytes() -> None:
    sink = _ShortSink()
    read_json_string(UTF8Cursor(_SplitSource(b'"abcdef"', 2)), sink)
    assert sink.getvalue() == b'"abcdef"'


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (b'"\\ud800\\n"', b'"\xed\xa0\x80\\n"'),
        (b'"\\ud800\\ud800\\udc00"', bytes.fromhex("22 ed a0 80 f0 90 80 80 22")),
    ],
)
def test_unpaired_high_surrogates_do_not_consume_following_escapes(
    raw: bytes, expected: bytes
) -> None:
    sink = io.BytesIO()
    info = read_json_string(UTF8Cursor(_SplitSource(raw, 1)), sink)
    assert sink.getvalue() == expected
    assert info.has_unpaired_surrogate


@pytest.mark.parametrize("chunk_size", [0, -1, 65537, True])
def test_cursor_rejects_invalid_chunk_size(chunk_size: int) -> None:
    with pytest.raises(ValueError):
        UTF8Cursor(io.BytesIO(b'"x"'), chunk_size=chunk_size)


@pytest.mark.parametrize("size", [8 * 1024 * 1024, 64 * 1024 * 1024])
@pytest.mark.parametrize("following", [b":", b","])
def test_large_ascii_string_is_bounded_and_streamed_to_file(
    tmp_path: Path, size: int, following: bytes
) -> None:
    source_path = tmp_path / "source.json"
    output_path = tmp_path / "output.json"
    block = b"a" * 65536
    with source_path.open("wb") as source:
        source.write(b'"')
        remaining = size
        while remaining:
            piece = block[: min(len(block), remaining)]
            source.write(piece)
            remaining -= len(piece)
        source.write(b'"' + following)

    class CountingSource:
        def __init__(self, source: BinaryIO) -> None:
            self.source = source
            self.max_request = 0
            self.bytes_read = 0

        def read(self, requested: int) -> bytes:
            assert 0 < requested <= 65536
            self.max_request = max(self.max_request, requested)
            value = self.source.read(requested)
            self.bytes_read += len(value)
            return value

    with source_path.open("rb") as source, output_path.open("wb") as sink:
        counted = CountingSource(source)
        cursor = UTF8Cursor(counted)
        tracemalloc.start()
        before = tracemalloc.get_traced_memory()[0]
        try:
            info = read_json_string(cursor, sink)
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        assert cursor.read_char() == following.decode()
        assert not source.closed and not sink.closed
    assert info.byte_count == size + 2
    assert output_path.stat().st_size == size + 2
    assert peak - before <= 4 * 1024 * 1024
    expected_hash = hashlib.sha256(b'"')
    for _ in range(size // len(block)):
        expected_hash.update(block)
    expected_hash.update(b'"')
    output_hash = hashlib.sha256()
    with output_path.open("rb") as output:
        while chunk := output.read(65536):
            output_hash.update(chunk)
    assert info.digest == expected_hash.hexdigest() == output_hash.hexdigest()
    assert counted.bytes_read == size + 3
    assert not info.has_unpaired_surrogate
    print(json.dumps({"size": size, "role": "key" if following == b":" else "value",
                      "peak_bytes": peak - before, "max_read": counted.max_request,
                      "bytes_read": counted.bytes_read, "output_bytes": info.byte_count,
                      "sha256": info.digest}))
