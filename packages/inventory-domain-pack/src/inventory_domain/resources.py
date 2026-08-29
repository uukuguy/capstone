from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass, field
from importlib.resources import as_file, files
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import ClassVar, Self


class InventoryResourceError(RuntimeError):
    pass


class _ResourceOwner:
    def __init__(self, root: Traversable) -> None:
        self._temporary = tempfile.TemporaryDirectory(
            prefix="inventory-domain-resources-"
        )
        self.root = Path(self._temporary.name)
        try:
            with as_file(root) as source:
                shutil.copytree(source, self.root, dirs_exist_ok=True)
        except (OSError, TypeError) as exc:
            self._temporary.cleanup()
            raise InventoryResourceError(
                "packaged inventory resources could not be materialized"
            ) from exc
        self.capability_contract_root = self.root / "capabilities"
        self.system_policy_path = self.root / "policy" / "system-policy.md"
        self.guide_root = self.root / "guides"
        if not any(self.capability_contract_root.glob("*.json")):
            self._temporary.cleanup()
            raise InventoryResourceError("inventory capability resources are missing")
        if not self.system_policy_path.is_file():
            self._temporary.cleanup()
            raise InventoryResourceError("inventory policy resource is missing")
        if not (self.guide_root / "SKILL.md").is_file():
            self._temporary.cleanup()
            raise InventoryResourceError("inventory guide resource is missing")
        self.closed = False

    def close(self) -> None:
        if not self.closed:
            self._temporary.cleanup()
            self.closed = True


@dataclass(slots=True)
class InventoryResourceSet:
    capability_contract_root: Path
    system_policy_path: Path
    guide_root: Path
    _owner: _ResourceOwner = field(repr=False, compare=False)

    _cached: ClassVar["InventoryResourceSet | None"] = None

    @classmethod
    def load(cls) -> Self:
        cached = cls._cached
        if cached is not None and not cached._owner.closed:
            return cached
        owner = _ResourceOwner(files("inventory_domain").joinpath("resources"))
        cached = cls(
            owner.capability_contract_root,
            owner.system_policy_path,
            owner.guide_root,
            owner,
        )
        cls._cached = cached
        return cached

    def close(self) -> None:
        self._owner.close()
        type(self)._cached = None
