"""Binding-aware projection of generic capability observations.

This module intentionally understands only the Kernel's structured routing
metadata.  A domain authority verifies resource truth and a domain projector
turns that verified result into a state delta; the Kernel only persists the
opaque observation and binding-qualified transition.
"""

from __future__ import annotations

import hashlib
import math
import os
import stat
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from capability_agent.application.context_models import ContextEventDraft
from capability_agent.application.context_reducer import reduce_context
from capability_agent.application.context_store import ApplicationContextStore
from capability_agent.application.errors import (
    AuthorityIntegrityError,
    CapabilityRoutingError,
    CapabilityTransportError,
    DomainProjectionError,
)
from capability_agent.application.workspace import ApplicationWorkspace
from capability_agent.domain.projection import VerifiedInvocation
from capability_agent.tools.catalog import (
    BoundToolDocument,
    CapabilityKey,
    CompositeToolCatalog,
)
from capability_agent.trajectory.canonical import canonical_json_bytes
from capability_agent.tools.guide import GuideIndex, GuideNotFound
from capability_agent.trajectory.events import EventDraft, EventRefs, RunScope


@dataclass(frozen=True, slots=True)
class ProjectionOutcome:
    binding_id: str
    capability_id: str
    observation_ref: str
    result_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    state_revision: int | None


