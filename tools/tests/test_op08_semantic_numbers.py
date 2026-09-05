from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import math
import random
import sys
import tempfile
import tracemalloc
from pathlib import Path

import pytest

_PATH = Path(__file__).parents[1] / "experiments/op08_semantic/numbers.py"
_SPEC = importlib.util.spec_from_file_location("op08_numbers", _PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)
NumberCanonicalizer = _MODULE.NumberCanonicalizer
NumberDecodeError = _MODULE.NumberDecodeError
NumberIOError = _MODULE.NumberIOError


def canonicalize(raw: bytes, split: int = 1) -> tuple[object, bytes]:
    sink = io.BytesIO()
    with tempfile.TemporaryFile() as spool:
        parser = NumberCanonicalizer(sink, spool)
        for offset in range(0, len(raw), split):
            parser.feed(raw[offset : offset + split])
        info = parser.finish()
        assert not sink.closed and not spool.closed
    return info, sink.getvalue()


@pytest.mark.parametrize("raw", [
    b"0", b"-0", b"12", b"-12345", b"0.0", b"-0.0", b"1E+2", b"1e-2",
    b"1.234567890123456789", b"9007199254740993", b"9007199254740993.0",
    b"5e-324", b"2.2250738585072014e-308", b"1.7976931348623157e308",
    b"-1e-999999", b"-0e999999", b"1e999999", b"NaN", b"Infinity", b"-Infinity",
])
def test_numeric_oracle_all_chunk_sizes(raw: bytes) -> None:
    value = json.loads(raw)
    nonfinite = isinstance(value, float) and not math.isfinite(value)
    expected = b"" if nonfinite else json.dumps(value, allow_nan=False).encode()
    for split in range(1, len(raw) + 1):
        info, output = canonicalize(raw, split)
        assert output == expected
        assert info.byte_count == len(expected)
        assert info.digest == hashlib.sha256(expected).hexdigest()
        assert info.has_nonfinite is nonfinite


@pytest.mark.parametrize("raw", [
    b"", b"-", b"+1", b"01", b"-01", b"1.", b".1", b"1e", b"1e+",
    b"1e-", b"1 2", b" 1", b"1 ", b"1,", b"1e2.0", b"1e--1",
    b"nan", b"Inf", b"-NaN", b"Infinity0", b"1_0", "１２".encode(),
])
def test_invalid_complete_token_rejects(raw: bytes) -> None:
    with pytest.raises(NumberDecodeError):
        canonicalize(raw)


def test_integer_limit_is_deferred_until_token_kind_is_known() -> None:
    previous = sys.get_int_max_str_digits()
    try:
        sys.set_int_max_str_digits(640)
        raw = b"1" * 641
        with pytest.raises(NumberDecodeError):
            canonicalize(raw)
        info, output = canonicalize(raw + b".0", 37)
        assert info.has_nonfinite and output == b""
        sys.set_int_max_str_digits(0)
        info, output = canonicalize(raw, 37)
        assert output == raw and not info.has_nonfinite
    finally:
        sys.set_int_max_str_digits(previous)


def test_midpoint_sticky_and_exponent_cancellation() -> None:
    # Exactly halfway between 1.0 and its successor, then strictly above it.
    midpoint = b"1.00000000000000011102230246251565404236316680908203125"
    vectors = [midpoint, midpoint + b"0" * 1500 + b"1",
               b"0." + b"0" * 5000 + b"1e5001",
               b"1" + b"0" * 5000 + b"e-5000"]
    for raw in vectors:
        for split in [1, 7, 65536]:
            info, output = canonicalize(raw, split)
            expected = json.dumps(json.loads(raw), allow_nan=False).encode()
            assert output == expected
            assert not info.has_nonfinite


def test_nonempty_spool_is_not_overwritten() -> None:
    with tempfile.TemporaryFile() as spool:
        spool.write(b"user data")
        spool.flush()
        with pytest.raises(NumberIOError):
            NumberCanonicalizer(io.BytesIO(), spool)
        spool.seek(0)
        assert spool.read() == b"user data"


def test_in_memory_spool_is_not_a_disk_budget() -> None:
    with pytest.raises(NumberIOError):
        NumberCanonicalizer(io.BytesIO(), io.BytesIO())


