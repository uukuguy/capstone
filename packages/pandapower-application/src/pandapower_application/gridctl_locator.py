from __future__ import annotations

import os
import shutil
from pathlib import Path


class GridctlLocatorError(RuntimeError):
    pass


class GridctlLocator:
    def __init__(self, repository_root: Path, environ: dict[str, str] | None = None) -> None:
        self.repository_root = Path(repository_root)
        self.environ = dict(os.environ if environ is None else environ)

    def resolve(self) -> Path:
        explicit = self.environ.get("GRID_AGENT_GRIDCTL_EXECUTABLE")
        if explicit:
            candidate = Path(explicit)
            if not candidate.is_file() or not os.access(candidate, os.X_OK):
                raise GridctlLocatorError("Grid simulator executable is unavailable")
            return candidate

        managed = self._managed_path()
        if managed.is_file() and os.access(managed, os.X_OK):
            return managed

        installed = shutil.which(
            "gridctl.exe" if os.name == "nt" else "gridctl",
            path=self.environ.get("PATH", ""),
        )
        if installed:
            return Path(installed)
        raise GridctlLocatorError("Grid simulator executable is unavailable")

    def _managed_path(self) -> Path:
        bin_name = "gridctl.exe" if os.name == "nt" else "gridctl"
        folder = "Scripts" if os.name == "nt" else "bin"
        return self.repository_root / "packages/grid-simulator/.venv" / folder / bin_name
