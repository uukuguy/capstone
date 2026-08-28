from __future__ import annotations

from importlib.resources import files
from pathlib import Path
from typing import cast

from grid_simulator.capabilities.registry import CapabilityRegistry
from grid_simulator.capabilities.schema import CapabilityContract


def contract_root() -> Path:
    """Return the installed capability-definition resource directory.

    The simulator package owns these definitions.  Callers must use the
    returned resource object rather than reconstructing a checkout-relative
    path, which also keeps the API usable when the package is installed from a
    wheel.
    """

    # Wheel installations expose package resources as pathlib paths.  Keep the
    # runtime value untouched so callers can still pass non-filesystem
    # Traversables to importlib.resources.as_file when an archive loader is in
    # use.
    return cast(Path, files("grid_simulator.capabilities.definitions"))


__all__ = ["CapabilityContract", "CapabilityRegistry", "contract_root"]
