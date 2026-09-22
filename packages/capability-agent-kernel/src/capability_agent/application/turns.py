"""Domain-neutral turn and answer commit lifecycle.

The controller owns the parts of a turn that must be identical for every
business domain: nonce binding, active-turn fencing, draft durability, and the
final answer commit.  Reference meaning remains injected through each
binding's authority and answer policy.
"""

from __future__ import annotations

import math
import os
import secrets
import time
from collections.abc import Iterable, Mapping, Sequence, Set
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal, cast

from capability_agent.application.context_models import ContextEventDraft
from capability_agent.application.context_store import ApplicationContextStore
from capability_agent.application.errors import (
    AnswerCommitError,
    AuthorityIntegrityError,
    CapabilityAgentError,
)
from capability_agent.application.workspace import ApplicationWorkspace
from capability_agent.domain.answer_admission import AnswerAdmissionDecision, AnswerAdmissionInput, AnswerAdmissionPolicy
from capability_agent.domain.policy import AnswerEvidencePolicy
from capability_agent.trajectory.answers import (
    AnswerClaim,
    AnswerReferencePolicy,
    AnswerSubmission,
    NeutralAnswerReferencePolicy,
    validate_submission,
)
from capability_agent.trajectory.canonical import canonical_json_bytes
from capability_agent.trajectory.events import (
    Causation,
    EventDraft,
    EventRefs,
    EventSource,
    RunScope,
)


class StaleAnswerDraftError(AnswerCommitError):
    """Raised when an answer handle no longer owns the active turn."""


class ActiveTurnInProgressError(CapabilityAgentError):
    """Raised when a new turn is requested while another turn is active."""


@dataclass(frozen=True, slots=True)
class ActiveTurnHandle:
    ordinal: int
    turn_id: str
    instruction: str
    instruction_sha256: str
    turn_nonce: str
    started_monotonic: float


@dataclass(frozen=True, slots=True)
class FinalizedTurn:
    """A controller-committed answer, qualified by its selected bindings."""

    turn_id: str
    status: Literal["success", "limited", "failed"]
    answer_output: str
    answer_path: Path | None
    answer_ref: str | None
    admission_ref: str | None
    referenced_bindings: tuple[str, ...]
    result_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    submission: AnswerSubmission | None
    audit_diagnostics: tuple[object, ...]
    admission: AnswerAdmissionDecision | None
    error: str | None
    post_commit_diagnostic_codes: tuple[str, ...] = ()


class _AuthorityReferenceVerifier:
    """Adapt one public domain authority to the trajectory verifier SPI."""

    def __init__(self, authority: object) -> None:
        self._authority = authority

    def verify(self, reference: str, group: str) -> object:
        if group == "result_refs":
            verifier = getattr(self._authority, "verify_result", None)
            if not callable(verifier):
                raise AuthorityIntegrityError("binding authority cannot verify results")
            verified = verifier(reference)
            _validate_verified_reference(self._authority, reference, verified)
            return verified
        if group == "claim_evidence_refs":
            verifier = getattr(self._authority, "verify_evidence", None)
            if callable(verifier):
                verified = verifier(reference)
                _validate_verified_reference(self._authority, reference, verified)
                return verified
            # The generic authority contract intentionally requires only
            # verify_result.  Its answer audit is the public evidence verifier
            # for authorities that expose no separate evidence method.
            if callable(getattr(self._authority, "audit_answer_references", None)):
                return object()
            raise AuthorityIntegrityError("binding authority cannot verify evidence")
        raise AuthorityIntegrityError("unsupported answer reference group")


def _validate_verified_reference(
    authority: object, reference: str, verified: object
) -> None:
    """Ensure an authority did not verify a different or foreign artifact.

    The public authority SPI returns an opaque verified artifact.  Concrete
    domains normally expose ``reference`` and ``path`` on that object, but a
    Kernel test double may intentionally return an opaque token.  When the
    optional identity fields are present, validate them here so a malicious
    or misconfigured authority cannot substitute another run's artifact.
    """

    verified_reference = getattr(verified, "reference", None)
    if verified_reference is not None and verified_reference != reference:
        raise AuthorityIntegrityError("binding authority verified another reference")
    path = getattr(verified, "path", None)
    if path is None:
        return
    if not isinstance(path, Path):
        raise AuthorityIntegrityError("binding authority returned an invalid artifact path")
    root = getattr(authority, "workspace_root", None)
    if not isinstance(root, Path):
        raise AuthorityIntegrityError("binding authority workspace is invalid")
    try:
        path.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        raise AuthorityIntegrityError("binding artifact is outside this run") from None