class ApplicationInvocationProjector:
    """Route one capability result to exactly one prepared binding."""

    def __init__(
        self,
        store: ApplicationContextStore,
        catalog: CompositeToolCatalog,
        bindings: Mapping[str, object],
        recorder: object | None = None,
    ) -> None:
        self._store = store
        self._catalog = catalog
        self._bindings = dict(bindings)
        self._recorder = recorder
        self._starts: dict[str, Mapping[str, Any]] = {}
        self._validate_binding_set()

    @property
    def store(self) -> ApplicationContextStore:
        return self._store

    def observe(
        self,
        event: Mapping[str, object],
        *,
        turn_id: str | None = None,
        trace_sequence: int | None = None,
    ) -> ProjectionOutcome | None:
        """Observe a transport event and project successful domain results.

        All authority, projector, adapter, and reducer validation runs before
        the first durable append.  Consequently an integrity or projection
        failure cannot leave a result, evidence, or domain state transition in
        the context store.
        """

        event_type = _event_type(event)
        if event_type in {"tool_execution_start", "tool.started", "tool_start"}:
            call_id = _call_id(event)
            if call_id is not None:
                self._starts[call_id] = dict(event)
            return None
        if event_type not in {"tool_result", "tool.completed", "tool.result"}:
            return None

        start = self._matching_start(event)
        tool = self._resolve_tool(event, start)
        if tool is None:
            self._observe_guide(event, start, turn_id, trace_sequence)
            # Core tools are deliberately opaque to the domain projector.
            self._forget_start(event)
            return None
        key = tool.key
        binding_id = key.binding_id
        binding = self._bindings.get(binding_id)
        if binding is None:
            raise CapabilityRoutingError("capability binding is not prepared")
        self._validate_run_identity(event, start)
        resolved_turn_id = self._resolve_turn_id(event, start, turn_id)
        ok = event.get("ok") is True
        if not ok:
            outcome = self._record_failed_observation(
                event,
                start,
                tool,
                resolved_turn_id,
                trace_sequence,
            )
            self._forget_start(event)
            return outcome
        result = event.get("result", {})
        if not isinstance(result, Mapping):
            raise CapabilityTransportError("capability result is not an object")
        result = _json_mapping(result, label="capability result")
        evidence_refs = _event_refs(event, "evidence_refs")
        if not evidence_refs:
            evidence_refs = _event_refs(result, "evidence_refs")
        declared_result_refs = _declared_result_refs(event, result)

        authority = _binding_authority(binding)
        self._validate_authority_identity(tool, binding, authority)
        artifact_root = self._binding_artifact_root(binding_id, binding)
        references = self._admit_references(
            authority,
            key.capability_id,
            result,
            evidence_refs,
        )
        context_refs = _artifact_refs(
            references, "context", self._store.workspace, artifact_root=artifact_root
        )
        result_refs = _artifact_refs(references, "results", self._store.workspace, artifact_root=artifact_root)
        admitted_evidence_refs = _artifact_refs(
            references,
            "evidence",
            self._store.workspace,
            artifact_root=artifact_root,
        )
        if declared_result_refs and not set(declared_result_refs).issubset(result_refs):
            raise AuthorityIntegrityError("capability result was not admitted")
        if evidence_refs and not set(evidence_refs).issubset(admitted_evidence_refs):
            raise AuthorityIntegrityError("capability evidence was not admitted")

        projector_id = _projector_id(event, result)
        if projector_id is None:
            raise DomainProjectionError("capability result has no projector identity")
        state_adapter = _binding_state_adapter(binding)
        registry = _binding_projector_registry(binding)
        current_envelope = self._store.snapshot.domains.get(binding_id)
        if current_envelope is None:
            raise CapabilityRoutingError("capability binding has no context state")
        arguments = _arguments(start, event)
        result_paths = _artifact_paths(
            references,
            "results",
            self._store.workspace,
            artifact_root=artifact_root,
        )
        active_revision_ref = result.get("revision_ref")
        if not isinstance(active_revision_ref, str):
            active_revision_ref = None
        invocation = VerifiedInvocation(
            capability=key.capability_id,
            projector_id=projector_id,
            result_kind=_result_kind(event, result),
            result=result,
            arguments=arguments,
            turn_id=resolved_turn_id,
            result_paths=result_paths,
            active_revision_ref=active_revision_ref,
        )
        delta, merged_state = self._project_state(
            state_adapter,
            registry,
            binding_id,
            current_envelope.state,
            invocation,
            projector_id,
        )
        del delta  # The validated merged state is the only state persisted.
        observation_ref = _observation_ref(
            binding_id,
            key.capability_id,
            resolved_turn_id,
            _call_id(event),
            arguments,
            result,
        )
        drafts = self._build_success_drafts(
            tool=tool,
            binding_id=binding_id,
            turn_id=resolved_turn_id,
            trace_sequence=trace_sequence,
            event=event,
            start=start,
            result=result,
            arguments=arguments,
            observation_ref=observation_ref,
            result_refs=result_refs,
            evidence_refs=admitted_evidence_refs,
            merged_state=merged_state,
            current_revision=current_envelope.revision,
            schema_id=current_envelope.schema_id,
            references=references,
            context_refs=context_refs,
            artifact_root=artifact_root,
        )
        self._preflight_context(drafts)
        try:
            self._store.append_many(drafts)
        except Exception:
            raise DomainProjectionError("capability projection persistence failed") from None
        self._record_tool_completed(
            tool, resolved_turn_id, result_refs, admitted_evidence_refs
        )
        self._forget_start(event)
        return ProjectionOutcome(
            binding_id=binding_id,
            capability_id=key.capability_id,
            observation_ref=observation_ref,
            result_refs=result_refs,
            evidence_refs=admitted_evidence_refs,
            state_revision=current_envelope.revision + 1,
        )

    def _observe_guide(
        self, event: Mapping[str, object], start: Mapping[str, object],
        turn_id: str | None, trace_sequence: int | None,
    ) -> None:
        name = _first_string(event, "tool_name", "name", "toolName") or _first_string(start, "tool_name", "name", "toolName")
        binding_id = self._catalog.guide_tool_bindings.get(name) if name is not None else None
        if binding_id is None or event.get("ok") is not True:
            return
        self._validate_run_identity(event, start)
        current_turn = self._resolve_turn_id(event, start, turn_id)
        result = event.get("result")
        if not isinstance(result, Mapping):
            return
        resource_id, text = result.get("resource_id"), result.get("text")
        if not isinstance(resource_id, str) or not isinstance(text, str):
            return
        prepared = self._bindings[binding_id]
        binding = getattr(prepared, "binding", prepared)
        root = getattr(getattr(getattr(binding, "profile", None), "manifest", None), "guide_root", None)
        if not isinstance(root, Path):
            return
        try:
            document = GuideIndex.load(root).open(resource_id)
        except (GuideNotFound, OSError, ValueError):
            return
        if document.text.strip() != text.strip():
            return
        self._store.append(ContextEventDraft(
            event_type="tool.observation.recorded", binding_id=binding_id,
            turn_id=current_turn, trace_sequence=trace_sequence,
            payload={"kind": "published_guide_read", "binding_id": binding_id,
                     "turn_id": current_turn, "resource_id": resource_id,
                     "sha256": hashlib.sha256(text.strip().encode()).hexdigest()},
        ))

    def _resolve_tool(
        self,
        event: Mapping[str, object],
        start: Mapping[str, object],
    ) -> BoundToolDocument | None:
        event_key = _read_capability_key(event)
        start_key = _read_capability_key(start)
        if event_key is not None and start_key is not None and event_key != start_key:
            raise CapabilityRoutingError("capability key changed during invocation")
        key = event_key or start_key
        event_tool_name = _first_string(event, "tool_name", "name", "toolName")
        start_tool_name = _first_string(start, "tool_name", "name", "toolName")
        if event_tool_name is not None and start_tool_name is not None and event_tool_name != start_tool_name:
            raise CapabilityRoutingError("tool identity changed during invocation")
        tool_name = event_tool_name or start_tool_name
        looked_up: object | None = None
        if tool_name is not None:
            try:
                looked_up = self._catalog.require(tool_name)
            except KeyError:
                if self._catalog.is_auxiliary(tool_name):
                    return None
                raise CapabilityRoutingError("capability tool is not registered") from None
            if not isinstance(looked_up, BoundToolDocument):
                # Core tools are intentionally outside domain projection. A
                # core result may omit domain routing metadata, but a domain
                # result may never derive its identity from ``tool_name``.
                return None
            if key is None:
                raise CapabilityRoutingError(
                    "domain capability result requires a structured key"
                )
            if looked_up.key != key:
                raise CapabilityRoutingError("tool name and capability key disagree")
        if key is None:
            capability_value = _first_string(event, "capability") or _first_string(start, "capability")
            if capability_value is not None:
                raise CapabilityRoutingError(
                    "capability result requires a structured key"
                )
        if key is None:
            raise CapabilityRoutingError("capability result has no structured key")
        capability_values = tuple(
            value
            for value in (
                _first_string(event, "capability"),
                _first_string(start, "capability"),
            )
            if value is not None
        )
        if capability_values and any(
            value != key.capability_id for value in capability_values
        ):
            raise CapabilityRoutingError("capability name and structured key disagree")
        if looked_up is None:
            candidates = [candidate for candidate in self._catalog.domain_tools if candidate.key == key]
            if len(candidates) != 1:
                raise CapabilityRoutingError("capability key is not registered")
            looked_up = candidates[0]
        if not isinstance(looked_up, BoundToolDocument):
            return None
        return looked_up

    def _matching_start(self, event: Mapping[str, object]) -> Mapping[str, object]:
        call_id = _call_id(event)
        if call_id is None:
            return {}
        return self._starts.get(call_id, {})

    def _forget_start(self, event: Mapping[str, object]) -> None:
        call_id = _call_id(event)
        if call_id is not None:
            self._starts.pop(call_id, None)

    def _resolve_turn_id(
        self,
        event: Mapping[str, object],
        start: Mapping[str, object],
        explicit: str | None,
    ) -> str:
        if explicit is not None and (not isinstance(explicit, str) or not explicit):
            raise CapabilityRoutingError("capability turn identity is invalid")
        declared = tuple(
            value
            for value in (
                *(_optional_identity(source, key)
                  for source in (event, start)
                  for key in ("turn_id", "turnId", "correlation_id")),
                explicit,
            )
            if value is not None
        )
        if len(set(declared)) > 1:
            raise CapabilityRoutingError(
                "capability result turn changed during invocation"
            )
        candidate = declared[0] if declared else None
        active = self._store.snapshot.core.active_turn
        active_id = active.get("turn_id") if isinstance(active, Mapping) else None
        if not isinstance(candidate, str) or not candidate:
            candidate = active_id if isinstance(active_id, str) else None
        if not isinstance(candidate, str) or not candidate:
            raise CapabilityRoutingError("capability result has no turn identity")
        if candidate != active_id:
            raise CapabilityRoutingError("capability result is outside the active turn")
        return candidate

    def _validate_run_identity(
        self, event: Mapping[str, object], start: Mapping[str, object]
    ) -> None:
        declared = tuple(
            value
            for value in (
                _optional_identity(event, "run_id", "runId"),
                _optional_identity(start, "run_id", "runId"),
            )
            if value is not None
        )
        if len(set(declared)) > 1:
            raise CapabilityRoutingError(
                "capability run identity changed during invocation"
            )
        if declared and declared[0] != self._store.workspace.run_id:
            raise CapabilityRoutingError("capability result belongs to another run")

    def _validate_binding_set(self) -> None:
        declared = set(self._store.workspace.domain_roots)
        if set(self._bindings) != declared:
            raise CapabilityRoutingError("prepared bindings do not match the workspace")
        for binding_id, prepared in self._bindings.items():
            binding = getattr(prepared, "binding", prepared)
            if getattr(binding, "binding_id", None) != binding_id:
                raise CapabilityRoutingError("prepared binding identity is inconsistent")

    def _validate_authority_identity(
        self, tool: BoundToolDocument, prepared: object, authority: object
    ) -> None:
        actual = getattr(authority, "authority_id", None)
        if actual != tool.authority_id:
            raise CapabilityRoutingError("capability authority does not match its binding")
        binding = getattr(prepared, "binding", prepared)
        profile = getattr(binding, "profile", None)
        manifest = getattr(profile, "manifest", None)
        expected = getattr(manifest, "authority_id", None)
        if not isinstance(expected, str) or expected != actual:
            raise CapabilityRoutingError("binding manifest authority does not match")
        root = getattr(authority, "workspace_root", None)
        if not isinstance(root, Path):
            raise AuthorityIntegrityError("binding authority workspace is invalid")
        try:
            allowed_roots = {
                self._store.workspace.root.resolve(),
                self._store.workspace.domain_roots[tool.key.binding_id].resolve(),
            }
            if root.resolve() not in allowed_roots:
                raise AuthorityIntegrityError("binding authority is outside this run")
        except OSError:
            raise AuthorityIntegrityError("binding authority workspace is invalid") from None
        except KeyError:
            raise CapabilityRoutingError("capability binding workspace is not declared") from None

    def _binding_artifact_root(self, binding_id: str, prepared: object) -> Path:
        """Resolve an artifact root owned by one declared binding.

        Authorities may be configured with the whole run root for legacy
        reasons, but that root is never sufficient to authorize sibling
        binding artifacts. An optional explicit ``artifact_root`` is accepted
        only as a sub-root of the binding's declared domain directory.
        """

        try:
            declared_root = self._store.workspace.domain_roots[binding_id]
        except KeyError:
            raise CapabilityRoutingError("capability binding workspace is not declared") from None
        binding = getattr(prepared, "binding", prepared)
        profile = getattr(binding, "profile", None)
        runtime = getattr(prepared, "runtime", None)
        explicit_roots = [
            getattr(prepared, "artifact_root", None),
            getattr(runtime, "artifact_root", None),
            getattr(binding, "artifact_root", None),
            getattr(profile, "artifact_root", None),
        ]
        explicit = next((value for value in explicit_roots if value is not None), None)
        root = declared_root if explicit is None else explicit
        if not isinstance(root, Path):
            raise AuthorityIntegrityError("binding artifact root is invalid")
        _validate_owned_root(root, declared_root, self._store.workspace)
        return root

    def _admit_references(
        self,
        authority: object,
        capability_id: str,
        result: Mapping[str, object],
        evidence_refs: tuple[str, ...],
    ) -> object:
        admit = getattr(authority, "admit", None)
        if not callable(admit):
            raise AuthorityIntegrityError("binding authority cannot admit references")
        try:
            references = admit(capability_id, result, evidence_refs)
        except Exception:
            raise AuthorityIntegrityError("current-run artifact admission failed") from None
        for group in ("context", "results", "evidence"):
            if not hasattr(references, group):
                raise AuthorityIntegrityError("binding authority returned invalid references")
        return references

    def _project_state(
        self,
        adapter: object,
        registry: object,
        binding_id: str,
        current_state: Mapping[str, object],
        invocation: VerifiedInvocation,
        projector_id: str,
    ) -> tuple[Mapping[str, object], Mapping[str, object]]:
        validate = getattr(adapter, "validate", None)
        merge = getattr(adapter, "merge", None)
        require = getattr(registry, "require", None)
        if not callable(validate) or not callable(merge) or not callable(require):
            raise DomainProjectionError("prepared binding has incomplete projection contracts")
        try:
            current_copy = _json_mapping(current_state, label="domain state")
            validate(binding_id=binding_id, state=current_copy)
            projector = require(projector_id)
            project = getattr(projector, "project", None)
            if not callable(project):
                raise DomainProjectionError("domain projector is not callable")
            delta = project(invocation)
            dump = getattr(delta, "model_dump", None)
            if not callable(dump):
                raise DomainProjectionError("domain projector returned an invalid delta")
            raw_delta = dump(mode="json")
            if not isinstance(raw_delta, Mapping):
                raise DomainProjectionError("domain projector returned an invalid delta")
            merged = merge(
                binding_id=binding_id,
                state=current_copy,
                delta=delta,
            )
            if not isinstance(merged, Mapping):
                raise DomainProjectionError("domain projector returned invalid state")
            merged_mapping = _json_mapping(merged, label="domain state")
            validate(binding_id=binding_id, state=merged_mapping)
        except DomainProjectionError:
            raise
        except Exception:
            raise DomainProjectionError("domain projection failed") from None
        return raw_delta, merged_mapping

    def _build_success_drafts(
        self,
        *,
        tool: BoundToolDocument,
        binding_id: str,
        turn_id: str,
        trace_sequence: int | None,
        event: Mapping[str, object],
        start: Mapping[str, object],
        result: Mapping[str, object],
        arguments: Mapping[str, object],
        observation_ref: str,
        result_refs: tuple[str, ...],
        evidence_refs: tuple[str, ...],
        merged_state: Mapping[str, object],
        current_revision: int,
        schema_id: str,
        references: object,
        context_refs: tuple[str, ...],
        artifact_root: Path,
    ) -> tuple[ContextEventDraft, ...]:
        drafts: list[ContextEventDraft] = [
            ContextEventDraft(
                event_type="tool.observation.recorded",
                binding_id=binding_id,
                turn_id=turn_id,
                capability=tool.key.capability_id,
                trace_sequence=trace_sequence,
                payload={
                    "observation_ref": observation_ref,
                    "binding_id": binding_id,
                    "turn_id": turn_id,
                    "capability_id": tool.key.capability_id,
                    "tool_name": tool.name,
                    "call_id": _call_id(event),
                    "ok": True,
                    "arguments": arguments,
                    "result": result,
                    "result_refs": result_refs,
                    "evidence_refs": evidence_refs,
                    "context_refs": context_refs,
                },
            )
        ]
        for artifact in _artifacts(references, "results"):
            reference = getattr(artifact, "reference", None)
            if not isinstance(reference, str):
                continue
            drafts.append(
                ContextEventDraft(
                    event_type="result.registered",
                    binding_id=binding_id,
                    turn_id=turn_id,
                    capability=tool.key.capability_id,
                    payload={
                        "binding_id": binding_id,
                        "turn_id": turn_id,
                        "result_ref": reference,
                        "path": _relative_artifact_path(
                            artifact,
                            self._store.workspace,
                            artifact_root=artifact_root,
                        ),
                        "evidence_refs": evidence_refs,
                    },
                )
            )
        for artifact in _artifacts(references, "evidence"):
            reference = getattr(artifact, "reference", None)
            if not isinstance(reference, str):
                continue
            drafts.append(
                ContextEventDraft(
                    event_type="evidence.registered",
                    binding_id=binding_id,
                    turn_id=turn_id,
                    capability=tool.key.capability_id,
                    payload={
                        "binding_id": binding_id,
                        "turn_id": turn_id,
                        "evidence_ref": reference,
                        "path": _relative_artifact_path(
                            artifact,
                            self._store.workspace,
                            artifact_root=artifact_root,
                        ),
                    },
                )
            )
        drafts.append(
            ContextEventDraft(
                event_type="domain.state.projected",
                binding_id=binding_id,
                turn_id=turn_id,
                capability=tool.key.capability_id,
                payload={
                    "schema_id": schema_id,
                    "previous_revision": current_revision,
                    "state": merged_state,
                },
            )
        )
        return tuple(drafts)

    def _preflight_context(self, drafts: tuple[ContextEventDraft, ...]) -> None:
        state = self._store.snapshot
        try:
            for draft in drafts:
                state = reduce_context(state, draft)
        except Exception:
            raise DomainProjectionError("projected context transition is invalid") from None

    def _record_tool_completed(
        self,
        tool: BoundToolDocument,
        turn_id: str,
        result_refs: tuple[str, ...],
        evidence_refs: tuple[str, ...],
    ) -> None:
        append = getattr(self._recorder, "append", None)
        if not callable(append):
            return
        artifact_ref = result_refs[0] if result_refs else None
        append(
            EventDraft(
                event_type="tool.completed",
                scope=RunScope(turn_id=turn_id),
                refs=EventRefs(consumed=(*result_refs, *evidence_refs)),
                payload={
                    "capability": tool.key.capability_id,
                    "artifact_ref": artifact_ref,
                    "ok": True,
                },
            )
        )

    def _record_failed_observation(
        self,
        event: Mapping[str, object],
        start: Mapping[str, object],
        tool: BoundToolDocument,
        turn_id: str,
        trace_sequence: int | None,
    ) -> ProjectionOutcome:
        call_id = _call_id(event)
        observation_ref = _observation_ref(
            tool.key.binding_id,
            tool.key.capability_id,
            turn_id,
            call_id,
            _arguments(start, event),
            {},
        )
        error = event.get("error")
        error_mapping = error if isinstance(error, Mapping) else {}
        error_code = _first_string(error_mapping, "code", "error_code") or _first_string(
            event, "error_code", "code"
        )
        error_message = _first_string(
            error_mapping, "message", "error_message", "detail"
        ) or _first_string(event, "error_message", "message", "detail")
        payload: dict[str, object] = {
            "binding_id": tool.key.binding_id,
            "turn_id": turn_id,
            "capability_id": tool.key.capability_id,
            "observation_ref": observation_ref,
            "message": "capability returned a bounded failure",
        }
        if error_code is not None:
            payload["error_code"] = error_code
        if error_message is not None:
            payload["error_message"] = error_message
        draft = ContextEventDraft(
            event_type="tool.failed",
            binding_id=tool.key.binding_id,
            turn_id=turn_id,
            capability=tool.key.capability_id,
            trace_sequence=trace_sequence,
            payload=payload,
        )
        self._preflight_context((draft,))
        try:
            self._store.append_many((draft,))
        except Exception:
            raise CapabilityTransportError("capability failure could not be recorded") from None
        return ProjectionOutcome(
            binding_id=tool.key.binding_id,
            capability_id=tool.key.capability_id,
            observation_ref=observation_ref,
            result_refs=(),
            evidence_refs=(),
            state_revision=None,
        )


