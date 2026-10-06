"""Application grants for models used by a prepared Thread runtime."""
from collections.abc import Mapping
import json
from pathlib import Path
from typing import cast

from capability_agent._safe_files import write_bound_text
from capability_agent.application.context_store import ApplicationContextStore
from capability_agent.application.composition import PreparedBinding
from capability_agent.application.reference_handoff import ReferenceHandoffService

from .kernel_capability_preparation import PreparedKernelApplicationProfile


class PreparedKernelReferenceHandoffs:
    def __init__(self, profiles: tuple[PreparedKernelApplicationProfile, ...]) -> None:
        self.path: Path | None = None
        self._profiles: dict[str, PreparedKernelApplicationProfile] = {}
        self._services: dict[str, ReferenceHandoffService] = {}
        self._prepared_refs: set[tuple[str, str]] = set()
        self._records: list[dict[str, str]] = []
        for profile in profiles:
            source = profile.model_binding.binding_id
            grants = tuple(grant for grant in profile.profile.reference_grants
                if grant.source_binding_id == source and grant.reference_kind == "model")
            if not grants:
                continue
            path = profile.workspace.core_path / "reference-handoffs.json"
            if self.path is not None and path != self.path:
                raise ValueError("reference handoffs use different workspaces")
            self.path = path
            store = (ApplicationContextStore(profile.workspace, ApplicationContextStore.replay(profile.workspace))
                if profile.workspace.context_events_path.stat().st_size
                else ApplicationContextStore.initialize(profile.workspace))
            self._profiles[source] = profile
            bindings = cast(Mapping[str, PreparedBinding], getattr(profile.prepared_application, "bindings", {}))
            self._services[source] = ReferenceHandoffService(profile.profile, profile.workspace,
                store, bindings)
        if self.path is None:
            return
        previous = json.loads(self.path.read_text()) if self.path.exists() else None
        if previous is not None:
            if previous.get("schema") != "capability-agent-reference-handoffs/1.0":
                raise ValueError("reference handoff index is invalid")
            for record in previous["handoffs"]:
                self._prepare(record["source_binding_id"], record["reference"])
        for source, profile in self._profiles.items():
            self._prepare(source, profile.model_binding.context_ref)

    def _prepare(self, source: str, reference: str) -> None:
        profile = self._profiles.get(source)
        if profile is None:
            raise ValueError("reference has no application grant")
        if not profile.model_binding.accepts_model_reference(reference):
            raise ValueError("handoff model reference is not bound to this Thread")
        if (source, reference) in self._prepared_refs:
            return
        for grant in profile.profile.reference_grants:
            if grant.source_binding_id != source or grant.reference_kind != "model":
                continue
            bindings = cast(Mapping[str, PreparedBinding], getattr(profile.prepared_application, "bindings", {}))
            target = bindings[grant.target_binding_id]
            capability = next((document["id"] for document in target.runtime.capability_documents
                if str(document.get("id", "")).startswith(grant.capability_family + ".")), None)
            if not isinstance(capability, str):
                raise ValueError("granted capability family is not published")
            receipt = self._services[source].prepare_handoff(source_binding_id=source,
                target_binding_id=grant.target_binding_id, reference=reference,
                reference_kind=grant.reference_kind, purpose=grant.purpose, capability=capability)
            self._records.append({**receipt.document(), "handoff_ref": receipt.receipt_ref})
        self._prepared_refs.add((source, reference))
        assert self.path is not None
        write_bound_text(self.path, json.dumps({"schema": "capability-agent-reference-handoffs/1.0",
            "run_id": profile.workspace.run_id, "handoffs": self._records}, sort_keys=True) + "\n")

    def observe(self, event: Mapping[str, object]) -> None:
        if event.get("type") != "tool_result" or event.get("ok") is not True:
            return
        key, result = event.get("capability_key"), event.get("result")
        if not isinstance(key, Mapping) or not isinstance(result, Mapping):
            return
        source, reference = key.get("binding_id"), result.get("model_ref")
        if isinstance(source, str) and source in self._profiles and isinstance(reference, str):
            self._prepare(source, reference)
