from __future__ import annotations

import json
import stat
from collections.abc import Mapping
from pathlib import Path


class PiExtensionLocatorError(RuntimeError):
    """The application-facing Pi extension is not a verified local package."""


class PiExtensionLocator:
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
        self.project_root = Path(project_root).resolve()
        # Accepted for call-site symmetry only. Environment-selected extension
        # paths are intentionally outside this discovery contract.
        self._environ = dict(environ or {})

    def resolve(self) -> Path:
        for relative_root in self._CANDIDATES:
            package_root = self.project_root / relative_root
            if not _lexically_present(package_root):
                continue
            return self._validate_package(relative_root)
        raise PiExtensionLocatorError(
            "Verified project-local @grid-static-analysis/pi-grid-tools is unavailable"
        )

    def _validate_package(self, relative_root: Path) -> Path:
        package_root = self.project_root / relative_root
        manifest_path = package_root / "package.json"
        extension_path = package_root / "src/domain-tools.mjs"
        _require_no_symlink_regular_file(self.project_root, manifest_path)
        _require_no_symlink_regular_file(self.project_root, extension_path)
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PiExtensionLocatorError(
                f"Pi extension package manifest is invalid: {manifest_path}"
            ) from exc
        if not isinstance(manifest, dict):
            raise PiExtensionLocatorError("Pi extension package manifest must be an object")
        if (
            manifest.get("name") != self.PACKAGE_NAME
            or manifest.get("version") != self.PACKAGE_VERSION
        ):
            raise PiExtensionLocatorError(
                "Pi extension package identity does not match the application contract"
            )
        return extension_path


def _lexically_present(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    return True


def _require_no_symlink_regular_file(root: Path, path: Path) -> None:
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise PiExtensionLocatorError("Pi extension path is not project-local") from exc
    current = root
    for index, component in enumerate(relative.parts):
        current = current / component
        try:
            metadata = current.lstat()
        except OSError as exc:
            raise PiExtensionLocatorError(
                f"Pi extension project-local path is unavailable: {current}"
            ) from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise PiExtensionLocatorError(
                f"Pi extension project-local path must not contain symlinks: {current}"
            )
        if index < len(relative.parts) - 1 and not stat.S_ISDIR(metadata.st_mode):
            raise PiExtensionLocatorError(
                f"Pi extension project-local parent is not a directory: {current}"
            )
        if index == len(relative.parts) - 1 and not stat.S_ISREG(metadata.st_mode):
            raise PiExtensionLocatorError(
                f"Pi extension project-local leaf is not a regular file: {current}"
            )