def _binding_authority(prepared: object) -> object:
    runtime = getattr(prepared, "runtime", None)
    authority = getattr(runtime, "authority", None)
    if authority is None:
        authority = getattr(prepared, "authority", None)
    if authority is None:
        raise AuthorityIntegrityError("prepared binding has no authority")
    return authority


def _binding_state_adapter(prepared: object) -> object:
    binding = getattr(prepared, "binding", prepared)
    profile = getattr(binding, "profile", None)
    adapter = getattr(profile, "state_adapter", None)
    if adapter is None:
        adapter = getattr(getattr(prepared, "runtime", None), "state_adapter", None)
    if adapter is None:
        raise DomainProjectionError("prepared binding has no state adapter")
    return adapter


def _binding_projector_registry(prepared: object) -> object:
    binding = getattr(prepared, "binding", prepared)
    profile = getattr(binding, "profile", None)
    registry = getattr(profile, "projector_registry", None)
    if registry is None:
        registry = getattr(getattr(prepared, "runtime", None), "projector_registry", None)
    if registry is None:
        raise DomainProjectionError("prepared binding has no projector registry")
    return registry


def _event_type(event: Mapping[str, object]) -> str | None:
    value = (
        event.get("type")
        or event.get("event")
        or event.get("event_type")
        or event.get("eventType")
    )
    return value if isinstance(value, str) else None


