from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path

import pytest
from capability_agent.runtime.capacity import CapacityExceeded

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


def test_guide_capacity_is_selected_at_initialization_and_failure_is_precise(tmp_path):
    provider = _Provider(text='x' * 300000)
    workspace = tmp_path / 'binding'
    workspace.mkdir()
    materialize_guide_provider(provider, workspace=workspace, guide_root_path=workspace/'guides',
        guide_index_path=workspace/'index.json', runtime_limits={'guide_document_bytes':400000})
    from capability_agent.runtime.capacity import CapacityExceeded
    with pytest.raises(CapacityExceeded, match='guide_document_bytes.*300000.*100'):
        materialize_guide_provider(provider, workspace=workspace, guide_root_path=workspace/'other',
            guide_index_path=workspace/'other.json', runtime_limits={'guide_document_bytes':100})


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


def test_existing_guide_is_reused_only_after_exact_provider_verification(tmp_path: Path) -> None:
    workspace = tmp_path / "binding"
    root = workspace / "guides"
    index = workspace / "guide-index.json"
    provider = _Provider(text="# Original\n")
    materialize_guide_provider(provider, workspace=workspace, guide_root_path=root, guide_index_path=index)
    original = index.read_bytes()
    materialize_guide_provider(provider, workspace=workspace, guide_root_path=root,
                              guide_index_path=index, reuse_existing=True)
    assert index.read_bytes() == original
    (root / "SKILL.md").write_text("changed")
    with pytest.raises(GuideMaterializationError, match="does not match"):
        materialize_guide_provider(provider, workspace=workspace, guide_root_path=root,
                                  guide_index_path=index, reuse_existing=True)
    assert (root / "SKILL.md").read_text() == "changed"
    assert index.read_bytes() == original


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

    with pytest.raises(CapacityExceeded, match='guide_resource_count'):
        materialize_guide_provider(
            _IndexedProvider(documents),
            workspace=tmp_path / "binding",
            guide_root_path=tmp_path / "binding" / "guides",
            guide_index_path=tmp_path / "binding" / "guide-index.json",
            runtime_limits={'guide_resource_count':64},
        )


def test_materialize_guide_provider_rejects_oversized_document_and_title(
    tmp_path: Path,
) -> None:
    oversized = "# Guide\n" + "x" * (256 * 1024)
    with pytest.raises(CapacityExceeded, match='guide_document_bytes'):
        materialize_guide_provider(
            _IndexedProvider((("overview", "Guide", oversized),)),
            workspace=tmp_path / "large-document",
            guide_root_path=tmp_path / "large-document" / "guides",
            guide_index_path=tmp_path / "large-document" / "guide-index.json",
            runtime_limits={'guide_document_bytes':256*1024},
        )

    long_title = "T" * 257
    with pytest.raises(CapacityExceeded, match='guide_title_chars'):
        materialize_guide_provider(
            _IndexedProvider((("overview", long_title, "# Guide\n"),)),
            workspace=tmp_path / "large-title",
            guide_root_path=tmp_path / "large-title" / "guides",
            guide_index_path=tmp_path / "large-title" / "guide-index.json",
            runtime_limits={'guide_title_chars':256},
        )


def test_materialize_guide_provider_rejects_oversized_total(
    tmp_path: Path,
) -> None:
    text = "# Guide\n" + "x" * (200 * 1024)
    documents = tuple(
        ("overview" if index == 0 else f"guide-{index}", "Guide", text)
        for index in range(6)
    )

    with pytest.raises(CapacityExceeded, match='guide_total_bytes'):
        materialize_guide_provider(
            _IndexedProvider(documents),
            workspace=tmp_path / "binding",
            guide_root_path=tmp_path / "binding" / "guides",
            guide_index_path=tmp_path / "binding" / "guide-index.json",
            runtime_limits={'guide_total_bytes':1024*1024},
        )
