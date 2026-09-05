"""Isolated disk-backed JSON mapping canonicalization, not production authority."""

from __future__ import annotations

import codecs
import hashlib
import json
import os
import sqlite3
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Iterator

from tools.experiments.op08_semantic.document_store import DocumentStore
from tools.experiments.op08_semantic.numbers import NumberCanonicalizer, NumberDecodeError
from tools.experiments.op08_semantic.object_index import ObjectIndexError
from tools.experiments.op08_semantic.strings import (
    StringDecodeError, StringIOError, UTF8Cursor, read_json_string,
)


class DocumentDecodeError(ValueError):
    """Malformed syntax/encoding or a parse-time numeric restriction."""


class DocumentShapeError(ValueError):
    """The complete JSON root is not a mapping."""


class DocumentCanonicalError(ValueError):
    """A reachable value/key cannot be encoded by the authority's canonical form."""


class DocumentResourceError(OSError):
    """Scratch, stream or runtime resources failed; not a JSON-invalid verdict."""


@dataclass(frozen=True, slots=True)
class DocumentInfo:
    byte_count: int
    digest: str


def _write(stream: BinaryIO, payload: bytes) -> None:
    remaining = memoryview(payload)
    while remaining:
        try:
            written = stream.write(remaining)
        except (OSError, UnicodeError) as error:
            raise DocumentResourceError("output write failed") from error
        if isinstance(written, bool) or not isinstance(written, int) or not 0 < written <= len(remaining):
            raise DocumentResourceError("invalid output write progress")
        remaining = remaining[written:]


@contextmanager
def _integer_spool(directory: Path) -> Iterator[BinaryIO]:
    spool = tempfile.TemporaryFile(dir=directory)
    primary: BaseException | None = None
    try:
        yield spool
    except BaseException as error:
        primary = error
        raise
    finally:
        try:
            spool.close()
        except BaseException as cleanup:
            if primary is not None:
                primary.add_note("integer spool cleanup failed")
            else:
                raise DocumentResourceError("integer spool cleanup failed") from cleanup


def _value(cursor: UTF8Cursor, store: DocumentStore, blobs: BinaryIO,
           directory: Path, parent: int | None) -> int:
    cursor.skip_whitespace()
    character = cursor.peek_char()
    if character in {"{", "["}:
        cursor.read_char()
        return store.create("object" if character == "{" else "array", parent)
    offset = blobs.tell()
    if character == '"':
        info = read_json_string(cursor, blobs)
        return store.create("scalar", parent, offset, info.byte_count, info.has_unpaired_surrogate)
    if character and character in "-0123456789NI":
        with _integer_spool(directory) as integer_spool:
            number = NumberCanonicalizer(blobs, integer_spool)
            while span := cursor.read_number_span():
                try:
                    chunk = span.encode("ascii")
                except UnicodeEncodeError as error:
                    raise DocumentDecodeError("non-ASCII numeric token") from error
                number.feed(chunk)
            number_info = number.finish()
        return store.create("scalar", parent, offset, number_info.byte_count, number_info.has_nonfinite)
    literals = {"t": "true", "f": "false", "n": "null"}
    if character in literals:
        literal = literals[character]
        for expected in literal:
            if cursor.read_char() != expected:
                raise DocumentDecodeError("invalid JSON literal")
        payload = literal.encode("ascii")
        _write(blobs, payload)
        return store.create("scalar", parent, offset, len(payload))
    raise DocumentDecodeError("missing JSON value")


def _parse(cursor: UTF8Cursor, store: DocumentStore, blobs: BinaryIO, directory: Path) -> int:
    root = _value(cursor, store, blobs, directory, None)
    current: int | None = root
    while current is not None:
        node = store.node(current)
        if node.kind == "scalar":
            current = store.attach(current)
            continue
        cursor.skip_whitespace()
        character = cursor.peek_char()
        closing = "}" if node.kind == "object" else "]"
        if node.state == "first" and character == closing:
            cursor.read_char()
            current = store.attach(current)
        elif node.state == "comma":
            if character == closing:
                cursor.read_char()
                current = store.attach(current)
            elif character == ",":
                cursor.read_char()
                store.state(current, "key" if node.kind == "object" else "value")
            else:
                raise DocumentDecodeError("missing container separator")
        elif node.kind == "object" and node.state in {"first", "key"}:
            if character != '"':
                raise DocumentDecodeError("missing object key")
            offset = blobs.tell()
            info = read_json_string(cursor, blobs)
            store.key(current, offset, info.byte_count)
        elif node.state == "colon":
            if cursor.read_char() != ":":
                raise DocumentDecodeError("missing object colon")
            store.state(current, "value")
        elif node.state in {"first", "value"}:
            current = _value(cursor, store, blobs, directory, current)
        else:
            raise DocumentResourceError("invalid parser state")
    cursor.skip_whitespace()
    if cursor.peek_char():
        raise DocumentDecodeError("trailing JSON data")
    if store.node(root).kind != "object":
        raise DocumentShapeError("document root must be an object")
    return root