def _first_string(event: Mapping[str, object], *keys: str) -> str | None:
    for key in keys:
        value = event.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _optional_identity(event: Mapping[str, object], *keys: str) -> str | None:
    """Read one optional identity field without accepting malformed values."""

    for key in keys:
        if key not in event:
            continue
        value = event[key]
        if not isinstance(value, str) or not value:
            raise CapabilityRoutingError("capability identity is invalid")
        return value
    return None


def _call_id(event: Mapping[str, object]) -> str | None:
    return _first_string(
        event,
        "call_id",
        "tool_call_id",
        "request_id",
        "id",
        "callId",
        "toolCallId",
        "requestId",
    )


def _capability_key(value: object) -> CapabilityKey | None:
    if isinstance(value, CapabilityKey):
        return value
    if isinstance(value, Mapping):
        binding_id = value.get("binding_id", value.get("bindingId"))
        capability_id = value.get("capability_id", value.get("capabilityId"))
        if (
            isinstance(binding_id, str)
            and binding_id
            and isinstance(capability_id, str)
            and capability_id
        ):
            return CapabilityKey(binding_id, capability_id)
    return None


def _read_capability_key(event: Mapping[str, object]) -> CapabilityKey | None:
    """Read a structured key, rejecting malformed present aliases."""

    for field in ("capability_key", "capabilityKey", "key"):
        if field not in event:
            continue
        key = _capability_key(event[field])
        if key is None:
            raise CapabilityRoutingError("capability key is invalid")
        return key
    return None


