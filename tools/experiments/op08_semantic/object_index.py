"""Isolated disk-backed first-position/last-value object member index."""

from __future__ import annotations

import hashlib
import os
import sqlite3
import stat
from contextlib import closing, contextmanager
from dataclasses import dataclass
from typing import BinaryIO, Iterator


class ObjectIndexError(OSError):
    """An index storage/protocol/state failure; not a document verdict."""


@dataclass(frozen=True, slots=True)
class Member:
    position: int
    key_offset: int
    key_length: int
    value_id: int


_CHUNK_SIZE = 65536
_MAX_INTEGER = 2**63 - 1


def _integer(value: int, *, minimum: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= _MAX_INTEGER:
        raise ValueError("invalid index integer")


def _read_exact(fd: int, offset: int, length: int) -> bytes:
    """Read one bounded block without disturbing the append writer's offset."""
    output = bytearray()
    while len(output) < length:
        requested = length - len(output)
        try:
            chunk = os.pread(fd, requested, offset + len(output))
        except (OSError, TypeError, ValueError, AttributeError) as error:
            raise ObjectIndexError("key read failed") from error
        if not isinstance(chunk, bytes) or not 0 < len(chunk) <= requested:
            raise ObjectIndexError("invalid key read progress")
        output.extend(chunk)
    return bytes(output)


def _digest_range(fd: int, offset: int, length: int) -> bytes:
    digest = hashlib.sha256()
    for consumed in range(0, length, _CHUNK_SIZE):
        digest.update(_read_exact(fd, offset + consumed, min(_CHUNK_SIZE, length - consumed)))
    return digest.digest()


def _equal_ranges(fd: int, first: int, second: int, length: int) -> bool:
    for consumed in range(0, length, _CHUNK_SIZE):
        size = min(_CHUNK_SIZE, length - consumed)
        if _read_exact(fd, first + consumed, size) != _read_exact(fd, second + consumed, size):
            return False
    return True


class DiskObjectIndex:
    """Caller-owned SQLite/key files with lazy rows and bounded key buffers.

    Keys are canonical quoted bytes supplied by the string primitive, exclusively
    appended by the caller. This class neither decodes JSON nor proves source
    identity, reachability, native RSS bounds, or total disk quotas.
    """

    def __init__(self, connection: sqlite3.Connection, keys: BinaryIO) -> None:
        self._connection = connection
        self._keys = keys
        self._poisoned = False
        self._readers = 0
        try:
            if (not isinstance(connection, sqlite3.Connection)
                    or connection.row_factory is not None or connection.text_factory is not str):
                raise ObjectIndexError("unsupported index connection")
            self._ready(write=True)
            self._fd = keys.fileno()
            if (not stat.S_ISREG(os.fstat(self._fd).st_mode) or not keys.seekable()
                    or not keys.readable() or not keys.writable()):
                raise ObjectIndexError("keys must be a readable writable regular file")
            with closing(connection.execute("PRAGMA database_list")) as cursor:
                main = cursor.fetchone()
                if main is None or main[1] != "main" or not main[2] or cursor.fetchone() is not None:
                    raise ObjectIndexError("index requires only a disk main database")
                if not stat.S_ISREG(os.stat(main[2]).st_mode):
                    raise ObjectIndexError("index database must be a regular file")
            if self._one("SELECT 1 FROM sqlite_schema LIMIT 1") is not None:
                raise ObjectIndexError("index database must have a fresh schema")
            for command, query, expected in [
                ("PRAGMA cache_size=-1024", "PRAGMA cache_size", -1024),
                ("PRAGMA mmap_size=0", "PRAGMA mmap_size", 0),
                ("PRAGMA temp_store=FILE", "PRAGMA temp_store", 1),
            ]:
                connection.execute(command).close()
                if self._one(query) != (expected,):
                    raise ObjectIndexError("index cache configuration unavailable")
            with self._transaction():
                connection.execute(
                    "CREATE TABLE objects(id INTEGER PRIMARY KEY, next_position INTEGER NOT NULL)"
                ).close()
                connection.execute(
                    "CREATE TABLE object_members("
                    "object_id INTEGER NOT NULL, position INTEGER NOT NULL,"
                    "key_offset INTEGER NOT NULL, key_length INTEGER NOT NULL,"
                    "digest BLOB NOT NULL, value_id INTEGER NOT NULL,"
                    "PRIMARY KEY(object_id, position)) WITHOUT ROWID"
                ).close()
                connection.execute(
                    "CREATE INDEX member_bucket ON object_members(object_id,digest,key_length,position)"
                ).close()
        except ObjectIndexError:
            raise
        except (sqlite3.Error, OSError, AttributeError, TypeError, ValueError) as error:
            raise ObjectIndexError("index initialization failed") from error

    def _one(self, sql: str, parameters: tuple[object, ...] = ()) -> tuple | None:
        with closing(self._connection.execute(sql, parameters)) as cursor:
            return cursor.fetchone()

    def _ready(self, *, write: bool) -> None:
        if self._poisoned:
            raise ObjectIndexError("index is unusable after cleanup failure")
        try:
            if self._connection.in_transaction or (write and self._readers):
                raise ObjectIndexError("index transaction or iterator is already active")
        except sqlite3.Error as error:
            raise ObjectIndexError("index connection unavailable") from error

    @contextmanager
    def _transaction(self) -> Iterator[None]:
        self._ready(write=True)
        started = False
        try:
            self._connection.execute("SAVEPOINT op08_index").close()
            started = True
            yield
            self._connection.execute("RELEASE op08_index").close()
        except BaseException as primary:
            if started:
                try:
                    self._connection.execute("ROLLBACK TO op08_index").close()
                    self._connection.execute("RELEASE op08_index").close()
                except BaseException:
                    self._poisoned = True
                    primary.add_note("index rollback cleanup failed; discard this index")
            if not isinstance(primary, Exception) or isinstance(primary, ObjectIndexError):
                raise
            raise ObjectIndexError("index transaction failed") from primary

    def new_object(self) -> int:
        with self._transaction():
            with closing(self._connection.execute("INSERT INTO objects(next_position) VALUES(0)")) as cursor:
                object_id = cursor.lastrowid
                if object_id is None:
                    raise ObjectIndexError("missing allocated object id")
                return object_id

    def put(self, object_id: int, key_offset: int, key_length: int, value_id: int) -> Member:
        """Upsert by exact key bytes; a replacement never changes first position."""
        _integer(object_id, minimum=1)
        _integer(key_offset, minimum=0)
        _integer(key_length, minimum=1)
        _integer(value_id, minimum=1)
        self._ready(write=True)
        try:
            self._keys.flush()
            if key_offset + key_length > os.fstat(self._fd).st_size:
                raise ObjectIndexError("key range exceeds stored bytes")
            digest = _digest_range(self._fd, key_offset, key_length)
        except ObjectIndexError:
            raise
        except (OSError, AttributeError, TypeError, ValueError) as error:
            raise ObjectIndexError("key storage unavailable") from error
        with self._transaction():
            parent = self._one("SELECT next_position FROM objects WHERE id=?", (object_id,))
            if parent is None:
                raise ObjectIndexError("object is missing")
            with closing(self._connection.execute(
                "SELECT position,key_offset,key_length,value_id FROM object_members "
                "WHERE object_id=? AND digest=? AND key_length=? ORDER BY position",
                (object_id, digest, key_length),
            )) as candidates:
                for row in candidates:
                    if _equal_ranges(self._fd, key_offset, row[1], key_length):
                        self._connection.execute(
                            "UPDATE object_members SET value_id=? WHERE object_id=? AND position=?",
                            (value_id, object_id, row[0]),
                        ).close()
                        return Member(row[0], row[1], row[2], value_id)
            position = parent[0]
            self._connection.execute(
                "INSERT INTO object_members VALUES(?,?,?,?,?,?)",
                (object_id, position, key_offset, key_length, digest, value_id),
            ).close()
            self._connection.execute(
                "UPDATE objects SET next_position=? WHERE id=?", (position + 1, object_id)
            ).close()
            return Member(position, key_offset, key_length, value_id)

    def member_after(self, object_id: int, position: int) -> Member | None:
        """Return one keyset row, retaining no cursor across subtree traversal."""
        _integer(object_id, minimum=1)
        _integer(position, minimum=-1)
        self._ready(write=False)
        try:
            if self._one("SELECT 1 FROM objects WHERE id=?", (object_id,)) is None:
                raise ObjectIndexError("object is missing")
            row = self._one(
                "SELECT position,key_offset,key_length,value_id FROM object_members "
                "WHERE object_id=? AND position>? ORDER BY position LIMIT 1",
                (object_id, position),
            )
            return None if row is None else Member(*row)
        except ObjectIndexError:
            raise
        except (sqlite3.Error, OSError, AttributeError, TypeError, ValueError) as error:
            raise ObjectIndexError("member keyset read failed") from error

    def members(self, object_id: int) -> Iterator[Member]:
        """Yield ordered rows lazily; close the iterator to release write exclusion."""
        _integer(object_id, minimum=1)
        self._ready(write=False)
        cursor: sqlite3.Cursor | None = None
        primary: BaseException | None = None
        registered = False
        try:
            if self._one("SELECT 1 FROM objects WHERE id=?", (object_id,)) is None:
                raise ObjectIndexError("object is missing")
            cursor = self._connection.execute(
                "SELECT position,key_offset,key_length,value_id FROM object_members "
                "WHERE object_id=? ORDER BY position", (object_id,)
            )
            self._readers += 1
            registered = True
            for row in cursor:
                yield Member(*row)
        except BaseException as error:
            primary = error
            if not isinstance(error, Exception) or isinstance(error, ObjectIndexError):
                raise
            raise ObjectIndexError("member iteration failed") from error
        finally:
            if registered:
                self._readers -= 1
            if cursor is not None:
                try:
                    cursor.close()
                except BaseException as cleanup:
                    self._poisoned = True
                    if primary is not None:
                        primary.add_note("member cursor cleanup failed; discard this index")
                    else:
                        raise ObjectIndexError("member cursor cleanup failed") from cleanup