class TurnController:
    """Fence, validate, and commit one answer for declared domain bindings."""

    def __init__(
        self,
        *,
        store: ApplicationContextStore,
        workspace: ApplicationWorkspace,
        bindings: Mapping[str, object],
        recorder: object | None = None,
        allowed_refs: Set[str] | Mapping[str, Iterable[str]] | None = None,
        reference_policy: AnswerReferencePolicy | None = None,
    ) -> None:
        self._store = store
        self._workspace = workspace
        self._bindings = dict(bindings)
        self._recorder = recorder
        self._reference_policy = reference_policy or NeutralAnswerReferencePolicy()
        self._allowed_refs, self._allowed_ref_owners = _normalize_allowed_refs(
            allowed_refs
        )
        self._validate_bindings()

    @property
    def store(self) -> ApplicationContextStore:
        return self._store

    @property
    def workspace(self) -> ApplicationWorkspace:
        return self._workspace

    def start(self, ordinal: int, instruction: str) -> ActiveTurnHandle:
        if type(ordinal) is not int or ordinal < 1:
            raise AnswerCommitError("turn ordinal must be a positive integer")
        if not isinstance(instruction, str) or not instruction.strip():
            raise AnswerCommitError("turn instruction must not be empty")
        if self._store.snapshot.core.active_turn is not None:
            raise ActiveTurnInProgressError("active turn already exists")

        turn_nonce = secrets.token_urlsafe(32)
        instruction_sha256 = _sha256_text(instruction)
        handle = ActiveTurnHandle(
            ordinal=ordinal,
            turn_id=f"{self._workspace.run_id}-t{ordinal:03d}",
            instruction=instruction,
            instruction_sha256=instruction_sha256,
            turn_nonce=turn_nonce,
            started_monotonic=time.monotonic(),
        )
        if any(
            isinstance(turn, Mapping) and turn.get("turn_id") == handle.turn_id
            for turn in self._store.snapshot.core.turns
        ):
            raise AnswerCommitError("turn identifier was already completed")
        active_path = self._active_turn_path
        draft_path = self._active_answer_draft_path
        old_active = _read_file_state(active_path)
        old_draft = _read_file_state(draft_path)
        active_payload = {
            "schema_version": "capability-agent-active-turn/1.0",
            "run_id": self._workspace.run_id,
            "ordinal": ordinal,
            "turn_id": handle.turn_id,
            "instruction": instruction,
            "instruction_sha256": instruction_sha256,
            "turn_nonce": turn_nonce,
            "started_monotonic": handle.started_monotonic,
        }
        try:
            _remove_if_present(draft_path)
            _write_json_atomic(active_path, active_payload)
            self._store.append(
                ContextEventDraft(
                    event_type="turn.started",
                    turn_id=handle.turn_id,
                    payload={
                        "ordinal": ordinal,
                        "instruction": instruction,
                        "instruction_sha256": instruction_sha256,
                        "nonce_sha256": _sha256_text(turn_nonce),
                    },
                )
            )
        except BaseException:
            _restore_file_state(active_path, old_active)
            _restore_file_state(draft_path, old_draft)
            raise

        self._record_turn_started(handle)
        return handle

    def submit(
        self,
        handle: ActiveTurnHandle,
        *,
        answer_output: str,
        referenced_bindings: Iterable[str] = (),
        result_refs: Iterable[str] = (),
        evidence_refs: Iterable[str] = (),
        claims: Iterable[AnswerClaim | Mapping[str, object]] = (),
        duration_seconds: float,
        submission_id: str | None = None,
    ) -> FinalizedTurn:
        """Validate and commit an answer without allowing cross-binding refs."""

        self._require_active_turn(handle)
        if not isinstance(answer_output, str) or not answer_output.strip():
            raise AnswerCommitError("answer output must not be empty")
        duration = _duration(duration_seconds)
        selected = _portable_binding_ids(referenced_bindings)
        results = _string_refs(result_refs, "result_refs")
        evidence = _string_refs(evidence_refs, "evidence_refs")
        if not selected and (results or evidence):
            if len(self._bindings) == 1:
                selected = (next(iter(self._bindings)),)
            else:
                raise AnswerCommitError(
                    "references require explicitly selected bindings"
                )
        unknown_bindings = set(selected).difference(self._bindings)
        if unknown_bindings:
            raise AnswerCommitError("answer references an undeclared binding")

        try:
            claim_values = tuple(claims)
        except TypeError:
            raise AnswerCommitError("answer claims are invalid") from None
        if submission_id is None:
            submission_id = handle.turn_id
        if not isinstance(submission_id, str) or not submission_id:
            raise AnswerCommitError("submission identifier is invalid")

        owners = self._current_turn_reference_owners(handle.turn_id)
        self._assert_current_turn_references(
            (*results, *evidence), selected, owners
        )
        try:
            claims_by_binding = self._claims_by_binding(
                claim_values, owners, selected
            )
        except AnswerCommitError:
            raise
        except Exception:
            raise AnswerCommitError("answer claims are invalid") from None

        # Evaluation annotates the answer; it cannot rewrite or veto it.
        # Reference integrity validation remains on the primary path above.
        try:
            admission = self._admit_answer(
                handle=handle, answer_output=answer_output, selected=selected,
                results=results, evidence=evidence, owners=owners,
            )
        except Exception:
            admission = AnswerAdmissionDecision(
                mode="limited", assurance="limited", answer_output=answer_output,
                diagnostic_codes=("answer_evaluation_unavailable",),
            )

        validated_by_binding: list[AnswerSubmission] = []
        audit_diagnostics: list[object] = []
        for binding_id in selected:
            binding = self._bindings[binding_id]
            authority = _binding_authority(binding)
            policy = _binding_answer_policy(binding)
            try:
                self._validate_authority_identity(binding_id, binding, authority)
            except AnswerCommitError:
                raise
            except CapabilityAgentError:
                raise AnswerCommitError(
                    "answer evidence validation failed for the selected binding"
                ) from None
            binding_results = tuple(ref for ref in results if owners.get(ref, binding_id) == binding_id)
            binding_evidence = tuple(
                ref for ref in evidence if owners.get(ref, binding_id) == binding_id
            )
            binding_claims = claims_by_binding.get(binding_id, ())
            try:
                submission = validate_submission(
                    {
                        "submission_id": submission_id,
                        "answer_output": answer_output,
                        "result_refs": binding_results,
                        "claim_evidence_refs": binding_evidence,
                        "claims": binding_claims,
                        "referenced_bindings": (binding_id,),
                    },
                    _AuthorityReferenceVerifier(authority),
                    frozenset((*binding_results, *binding_evidence)),
                    reference_policy=self._reference_policy,
                )
                for claim in submission.claims:
                    policy.validate_claim(claim)
                policy.validate_submission(submission)
                diagnostics = _audit_binding_references(
                    authority,
                    binding_evidence,
                    binding_results,
                )
            except AnswerCommitError:
                raise
            except CapabilityAgentError:
                raise AnswerCommitError(
                    "answer evidence validation failed for the selected binding"
                ) from None
            except Exception:
                raise AnswerCommitError(
                    "answer evidence validation failed for the selected binding"
                ) from None
            validated_by_binding.append(submission)
            audit_diagnostics.extend(diagnostics)

        # The per-binding submissions contain the same answer text but disjoint
        # references.  The committed answer stores the composite view.
        composite_submission = AnswerSubmission(
            submission_id=submission_id,
            answer_output=answer_output,
            result_refs=results,
            claim_evidence_refs=evidence,
            claims=tuple(
                claim
                for submission in validated_by_binding
                for claim in submission.claims
            ),
            referenced_bindings=selected,
        )
        draft = {
            "run_id": self._workspace.run_id,
            "turn_id": handle.turn_id,
            "turn_nonce": handle.turn_nonce,
            "submission_id": composite_submission.submission_id,
            "answer_output": answer_output,
            "referenced_bindings": list(selected),
            "result_refs": list(results),
            "claim_evidence_refs": list(evidence),
            "claims": [claim.model_dump(mode="json") for claim in composite_submission.claims],
        }
        raw_draft = canonical_json_bytes(draft)
        turn_path = self._turn_path(handle)
        archived_draft_path = turn_path / "answer-draft.json"
        answer_path = turn_path / "answer.json"
        answer_payload = {
            "schema": "capability-agent-answer/1.0",
            "run_id": self._workspace.run_id,
            "turn_id": handle.turn_id,
            "submission_id": composite_submission.submission_id,
            "answer_output": answer_output,
            "referenced_bindings": list(selected),
            "result_refs": list(results),
            "evidence_refs": list(evidence),
            "claims": [claim.model_dump(mode="json") for claim in composite_submission.claims],
        }
        answer_bytes = canonical_json_bytes(answer_payload)
        answer_ref = "answer:sha256:" + sha256(answer_bytes).hexdigest()
        admission_path = turn_path / "answer-admission.json"
        admission_bytes = canonical_json_bytes({
            "schema": ("capability-agent-answer-admission/1.1" if admission.assurance == "guide_access_verified" else "capability-agent-answer-admission/1.0"),
            "run_id": self._workspace.run_id,
            "turn_id": handle.turn_id,
            "answer_ref": answer_ref,
            "mode": admission.mode,
            "assurance": admission.assurance,
            "diagnostic_codes": list(admission.diagnostic_codes),
        })
        admission_ref = "admission:sha256:" + sha256(admission_bytes).hexdigest()
        artifact_states = tuple(
            (path, _read_file_state(path))
            for path in (
                self._active_answer_draft_path,
                archived_draft_path,
                answer_path,
                admission_path,
            )
        )

        answer_event = ContextEventDraft(
            event_type="answer.submitted",
            turn_id=handle.turn_id,
            payload={
                "submission_id": composite_submission.submission_id,
                "turn_id": handle.turn_id,
                "turn_nonce_sha256": _sha256_text(handle.turn_nonce),
                "answer_ref": answer_ref,
                "answer_path": str(answer_path.relative_to(self._workspace.root)),
                "answer_sha256": sha256(answer_bytes).hexdigest(),
                "answer_draft_path": str(
                    archived_draft_path.relative_to(self._workspace.root)
                ),
                "admission_ref": admission_ref,
                "admission_path": str(admission_path.relative_to(self._workspace.root)),
                "referenced_bindings": list(selected),
                "result_refs": list(results),
                "claim_evidence_refs": list(evidence),
            },
        )
        completed_event = ContextEventDraft(
            event_type="turn.completed",
            turn_id=handle.turn_id,
            payload={
                "status": "success",
                "answer_ref": answer_ref,
                "answer_path": str(answer_path.relative_to(self._workspace.root)),
                "answer_sha256": sha256(answer_bytes).hexdigest(),
                "duration_seconds": duration,
                "referenced_bindings": list(selected),
                "result_refs": list(results),
                "evidence_refs": list(evidence),
                "admission_ref": admission_ref,
            },
        )
        self._preflight_context_events((answer_event, completed_event))
        try:
            _write_bytes_atomic(self._active_answer_draft_path, raw_draft)
            _write_bytes_atomic(archived_draft_path, raw_draft)
            _write_bytes_atomic(answer_path, answer_bytes)
            _write_bytes_atomic(admission_path, admission_bytes)
            context_events = self._store.append_many((answer_event, completed_event))
            if len(context_events) != 2:
                raise RuntimeError("context store returned an invalid transaction")
            answer_context_event = context_events[0]
        except BaseException as error:
            for path, state in artifact_states:
                try:
                    _restore_file_state(path, state)
                except Exception:
                    # A failed rollback leaves the store unavailable and the
                    # original sanitized failure is still the useful signal.
                    pass
            if isinstance(error, AnswerCommitError):
                raise
            if not isinstance(error, Exception):
                raise
            raise AnswerCommitError("answer commit persistence failed") from None

        post_commit_diagnostics: list[str] = []
        try:
            self._record_answer_committed(
                handle,
                composite_submission,
                answer_ref,
                answer_context_event,
            )
        except Exception:
            post_commit_diagnostics.append("trajectory_recording_unavailable")
        cleanup_failed = False
        for path in (self._active_answer_draft_path, self._active_turn_path):
            try:
                _remove_if_present(path)
            except Exception:
                cleanup_failed = True
        if cleanup_failed:
            post_commit_diagnostics.append("turn_cleanup_unavailable")
        return FinalizedTurn(
            turn_id=handle.turn_id,
            status="success",
            answer_output=answer_output,
            answer_path=answer_path,
            answer_ref=answer_ref,
            admission_ref=admission_ref,
            referenced_bindings=selected,
            result_refs=results,
            evidence_refs=evidence,
            submission=composite_submission,
            audit_diagnostics=tuple(audit_diagnostics),
            admission=admission,
            error=None,
            post_commit_diagnostic_codes=tuple(post_commit_diagnostics),
        )

    def fail(
        self,
        handle: ActiveTurnHandle,
        *,
        error: str,
        duration_seconds: float,
        publish_answer: bool = False,
    ) -> FinalizedTurn:
        self._require_active_turn(handle)
        duration = _duration(duration_seconds)
        message = error.strip() if isinstance(error, str) and error.strip() else "turn failed"
        limitation_ref = "limitation:sha256:" + _sha256_text(
            f"{handle.turn_id}\n{message}"
        )
        try:
            self._store.append_many(
                (
                    ContextEventDraft(
                        event_type="limitation.recorded",
                        turn_id=handle.turn_id,
                        payload={
                            "limitation_ref": limitation_ref,
                            "message": message,
                            "refs": [],
                        },
                    ),
                    ContextEventDraft(
                        event_type="turn.completed",
                        turn_id=handle.turn_id,
                        payload={
                            "status": "failed",
                            "answer_path": None,
                            "answer_sha256": None,
                            "duration_seconds": duration,
                        },
                    ),
                )
            )
        except BaseException as persistence_error:
            if not isinstance(persistence_error, Exception):
                raise
            raise AnswerCommitError("turn failure persistence failed") from None
        if publish_answer:
            answer_path = self._turn_path(handle) / "answer.json"
            payload = {
                "schema": "capability-agent-answer/1.0",
                "run_id": self._workspace.run_id,
                "turn_id": handle.turn_id,
                "answer_output": f"execution limitation: {message}",
                "referenced_bindings": [],
                "result_refs": [],
                "evidence_refs": [],
            }
            _write_bytes_atomic(answer_path, canonical_json_bytes(payload))
        else:
            answer_path = None
        _remove_if_present(self._active_answer_draft_path)
        _remove_if_present(self._active_turn_path)
        self._record_turn_failed(handle, message, duration)
        return FinalizedTurn(
            turn_id=handle.turn_id,
            status="failed",
            answer_output=f"execution limitation: {message}",
            answer_path=answer_path,
            answer_ref=None,
            admission_ref=None,
            referenced_bindings=(),
            result_refs=(),
            evidence_refs=(),
            submission=None,
            audit_diagnostics=(),
            admission=None,
            error=message,
        )

    def _require_active_turn(self, handle: ActiveTurnHandle) -> Mapping[str, Any]:
        active = self._store.snapshot.core.active_turn
        if (
            active is None
            or active.get("turn_id") != handle.turn_id
            or active.get("nonce_sha256") != _sha256_text(handle.turn_nonce)
        ):
            raise StaleAnswerDraftError("answer is not bound to the active turn")
        return active

    def _validate_bindings(self) -> None:
        declared = set(self._workspace.domain_roots)
        if set(self._bindings) != declared:
            raise AnswerCommitError("controller bindings do not match the workspace")
        for key, prepared in self._bindings.items():
            binding = getattr(prepared, "binding", prepared)
            if getattr(binding, "binding_id", None) != key:
                raise AnswerCommitError("controller binding identity is inconsistent")

    def _admit_answer(self, *, handle: ActiveTurnHandle, answer_output: str,
        selected: tuple[str, ...], results: tuple[str, ...], evidence: tuple[str, ...],
        owners: Mapping[str, str]) -> AnswerAdmissionDecision:
        binding_ids = selected or tuple(self._bindings)
        decisions: list[AnswerAdmissionDecision] = []
        for binding_id in binding_ids:
            prepared = self._bindings[binding_id]
            authority = _binding_authority(prepared)
            policy = _binding_answer_admission_policy(prepared, authority)
            observations = tuple(
                record for record in self._store.snapshot.core.diagnostics
                if record.get("turn_id") == handle.turn_id and record.get("binding_id") == binding_id
            )
            # Successful stateless discovery does not promise run evidence.
            # Read the binding's published contracts, never question/tool names.
            informational_capabilities = {
                document["id"]
                for document in getattr(getattr(prepared, "runtime", None), "capability_documents", ())
                if document.get("evidence_required") is False
                and document.get("state_effect") == "none"
            }
            request = AnswerAdmissionInput(
                question=handle.instruction, answer_output=answer_output,
                result_refs=tuple(ref for ref in results if owners.get(ref, binding_id) == binding_id),
                evidence_refs=tuple(ref for ref in evidence if owners.get(ref, binding_id) == binding_id),
                guide_reads=tuple(
                    (record["resource_id"], record["sha256"])
                    for record in observations if record.get("kind") == "published_guide_read"
                ),
                authority_attempted=any(
                    record.get("capability_id")
                    and not (record.get("ok") is True
                             and record.get("capability_id") in informational_capabilities)
                    for record in observations
                ),
            )
            try:
                decision = policy.admit(request)
            except Exception:
                raise AnswerCommitError("domain answer admission failed") from None
            _validate_admission_decision(decision, request)
            capabilities = getattr(
                getattr(getattr(prepared, "binding", prepared), "profile", None),
                "answer_admission_capabilities",
                None,
            )
            if not isinstance(capabilities, frozenset) or decision.mode not in capabilities:
                raise AnswerCommitError("domain answer admission mode is not declared")
            decisions.append(decision)
        if len(decisions) != 1:
            raise AnswerCommitError("answer admission requires exactly one binding")
        return decisions[0]

    def _validate_authority_identity(
        self, binding_id: str, prepared: object, authority: object
    ) -> None:
        binding = getattr(prepared, "binding", prepared)
        profile = getattr(binding, "profile", None)
        manifest = getattr(profile, "manifest", None)
        expected = getattr(manifest, "authority_id", None)
        actual = getattr(authority, "authority_id", None)
        if not isinstance(expected, str) or actual != expected:
            raise AnswerCommitError(f"binding authority mismatch for {binding_id}")
        root = getattr(authority, "workspace_root", None)
        if not isinstance(root, Path):
            raise AuthorityIntegrityError("binding authority workspace is invalid")
        try:
            allowed_roots = {
                self._workspace.root.resolve(),
                self._workspace.domain_roots[binding_id].resolve(),
            }
            if root.resolve() not in allowed_roots:
                raise AuthorityIntegrityError("binding authority is outside this run")
        except OSError:
            raise AuthorityIntegrityError("binding authority workspace is invalid") from None
        except KeyError:
            raise AnswerCommitError("binding authority workspace is not declared") from None

    def _current_turn_reference_owners(self, turn_id: str) -> dict[str, str]:
        owners: dict[str, str] = {}
        diagnostics = self._store.snapshot.core.diagnostics
        for record in diagnostics:
            if not isinstance(record, Mapping) or record.get("turn_id") != turn_id:
                continue
            binding_id = record.get("binding_id")
            if not isinstance(binding_id, str) or binding_id not in self._bindings:
                continue
            for field in ("result_refs", "evidence_refs"):
                refs = record.get(field)
                if isinstance(refs, Sequence) and not isinstance(refs, (str, bytes)):
                    for reference in refs:
                        if isinstance(reference, str):
                            existing = owners.get(reference)
                            if existing is not None and existing != binding_id:
                                raise AnswerCommitError(
                                    "reference has conflicting binding ownership"
                                )
                            owners[reference] = binding_id
            for field in ("result_ref", "evidence_ref"):
                reference = record.get(field)
                if isinstance(reference, str):
                    existing = owners.get(reference)
                    if existing is not None and existing != binding_id:
                        raise AnswerCommitError(
                            "reference has conflicting binding ownership"
                        )
                    owners[reference] = binding_id
        return owners

    def _assert_current_turn_references(
        self,
        references: Iterable[str],
        selected: tuple[str, ...],
        owners: Mapping[str, str],
    ) -> None:
        for reference in references:
            owner = owners.get(reference)
            if owner is None:
                raise AnswerCommitError(
                    "answer reference was not admitted for the current turn"
                )
            if self._allowed_refs and reference not in self._allowed_refs:
                raise AnswerCommitError("answer reference is not permitted by the allowlist")
            allowed_owner = self._allowed_ref_owners.get(reference)
            if allowed_owner is not None and owner != allowed_owner:
                raise AnswerCommitError("answer reference conflicts with its allowlist binding")
            if owner is not None and owner not in selected:
                raise AnswerCommitError("answer reference belongs to another binding")
            if owner is None and len(selected) > 1:
                raise AnswerCommitError(
                    "answer reference has no unambiguous binding owner"
                )

    def _claims_by_binding(
        self,
        claims: tuple[AnswerClaim | Mapping[str, object], ...],
        owners: Mapping[str, str],
        selected: tuple[str, ...],
    ) -> dict[str, tuple[AnswerClaim | Mapping[str, object], ...]]:
        grouped: dict[str, list[AnswerClaim | Mapping[str, object]]] = {
            binding_id: [] for binding_id in selected
        }
        for raw_claim in claims:
            claim = (
                raw_claim
                if isinstance(raw_claim, AnswerClaim)
                else AnswerClaim.model_validate(raw_claim)
            )
            claim_owners = {
                owners[reference]
                for reference in (*claim.result_refs, *claim.evidence_refs)
                if reference in owners
            }
            if len(claim_owners) > 1:
                raise AnswerCommitError("one claim cannot cross binding boundaries")
            if claim_owners:
                binding_id = next(iter(claim_owners))
                if binding_id not in grouped:
                    raise AnswerCommitError("claim references an unselected binding")
                grouped[binding_id].append(claim)
            elif len(selected) == 1:
                grouped[selected[0]].append(claim)
            elif selected:
                raise AnswerCommitError(
                    "unqualified claims require one selected binding"
                )
        return {key: tuple(value) for key, value in grouped.items()}

    def _preflight_context_events(
        self, events: tuple[ContextEventDraft, ...]
    ) -> None:
        state = self._store.snapshot
        from capability_agent.application.context_reducer import reduce_context

        try:
            for event in events:
                state = reduce_context(state, event)
        except Exception:
            raise AnswerCommitError("answer lifecycle transition is invalid") from None

    def _record_turn_started(self, handle: ActiveTurnHandle) -> None:
        recorder = self._recorder
        append = getattr(recorder, "append", None)
        if not callable(append):
            return
        append(
            EventDraft(
                event_type="turn.started",
                scope=RunScope(turn_id=handle.turn_id),
                payload={
                    "ordinal": handle.ordinal,
                    "instruction_sha256": handle.instruction_sha256,
                },
            )
        )

    def _record_answer_committed(
        self,
        handle: ActiveTurnHandle,
        submission: AnswerSubmission,
        answer_ref: str,
        answer_event: object,
    ) -> None:
        recorder = self._recorder
        append = getattr(recorder, "append", None)
        if not callable(append):
            return
        sequence = getattr(answer_event, "sequence", None)
        append(
            EventDraft(
                event_type="answer.submitted",
                scope=RunScope(turn_id=handle.turn_id),
                causation=Causation(parent_sequence=sequence),
                refs=EventRefs(
                    consumed=(*submission.result_refs, *submission.claim_evidence_refs),
                    produced=(answer_ref,),
                ),
                payload={
                    "submission_id": submission.submission_id,
                    "artifact_ref": answer_ref,
                    "result_refs": submission.result_refs,
                    "evidence_refs": submission.claim_evidence_refs,
                },
            )
        )
        for claim in submission.claims:
            append(
                EventDraft(
                    event_type="business.claim.declared",
                    scope=RunScope(turn_id=handle.turn_id),
                    source=EventSource(kind="agent-declared"),
                    refs=EventRefs(
                        consumed=claim.result_refs,
                        evidence=claim.evidence_refs,
                    ),
                    payload={
                        "submission_id": submission.submission_id,
                        **claim.model_dump(mode="json"),
                    },
                )
            )

    def _record_turn_failed(
        self, handle: ActiveTurnHandle, error: str, duration: float
    ) -> None:
        recorder = self._recorder
        append = getattr(recorder, "append", None)
        if not callable(append):
            return
        append(
            EventDraft(
                event_type="turn.failed",
                scope=RunScope(turn_id=handle.turn_id),
                payload={"error_type": "turn_failed", "message": error},
            )
        )

    @property
    def _active_turn_path(self) -> Path:
        return self._workspace.turns_path / "active-turn.json"

    @property
    def _active_answer_draft_path(self) -> Path:
        return self._workspace.turns_path / "active-answer-draft.json"

    def _turn_path(self, handle: ActiveTurnHandle) -> Path:
        path = self._workspace.turns_path / handle.turn_id
        try:
            path.mkdir(mode=0o700, exist_ok=True)
        except OSError:
            raise AnswerCommitError("turn artifact directory could not be created") from None
        return path


