from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path


class InventoryAuthorityNotImplementedError(RuntimeError):
    pass


class InventoryArtifactAuthority:
    authority_id = "inventoryctl"

    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = Path(workspace_root)

    def admit(
        self,
        capability: str,
        result: Mapping[str, object],
        evidence_refs: tuple[str, ...],
    ) -> object:
        raise InventoryAuthorityNotImplementedError(
            "inventory artifact admission is implemented by C-H004"
        )

    def verify_result(self, reference: str) -> object:
        raise InventoryAuthorityNotImplementedError(
            "inventory result verification is implemented by C-H004"
        )

    def audit_answer_references(
        self,
        claim_evidence_refs: tuple[str, ...],
        result_refs: tuple[str, ...],
    ) -> tuple[object, ...]:
        raise InventoryAuthorityNotImplementedError(
            "inventory answer audit is implemented by C-H004"
        )
