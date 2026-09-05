"""Small, digest-bound inventory resources; no generic file capability."""

from __future__ import annotations

import hashlib
import os
import stat
from collections.abc import Mapping
from pathlib import Path

from capability_agent.tools.guide import GuideNotFound

from inventory_domain.resources import InventoryResourceSet

_MAX_TEXT_BYTES = 64 * 1024
_GUIDES = {
    "overview": ("SKILL.md",),
    "capability-map": ("references", "capability-map.md"),
    "evidence-and-recovery": ("references", "evidence-and-recovery.md"),
}


def _read_text(root: Path, parts: tuple[str, ...]) -> str:
    """Bind each directory and read the same bounded, regular descriptor."""
    descriptors: list[int] = []
    try:
        directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        parent = os.open(root, directory_flags)
        descriptors.append(parent)
        for part in parts[:-1]:
            parent = os.open(part, directory_flags, dir_fd=parent)
            descriptors.append(parent)
        descriptor = os.open(
            parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent
        )
        descriptors.append(descriptor)
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > _MAX_TEXT_BYTES:
            raise RuntimeError("inventory resource must be a bounded regular file")
        chunks: list[bytes] = []
        remaining = _MAX_TEXT_BYTES + 1
        while remaining:
            chunk = os.read(descriptor, min(remaining, 8192))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        content = b"".join(chunks)
        if len(content) > _MAX_TEXT_BYTES:
            raise RuntimeError("inventory resource exceeds its size limit")
        text = content.decode("utf-8")
        if not text.strip():
            raise RuntimeError("inventory resource is empty")
        return text
    except (OSError, UnicodeError) as exc:
        raise RuntimeError("inventory resource is unavailable or unsafe") from exc
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


class _CapturedText:
    def __init__(self, root: Path, parts: tuple[str, ...]) -> None:
        self.root = root
        self.parts = parts
        self.digest = self._digest(_read_text(root, parts))

    @staticmethod
    def _digest(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def read(self) -> str:
        text = _read_text(self.root, self.parts)
        if self._digest(text) != self.digest:
            raise RuntimeError("inventory resource digest does not match its capture")
        return text


class InventoryGuideProvider:
    def __init__(self, guide_root: Path | None = None) -> None:
        root = Path(guide_root) if guide_root is not None else InventoryResourceSet.load().guide_root
        self._documents = {
            key: _CapturedText(root, parts) for key, parts in _GUIDES.items()
        }

    def open(self, resource_id: str) -> Mapping[str, object]:
        document = self._documents.get(resource_id)
        if document is None:
            raise GuideNotFound(resource_id)
        text = document.read()
        title = next(
            (line[2:].strip() for line in text.splitlines() if line.startswith("# ")),
            resource_id,
        )
        return {
            "resource_id": resource_id, "title": title,
            "sha256": document.digest, "text": text,
        }

    def load(self) -> tuple[Mapping[str, object], ...]:
        return tuple(
            {key: value for key, value in self.open(resource_id).items() if key != "text"}
            for resource_id in self._documents
        )


class InventoryPolicyProvider:
    def __init__(self, policy_path: Path | None = None) -> None:
        path = Path(policy_path) if policy_path is not None else InventoryResourceSet.load().system_policy_path
        self._document = _CapturedText(path.parent, (path.name,))

    def load(self) -> str:
        return self._document.read()