def _binding_authority(prepared: object) -> object:
    runtime = getattr(prepared, "runtime", None)
    authority = getattr(runtime, "authority", None)
    if authority is None:
        authority = getattr(prepared, "authority", None)
    if authority is None:
        raise AnswerCommitError("prepared binding has no authority")
    return authority


def _binding_answer_policy(prepared: object) -> AnswerEvidencePolicy:
    binding = getattr(prepared, "binding", prepared)
    profile = getattr(binding, "profile", None)
    policy = getattr(profile, "answer_policy", None)
    if policy is None:
        raise AnswerCommitError("prepared binding has no answer policy")
    return cast(AnswerEvidencePolicy, policy)


def _binding_answer_admission_policy(prepared: object, authority: object) -> AnswerAdmissionPolicy:
    binding = getattr(prepared, "binding", prepared)
    profile = getattr(binding, "profile", None)
    factory = getattr(profile, "create_answer_admission_policy", None)
    if not callable(factory):
        raise AnswerCommitError("prepared binding has no answer admission policy")
    try:
        policy = factory(authority)
    except Exception:
        raise AnswerCommitError("prepared binding answer admission is invalid") from None
    if not callable(getattr(policy, "admit", None)):
        raise AnswerCommitError("prepared binding answer admission is invalid")
    return cast(AnswerAdmissionPolicy, policy)


