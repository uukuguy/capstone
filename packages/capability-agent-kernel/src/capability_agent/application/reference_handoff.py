"""Application-controlled transfer of verified, opaque authority references."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Protocol, cast

from capability_agent.application.composition import PreparedBinding
from capability_agent.application.context_models import ContextEventDraft
from capability_agent.application.context_store import ApplicationContextStore
from capability_agent.application.profile import ApplicationProfile, ReferenceGrant
from capability_agent.application.workspace import ApplicationWorkspace
from capability_agent.trajectory.canonical import canonical_json_bytes


class ReferenceHandoffError(RuntimeError):
    """A reference cannot cross the declared application binding boundary."""


@dataclass(frozen=True, slots=True)
class VerifiedTransferReference:
    reference: str
    revision_digest: str
    run_id: str
    authority_id: str


@dataclass(frozen=True, slots=True)
class ReferenceHandoffReceipt:
    receipt_ref: str
    run_id: str
    source_binding_id: str
    target_binding_id: str
    reference: str
    reference_kind: str
    revision_digest: str
    authority_id: str
    purpose: str
    capability_family: str

    def document(self) -> dict[str, str]:
        return {
            "schema": "capability-agent-reference-handoff/1.0",
            "run_id": self.run_id,
            "source_binding_id": self.source_binding_id,
            "target_binding_id": self.target_binding_id,
            "reference": self.reference,
            "reference_kind": self.reference_kind,
            "revision_digest": self.revision_digest,
            "authority_id": self.authority_id,
            "purpose": self.purpose,
            "capability_family": self.capability_family,
        }


class TransferSource(Protocol):
    def verify_transfer_reference(
        self, reference: str, kind: str
    ) -> VerifiedTransferReference: ...


class TransferTarget(Protocol):
    def admit_handoff(
        self, receipt: ReferenceHandoffReceipt, *, source_workspace: Path
    ) -> None: ...


class ReferenceHandoffService:
    """Issue and consume receipts only through trusted application assembly."""

    def __init__(
        self,
        profile: ApplicationProfile,
        workspace: ApplicationWorkspace,
        store: ApplicationContextStore,
        bindings: Mapping[str, PreparedBinding],
    ) -> None:
        if store.workspace != workspace:
            raise ReferenceHandoffError("context store belongs to another run")
        self.profile = profile
        self.workspace = workspace
        self.store = store
        self.bindings = bindings

    def invoke_target(
        self, *, source_binding_id: str, target_binding_id: str,
        reference: str, reference_kind: str, purpose: str,
        capability: str, arguments: Mapping[str, object],
    ) -> tuple[dict[str, object], ReferenceHandoffReceipt]:
        """Record a grant decision before asking the target authority to admit it."""

        grant = self._grant(
            source_binding_id, target_binding_id, reference_kind,
            purpose, capability,
        )
        if not isinstance(reference, str) or not reference:
            raise ReferenceHandoffError("reference is invalid")
        if "reference" in arguments or "handoff_ref" in arguments:
            raise ReferenceHandoffError("handoff arguments are application-owned")
        source = self._binding(source_binding_id)
        target = self._binding(target_binding_id)
        if not any(
            item.get("id") == capability
            for item in target.runtime.capability_documents
        ):
            raise ReferenceHandoffError("target capability is not published")
        verified = self._verify_source(source, reference, reference_kind)
        if verified.run_id != self.workspace.run_id or verified.reference != reference:
            raise ReferenceHandoffError("reference belongs to another run")
        if not verified.revision_digest or not verified.authority_id:
            raise ReferenceHandoffError("source authority returned incomplete revision identity")
        document = {
            "schema": "capability-agent-reference-handoff/1.0",
            "run_id": self.workspace.run_id,
            "source_binding_id": source_binding_id,
            "target_binding_id": target_binding_id,
            "reference": reference,
            "reference_kind": reference_kind,
            "revision_digest": verified.revision_digest,
            "authority_id": verified.authority_id,
            "purpose": purpose,
            "capability_family": grant.capability_family,
        }
        receipt = ReferenceHandoffReceipt(
            receipt_ref=_receipt_ref(document), run_id=self.workspace.run_id,
            source_binding_id=source_binding_id,
            target_binding_id=target_binding_id, reference=reference,
            reference_kind=reference_kind,
            revision_digest=verified.revision_digest,
            authority_id=verified.authority_id,
            purpose=purpose, capability_family=grant.capability_family,
        )
        self.store.append(ContextEventDraft(
            event_type="decision.recorded",
            payload={
                "decision": "reference-handoff", "receipt_ref": receipt.receipt_ref,
                "receipt": document,
            },
        ))
        self.verify_receipt(receipt)
        try:
            cast(TransferTarget, target.runtime.authority).admit_handoff(
                receipt, source_workspace=self.workspace.domain_roots[source_binding_id]
            )
        except Exception as exc:
            raise ReferenceHandoffError("target authority rejected handoff") from exc
        passed = dict(arguments)
        passed.update(reference=reference, handoff_ref=receipt.receipt_ref)
        return target.endpoint.executor.invoke(capability, passed), receipt

    def verify_receipt(self, receipt: ReferenceHandoffReceipt) -> ReferenceHandoffReceipt:
        if not isinstance(receipt, ReferenceHandoffReceipt):
            raise ReferenceHandoffError("handoff receipt has an invalid type")
        document = receipt.document()
        if receipt.run_id != self.workspace.run_id or receipt.receipt_ref != _receipt_ref(document):
            raise ReferenceHandoffError("handoff receipt integrity failed")
        if ReferenceGrant(
            receipt.source_binding_id, receipt.target_binding_id,
            receipt.reference_kind, receipt.purpose, receipt.capability_family,
        ) not in self.profile.reference_grants:
            raise ReferenceHandoffError("handoff grant is absent")
        try:
            _state, events = ApplicationContextStore.replay_events(self.workspace)
        except Exception as exc:
            raise ReferenceHandoffError("handoff decision cannot be replayed") from exc
        if not any(
            event.event_type == "decision.recorded"
            and event.payload.get("decision") == "reference-handoff"
            and event.payload.get("receipt_ref") == receipt.receipt_ref
            and dict(event.payload.get("receipt", {})) == document
            for event in events
        ):
            raise ReferenceHandoffError("handoff decision is absent")
        verified = self._verify_source(
            self._binding(receipt.source_binding_id),
            receipt.reference, receipt.reference_kind,
        )
        if (
            verified.run_id != receipt.run_id
            or verified.reference != receipt.reference
            or verified.revision_digest != receipt.revision_digest
            or verified.authority_id != receipt.authority_id
        ):
            raise ReferenceHandoffError("handoff source revision changed")
        return receipt

    def _binding(self, binding_id: str) -> PreparedBinding:
        try:
            return self.bindings[binding_id]
        except KeyError:
            raise ReferenceHandoffError("handoff binding is unavailable") from None

    def _verify_source(
        self, source: PreparedBinding, reference: str, kind: str
    ) -> VerifiedTransferReference:
        try:
            verified = cast(TransferSource, source.runtime.authority).verify_transfer_reference(reference, kind)
        except Exception as exc:
            raise ReferenceHandoffError("source authority rejected reference") from exc
        if not isinstance(verified, VerifiedTransferReference):
            raise ReferenceHandoffError("source authority returned invalid verification")
        return verified

    def _grant(
        self, source: str, target: str, kind: str, purpose: str, capability: str
    ) -> ReferenceGrant:
        for grant in self.profile.reference_grants:
            if (
                grant.source_binding_id == source
                and grant.target_binding_id == target
                and grant.reference_kind == kind
                and grant.purpose == purpose
                and capability.startswith(grant.capability_family + ".")
            ):
                return grant
        raise ReferenceHandoffError("no reference grant covers this target capability")


def _receipt_ref(document: Mapping[str, str]) -> str:
    return "handoff:sha256:" + sha256(canonical_json_bytes(dict(document))).hexdigest()