def test_sink_cannot_be_the_spool() -> None:
    with tempfile.TemporaryFile() as spool:
        with pytest.raises(NumberIOError):
            NumberCanonicalizer(spool, spool)


@pytest.mark.parametrize("progress", [None, 0, -1, True, 99999])
def test_invalid_output_progress_rejects(progress: object) -> None:
    class BadSink:
        def write(self, chunk: bytes) -> object:
            return progress

    with tempfile.TemporaryFile() as spool:
        with pytest.raises(NumberIOError):
            parser = NumberCanonicalizer(BadSink(), spool)
            parser.feed(b"1.0")
            parser.finish()


class SpoolProxy:
    def __init__(self, wrapped: object) -> None:
        self.wrapped = wrapped

    def __getattr__(self, name: str) -> object:
        return getattr(self.wrapped, name)


@pytest.mark.parametrize("operation", ["fileno", "tell", "seekable", "readable", "writable", "write", "seek", "read"])
@pytest.mark.parametrize("fault_type", [OSError, AttributeError, TypeError])
def test_spool_fault_retains_cause_and_ownership(operation: str, fault_type: type[Exception]) -> None:
    fault = fault_type("private payload")

    class Broken(SpoolProxy):
        def __getattr__(self, name: str) -> object:
            if name == operation:
                def fail(*args: object) -> object:
                    raise fault
                return fail
            return super().__getattr__(name)

    with tempfile.TemporaryFile() as spool:
        sink = io.BytesIO()
        with pytest.raises(NumberIOError) as error:
            parser = NumberCanonicalizer(sink, Broken(spool))
            parser.feed(b"123")
            parser.finish()
        assert error.value.__cause__ is fault
        assert "private payload" not in str(error.value)
        assert not spool.closed and not sink.closed


def test_short_output_writes_complete_and_failure_does_not_close() -> None:
    class ShortSink(io.BytesIO):
        def write(self, chunk: bytes) -> int:
            return super().write(chunk[:1])

    sink = ShortSink()
    with tempfile.TemporaryFile() as spool:
        parser = NumberCanonicalizer(sink, spool)
        parser.feed(b"-1234")
        info = parser.finish()
        assert sink.getvalue() == b"-1234" and info.byte_count == 5
        assert spool.tell() == 4
        assert not sink.closed and not spool.closed


@pytest.mark.parametrize("fault_type", [OSError, AttributeError, TypeError])
def test_output_io_fault_has_original_cause(fault_type: type[Exception]) -> None:
    fault = fault_type("private payload")

    class Broken(io.BytesIO):
        def write(self, chunk: bytes) -> int:
            raise fault

    with tempfile.TemporaryFile() as spool:
        sink = Broken()
        parser = NumberCanonicalizer(sink, spool)
        parser.feed(b"1.0")
        with pytest.raises(NumberIOError) as error:
            parser.finish()
        assert error.value.__cause__ is fault
        assert "private payload" not in str(error.value)
        assert not sink.closed and not spool.closed


def test_missing_spool_or_output_protocol_is_io_error() -> None:
    with pytest.raises(NumberIOError):
        NumberCanonicalizer(io.BytesIO(), object())
    with tempfile.TemporaryFile() as spool:
        parser = NumberCanonicalizer(object(), spool)
        parser.feed(b"1.0")
        with pytest.raises(NumberIOError):
            parser.finish()


def test_spool_overread_violates_fixed_chunk_protocol() -> None:
    class Overread(SpoolProxy):
        def read(self, size: int) -> bytes:
            return self.wrapped.read(size + 1)

    previous = sys.get_int_max_str_digits()
    try:
        sys.set_int_max_str_digits(0)
        with tempfile.TemporaryFile() as spool:
            parser = NumberCanonicalizer(io.BytesIO(), Overread(spool))
            parser.feed(b"1" * 65536)
            parser.feed(b"1")
            with pytest.raises(NumberIOError):
                parser.finish()
    finally:
        sys.set_int_max_str_digits(previous)


def test_completed_and_failed_instances_cannot_be_reused() -> None:
    for initial in [b"1", b"01"]:
        with tempfile.TemporaryFile() as spool:
            parser = NumberCanonicalizer(io.BytesIO(), spool)
            if initial == b"01":
                with pytest.raises(NumberDecodeError):
                    parser.feed(initial)
            else:
                parser.feed(initial)
                parser.finish()
            with pytest.raises(NumberDecodeError):
                parser.feed(b"2")
            with pytest.raises(NumberDecodeError):
                parser.finish()


