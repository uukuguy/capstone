"""Isolated bounded numeric-token canonicalizer, not a document verifier."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import stat
import sys
from dataclasses import dataclass
from typing import BinaryIO


class NumberDecodeError(ValueError):
    """Invalid complete numeric token or the interpreter's integer digit limit."""


class NumberIOError(OSError):
    """Caller-owned spool or output stream failed its protocol."""


@dataclass(frozen=True, slots=True)
class NumberInfo:
    """Canonical bytes emitted; nonfinite values emit none and remain deferred."""

    byte_count: int
    digest: str
    has_nonfinite: bool


_DIGITS = re.compile(rb"[0-9]+")
_PREFIX_DIGITS = 1100
_CHUNK_BYTES = 65536
_CONSTANTS = (b"NaN", b"Infinity", b"-Infinity")


def _write_all(stream: BinaryIO, payload: bytes) -> None:
    pending = memoryview(payload)
    while pending:
        try:
            written = stream.write(pending)
        except (OSError, ValueError, AttributeError, TypeError) as error:
            raise NumberIOError("stream write failed") from error
        if (isinstance(written, bool) or not isinstance(written, int)
                or not 0 < written <= len(pending)):
            raise NumberIOError("invalid stream write progress")
        pending = pending[written:]


class NumberCanonicalizer:
    """Consume one complete token in bounded chunks, with a caller-owned spool.

    The spool must be an exclusive empty regular read/write file at offset zero,
    distinct from the sink. Its integer prefix remains on disk after completion.
    Failure leaves partial output/spool contents for caller cleanup; this class
    never closes or truncates either stream. Quota/identity policy belongs to the
    future document parser and is not established by this primitive.
    """

    def __init__(self, sink: BinaryIO, integer_spool: BinaryIO) -> None:
        info = sys.float_info
        if (sys.implementation.name != "cpython" or info.radix != 2
                or info.mant_dig != 53 or info.max_exp != 1024
                or info.min_exp != -1021 or info.rounds != 1):
            raise RuntimeError("numeric prototype requires calibrated CPython binary64")
        if sink is integer_spool:
            raise NumberIOError("sink and spool must be distinct")
        try:
            metadata = os.fstat(integer_spool.fileno())
            valid = (stat.S_ISREG(metadata.st_mode) and metadata.st_size == 0
                     and integer_spool.tell() == 0 and integer_spool.seekable()
                     and integer_spool.readable() and integer_spool.writable())
        except (OSError, ValueError, AttributeError, TypeError) as error:
            raise NumberIOError("invalid integer spool") from error
        if not valid:
            raise NumberIOError("integer spool must be an empty seekable regular file")
        self._sink = sink
        self._spool = integer_spool
        self._state = "start"
        self._negative = False
        self._exponent_negative = False
        self._exponent = 0
        self._float_form = False
        self._integer_digits = 0
        self._fraction_digits = 0
        self._total_digits = 0
        self._significant_digits = 0
        self._prefix = b""
        self._sticky = False
        self._constant = b""
        self._byte_count = 0
        self._digest = hashlib.sha256()

    def _mantissa(self, digits: bytes, *, fractional: bool) -> None:
        self._total_digits += len(digits)
        if fractional:
            self._fraction_digits += len(digits)
        else:
            self._integer_digits += len(digits)
            _write_all(self._spool, digits)
        if not self._significant_digits:
            digits = digits.lstrip(b"0")
        self._significant_digits += len(digits)
        available = _PREFIX_DIGITS - len(self._prefix)
        self._prefix += digits[:available]
        if not self._sticky and digits[available:].strip(b"0"):
            self._sticky = True

    def _exponent_digits(self, digits: bytes) -> None:
        # Mantissa length is now final. This relative cap preserves cancellation.
        cap = self._total_digits + 2000
        if self._exponent == cap:
            return
        digits = digits.lstrip(b"0") if self._exponent == 0 else digits
        if not digits:
            return
        if len(digits) > len(str(cap)):
            self._exponent = cap
        else:
            self._exponent = min(cap, self._exponent * 10 ** len(digits) + int(digits))

    def feed(self, chunk: bytes) -> None:
        """Supply at most 64 KiB of a token, excluding whitespace/delimiters."""
        if self._state in {"finished", "failed"}:
            raise NumberDecodeError("numeric token is no longer writable")
        try:
            if not isinstance(chunk, bytes) or len(chunk) > _CHUNK_BYTES:
                raise NumberIOError("invalid numeric input chunk")
            self._feed(chunk)
        except (NumberDecodeError, NumberIOError):
            self._state = "failed"
            raise

    def _feed(self, chunk: bytes) -> None:
        offset = 0
        while offset < len(chunk):
            character = chunk[offset]
            if self._state == "constant":
                self._constant += chunk[offset:offset + 10]
                if (len(chunk) - offset > 9
                        or not any(value.startswith(self._constant) for value in _CONSTANTS)):
                    raise NumberDecodeError("invalid numeric constant")
                return
            if self._state in {"start", "sign"}:
                if character == 45 and self._state == "start":
                    self._negative = True
                    self._state = "sign"
                    offset += 1
                    continue
                if character == 73 or (character == 78 and self._state == "start"):
                    self._constant = b"-" if self._negative else b""
                    self._state = "constant"
                    continue
                if character == 48:
                    self._mantissa(b"0", fractional=False)
                    self._state = "zero"
                    offset += 1
                    continue
                if 49 <= character <= 57:
                    self._state = "integer"
                    continue
                raise NumberDecodeError("invalid numeric start")
            if self._state in {"integer", "dot", "fraction", "exponent_sign", "exponent_digits"}:
                match = _DIGITS.match(chunk, offset)
                if match is not None:
                    digits = match.group()
                    if self._state.startswith("exponent"):
                        self._exponent_digits(digits)
                        self._state = "exponent_digits"
                    else:
                        fractional = self._state != "integer"
                        self._mantissa(digits, fractional=fractional)
                        self._state = "fraction" if fractional else "integer"
                    offset = match.end()
                    continue
                if self._state in {"dot", "exponent_sign"}:
                    raise NumberDecodeError("missing numeric digits")
            if self._state in {"integer", "zero"} and character == 46:
                self._float_form = True
                self._state = "dot"
            elif self._state in {"integer", "zero", "fraction"} and character in {69, 101}:
                self._float_form = True
                self._state = "exponent_mark"
            elif self._state == "exponent_mark":
                self._state = "exponent_sign"
                if character in {43, 45}:
                    self._exponent_negative = character == 45
                else:
                    continue
            else:
                raise NumberDecodeError("invalid numeric token")
            offset += 1

    def _emit(self, payload: bytes) -> None:
        _write_all(self._sink, payload)
        self._digest.update(payload)
        self._byte_count += len(payload)

    def _float_value(self) -> float:
        sign = "-" if self._negative else ""
        if not self._significant_digits:
            return float(sign + "0.0")
        exponent = -self._exponent if self._exponent_negative else self._exponent
        exponent += self._significant_digits - self._fraction_digits - len(self._prefix)
        representative = self._prefix
        if self._sticky:
            representative += b"1"
            exponent -= 1
        return float(sign + representative.decode("ascii") + "e" + str(exponent))

    def finish(self) -> NumberInfo:
        """Validate the complete token and emit finite canonical output once."""
        state = self._state
        self._state = "failed"
        if state == "constant":
            if self._constant not in _CONSTANTS:
                raise NumberDecodeError("incomplete numeric constant")
            nonfinite = True
        elif state not in {"integer", "zero", "fraction", "exponent_digits"}:
            raise NumberDecodeError("incomplete numeric token")
        elif self._float_form:
            value = self._float_value()
            nonfinite = not math.isfinite(value)
            if not nonfinite:
                self._emit(json.dumps(value, allow_nan=False).encode("ascii"))
        else:
            limit = sys.get_int_max_str_digits()
            if limit and self._integer_digits > limit:
                raise NumberDecodeError("integer exceeds interpreter digit limit")
            nonfinite = False
            if self._negative and state != "zero":
                self._emit(b"-")
            try:
                self._spool.seek(0)
                remaining = self._integer_digits
                while remaining:
                    requested = min(_CHUNK_BYTES, remaining)
                    chunk = self._spool.read(requested)
                    if not isinstance(chunk, bytes) or not 0 < len(chunk) <= requested:
                        raise NumberIOError("invalid spool read progress")
                    self._emit(chunk)
                    remaining -= len(chunk)
            except (OSError, ValueError, AttributeError, TypeError) as error:
                if isinstance(error, NumberIOError):
                    raise
                raise NumberIOError("integer spool read failed") from error
        self._state = "finished"
        return NumberInfo(self._byte_count, self._digest.hexdigest(), nonfinite)
