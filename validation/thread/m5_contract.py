"""Small, secret-free validation summaries; full execution stays in the ledger."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlsplit


class M5ValidationError(ValueError):
    """A validation summary is invalid or cannot be safely persisted."""


def _details(value: object, depth: int = 0) -> object:
    if depth > 4:
        raise M5ValidationError("details nesting exceeds limit")
    if value is None or isinstance(value, bool) or isinstance(value, int):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    if isinstance(value, str) and len(value) <= 2048:
        return re.sub(
            r"(?i)(?:bearer\s+\S+|(?:operator[-_ ]?token|provider[-_ ]?key|api[-_]?key|secret|password|credential)\s*[:=]\s*\S+)",
            "[redacted]",
            value,
        )
    if isinstance(value, (tuple, list)) and len(value) <= 128:
        return [_details(item, depth + 1) for item in value]
    if isinstance(value, dict) and len(value) <= 64:
        output: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str) or not key or len(key) > 128:
                raise M5ValidationError("details key is invalid")
            output[key] = "[redacted]" if re.search(r"(?i)token|secret|password|authorization|api.?key|credential|operator|provider|auth", key) else _details(item, depth + 1)
        return output
    raise M5ValidationError("details value is invalid or exceeds limit")


@dataclass(frozen=True)
class M5CheckResult:
    name: str
    status: Literal["passed", "skipped", "failed"]
    details: dict[str, object]

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name or len(self.name) > 128:
            raise M5ValidationError("check name is invalid")
        if self.status not in {"passed", "skipped", "failed"}:
            raise M5ValidationError("check status is invalid")
        if not isinstance(self.details, dict):
            raise M5ValidationError("details must be an object")
        _details(self.details)

    def to_document(self) -> dict[str, object]:
        return {"name": self.name, "status": self.status, "details": _details(self.details)}


@dataclass(frozen=True)
class M5RunSummary:
    application_id: str
    api_origin: str
    checks: tuple[M5CheckResult, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.application_id, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", self.application_id):
            raise M5ValidationError("application_id is invalid")
        origin = urlsplit(self.api_origin)
        if origin.scheme not in {"http", "https"} or not origin.netloc or origin.username or origin.password or origin.path or origin.query or origin.fragment:
            raise M5ValidationError("api_origin is invalid")
        if not isinstance(self.checks, tuple) or len(self.checks) > 128 or any(not isinstance(check, M5CheckResult) for check in self.checks):
            raise M5ValidationError("checks are invalid or exceed limit")

    def to_document(self) -> dict[str, object]:
        document: dict[str, object] = {
            "schema": "capstone-m5-validation/1", "application_id": self.application_id,
            "api_origin": self.api_origin, "checks": [check.to_document() for check in self.checks],
        }
        if len(json.dumps(document, ensure_ascii=False, allow_nan=False).encode()) > 256 * 1024:
            raise M5ValidationError("checks document exceeds limit")
        return document
