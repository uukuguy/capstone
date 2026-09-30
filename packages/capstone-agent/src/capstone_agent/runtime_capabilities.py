"""Application-owned registry for generic Pi/DSH runtime capabilities."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal


_CAPABILITY_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
CapabilityKind = Literal["skill", "mcp", "plugin"]


@dataclass(frozen=True, slots=True)
class RuntimeCapabilityDescriptor:
    capability_id: str
    kind: CapabilityKind
    version: str
    source: str

    def __post_init__(self) -> None:
        if not isinstance(self.capability_id, str) or not _CAPABILITY_ID.fullmatch(self.capability_id):
            raise ValueError("runtime capability id is invalid")
        if self.kind not in {"skill", "mcp", "plugin"}:
            raise ValueError("runtime capability kind is invalid")
        for name in ("version", "source"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or len(value) > 512:
                raise ValueError(f"runtime capability {name} is invalid")


class RuntimeCapabilityRegistry:
    """Trusted application registration, independent from domain Profiles."""

    def __init__(self) -> None:
        self._items: dict[str, RuntimeCapabilityDescriptor] = {}
        self._sealed = False

    def register(self, descriptor: RuntimeCapabilityDescriptor) -> None:
        if self._sealed:
            raise RuntimeError("runtime capability registry is sealed")
        if not isinstance(descriptor, RuntimeCapabilityDescriptor):
            raise TypeError("runtime capability descriptor is invalid")
        if descriptor.capability_id in self._items:
            raise ValueError(f"duplicate runtime capability: {descriptor.capability_id}")
        self._items[descriptor.capability_id] = descriptor

    def seal(self) -> None:
        self._sealed = True

    def snapshot(self) -> tuple[RuntimeCapabilityDescriptor, ...]:
        return tuple(self._items[key] for key in sorted(self._items))

    def contains(self, capability_id: str) -> bool:
        return capability_id in self._items


__all__ = ["CapabilityKind", "RuntimeCapabilityDescriptor", "RuntimeCapabilityRegistry"]
