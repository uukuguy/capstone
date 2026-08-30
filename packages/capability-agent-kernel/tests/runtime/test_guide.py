from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path

import pytest

from capability_agent.tools.guide import (
    GuideMaterializationError,
    materialize_guide_provider,
)


class _Provider:
    def __init__(self, *, resource_id: str = "overview", text: str = "# Guide\n") -> None:
        self.resource_id = resource_id
        self.text = text
        self.digest = hashlib.sha256(text.encode("utf-8")).hexdigest()

    def load(self) -> tuple[Mapping[str, object], ...]:
        return (
            {
                "resource_id": self.resource_id,
                "title": "Guide",
                "sha256": self.digest,
            },
        )

    def open(self, resource_id: str) -> Mapping[str, object]:
        if resource_id != self.resource_id:
            raise KeyError(resource_id)
        return {
            "resource_id": resource_id,
            "title": "Guide",
            "sha256": self.digest,
            "text": self.text,
        }


class _IndexedProvider:
    def __init__(self, documents: tuple[tuple[str, str, str], ...]) -> None:
        self.documents = documents

    def load(self) -> tuple[Mapping[str, object], ...]:
        return tuple(
            {
                "resource_id": resource_id,
                "title": title,
                "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            }
            for resource_id, title, text in self.documents
        )

    def open(self, resource_id: str) -> Mapping[str, object]:
        for current_id, title, text in self.documents:
            if current_id == resource_id:
                return {
                    "resource_id": current_id,
                    "title": title,
                    "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    "text": text,
                }
        raise KeyError(resource_id)


def test_materialize_guide_provider_publishes_binding_owned_snapshot(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "binding"
    root = workspace / "guides"
    index_path = workspace / "guide-index.json"

    materialize_guide_provider(
        _Provider(resource_id="overview", text="# Overview\n"),
        workspace=workspace,
        guide_root_path=root,
        guide_index_path=index_path,
        protocol="fixture-guide-index",
    )

    payload = json.loads(index_path.read_text(encoding="utf-8"))
    assert payload["root"] == str(root)
    assert payload["resources"] == {"overview": str(root / "SKILL.md")}
    assert (root / "SKILL.md").read_text(encoding="utf-8") == "# Overview\n"
    assert not any("source" in path.as_posix() for path in root.rglob("*"))


def test_materialize_guide_provider_rejects_digest_mismatch_without_publishing(
    tmp_path: Path,
) -> None:
    provider = _Provider(text="# Actual\n")
    provider.digest = "0" * 64
    root = tmp_path / "binding" / "guides"
    index_path = tmp_path / "binding" / "guide-index.json"

    with pytest.raises(GuideMaterializationError, match="digest"):
        materialize_guide_provider(
            provider,
            workspace=tmp_path / "binding",
            guide_root_path=root,
            guide_index_path=index_path,
        )

    assert not root.exists()
    assert not index_path.exists()


def test_materialize_guide_provider_rejects_unportable_id_and_path_escape(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "binding"
    with pytest.raises(GuideMaterializationError, match="portable"):
        materialize_guide_provider(
            _Provider(resource_id="../outside"),
            workspace=workspace,
            guide_root_path=workspace / "guides",
            guide_index_path=workspace / "guide-index.json",
        )

    with pytest.raises(GuideMaterializationError, match="escapes"):
        materialize_guide_provider(
            _Provider(),
            workspace=workspace,
            guide_root_path=tmp_path / "outside-guides",
            guide_index_path=workspace / "guide-index.json",
        )


def test_materialize_guide_provider_never_replaces_existing_snapshot_or_symlink(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "binding"
    root = workspace / "guides"
    index_path = workspace / "guide-index.json"
    materialize_guide_provider(
        _Provider(text="# Original\n"),
        workspace=workspace,
        guide_root_path=root,
        guide_index_path=index_path,
    )
    original = index_path.read_bytes()

    with pytest.raises(GuideMaterializationError, match="already exists"):
        materialize_guide_provider(
            _Provider(text="# Replacement\n"),
            workspace=workspace,
            guide_root_path=root,
            guide_index_path=index_path,
        )
    assert index_path.read_bytes() == original
    assert (root / "SKILL.md").read_text(encoding="utf-8") == "# Original\n"

    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel.txt"
    sentinel.write_text("keep", encoding="utf-8")
    linked_root = tmp_path / "linked-guides"
    linked_root.symlink_to(outside, target_is_directory=True)
    with pytest.raises(GuideMaterializationError, match="symlink"):
        materialize_guide_provider(
            _Provider(),
            workspace=tmp_path,
            guide_root_path=linked_root,
            guide_index_path=tmp_path / "linked-index.json",
        )
    assert sentinel.read_text(encoding="utf-8") == "keep"


def test_materialize_guide_provider_rejects_too_many_resources(
    tmp_path: Path,
) -> None:
    documents = tuple(
        ("overview" if index == 0 else f"guide-{index}", "Guide", "# Guide\n")
        for index in range(65)
    )

    with pytest.raises(GuideMaterializationError, match="resource count"):
        materialize_guide_provider(
            _IndexedProvider(documents),
            workspace=tmp_path / "binding",
            guide_root_path=tmp_path / "binding" / "guides",
            guide_index_path=tmp_path / "binding" / "guide-index.json",
        )


def test_materialize_guide_provider_rejects_oversized_document_and_title(
    tmp_path: Path,
) -> None:
    oversized = "# Guide\n" + "x" * (256 * 1024)
    with pytest.raises(GuideMaterializationError, match="document size"):
        materialize_guide_provider(
            _IndexedProvider((("overview", "Guide", oversized),)),
            workspace=tmp_path / "large-document",
            guide_root_path=tmp_path / "large-document" / "guides",
            guide_index_path=tmp_path / "large-document" / "guide-index.json",
        )

    long_title = "T" * 257
    with pytest.raises(GuideMaterializationError, match="title"):
        materialize_guide_provider(
            _IndexedProvider((("overview", long_title, "# Guide\n"),)),
            workspace=tmp_path / "large-title",
            guide_root_path=tmp_path / "large-title" / "guides",
            guide_index_path=tmp_path / "large-title" / "guide-index.json",
        )


def test_materialize_guide_provider_rejects_oversized_total(
    tmp_path: Path,
) -> None:
    text = "# Guide\n" + "x" * (200 * 1024)
    documents = tuple(
        ("overview" if index == 0 else f"guide-{index}", "Guide", text)
        for index in range(6)
    )

    with pytest.raises(GuideMaterializationError, match="total"):
        materialize_guide_provider(
            _IndexedProvider(documents),
            workspace=tmp_path / "binding",
            guide_root_path=tmp_path / "binding" / "guides",
            guide_index_path=tmp_path / "binding" / "guide-index.json",
        )