def test_seeded_long_float_differential() -> None:
    generator = random.Random(8102)
    for _ in range(160):
        length = generator.choice([17, 767, 1099, 1100, 1101, 1500, 4000])
        digits = str(generator.randrange(1, 10)) + "".join(str(generator.randrange(10)) for _ in range(length - 1))
        raw = (generator.choice(["", "-"]) + digits + "e" + str(generator.randrange(-length - 400, -length + 400))).encode()
        value = json.loads(raw)
        info, output = canonicalize(raw, 71)
        nonfinite = not math.isfinite(value)
        expected = b"" if nonfinite else json.dumps(value, allow_nan=False).encode()
        assert info.has_nonfinite is nonfinite
        assert output == expected


def test_exact_subnormal_and_overflow_rounding_boundaries() -> None:
    # Half the smallest subnormal is exactly 5**1075 * 10**-1075.
    coefficient = str(5 ** 1075).encode()
    overflow = str((2 ** 54 - 1) * 2 ** 970).encode()
    vectors = [coefficient + b"e-1075", (coefficient + b"0" * 1200 + b"1e-2276"),
               overflow + b".0", str(int(overflow) - 1).encode() + b".0"]
    for raw in vectors:
        for sign in [b"", b"-"]:
            value = json.loads(sign + raw)
            info, output = canonicalize(sign + raw, 37)
            nonfinite = not math.isfinite(value)
            assert info.has_nonfinite is nonfinite
            assert output == (b"" if nonfinite else json.dumps(value, allow_nan=False).encode())


@pytest.mark.parametrize("size", [8 * 1024 * 1024, 64 * 1024 * 1024])
@pytest.mark.parametrize("shape", ["integer", "integer_to_float", "cancellation", "exponent"])
def test_large_real_numeric_spellings_have_fixed_memory(size: int, shape: str) -> None:
    # Construct and hash fixtures before tracing; output and spool are real files.
    if shape in {"integer", "integer_to_float"}:
        prefix, suffix = b"1", b"" if shape == "integer" else b".0"
    elif shape == "cancellation":
        prefix, suffix = b"0.", b"1e" + str(size + 1).encode()
    else:
        prefix, suffix = b"1e", b"1"
    block = b"0" * 65536
    expected_digest = hashlib.sha256(prefix)
    previous_limit = sys.get_int_max_str_digits()
    with tempfile.TemporaryFile() as source, tempfile.TemporaryFile() as sink, tempfile.TemporaryFile() as spool:
        source.write(prefix)
        for _ in range(size // len(block)):
            source.write(block)
            expected_digest.update(block)
        source.write(suffix)
        source.seek(0)
        if shape == "integer":
            sys.set_int_max_str_digits(0)
        max_read = 0
        total_read = 0
        try:
            tracemalloc.start()
            before = tracemalloc.get_traced_memory()[0]
            parser = NumberCanonicalizer(sink, spool)
            while chunk := source.read(65536):
                max_read = max(max_read, len(chunk))
                total_read += len(chunk)
                parser.feed(chunk)
            info = parser.finish()
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
            sys.set_int_max_str_digits(previous_limit)
        assert peak - before <= 4 * 1024 * 1024
        assert total_read == len(prefix) + size + len(suffix)
        assert max_read == 65536
        if shape == "integer":
            expected_size = size + 1
            expected_hash = expected_digest.hexdigest()
        else:
            expected = {"integer_to_float": b"", "cancellation": b"1.0", "exponent": b"10.0"}[shape]
            expected_size = len(expected)
            expected_hash = hashlib.sha256(expected).hexdigest()
        assert info.has_nonfinite is (shape == "integer_to_float")
        assert info.byte_count == expected_size
        assert info.digest == expected_hash
        assert sink.tell() == expected_size
        sink.seek(0)
        output_hash = hashlib.sha256()
        while chunk := sink.read(65536):
            output_hash.update(chunk)
        assert output_hash.hexdigest() == expected_hash
        print(json.dumps({"shape": shape, "zero_digits": size, "peak_bytes": peak - before,
                          "max_read": max_read, "input_bytes": total_read,
                          "output_bytes": info.byte_count, "sha256": info.digest}))
