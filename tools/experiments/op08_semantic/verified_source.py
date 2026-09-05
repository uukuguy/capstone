"""Isolated binding of canonicalization input to an already admitted descriptor."""

from __future__ import annotations

import hashlib
import os
import stat


def _identity(details: os.stat_result) -> tuple[int, int, int, int, int]:
    return (details.st_dev, details.st_ino, details.st_size,
            details.st_mtime_ns, details.st_ctime_ns)


class VerifiedSource:
    """Read one admitted ordinary file without reopening it or moving its cursor.

    EOF is delivered only after raw digest and descriptor identity verification.
    The caller owns the descriptor and must keep it open and stable. This is not
    path admission or protection against a hostile concurrent writer.
    """

    def __init__(self, fd: int, expected_digest: str, expected_size: int) -> None:
        self._fd = fd
        self._original = os.fstat(fd)
        if not stat.S_ISREG(self._original.st_mode) or self._original.st_size != expected_size:
            raise OSError("source is not the expected regular file")
        self._expected_digest = expected_digest
        self._digest = hashlib.sha256()
        self._offset = 0
        self._finished = False
        self._failed = False

    def read(self, size: int) -> bytes:
        if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
            raise ValueError("read size must be positive")
        if self._failed:
            raise OSError("source verification previously failed")
        if self._finished:
            return b""
        try:
            chunk = os.pread(self._fd, min(size, 65536), self._offset)
            if chunk:
                self._offset += len(chunk)
                if self._offset > self._original.st_size:
                    raise OSError("source length changed")
                self._digest.update(chunk)
                return chunk
            if (self._offset != self._original.st_size
                    or self._digest.hexdigest() != self._expected_digest
                    or _identity(os.fstat(self._fd)) != _identity(self._original)):
                raise OSError("source content or identity changed")
            self._finished = True
            return b""
        except OSError:
            self._failed = True
            raise
