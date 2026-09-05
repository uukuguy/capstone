"""Isolated bounded JSON string primitive; not a production semantic verifier."""

from __future__ import annotations

import codecs
import hashlib
import re
from dataclasses import dataclass
from typing import BinaryIO


class StringDecodeError(ValueError):
    """The input does not contain a valid UTF-8 JSON string token."""


class StringIOError(OSError):
    """A caller-owned stream failed or violated its I/O protocol."""


@dataclass(frozen=True, slots=True)
class StringInfo:
    """Summary of canonical quoted bytes written, without retaining the body."""

    byte_count: int
    digest: str
    has_unpaired_surrogate: bool


_SPECIAL_CHARACTER = re.compile(r'["\\\x00-\x1f]')
_NUMBER_DELIMITER = re.compile(r'[,\]} \t\r\n]')
_JSON_WHITESPACE = re.compile(r'[ \t\r\n]+')
_SIMPLE_ESCAPES = {
    '"': '"', "\\": "\\", "/": "/", "b": "\b", "f": "\f",
    "n": "\n", "r": "\r", "t": "\t",
}
_CANONICAL_ESCAPES = {
    "\b": b"\\b", "\f": b"\\f", "\n": b"\\n", "\r": b"\\r",
    "\t": b"\\t", '"': b'\\"', "\\": b"\\\\",
}


class UTF8Cursor:
    """Strict incremental UTF-8 cursor with at most 64 KiB source reads.

    Read-ahead stays in bounded buffers. Neither this cursor nor the string
    primitive closes the source. Consumers must continue through this cursor,
    not through the underlying stream, to preserve unread characters.
    """

    def __init__(self, source: BinaryIO, *, chunk_size: int = 65536) -> None:
        if isinstance(chunk_size, bool) or not isinstance(chunk_size, int):
            raise ValueError("invalid chunk_size")
        if not 0 < chunk_size <= 65536:
            raise ValueError("invalid chunk_size")
        self._source = source
        self._chunk_size = chunk_size
        self._decoder = codecs.getincrementaldecoder("utf8")("strict")
        self._text = ""
        self._offset = 0
        self._eof = False

    def _fill(self) -> None:
        while self._offset == len(self._text) and not self._eof:
            try:
                raw = self._source.read(self._chunk_size)
            except (OSError, UnicodeError) as error:
                raise StringIOError("source read failed") from error
            if not isinstance(raw, bytes):
                raise StringIOError("source returned non-bytes")
            try:
                self._eof = not raw
                self._text = self._decoder.decode(raw, final=self._eof)
                self._offset = 0
            except UnicodeDecodeError as error:
                raise StringDecodeError("invalid UTF-8") from error

    def read_char(self) -> str:
        self._fill()
        character = self._text[self._offset : self._offset + 1]
        self._offset += len(character)
        return character

    def peek_char(self) -> str:
        self._fill()
        return self._text[self._offset : self._offset + 1]

    def read_plain_span(self) -> str:
        """Return a bounded ordinary span, leaving its terminator unread."""
        self._fill()
        match = _SPECIAL_CHARACTER.search(self._text, self._offset)
        end = match.start() if match is not None else len(self._text)
        span = self._text[self._offset : end]
        self._offset = end
        return span

    def read_number_span(self) -> str:
        """Return a bounded numeric-token fragment, preserving its delimiter."""
        self._fill()
        match = _NUMBER_DELIMITER.search(self._text, self._offset)
        end = match.start() if match is not None else len(self._text)
        span = self._text[self._offset:end]
        self._offset = end
        return span

    def skip_whitespace(self) -> None:
        """Consume only JSON's four whitespace characters in bounded spans."""
        while True:
            self._fill()
            match = _JSON_WHITESPACE.match(self._text, self._offset)
            if match is None:
                return
            self._offset = match.end()


def _write_all(sink: BinaryIO, value: bytes) -> None:
    remaining = memoryview(value)
    while remaining:
        try:
            written = sink.write(remaining)
        except OSError as error:
            raise StringIOError("sink write failed") from error
        if (isinstance(written, bool) or not isinstance(written, int)
                or written <= 0 or written > len(remaining)):
            raise StringIOError("invalid sink progress")
        remaining = remaining[written:]


def _canonical_character(character: str) -> bytes:
    escaped = _CANONICAL_ESCAPES.get(character)
    if escaped is not None:
        return escaped
    if ord(character) < 32:
        return f"\\u{ord(character):04x}".encode("ascii")
    return character.encode("utf8", "surrogatepass")


def _read_escape(cursor: UTF8Cursor) -> str:
    escape = cursor.read_char()
    if escape in _SIMPLE_ESCAPES:
        return _SIMPLE_ESCAPES[escape]
    if escape != "u":
        raise StringDecodeError("invalid escape")
    digits = "".join(cursor.read_char() for _ in range(4))
    if len(digits) != 4 or any(digit not in "0123456789abcdefABCDEF" for digit in digits):
        raise StringDecodeError("invalid unicode escape")
    return chr(int(digits, 16))


def read_json_string(cursor: UTF8Cursor, sink: BinaryIO) -> StringInfo:
    """Emit Python-equivalent canonical string bytes and preserve the next token.

    A pending high surrogate is paired only with the next decoded low surrogate.
    Other surrogates remain flagged and use surrogatepass: future duplicate-key
    elimination may discard them. Partial output after failure is caller-owned,
    never a successful verification result.
    """
    if cursor.read_char() != '"':
        raise StringDecodeError("missing opening quote")
    digest = hashlib.sha256()
    byte_count = 0
    has_unpaired = False
    pending_high: str | None = None

    def emit(value: bytes) -> None:
        nonlocal byte_count
        _write_all(sink, value)
        digest.update(value)
        byte_count += len(value)

    def flush_pending() -> None:
        nonlocal pending_high, has_unpaired
        if pending_high is not None:
            emit(_canonical_character(pending_high))
            pending_high = None
            has_unpaired = True

    emit(b'"')
    while True:
        span = cursor.read_plain_span()
        if span:
            flush_pending()
            emit(span.encode("utf8"))
            continue
        character = cursor.read_char()
        if not character:
            raise StringDecodeError("unterminated string")
        if character == '"':
            flush_pending()
            emit(b'"')
            return StringInfo(byte_count, digest.hexdigest(), has_unpaired)
        if ord(character) < 32:
            raise StringDecodeError("unescaped control")
        if character == "\\":
            character = _read_escape(cursor)
        codepoint = ord(character)
        if pending_high is not None and 0xDC00 <= codepoint <= 0xDFFF:
            scalar = 0x10000 + (ord(pending_high) - 0xD800) * 0x400 + codepoint - 0xDC00
            emit(chr(scalar).encode("utf8"))
            pending_high = None
            continue
        flush_pending()
        if 0xD800 <= codepoint <= 0xDBFF:
            pending_high = character
        else:
            has_unpaired |= 0xDC00 <= codepoint <= 0xDFFF
            emit(_canonical_character(character))
