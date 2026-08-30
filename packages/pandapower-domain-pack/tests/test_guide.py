from __future__ import annotations

from pathlib import Path

import pytest

from pandapower_domain.guide import PandapowerGuideProvider


def test_guide_provider_loads_only_digest_bound_allowlisted_documents() -> None:
    provider = PandapowerGuideProvider()

    index = provider.load()
    assert index
    assert all(set(document) == {"resource_id", "title", "sha256"} for document in index)
    opened = provider.open(index[0]["resource_id"])
    assert opened["sha256"] == index[0]["sha256"]
    assert opened["text"]


def test_guide_provider_rejects_unallowlisted_or_changed_documents(
    tmp_path: Path,
) -> None:
    guide = tmp_path / "guides"
    guide.mkdir()
    (guide / "SKILL.md").write_text("# Guide\n\nSafe guide.\n", encoding="utf-8")
    provider = PandapowerGuideProvider(guide)
    provider.load()

    with pytest.raises(KeyError):
        provider.open("not-allowlisted")
    (guide / "SKILL.md").write_text("# Changed\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="digest"):
        provider.open("overview")


def test_guide_provider_rejects_allowlisted_leaf_replaced_by_symlink(
    tmp_path: Path,
) -> None:
    guide = tmp_path / "guides"
    guide.mkdir()
    overview = guide / "SKILL.md"
    overview.write_text("# Guide\n\nSafe guide.\n", encoding="utf-8")
    provider = PandapowerGuideProvider(guide)
    outside = tmp_path / "outside.md"
    outside.write_text(overview.read_text(encoding="utf-8"), encoding="utf-8")
    overview.unlink()
    overview.symlink_to(outside)

    with pytest.raises(RuntimeError, match="symlink"):
        provider.open("overview")


def test_guide_provider_rejects_allowlisted_parent_replaced_by_symlink(
    tmp_path: Path,
) -> None:
    guide = tmp_path / "guides"
    references = guide / "references"
    references.mkdir(parents=True)
    (guide / "SKILL.md").write_text("# Guide\n", encoding="utf-8")
    (references / "safe.md").write_text("# Safe\n", encoding="utf-8")
    provider = PandapowerGuideProvider(guide)
    outside = tmp_path / "outside-references"
    outside.mkdir()
    (outside / "safe.md").write_text("# Safe\n", encoding="utf-8")
    references.rename(tmp_path / "original-references")
    references.symlink_to(outside, target_is_directory=True)

    with pytest.raises(RuntimeError, match="symlink"):
        provider.load()


def test_guide_provider_rejects_a_symlinked_root_and_path_traversal(
    tmp_path: Path,
) -> None:
    actual = tmp_path / "actual-guides"
    actual.mkdir()
    (actual / "SKILL.md").write_text("# Guide\n", encoding="utf-8")
    linked = tmp_path / "linked-guides"
    linked.symlink_to(actual, target_is_directory=True)

    with pytest.raises(RuntimeError, match="symlink"):
        PandapowerGuideProvider(linked)

    provider = PandapowerGuideProvider(actual)
    with pytest.raises(KeyError):
        provider.open("../SKILL")