def _declared_result_refs(
    event: Mapping[str, object], result: Mapping[str, object]
) -> tuple[str, ...]:
    values: list[str] = []
    for source in (event, result):
        scalar = source.get("result_ref") or source.get("resultRef")
        if scalar is not None:
            if not isinstance(scalar, str) or not scalar:
                raise CapabilityTransportError("capability result reference is invalid")
            values.append(scalar)
        values.extend(_event_refs(source, "result_refs"))
    return tuple(dict.fromkeys(values))


def _arguments(
    start: Mapping[str, object], event: Mapping[str, object]
) -> Mapping[str, object]:
    for source in (start, event):
        for key in ("arguments", "args", "input", "toolArguments"):
            value = source.get(key)
            if isinstance(value, Mapping):
                return _json_mapping(value, label="capability arguments")
    return {}


def _event_refs(source: Mapping[str, object], field: str) -> tuple[str, ...]:
    aliases = {
        "evidence_refs": ("evidence_refs", "evidenceRefs"),
        "result_refs": ("result_refs", "resultRefs"),
    }
    value = next(
        (source[key] for key in aliases.get(field, (field,)) if key in source),
        None,
    )
    if value is None:
        return ()
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise CapabilityTransportError("capability reference list is invalid")
    if not all(isinstance(item, str) and item for item in value):
        raise CapabilityTransportError("capability reference list is invalid")
    return tuple(dict.fromkeys(value))


