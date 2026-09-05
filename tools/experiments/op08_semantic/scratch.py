"""Component limits for disposable prototype scratch, not a filesystem quota."""

from __future__ import annotations

import io
import sqlite3
from collections.abc import Buffer
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ScratchLimits:
    blob_bytes: int = 256 * 1024 * 1024
    integer_bytes: int = 256 * 1024 * 1024
    database_bytes: int = 256 * 1024 * 1024

    def __post_init__(self) -> None:
        for value in (self.blob_bytes, self.integer_bytes, self.database_bytes):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError("scratch limits must be positive integers")


class LimitedFile(io.FileIO):
    """Unbuffered owned scratch writes checked before extending the file."""

    def __init__(self, file: Path | int, limit: int, *, closefd: bool = True) -> None:
        self._limit = limit
        super().__init__(file, "r+" if isinstance(file, int) else "x+", closefd=closefd)

    def write(self, b: Buffer, /) -> int | None:
        if self.tell() + memoryview(b).nbytes > self._limit:
            raise OSError("scratch file limit exceeded")
        return super().write(b)


def limit_database(connection: sqlite3.Connection, byte_limit: int) -> None:
    with closing(connection.execute("PRAGMA page_size")) as cursor:
        page_size = cursor.fetchone()[0]
    pages = byte_limit // page_size
    if pages < 1:
        raise OSError("database limit cannot hold one page")
    with closing(connection.execute(f"PRAGMA max_page_count={pages}")) as cursor:
        if cursor.fetchone()[0] != pages:
            raise OSError("database limit unavailable")
