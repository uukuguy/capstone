"""Digest-bound allowlisted guides for the pandapower Domain Pack."""

from __future__ import annotations

import hashlib
import os
import stat
from collections.abc import Mapping
from pathlib import Path

from capability_agent.tools.guide import GuideNotFound

from pandapower_domain.resources import PandapowerResourceSet


class PandapowerGuideProvider:
    """Publish only guides captured by the installed domain resource set."""

    schema_id = "pandapower-guide-index/1.0"

    def __init__(self, guide_root: Path | None = None) -> None:
        configured_root = (
            Path(guide_root)
            if guide_root is not None
            else PandapowerResourceSet.load().guide_root
        )
        self.guide_root = _canonical_root(configured_root)
        self._root_identity = _identity(self.guide_root, label="guide root")
        self._digests: dict[str, str] = {}
        self._paths: dict[str, Path] = {}
        self._identities: dict[str, tuple[int, int]] = {}
        self._references_identity: tuple[int, int] | None = None
        self._capture_index()

    def load(self) -> tuple[Mapping[str, object], ...]:
        self._verify_layout()
        self._verify_digests()
        return tuple(
            {
                "resource_id": resource_id,
                "title": title,
                "sha256": self._digests[resource_id],
            }
            for resource_id, title in self._titles()
        )

    def open(self, resource_id: str) -> Mapping[str, object]:
        if resource_id not in self._paths:
            raise GuideNotFound(resource_id)
        self._verify_layout()
        self._verify_digest(resource_id)
        path = self._paths[resource_id]
        try:
            text = _read_text(path, label=f"guide {resource_id}")
        except RuntimeError:
            raise
        except OSError as exc:
            raise RuntimeError("pandapower guide could not be read") from exc
        return {
            "resource_id": resource_id,
            "title": _title(text, resource_id),
            "sha256": self._digests[resource_id],
            "text": text,
        }

    def _capture_index(self) -> None:
        paths: dict[str, Path] = {}
        overview = self.guide_root / "SKILL.md"
        if _exists(overview):
            _require_regular(overview, label="guide overview")
            paths["overview"] = overview
        references = self.guide_root / "references"
        if _exists(references):
            _require_directory(references, label="guide references")
            self._references_identity = _identity(
                references, label="guide references"
            )
            try:
                candidates = sorted(
                    references.iterdir(), key=lambda item: item.name
                )
            except OSError as exc:
                raise RuntimeError("pandapower guide index is unavailable") from exc
            for path in candidates:
                if path.suffix != ".md":
                    continue
                _require_regular(path, label="allowlisted guide")
                if not path.is_relative_to(self.guide_root):
                    raise RuntimeError("pandapower guide path escapes its root")
                resource_id = path.stem
                if resource_id in paths:
                    raise RuntimeError("pandapower guide resource IDs are ambiguous")
                paths[resource_id] = path
        self._paths = paths
        self._identities = {
            resource_id: _identity(path, label="allowlisted guide")
            for resource_id, path in sorted(paths.items())
        }
        self._digests = {
            resource_id: _digest(path) for resource_id, path in sorted(paths.items())
        }

    def _verify_layout(self) -> None:
        if _identity(self.guide_root, label="guide root") != self._root_identity:
            raise RuntimeError("pandapower guide root was replaced")
        references = self.guide_root / "references"
        if self._references_identity is None:
            if _exists(references):
                raise RuntimeError("pandapower guide references were replaced")
        elif _identity(references, label="guide references") != self._references_identity:
            raise RuntimeError("pandapower guide references were replaced")
        for resource_id, path in self._paths.items():
            if _identity(path, label=f"guide {resource_id}") != self._identities[resource_id]:
                raise RuntimeError("pandapower guide allowlist path was replaced")

    def _verify_digests(self) -> None:
        for resource_id in self._paths:
            self._verify_digest(resource_id)

    def _verify_digest(self, resource_id: str) -> None:
        path = self._paths[resource_id]
        if _digest(path) != self._digests[resource_id]:
            raise RuntimeError("pandapower guide digest does not match allowlist")

    def _titles(self) -> tuple[tuple[str, str], ...]:
        result: list[tuple[str, str]] = []
        for resource_id, path in sorted(self._paths.items()):
            try:
                title = _title(
                    _read_text(path, label=f"guide {resource_id}"), resource_id
                )
            except RuntimeError:
                raise
            except OSError as exc:
                raise RuntimeError("pandapower guide index is unavailable") from exc
            result.append((resource_id, title))
        return tuple(result)


def _digest(path: Path) -> str:
    try:
        return hashlib.sha256(_read_bytes(path, label="guide document")).hexdigest()
    except OSError as exc:
        raise RuntimeError("pandapower guide digest could not be calculated") from exc


def _canonical_root(path: Path) -> Path:
    candidate = Path(os.path.abspath(os.fspath(path)))
    try:
        metadata = candidate.lstat()
    except OSError as exc:
        raise RuntimeError("pandapower guide root is unavailable") from exc
    if stat.S_ISLNK(metadata.st_mode):
        raise RuntimeError("pandapower guide root must not be a symlink")
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise RuntimeError("pandapower guide root is unavailable") from exc
    _require_directory(resolved, label="guide root")
    return resolved


def _exists(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise RuntimeError("pandapower guide path cannot be inspected") from exc
    return True


def _require_regular(path: Path, *, label: str) -> None:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise RuntimeError(f"{label} is unavailable") from exc
    if stat.S_ISLNK(metadata.st_mode):
        raise RuntimeError(f"{label} must not be a symlink")
    if not stat.S_ISREG(metadata.st_mode):
        raise RuntimeError(f"{label} is not a regular file")


def _require_directory(path: Path, *, label: str) -> None:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise RuntimeError(f"{label} is unavailable") from exc
    if stat.S_ISLNK(metadata.st_mode):
        raise RuntimeError(f"{label} must not be a symlink")
    if not stat.S_ISDIR(metadata.st_mode):
        raise RuntimeError(f"{label} is not a directory")


def _identity(path: Path, *, label: str) -> tuple[int, int]:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise RuntimeError(f"{label} is unavailable") from exc
    if stat.S_ISLNK(metadata.st_mode):
        raise RuntimeError(f"{label} must not be a symlink")
    return (metadata.st_dev, metadata.st_ino)


def _read_bytes(path: Path, *, label: str) -> bytes:
    _require_regular(path, label=label)
    descriptor: int | None = None
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise RuntimeError(f"{label} is not a regular file")
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = None
            return stream.read()
    except RuntimeError:
        raise
    except OSError as exc:
        if path.is_symlink():
            raise RuntimeError(f"{label} must not be a symlink") from exc
        raise RuntimeError(f"{label} could not be read") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _read_text(path: Path, *, label: str) -> str:
    try:
        return _read_bytes(path, label=label).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RuntimeError(f"{label} is not valid UTF-8") from exc


def _title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


__all__ = ["PandapowerGuideProvider"]