def _projector_id(
    event: Mapping[str, object], result: Mapping[str, object]
) -> str | None:
    return _first_string(event, "projector_id", "projector", "projectorId") or _first_string(
        result, "projector_id", "projector", "projectorId"
    )


def _result_kind(
    event: Mapping[str, object], result: Mapping[str, object]
) -> str | None:
    return _first_string(event, "result_kind", "resultKind") or _first_string(
        result, "result_kind", "resultKind"
    )


def _artifacts(references: object, group: str) -> tuple[object, ...]:
    values = getattr(references, group, ())
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise AuthorityIntegrityError("binding authority returned invalid artifacts")
    return tuple(values)


def _artifact_refs(
    references: object,
    group: str,
    workspace: ApplicationWorkspace,
    *,
    artifact_root: Path,
) -> tuple[str, ...]:
    output: list[str] = []
    for artifact in _artifacts(references, group):
        reference = getattr(artifact, "reference", None)
        if not isinstance(reference, str) or not reference:
            raise AuthorityIntegrityError("binding authority returned invalid artifact reference")
        _validate_artifact_path(artifact, workspace, artifact_root=artifact_root)
        if reference not in output:
            output.append(reference)
    return tuple(output)


def _artifact_paths(
    references: object,
    group: str,
    workspace: ApplicationWorkspace,
    *,
    artifact_root: Path,
) -> Mapping[str, str]:
    paths: dict[str, str] = {}
    for artifact in _artifacts(references, group):
        reference = getattr(artifact, "reference", None)
        if not isinstance(reference, str):
            continue
        paths[reference] = _relative_artifact_path(
            artifact, workspace, artifact_root=artifact_root
        )
    return paths


