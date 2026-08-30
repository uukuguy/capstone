"""Resolve a controller-selected, project-local model extension package."""

from __future__ import annotations

import json
import stat
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path


class PiExtensionLocatorError(RuntimeError):
    """Raised when an extension package is not a verified local package."""


@dataclass(frozen=True, slots=True)
class ExtensionSpec:
    package_name: str
    package_version: str | None = None
    extension_relative_path: Path = Path("src/domain-tools.mjs")
    candidates: tuple[Path, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.package_name, str) or not self.package_name.strip():
            raise PiExtensionLocatorError("extension package name is required")
        if self.package_version is not None and not self.package_version.strip():
            raise PiExtensionLocatorError("extension package version is invalid")
        relative = Path(self.extension_relative_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise PiExtensionLocatorError("extension path must be package-local")


class PiExtensionLocator:
    def __init__(
        self,
        project_root: Path,
        environ: Mapping[str, str] | None = None,
        *,
        spec: ExtensionSpec | None = None,
        package_name: str = "@capability-agent/pi-tools",
        package_version: str | None = None,
        candidates: Iterable[Path] | None = None,
    ) -> None:
        del environ  # Environment-selected extension paths are not trusted.
        self.project_root = Path(project_root).resolve()
        if spec is None:
            candidate_paths = tuple(candidates or ())
            if not candidate_paths:
                candidate_paths = (
                    Path("packages/pi-tools"),
                    Path("node_modules") / package_name,
                )
            spec = ExtensionSpec(
                package_name=package_name,
                package_version=package_version,
                candidates=candidate_paths,
            )
        self.spec = spec

    def resolve(self) -> Path:
        for relative_root in self.spec.candidates:
            if relative_root.is_absolute() or ".." in relative_root.parts:
                raise PiExtensionLocatorError("extension candidate is not project-local")
            package_root = self.project_root / relative_root
            if not _lexically_present(package_root):
                continue
            return self._validate_package(relative_root)
        raise PiExtensionLocatorError("verified project-local extension is unavailable")

    def _validate_package(self, relative_root: Path) -> Path:
        package_root = self.project_root / relative_root
        manifest_path = package_root / "package.json"
        extension_path = package_root / self.spec.extension_relative_path
        _require_no_symlink_regular_file(self.project_root, manifest_path)
        _require_no_symlink_regular_file(self.project_root, extension_path)
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PiExtensionLocatorError("extension package manifest is invalid") from exc
        if not isinstance(manifest, dict):
            raise PiExtensionLocatorError("extension package manifest must be an object")
        if manifest.get("name") != self.spec.package_name:
            raise PiExtensionLocatorError("extension package identity is invalid")
        if self.spec.package_version is not None and manifest.get("version") != self.spec.package_version:
            raise PiExtensionLocatorError("extension package version is invalid")
        return extension_path


def _lexically_present(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise PiExtensionLocatorError("extension path cannot be inspected") from exc
    return True


def _require_no_symlink_regular_file(root: Path, path: Path) -> None:
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise PiExtensionLocatorError("extension path is not project-local") from exc
    current = root
    for index, component in enumerate(relative.parts):
        current /= component
        try:
            metadata = current.lstat()
        except OSError as exc:
            raise PiExtensionLocatorError("extension project-local path is unavailable") from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise PiExtensionLocatorError("extension project-local path must not contain symlinks")
        if index < len(relative.parts) - 1 and not stat.S_ISDIR(metadata.st_mode):
            raise PiExtensionLocatorError("extension project-local parent is not a directory")
        if index == len(relative.parts) - 1 and not stat.S_ISREG(metadata.st_mode):
            raise PiExtensionLocatorError("extension project-local leaf is not a regular file")


__all__ = ["ExtensionSpec", "PiExtensionLocator", "PiExtensionLocatorError"]
