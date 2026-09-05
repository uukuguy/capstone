from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path

import pytest

from inventory_domain.resources import InventoryResourceSet


def _copy_guides(tmp_path: Path) -> Path:
    return Path(shutil.copytree(InventoryResourceSet.load().guide_root, tmp_path / "guides"))


def test_packaged_guides_are_allowlisted_and_digest_bound():
    from inventory_domain.guide import InventoryGuideProvider

    provider = InventoryGuideProvider()
    index = provider.load()
    assert {item["resource_id"] for item in index} == {
        "overview", "capability-map", "evidence-and-recovery"
    }
    for item in index:
        document = provider.open(item["resource_id"])
        assert hashlib.sha256(document["text"].encode()).hexdigest() == item["sha256"]
        assert document["sha256"] == item["sha256"]
        assert document["text"].strip()


@pytest.mark.parametrize("resource_id", ["../policy/system-policy.md", "unknown", "SKILL.md", ""])
def test_unlisted_guide_is_rejected(resource_id):
    from capability_agent.tools.guide import GuideNotFound
    from inventory_domain.guide import InventoryGuideProvider

    with pytest.raises(GuideNotFound):
        InventoryGuideProvider().open(resource_id)


def test_modified_guide_fails_open_and_index(tmp_path):
    from inventory_domain.guide import InventoryGuideProvider

    root = _copy_guides(tmp_path)
    provider = InventoryGuideProvider(root)
    (root / "SKILL.md").write_text("# changed", encoding="utf-8")
    with pytest.raises(RuntimeError, match="digest"):
        provider.open("overview")
    with pytest.raises(RuntimeError, match="digest"):
        provider.load()


@pytest.mark.parametrize("kind", ["root", "directory", "file", "fifo", "large", "invalid_utf8"])
def test_untrusted_layout_or_document_rejected(tmp_path, kind):
    from inventory_domain.guide import InventoryGuideProvider

    root = _copy_guides(tmp_path)
    target = root / "SKILL.md"
    if kind == "root":
        linked = tmp_path / "linked"
        linked.symlink_to(root, target_is_directory=True)
        root = linked
    elif kind == "directory":
        (root / "references").rename(root / "saved")
        (root / "references").symlink_to(root / "saved", target_is_directory=True)
    elif kind == "file":
        target.rename(root / "saved.md")
        target.symlink_to(root / "saved.md")
    elif kind == "fifo":
        target.unlink()
        os.mkfifo(target)
    elif kind == "large":
        target.write_bytes(b"x" * (64 * 1024 + 1))
    else:
        target.write_bytes(b"\xff")
    with pytest.raises(RuntimeError):
        InventoryGuideProvider(root)


def test_policy_provider_uses_captured_packaged_text(tmp_path):
    from inventory_domain.guide import InventoryPolicyProvider

    source = InventoryResourceSet.load().system_policy_path
    path = tmp_path / "system-policy.md"
    shutil.copyfile(source, path)
    provider = InventoryPolicyProvider(path)
    assert provider.load() == source.read_text(encoding="utf-8")
    path.write_text("changed", encoding="utf-8")
    with pytest.raises(RuntimeError, match="digest"):
        provider.load()