def _validate_artifact_path(
    artifact: object,
    workspace: ApplicationWorkspace,
    *,
    artifact_root: Path,
) -> None:
    path = getattr(artifact, "path", None)
    if not isinstance(path, Path):
        raise AuthorityIntegrityError("binding authority returned an invalid artifact path")
    try:
        root = _absolute_path(artifact_root)
        candidate = _absolute_path(path)
        candidate.relative_to(root)
        _reject_symlink_chain(root, candidate)
        resolved_root = root.resolve(strict=False)
        resolved_path = candidate.resolve(strict=False)
        resolved_path.relative_to(resolved_root)
        resolved_path.relative_to(workspace.root.resolve(strict=False))
    except (OSError, ValueError):
        raise AuthorityIntegrityError("binding artifact is outside this run") from None


def _relative_artifact_path(
    artifact: object,
    workspace: ApplicationWorkspace,
    *,
    artifact_root: Path,
) -> str:
    _validate_artifact_path(artifact, workspace, artifact_root=artifact_root)
    path = getattr(artifact, "path")
    try:
        return str(path.resolve().relative_to(workspace.root.resolve()))
    except (OSError, ValueError):
        raise AuthorityIntegrityError("binding artifact is outside this run") from None


def _validate_owned_root(
    root: Path, declared_root: Path, workspace: ApplicationWorkspace
) -> None:
    """Ensure an explicit artifact root stays inside its binding directory."""

    try:
        root_absolute = _absolute_path(root)
        declared_absolute = _absolute_path(declared_root)
        root_absolute.relative_to(declared_absolute)
        _reject_symlink_chain(declared_absolute, root_absolute)
        resolved_root = root_absolute.resolve(strict=False)
        resolved_declared = declared_absolute.resolve(strict=False)
        resolved_root.relative_to(resolved_declared)
        resolved_root.relative_to(workspace.root.resolve(strict=False))
    except (OSError, ValueError):
        raise AuthorityIntegrityError("binding artifact root is outside this run") from None


