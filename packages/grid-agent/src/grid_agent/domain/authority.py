from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol


class VerifiedArtifact(Protocol):
    @property
    def reference(self) -> str: ...

    @property
    def document(self) -> Mapping[str, Any]: ...

    @property
    def path(self) -> Path: ...


class VerifiedReferenceSet(Protocol):
    @property
    def context(self) -> tuple[VerifiedArtifact, ...]: ...

    @property
    def results(self) -> tuple[VerifiedArtifact, ...]: ...

    @property
    def evidence(self) -> tuple[VerifiedArtifact, ...]: ...


class ArtifactAuthority(Protocol):
    authority_id: str
    workspace_root: Path

    def admit(
        self,
        capability: str,
        result: Mapping[str, object],
        evidence_refs: tuple[str, ...],
    ) -> VerifiedReferenceSet: ...

    def verify_result(self, reference: str) -> VerifiedArtifact: ...

    def audit_answer_references(
        self,
        claim_evidence_refs: tuple[str, ...],
        result_refs: tuple[str, ...],
    ) -> tuple[object, ...]: ...