def _validate_admission_decision(
    decision: object, request: AnswerAdmissionInput
) -> None:
    if not isinstance(decision, AnswerAdmissionDecision):
        raise AnswerCommitError("domain answer admission returned an invalid decision")
    if not isinstance(decision.answer_output, str) or not decision.answer_output.strip():
        raise AnswerCommitError("domain answer admission returned an empty answer")
    if not all(isinstance(code, str) and code for code in decision.diagnostic_codes):
        raise AnswerCommitError("domain answer admission diagnostics are invalid")
    if decision.mode == "authority_backed":
        if decision.assurance != "lineage_verified" or not (
            request.result_refs or request.evidence_refs
        ):
            raise AnswerCommitError("authority-backed answer admission is invalid")
        return
    if decision.mode == "offline_information":
        if decision.assurance not in {"deterministic_information", "guide_access_verified"} or (
            request.result_refs or request.evidence_refs
        ):
            raise AnswerCommitError("offline answer admission is invalid")
        if decision.assurance == "guide_access_verified" and (not request.guide_reads or request.authority_attempted):
            raise AnswerCommitError("guide answer admission is invalid")
        return
    if decision.mode == "limited" and decision.assurance == "limited":
        return
    raise AnswerCommitError("domain answer admission assurance is invalid")