def _absolute_path(path: Path) -> Path:
    try:
        return Path(os.path.abspath(os.fspath(path)))
    except (OSError, TypeError, ValueError):
        raise AuthorityIntegrityError("binding artifact path is invalid") from None


def _reject_symlink_chain(root: Path, candidate: Path) -> None:
    """Reject symlinks in an admitted root-to-artifact path (no-follow)."""

    try:
        relative = candidate.relative_to(root)
    except ValueError:
        raise AuthorityIntegrityError("binding artifact is outside this run") from None
    current = root
    for part in (None, *relative.parts):
        if part is not None:
            current = current / part
        try:
            metadata = current.lstat()
        except FileNotFoundError:
            # A not-yet-created artifact is valid; existing ancestors have
            # still been checked before the first missing component.
            break
        except OSError:
            raise AuthorityIntegrityError("binding artifact path is invalid") from None
        if stat.S_ISLNK(metadata.st_mode):
            raise AuthorityIntegrityError("binding artifact is outside this run")


def _json_mapping(value: Mapping[str, object], *, label: str) -> dict[str, object]:
    try:
        candidate = dict(value)
        _validate_json(candidate, label=label, active=set(), depth=0)
    except (CapabilityTransportError, ValueError):
        raise
    except Exception:
        raise CapabilityTransportError(f"{label} is not a JSON object") from None
    return candidate


def _validate_json(value: object, *, label: str, active: set[int], depth: int) -> None:
    if depth > 64:
        raise CapabilityTransportError(f"{label} is too deeply nested")
    if isinstance(value, Mapping):
        identity = id(value)
        if identity in active:
            raise CapabilityTransportError(f"{label} contains a cycle")
        active.add(identity)
        try:
            for key, item in value.items():
                if not isinstance(key, str):
                    raise CapabilityTransportError(f"{label} has invalid keys")
                _validate_json(item, label=label, active=active, depth=depth + 1)
        finally:
            active.remove(identity)
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        identity = id(value)
        if identity in active:
            raise CapabilityTransportError(f"{label} contains a cycle")
        active.add(identity)
        try:
            for item in value:
                _validate_json(item, label=label, active=active, depth=depth + 1)
        finally:
            active.remove(identity)
        return
    if value is None or type(value) in {str, bool, int}:
        return
    if type(value) is float and math.isfinite(value):
        return
    raise CapabilityTransportError(f"{label} contains an unsupported value")


def _observation_ref(
    binding_id: str,
    capability_id: str,
    turn_id: str,
    call_id: str | None,
    arguments: Mapping[str, object],
    result: Mapping[str, object],
) -> str:
    payload = {
        "binding_id": binding_id,
        "capability_id": capability_id,
        "turn_id": turn_id,
        "call_id": call_id,
        "arguments": arguments,
        "result": result,
    }
    return "observation:sha256:" + hashlib.sha256(
        canonical_json_bytes(payload)
    ).hexdigest()


__all__ = ["ApplicationInvocationProjector", "ProjectionOutcome"]
