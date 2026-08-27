from pathlib import Path

import pytest

from grid_agent.domain.contracts import (
    CapabilityContractSourceError,
    FilesystemCapabilityContractSource,
)


def test_filesystem_contract_source_loads_sorted_json(tmp_path: Path) -> None:
    root = tmp_path / "contracts"
    root.mkdir()
    (root / "b.json").write_text('{"id":"b.read"}', encoding="utf-8")
    (root / "a.json").write_text('{"id":"a.read"}', encoding="utf-8")

    documents = FilesystemCapabilityContractSource(root).load()

    assert [document["id"] for document in documents] == ["a.read", "b.read"]


def test_filesystem_contract_source_rejects_invalid_or_empty_roots(
    tmp_path: Path,
) -> None:
    with pytest.raises(CapabilityContractSourceError, match="no capability contracts"):
        FilesystemCapabilityContractSource(tmp_path / "missing").load()


@pytest.mark.parametrize("contents", ["not json", "[]"])
def test_filesystem_contract_source_rejects_invalid_documents(
    tmp_path: Path, contents: str
) -> None:
    root = tmp_path / "contracts"
    root.mkdir()
    (root / "invalid.json").write_text(contents, encoding="utf-8")

    with pytest.raises(CapabilityContractSourceError, match="capability contract"):
        FilesystemCapabilityContractSource(root).load()


def test_filesystem_contract_source_wraps_malformed_utf8(tmp_path: Path) -> None:
    root = tmp_path / "contracts"
    root.mkdir()
    (root / "invalid.json").write_bytes(b"\xff")

    with pytest.raises(CapabilityContractSourceError, match="capability contract"):
        FilesystemCapabilityContractSource(root).load()