def _normalize_allowed_refs(
    allowed_refs: Set[str] | Mapping[str, Iterable[str]] | None,
) -> tuple[frozenset[str], dict[str, str]]:
    if allowed_refs is None:
        return frozenset(), {}
    if isinstance(allowed_refs, Mapping):
        allowed: set[str] = set()
        owners: dict[str, str] = {}
        for binding_id, references in allowed_refs.items():
            if not isinstance(binding_id, str):
                raise AnswerCommitError("allowed reference binding is invalid")
            if isinstance(references, str):
                values = (references,)
            else:
                try:
                    values = tuple(references)
                except TypeError:
                    raise AnswerCommitError("allowed references are invalid") from None
            for reference in values:
                if not isinstance(reference, str) or not reference:
                    raise AnswerCommitError("allowed references are invalid")
                allowed.add(reference)
                existing = owners.get(reference)
                if existing is not None and existing != binding_id:
                    raise AnswerCommitError("allowed reference has conflicting owners")
                owners[reference] = binding_id
        return frozenset(allowed), owners
    try:
        values = tuple(allowed_refs)
    except TypeError:
        raise AnswerCommitError("allowed references are invalid") from None
    if not all(isinstance(reference, str) and reference for reference in values):
        raise AnswerCommitError("allowed references are invalid")
    return frozenset(values), {}