class _Output:
    def __init__(self, sink: BinaryIO, blobs: BinaryIO) -> None:
        self.sink = sink
        self.fd = blobs.fileno()
        self.count = 0
        self.digest = hashlib.sha256()

    def write(self, payload: bytes) -> None:
        _write(self.sink, payload)
        self.count += len(payload)
        self.digest.update(payload)

    def _chunk(self, offset: int, length: int) -> bytes:
        chunk = os.pread(self.fd, min(65536, length), offset)
        if not isinstance(chunk, bytes) or not 0 < len(chunk) <= min(65536, length):
            raise DocumentResourceError("invalid canonical blob read")
        return chunk

    def matches(self, offset: int, length: int, expected: bytes) -> bool:
        if length != len(expected):
            return False
        position = 0
        while position < length:
            chunk = self._chunk(offset + position, length - position)
            if chunk != expected[position:position + len(chunk)]:
                return False
            position += len(chunk)
        return True

    def blob(self, offset: int, length: int) -> None:
        decoder = codecs.getincrementaldecoder("utf8")("strict")
        remaining = length
        try:
            while remaining:
                chunk = self._chunk(offset, remaining)
                decoder.decode(chunk)
                self.write(chunk)
                offset += len(chunk)
                remaining -= len(chunk)
            decoder.decode(b"", final=True)
        except UnicodeDecodeError as error:
            raise DocumentCanonicalError("retained content cannot be UTF-8 encoded") from error


def _emit(store: DocumentStore, blobs: BinaryIO, sink: BinaryIO,
          root: int, omitted: str | None) -> DocumentInfo:
    blobs.flush()
    output = _Output(sink, blobs)
    omitted_bytes = None if omitted is None else json.dumps(
        omitted, ensure_ascii=False, separators=(",", ":")
    ).encode("utf8", "surrogatepass")
    current: int | None = root
    while current is not None:
        node = store.node(current)
        if node.kind == "scalar":
            if node.invalid:
                raise DocumentCanonicalError("retained value has no canonical encoding")
            output.blob(node.offset, node.length)
            current = node.parent
            continue
        if not node.emit_started:
            output.write(b"{" if node.kind == "object" else b"[")
            store.start_output(current)
        if node.kind == "object":
            assert node.object_id is not None
            member = store.index.member_after(node.object_id, node.emit_position)
            if member is None:
                output.write(b"}")
                current = node.parent
                continue
            skip = (current == root and omitted_bytes is not None
                    and output.matches(member.key_offset, member.key_length, omitted_bytes))
            store.advance_output(current, member.position, not skip)
            if skip:
                continue
            if node.emit_count:
                output.write(b",")
            output.blob(member.key_offset, member.key_length)
            output.write(b":")
            current = member.value_id
        else:
            edge = store.array_after(current, node.emit_position)
            if edge is None:
                output.write(b"]")
                current = node.parent
                continue
            position, child = edge
            store.advance_output(current, position, True)
            if node.emit_count:
                output.write(b",")
            current = child
    return DocumentInfo(output.count, output.digest.hexdigest())


def canonicalize_document(
    source: BinaryIO,
    sink: BinaryIO,
    *,
    scratch_parent: Path,
    omit_top_level_key: str | None = None,
) -> DocumentInfo:
    """Canonicalize one mapping using exclusively-owned scratch resources.

    Caller streams stay open. No successful summary is returned after parsing,
    emission or cleanup failure, even if the sink contains partial output.
    Source identity, total disk quota and process-RSS proof remain later gates.
    """
    directory: tempfile.TemporaryDirectory[str] | None = None
    connection: sqlite3.Connection | None = None
    blobs: BinaryIO | None = None
    primary: BaseException | None = None
    try:
        directory = tempfile.TemporaryDirectory(prefix="op08-document-", dir=scratch_parent)
        folder = Path(directory.name)
        connection = sqlite3.connect(folder / "document.sqlite3", isolation_level=None)
        blobs = (folder / "blobs.bin").open("w+b")
        store = DocumentStore(connection, blobs)
        root = _parse(UTF8Cursor(source), store, blobs, folder)
        return _emit(store, blobs, sink, root, omit_top_level_key)
    except (StringDecodeError, NumberDecodeError, UnicodeDecodeError) as error:
        primary = DocumentDecodeError("document syntax or encoding is invalid")
        raise primary from error
    except (DocumentDecodeError, DocumentShapeError, DocumentCanonicalError, DocumentResourceError) as error:
        primary = error
        raise
    except (StringIOError, ObjectIndexError, sqlite3.Error, OSError, AttributeError,
            TypeError, ValueError, MemoryError, RecursionError) as error:
        primary = DocumentResourceError("document resources unavailable")
        raise primary from error
    except BaseException as error:
        primary = error
        raise
    finally:
        cleanup_error: BaseException | None = None
        for resource in (blobs, connection):
            if resource is not None:
                try:
                    resource.close()
                except BaseException as error:
                    cleanup_error = cleanup_error or error
        if directory is not None:
            try:
                directory.cleanup()
            except BaseException as error:
                cleanup_error = cleanup_error or error
        if cleanup_error is not None:
            if primary is not None:
                primary.add_note("document scratch cleanup failed")
            else:
                raise DocumentResourceError("document scratch cleanup failed") from cleanup_error
