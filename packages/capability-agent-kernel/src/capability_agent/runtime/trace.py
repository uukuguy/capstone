"""Small durable JSONL trace writer with recursive secret redaction."""

from __future__ import annotations

import json
import os
import re
import stat
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO


class JsonlTraceWriter:
    def __init__(self, path: Path, *, secret_values: set[str] | None = None) -> None:
        self._path = Path(path)
        _reject_trace_symlink_ancestors(self._path.parent)
        self._path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        _reject_trace_symlink_ancestors(self._path.parent)
        try:
            if self._path.is_symlink():
                raise ValueError("trace file must not be a symlink")
        except OSError as exc:
            raise ValueError("trace file cannot be inspected") from exc
        self._secret_values = frozenset(
            value for value in (secret_values or set()) if value
        )
        self._sequence = self._read_existing_sequence(self._path)
        flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)
        descriptor: int | None = None
        try:
            descriptor = os.open(self._path, flags, 0o600)
            os.fchmod(descriptor, stat.S_IRUSR | stat.S_IWUSR)
            self._stream: TextIO = os.fdopen(descriptor, "a", encoding="utf-8")
            descriptor = None
        except OSError as exc:
            raise ValueError("trace file cannot be opened") from exc
        finally:
            if descriptor is not None:
                os.close(descriptor)

    @property
    def path(self) -> Path:
        return self._path

    def append(self, event: str, payload: Any) -> int:
        if not isinstance(event, str) or not event:
            raise ValueError("trace event must be non-empty text")
        sequence = self._sequence + 1
        record = {
            "sequence": sequence,
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "event": event,
        }
        try:
            record["payload"] = self._redact(payload)
            line = json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n"
        except Exception:
            raise ValueError("trace payload is not JSON-safe") from None
        try:
            self._stream.write(line)
            self._stream.flush()
            os.fsync(self._stream.fileno())
        except Exception:
            raise ValueError("trace event could not be persisted") from None
        self._sequence = sequence
        return sequence

    def close(self) -> None:
        if not self._stream.closed:
            self._stream.close()

    def __enter__(self) -> "JsonlTraceWriter":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def _redact(self, value: Any, active: set[int] | None = None) -> Any:
        active = set() if active is None else active
        if isinstance(value, str):
            redacted = value
            for secret in sorted(self._secret_values, key=len, reverse=True):
                redacted = redacted.replace(secret, "[REDACTED]")
            return _redact_secret_assignment(redacted)
        if isinstance(value, Mapping):
            identity = id(value)
            if identity in active:
                raise ValueError("trace payload contains a cycle")
            active.add(identity)
            try:
                return {
                    self._redact(key, active) if isinstance(key, str) else key: self._redact(item, active)
                    for key, item in value.items()
                }
            finally:
                active.remove(identity)
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            identity = id(value)
            if identity in active:
                raise ValueError("trace payload contains a cycle")
            active.add(identity)
            try:
                return [self._redact(item, active) for item in value]
            finally:
                active.remove(identity)
        return value

    @staticmethod
    def _read_existing_sequence(path: Path) -> int:
        try:
            if path.is_symlink():
                raise ValueError("trace file must not be a symlink")
        except OSError as exc:
            raise ValueError("trace file cannot be inspected") from exc
        if not path.exists():
            return 0
        last_sequence = 0
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
            for line in lines:
                if not line.strip():
                    continue
                record = json.loads(line)
                sequence = record.get("sequence")
                if isinstance(sequence, int) and sequence > last_sequence:
                    last_sequence = sequence
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("trace file cannot be read") from exc
        return last_sequence


_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(api[_-]?key|token|password|secret|credential|authorization)\s*[:=]\s*([^\s,;]+)"
)
_BEARER = re.compile(r"(?i)\b(bearer\s+)([^\s,;]+)")


def _redact_secret_assignment(value: str) -> str:
    value = _SECRET_ASSIGNMENT.sub(r"\1=[REDACTED]", value)
    return _BEARER.sub(r"\1[REDACTED]", value)


def _reject_trace_symlink_ancestors(path: Path) -> None:
    current = Path(path)
    while True:
        try:
            metadata = current.lstat()
        except FileNotFoundError:
            parent = current.parent
            if parent == current:
                return
            current = parent
            continue
        except OSError as exc:
            raise ValueError("trace directory cannot be inspected") from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise ValueError("trace directory must not contain symlinks")
        if not stat.S_ISDIR(metadata.st_mode):
            raise ValueError("trace directory is not a directory")
        parent = current.parent
        if parent == current:
            return
        current = parent


__all__ = ["JsonlTraceWriter"]