def _portable_binding_ids(values: Iterable[str]) -> tuple[str, ...]:
    try:
        result = tuple(values)
    except TypeError:
        raise AnswerCommitError("referenced bindings are invalid") from None
    if not all(isinstance(value, str) and value for value in result):
        raise AnswerCommitError("referenced bindings are invalid")
    return tuple(dict.fromkeys(result))


def _string_refs(values: Iterable[str], field: str) -> tuple[str, ...]:
    try:
        result = tuple(values)
    except TypeError:
        raise AnswerCommitError(f"{field} are invalid") from None
    if not all(isinstance(value, str) and value for value in result):
        raise AnswerCommitError(f"{field} are invalid")
    return tuple(dict.fromkeys(result))


def _audit_binding_references(
    authority: object,
    evidence_refs: tuple[str, ...],
    result_refs: tuple[str, ...],
) -> tuple[object, ...]:
    audit = getattr(authority, "audit_answer_references", None)
    if not callable(audit):
        return ()
    try:
        diagnostics = audit(evidence_refs, result_refs)
    except Exception:
        raise AuthorityIntegrityError("binding answer audit failed") from None
    if diagnostics is None:
        return ()
    try:
        # The dynamic authority hook is validated by tuple conversion below;
        # preserve support for iterables implemented through __getitem__ too.
        diagnostics_tuple = tuple(cast(Iterable[object], diagnostics))
    except TypeError:
        raise AuthorityIntegrityError("binding answer audit returned invalid diagnostics") from None
    for diagnostic in diagnostics_tuple:
        severity = (
            diagnostic.get("severity")
            if isinstance(diagnostic, Mapping)
            else getattr(diagnostic, "severity", None)
        )
        if severity == "error":
            raise AnswerCommitError("binding answer references failed audit")
    return diagnostics_tuple


