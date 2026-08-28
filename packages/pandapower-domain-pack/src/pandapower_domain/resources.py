from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass, field
from importlib.resources import as_file
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Self

from grid_simulator.capabilities import contract_root


class PandapowerResourceError(RuntimeError):
    """Installed pandapower resources cannot be materialized."""


class _ResourceOwner:
    """Own a temporary materialization for the lifetime of a resource set."""

    def __init__(self, source: Traversable) -> None:
        self._temporary = tempfile.TemporaryDirectory(
            prefix="pandapower-domain-resources-"
        )
        self.root = Path(self._temporary.name) / "capability-contracts"
        self.root.mkdir()
        try:
            with as_file(source) as source_path:
                if not source_path.is_dir():
                    raise PandapowerResourceError(
                        "packaged simulator capability resources are not a directory"
                    )
                for resource in sorted(
                    source_path.glob("*.json"), key=lambda path: path.name
                ):
                    target = self.root / resource.name
                    shutil.copyfile(resource, target)
        except PandapowerResourceError:
            self.close()
            raise
        except (OSError, TypeError) as exc:
            self.close()
            raise PandapowerResourceError(
                "packaged simulator capability resources could not be read"
            ) from exc

        if not any(self.root.glob("*.json")):
            self.close()
            raise PandapowerResourceError(
                "no packaged simulator capability resources were found"
            )

    def close(self) -> None:
        self._temporary.cleanup()


@dataclass(slots=True)
class PandapowerResourceSet:
    """Filesystem paths for immutable resources owned by the domain profile.

    grid-simulator remains the canonical owner of capability definitions.  The
    domain package materializes those resources outside the checkout so
    consumers that require Path objects work identically from an editable
    install and from a wheel.  The private owner keeps the materialized files
    alive until this set is closed or collected.
    """

    capability_contract_root: Path
    _owner: _ResourceOwner = field(repr=False, compare=False)

    @classmethod
    def load(cls) -> Self:
        owner = _ResourceOwner(contract_root())
        return cls(owner.root, owner)

    def close(self) -> None:
        self._owner.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, _exc_type: object, _exc_value: object, _traceback: object) -> None:
        self.close()
