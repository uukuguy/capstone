"""Allowlisted domain-guide contracts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol


class GuideProvider(Protocol):
    def load(self) -> tuple[Mapping[str, object], ...]: ...


__all__ = ["GuideProvider"]
