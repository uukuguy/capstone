from __future__ import annotations

import json
import os
import re
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from inventory_reference.artifacts import content_reference


_REFERENCE = re.compile(
    r"^inventory-(revision|context|result|evidence):sha256:([a-f0-9]{64})$"
)
_DIRECTORIES = {
    "revision": "revisions",
    "context": "contexts",
    "result": "results",
    "evidence": "facts",
}


class InventoryIntegrityError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class VerifiedArtifact:
    reference: str
    kind: Literal["context", "result", "evidence"]
    document: Mapping[str, Any]
    path: Path


@dataclass(frozen=True, slots=True)
class VerifiedReferenceSet:
    context: tuple[VerifiedArtifact, ...] = ()
    results: tuple[VerifiedArtifact, ...] = ()
    evidence: tuple[VerifiedArtifact, ...] = ()


@dataclass(frozen=True, slots=True)
class ReferenceDiagnostic:
    category: str
    severity: Literal["warning", "error"]
    reference: str
    message: str
    impact: str
    remediation: str


class InventoryArtifactAuthority:
    authority_id = "inventoryctl"

    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = Path(workspace_root)

    def admit(
        self,
        capability: str,
        result: Mapping[str, object],
        evidence_refs: tuple[str, ...],
    ) -> VerifiedReferenceSet:
        contexts: dict[str, VerifiedArtifact] = {}
        results: dict[str, VerifiedArtifact] = {}
        evidence: dict[str, VerifiedArtifact] = {}

        context_ref = result.get("context_ref")
        if isinstance(context_ref, str):
            contexts[context_ref] = self._verify_context(context_ref)

        result_ref = result.get("result_ref")
        if isinstance(result_ref, str):
            artifact = self.verify_result(result_ref)
            self._verify_returned_result(capability, result, artifact.document)
            results[result_ref] = artifact

        declared_evidence = list(evidence_refs)
        raw_evidence = result.get("evidence_refs")
        if isinstance(raw_evidence, list):
            declared_evidence.extend(
                item for item in raw_evidence if isinstance(item, str)
            )
        for reference in dict.fromkeys(declared_evidence):
            artifact = self._verify_evidence(reference)
            if isinstance(result_ref, str) and artifact.document.get(
                "result_ref"
            ) != result_ref:
                raise InventoryIntegrityError(
                    "inventory evidence is not linked to the returned result"
                )
            evidence[reference] = artifact

        if capability != "catalog.open" and not results:
            raise InventoryIntegrityError(
                "successful inventory result is missing result_ref"
            )
        return VerifiedReferenceSet(
            context=tuple(contexts.values()),
            results=tuple(results.values()),
            evidence=tuple(evidence.values()),
        )

    def verify_result(self, reference: str) -> VerifiedArtifact:
        path, document = self._read_artifact(reference, "result")
        context_ref = _required_string(document, "context_ref")
        revision_ref = _required_string(document, "revision_ref")
        context = self._verify_context(context_ref)
        if context.document.get("revision_ref") != revision_ref:
            raise InventoryIntegrityError(
                "inventory result revision does not match its context"
            )
        return VerifiedArtifact(reference, "result", document, path)

    def audit_answer_references(
        self,
        claim_evidence_refs: tuple[str, ...],
        result_refs: tuple[str, ...],
    ) -> tuple[ReferenceDiagnostic, ...]:
        diagnostics: list[ReferenceDiagnostic] = []
        valid_results: dict[str, VerifiedArtifact] = {}
        for reference in result_refs:
            try:
                valid_results[reference] = self.verify_result(reference)
            except RuntimeError as exc:
                diagnostics.append(
                    _diagnostic("invalid_result", reference, str(exc))
                )

        valid_evidence: dict[str, VerifiedArtifact] = {}
        for reference in claim_evidence_refs:
            try:
                valid_evidence[reference] = self._verify_evidence(reference)
            except RuntimeError as exc:
                diagnostics.append(
                    _diagnostic("invalid_evidence", reference, str(exc))
                )

        if diagnostics:
            return tuple(diagnostics)
        result_set = set(valid_results)
        for reference, artifact in valid_evidence.items():
            linked = artifact.document.get("result_ref")
            if linked not in result_set:
                diagnostics.append(
                    _diagnostic(
                        "unlinked_evidence",
                        reference,
                        "inventory evidence does not support a declared result",
                    )
                )
        return tuple(diagnostics)

    def _verify_context(self, reference: str) -> VerifiedArtifact:
        path, document = self._read_artifact(reference, "context")
        revision_ref = _required_string(document, "revision_ref")
        self._read_artifact(revision_ref, "revision")
        return VerifiedArtifact(reference, "context", document, path)

    def _verify_evidence(self, reference: str) -> VerifiedArtifact:
        path, document = self._read_artifact(reference, "evidence")
        result_ref = _required_string(document, "result_ref")
        context_ref = _required_string(document, "context_ref")
        revision_ref = _required_string(document, "revision_ref")
        result = self.verify_result(result_ref)
        if (
            result.document.get("context_ref") != context_ref
            or result.document.get("revision_ref") != revision_ref
        ):
            raise InventoryIntegrityError(
                "inventory evidence lineage does not match its result"
            )
        return VerifiedArtifact(reference, "evidence", document, path)

    def _read_artifact(
        self,
        reference: str,
        expected_kind: Literal["revision", "context", "result", "evidence"],
    ) -> tuple[Path, dict[str, object]]:
        matched = _REFERENCE.fullmatch(reference)
        if matched is None or matched.group(1) != expected_kind:
            raise InventoryIntegrityError(
                f"invalid inventory {expected_kind} reference"
            )
        digest = matched.group(2)
        descriptors: list[int] = []
        try:
            try:
                root = os.open(
                    self.workspace_root,
                    os.O_RDONLY
                    | os.O_DIRECTORY
                    | os.O_NOFOLLOW
                    | os.O_CLOEXEC,
                )
            except OSError as exc:
                raise InventoryIntegrityError(
                    "current-run inventory workspace root could not be opened without following links"
                ) from exc
            descriptors.append(root)
            evidence = _open_directory(root, "evidence", descriptors)
            kind_directory = _open_directory(
                evidence, _DIRECTORIES[expected_kind], descriptors
            )
            filename = f"{digest}.json"
            try:
                artifact = os.open(
                    filename,
                    os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
                    dir_fd=kind_directory,
                )
            except OSError as exc:
                raise InventoryIntegrityError(
                    f"inventory {expected_kind} reference is not in the current run or could not be opened without following links"
                ) from exc
            descriptors.append(artifact)
            before = os.fstat(artifact)
            if not stat.S_ISREG(before.st_mode):
                raise InventoryIntegrityError(
                    f"inventory {expected_kind} artifact is not a regular file"
                )
            chunks: list[bytes] = []
            while chunk := os.read(artifact, 65_536):
                chunks.append(chunk)
            after = os.fstat(artifact)
            named = os.stat(
                filename, dir_fd=kind_directory, follow_symlinks=False
            )
            if (
                (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
                != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
                or not stat.S_ISREG(named.st_mode)
                or (named.st_dev, named.st_ino) != (after.st_dev, after.st_ino)
            ):
                raise InventoryIntegrityError(
                    f"inventory {expected_kind} artifact changed while reading"
                )
            try:
                value = json.loads(b"".join(chunks).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise InventoryIntegrityError(
                    f"inventory {expected_kind} artifact is invalid JSON"
                ) from exc
            if not isinstance(value, dict):
                raise InventoryIntegrityError(
                    f"inventory {expected_kind} artifact must be an object"
                )
            if content_reference(expected_kind, value) != reference:
                raise InventoryIntegrityError(
                    f"inventory {expected_kind} artifact digest does not match reference"
                )
            path = (
                self.workspace_root
                / "evidence"
                / _DIRECTORIES[expected_kind]
                / filename
            )
            return path, value
        finally:
            for descriptor in reversed(descriptors):
                os.close(descriptor)

    @staticmethod
    def _verify_returned_result(
        capability: str,
        returned: Mapping[str, object],
        document: Mapping[str, object],
    ) -> None:
        if document.get("capability") != capability:
            raise InventoryIntegrityError(
                "returned result capability does not match its artifact"
            )
        for key in ("context_ref", "revision_ref"):
            if returned.get(key) != document.get(key):
                raise InventoryIntegrityError(
                    f"returned result {key} does not match its artifact"
                )
        data = document.get("data")
        if not isinstance(data, Mapping):
            raise InventoryIntegrityError(
                "inventory result artifact is missing data"
            )
        for key, value in data.items():
            if returned.get(key) != value:
                raise InventoryIntegrityError(
                    "returned result data does not match its artifact"
                )


def _open_directory(parent: int, name: str, descriptors: list[int]) -> int:
    try:
        descriptor = os.open(
            name,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=parent,
        )
    except OSError as exc:
        raise InventoryIntegrityError(
            "current-run inventory artifact directory could not be opened without following links"
        ) from exc
    descriptors.append(descriptor)
    return descriptor


def _required_string(document: Mapping[str, object], key: str) -> str:
    value = document.get(key)
    if not isinstance(value, str) or not value:
        raise InventoryIntegrityError(
            f"inventory artifact is missing {key}"
        )
    return value


def _diagnostic(
    category: str, reference: str, message: str
) -> ReferenceDiagnostic:
    return ReferenceDiagnostic(
        category=category,
        severity="error",
        reference=reference,
        message=message,
        impact="The answer cannot use this inventory claim as current-run business truth.",
        remediation="Run the inventory capability again and cite its admitted current-run references.",
    )