def _duration(value: float) -> float:
    if type(value) not in {int, float} or not math.isfinite(float(value)) or value < 0:
        raise AnswerCommitError("duration_seconds is invalid")
    return float(value)


@dataclass(frozen=True, slots=True)
class _FileState:
    exists: bool
    content: bytes | None = None


def _read_file_state(path: Path) -> _FileState:
    try:
        return _FileState(True, path.read_bytes())
    except FileNotFoundError:
        return _FileState(False)
    except OSError:
        raise AnswerCommitError("turn state file could not be read") from None


def _restore_file_state(path: Path, state: _FileState) -> None:
    if state.exists:
        if state.content is None:
            raise AnswerCommitError("turn state snapshot is invalid")
        _write_bytes_atomic(path, state.content)
    else:
        _remove_if_present(path)


def _remove_if_present(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return
    except OSError:
        raise AnswerCommitError("turn state file could not be removed") from None


def _write_json_atomic(path: Path, payload: Mapping[str, object]) -> None:
    _write_bytes_atomic(path, canonical_json_bytes(payload))


def _write_bytes_atomic(path: Path, payload: bytes) -> None:
    try:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
        with temporary.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except OSError:
        try:
            temporary.unlink()  # type: ignore[union-attr]
        except (UnboundLocalError, OSError):
            pass
        raise AnswerCommitError("turn artifact persistence failed") from None


def _sha256_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


__all__ = [
    "ActiveTurnHandle",
    "ActiveTurnInProgressError",
    "FinalizedTurn",
    "StaleAnswerDraftError",
    "TurnController",
]
