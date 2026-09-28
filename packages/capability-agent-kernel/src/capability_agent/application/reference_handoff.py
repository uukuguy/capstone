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
        receipt = self.prepare_handoff(
            source_binding_id=source_binding_id,
            target_binding_id=target_binding_id,
            reference=reference,
            reference_kind=reference_kind,
            purpose=purpose,
            capability=capability,
        )
        target = self._binding(target_binding_id)
        passed = dict(arguments)
        passed.update(reference=reference, handoff_ref=receipt.receipt_ref)
        return target.endpoint.executor.invoke(capability, passed), receipt

    def prepare_handoff(
        self, *, source_binding_id: str, target_binding_id: str,
        reference: str, reference_kind: str, purpose: str,
        capability: str,
    ) -> ReferenceHandoffReceipt:
        """Issue and admit an application-owned handoff without executing a capability.

        Provider transports use this before the model calls a target-domain
        tool.  The model never receives authority to mint the receipt; the
        application creates it after the source authority has returned a
        verified current-run reference.
        """
        grant = self._grant(
            source_binding_id, target_binding_id, reference_kind,
            purpose, capability,
        )
        if not isinstance(reference, str) or not reference:
            raise ReferenceHandoffError("reference is invalid")
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
        return receipt

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
        if resolve_handoff_receipt(self.workspace, receipt.receipt_ref) != receipt:
            raise ReferenceHandoffError("handoff decision differs from its receipt")
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


def resolve_handoff_receipt(
    workspace: ApplicationWorkspace | Path, receipt_ref: str,
    *, expected_run_id: str | None = None,
) -> ReferenceHandoffReceipt:
    """Replay an application-owned decision and recover one immutable receipt."""
    try:
        state, events = ApplicationContextStore.replay_events(workspace)
    except Exception as exc:
        raise ReferenceHandoffError("handoff decision cannot be replayed") from exc
    for event in events:
        if (
            event.event_type != "decision.recorded"
            or event.payload.get("decision") != "reference-handoff"
            or event.payload.get("receipt_ref") != receipt_ref
        ):
            continue
        raw = event.payload.get("receipt")
        if not isinstance(raw, Mapping):
            raise ReferenceHandoffError("handoff decision receipt is invalid")
        document = dict(raw)
        fields = (
            "run_id", "source_binding_id", "target_binding_id", "reference",
            "reference_kind", "revision_digest", "authority_id", "purpose",
            "capability_family",
        )
        if (
            set(document) != {*fields, "schema"}
            or document.get("schema") != "capability-agent-reference-handoff/1.0"
            or any(not isinstance(document.get(field), str) or not document[field] for field in fields)
            or document["run_id"] != state.run_id
            or (expected_run_id is not None and document["run_id"] != expected_run_id)
            or receipt_ref != _receipt_ref(document)
        ):
            raise ReferenceHandoffError("handoff decision receipt integrity failed")
        return ReferenceHandoffReceipt(receipt_ref, *(document[field] for field in fields))
    raise ReferenceHandoffError("handoff decision is absent")
