"""Legacy extension locator seam backed by the generic extension locator."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from capability_agent.runtime.extension import (
    PiExtensionLocator as _PiExtensionLocator,
    PiExtensionLocatorError,
)


class PiExtensionLocator(_PiExtensionLocator):
    PACKAGE_NAME = "@grid-static-analysis/pi-grid-tools"
    PACKAGE_VERSION = "1.0.1"
    _CANDIDATES = (
        Path("packages/pi-grid-tools"),
        Path("node_modules/@grid-static-analysis/pi-grid-tools"),
    )

    def __init__(
        self,
        project_root: Path,
        environ: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(
            project_root,
            environ,
            package_name=self.PACKAGE_NAME,
            package_version=self.PACKAGE_VERSION,
            candidates=self._CANDIDATES,
        )


__all__ = ["PiExtensionLocator", "PiExtensionLocatorError"]
