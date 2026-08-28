from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass, field
from importlib.resources import as_file, files
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import ClassVar, Self, cast

from grid_simulator.capabilities import contract_root


__all__ = ["PandapowerResourceError", "PandapowerResourceSet"]


class PandapowerResourceError(RuntimeError):
    """Installed pandapower resources cannot be materialized."""


class _ResourceOwner:
    """Own temporary materialized resources for the profile lifetime."""

    def __init__(
        self,
        *,
        contracts: Traversable,
        policy: Traversable,
        guides: Traversable,
    ) -> None:
        self._temporary = tempfile.TemporaryDirectory(
            prefix="pandapower-domain-resources-"
        )
        self.root = Path(self._temporary.name)
        self.capability_contract_root = self.root / "capability-contracts"
        self.system_policy_path = self.root / "policy" / "system-policy.md"
        self.guide_root = self.root / "guides"
        try:
            self._copy_directory(contracts, self.capability_contract_root)
            self._copy_file(policy, self.system_policy_path)
            self._copy_directory(guides, self.guide_root)
        except PandapowerResourceError:
            self.close()
            raise
        except (OSError, TypeError) as exc:
            self.close()
            raise PandapowerResourceError(
                "packaged pandapower resources could not be read"
            ) from exc

        if not any(self.capability_contract_root.glob("*.json")):
            self.close()
            raise PandapowerResourceError(
                "no packaged simulator capability resources were found"
            )
        if not self.system_policy_path.is_file():
            self.close()
            raise PandapowerResourceError(
                "packaged pandapower system policy was not found"
            )
        if not self.guide_root.is_dir() or not (self.guide_root / "SKILL.md").is_file():
            self.close()
            raise PandapowerResourceError(
                "packaged pandapower guides were not found"
            )
        self._closed = False

    @staticmethod
    def _copy_file(source: Traversable, target: Path) -> None:
        with as_file(source) as source_path:
            if not source_path.is_file():
                raise PandapowerResourceError(
                    "packaged pandapower policy resource is not a file"
                )
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_path, target)

    @classmethod
    def _copy_directory(cls, source: Traversable, target: Path) -> None:
        with as_file(source) as source_path:
            if not source_path.is_dir():
                raise PandapowerResourceError(
                    "packaged pandapower resource is not a directory"
                )
            target.mkdir(parents=True, exist_ok=True)
            for child in sorted(source_path.iterdir(), key=lambda path: path.name):
                destination = target / child.name
                if child.is_dir():
                    cls._copy_directory(child, destination)
                elif child.is_file():
                    shutil.copyfile(child, destination)

    @property
    def closed(self) -> bool:
        return getattr(self, "_closed", False)

    def close(self) -> None:
        if not self.closed:
            self._temporary.cleanup()
            self._closed = True


@dataclass(slots=True)
class PandapowerResourceSet:
    """Filesystem paths for immutable resources owned by the domain profile.

    Simulator capability definitions remain owned by ``grid-simulator``. All
    resources are resolved through ``importlib.resources`` and materialized to
    a stable temporary directory so callers can safely consume ``Path``
    objects from editable installs and wheels alike.
    """

    capability_contract_root: Path
    system_policy_path: Path
    guide_root: Path
    _owner: _ResourceOwner = field(repr=False, compare=False)

    _cached: ClassVar[PandapowerResourceSet | None] = None

    @classmethod
    def load(cls) -> Self:
        cached = cls._cached
        if cached is not None and not cached._owner.closed:
            return cast(Self, cached)

        package_root = files("pandapower_domain").joinpath("resources")
        owner = _ResourceOwner(
            contracts=contract_root(),
            policy=package_root.joinpath("policy", "system-policy.md"),
            guides=package_root.joinpath("guides"),
        )
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

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        _exc_type: object,
        _exc_value: object,
        _traceback: object,
    ) -> None:
        self.close()
