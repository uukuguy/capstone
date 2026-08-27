from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class CapabilityContractSourceError(ValueError):
    """Capability contracts cannot be discovered or decoded."""


class CapabilityContractSource(Protocol):
    def load(self) -> tuple[dict[str, object], ...]: ...


@dataclass(frozen=True, slots=True)
class FilesystemCapabilityContractSource:
    root: Path

    def load(self) -> tuple[dict[str, object], ...]:
        paths = sorted(Path(self.root).glob("*.json"), key=lambda path: path.name)
        if not paths:
            raise CapabilityContractSourceError(
                f"no capability contracts found under {self.root}"
            )
        documents: list[dict[str, object]] = []
        for path in paths:
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise CapabilityContractSourceError(
                    f"invalid capability contract: {path.name}"
                ) from exc
            if not isinstance(value, dict):
                raise CapabilityContractSourceError(
                    f"capability contract must be an object: {path.name}"
                )
            documents.append(value)
        return tuple(documents)
