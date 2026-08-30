from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

import pytest

import capability_agent.application.context_store as context_store_module
from capability_agent.application.context_store import ApplicationContextStore
from capability_agent.application.context_models import ContextEventDraft
from capability_agent.application.errors import (
    AuthorityIntegrityError,
    CapabilityRoutingError,
    DomainProjectionError,
)
from capability_agent.application.workspace import ApplicationWorkspace
from capability_agent.tools.catalog import (
    BoundToolDocument,
    CapabilityKey,
    CompositeToolCatalog,
    CoreToolCatalog,
)
from capability_agent.application.projector import ApplicationInvocationProjector


RESULT_REF = "result:opaque:one"
EVIDENCE_REF = "evidence:opaque:one"


@dataclass(frozen=True)
class Artifact:
    reference: str
    path: Path
    document: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class References:
    results: tuple[Artifact, ...] = ()
    evidence: tuple[Artifact, ...] = ()
    context: tuple[Artifact, ...] = ()


@dataclass
class Authority:
    workspace_root: Path
    authority_id: str = "grid-authority"
    admit_calls: list[tuple[str, dict[str, object], tuple[str, ...]]] = field(
        default_factory=list
    )
    fail_admit: bool = False
    raise_base_exception: bool = False
    admitted_references: References | None = None

    def admit(
        self,
        capability: str,
        result: dict[str, object],
        evidence_refs: tuple[str, ...],
    ) -> References:
        self.admit_calls.append((capability, result, evidence_refs))
        if self.raise_base_exception:
            raise KeyboardInterrupt("backend interrupt")
        if self.fail_admit:
            raise RuntimeError("foreign backend secret should not escape")
        if self.admitted_references is not None:
            return self.admitted_references
        return References(
            results=(Artifact(RESULT_REF, self.workspace_root / "result.json"),),
            evidence=(Artifact(EVIDENCE_REF, self.workspace_root / "evidence.json"),),
        )


@dataclass
class Delta:
    state: dict[str, object]

    def model_dump(self, *, mode: str = "python") -> dict[str, object]:
        assert mode in {"python", "json"}
        return {"state": self.state}


@dataclass
class Projector:
    projector_id: str = "state-v1"
    calls: list[object] = field(default_factory=list)

    def project(self, invocation: object) -> Delta:
        self.calls.append(invocation)
        return Delta({"last_capability": invocation.capability})


@dataclass
class ProjectorRegistry:
    projector: Projector
    calls: list[str] = field(default_factory=list)

    def require(self, projector_id: str) -> Projector:
        self.calls.append(projector_id)
        return self.projector


@dataclass
class StateAdapter:
    validate_calls: list[tuple[str, dict[str, object]]] = field(default_factory=list)
    merge_calls: list[tuple[str, dict[str, object], object]] = field(default_factory=list)

    def validate(self, *, binding_id: str, state: dict[str, object]) -> None:
        self.validate_calls.append((binding_id, state))

    def merge(
        self,
        *,
        binding_id: str,
        state: dict[str, object],
        delta: Delta,
    ) -> dict[str, object]:
        self.merge_calls.append((binding_id, state, delta))
        return {**state, **delta.state}


def _catalog() -> CompositeToolCatalog:
    core = CoreToolCatalog.default()
    domain_tool = BoundToolDocument(
        name="grid_asset_read",
        key=CapabilityKey("grid", "asset.read"),
        description="Read one bounded domain asset.",
        input_schema={"type": "object"},
        authority_id="grid-authority",
        protocol="grid-capability",
        protocol_version="1.0",
    )
    return CompositeToolCatalog(
        core_tools=core.tools,
        domain_tools=(domain_tool,),
    )


def _harness(tmp_path: Path, *, fail_admit: bool = False):
    workspace = ApplicationWorkspace.create(
        tmp_path / "runs", run_id="run-1", binding_ids=("grid", "inventory")
    )
    store = ApplicationContextStore.initialize(
        workspace,
        domains={
            "grid": "grid-state/1.0",
            "inventory": "inventory-state/1.0",
        },
    )
    store.append(
        ContextEventDraft(
            event_type="turn.started",
            turn_id="run-1-t001",
            payload={
                "ordinal": 1,
                "instruction": "Inspect",
                "instruction_sha256": "a" * 64,
                "nonce_sha256": "b" * 64,
            },
        )
    )
    grid_authority = Authority(
        workspace.domain_roots["grid"], fail_admit=fail_admit
    )
    inventory_authority = Authority(
        workspace.domain_roots["inventory"], authority_id="inventory-authority"
    )
    grid_projector = Projector()
    inventory_projector = Projector(projector_id="inventory-v1")
    grid_adapter = StateAdapter()
    inventory_adapter = StateAdapter()
    def prepared(binding_id: str, authority: Authority, projector: Projector, adapter: StateAdapter):
        profile = SimpleNamespace(
            manifest=SimpleNamespace(authority_id=authority.authority_id),
            state_adapter=adapter,
            projector_registry=ProjectorRegistry(projector),
        )
        return SimpleNamespace(
            binding=SimpleNamespace(binding_id=binding_id, profile=profile),
            runtime=SimpleNamespace(authority=authority),
        )
    bindings = {
        "grid": prepared("grid", grid_authority, grid_projector, grid_adapter),
        "inventory": prepared(
            "inventory", inventory_authority, inventory_projector, inventory_adapter
        ),
    }
    return SimpleNamespace(
        workspace=workspace,
        store=store,
        bindings=bindings,
        grid_authority=grid_authority,
        inventory_authority=inventory_authority,
        grid_projector=grid_projector,
        inventory_projector=inventory_projector,
        grid_adapter=grid_adapter,
        inventory_adapter=inventory_adapter,
    )


def test_projector_routes_structured_key_to_only_matching_binding(tmp_path: Path) -> None:
    current = _harness(tmp_path)
    projector = ApplicationInvocationProjector(
        store=current.store,
        catalog=_catalog(),
        bindings=current.bindings,
    )
    projector.observe(
        {
            "type": "tool_execution_start",
            "call_id": "call-1",
            "tool_name": "grid_asset_read",
            "capability_key": CapabilityKey("grid", "asset.read"),
            "arguments": {"asset_id": "a-1"},
        },
        turn_id="run-1-t001",
    )
    outcome = projector.observe(
        {
            "type": "tool_result",
            "call_id": "call-1",
            "capability_key": CapabilityKey("grid", "asset.read"),
            "projector_id": "state-v1",
            "ok": True,
            "result": {"value": 1},
            "evidence_refs": [EVIDENCE_REF],
        },
        turn_id="run-1-t001",
    )

    assert outcome.binding_id == "grid"
    assert current.grid_authority.admit_calls[0][0] == "asset.read"
    assert current.inventory_authority.admit_calls == []
    assert len(current.grid_projector.calls) == 1
    assert current.inventory_projector.calls == []
    assert current.grid_adapter.merge_calls[0][0] == "grid"
    assert current.inventory_adapter.merge_calls == []
    assert current.store.snapshot.domains["grid"].revision == 1
    assert current.store.snapshot.domains["inventory"].revision == 0


def test_projector_keeps_core_tool_references_opaque(tmp_path: Path) -> None:
    current = _harness(tmp_path)
    projector = ApplicationInvocationProjector(
        store=current.store,
        catalog=_catalog(),
        bindings=current.bindings,
    )

    projector.observe(
        {
            "type": "tool_result",
            "tool_name": "agent_record_decision",
            "ok": True,
            "result": {"decision": "continue"},
        },
        turn_id="run-1-t001",
    )

    assert current.grid_authority.admit_calls == []
    assert current.inventory_authority.admit_calls == []
    assert current.store.snapshot.domains["grid"].revision == 0
    assert current.store.snapshot.domains["inventory"].revision == 0


def test_projector_keeps_context_core_tool_opaque_when_domain_call_is_in_flight(
    tmp_path: Path,
) -> None:
    current = _harness(tmp_path)
    projector = ApplicationInvocationProjector(
        store=current.store,
        catalog=_catalog(),
        bindings=current.bindings,
    )

    projector.observe(
        {
            "type": "tool_execution_start",
            "tool_call_id": "domain-call",
            "tool_name": "grid_asset_read",
        }
    )
    projector.observe(
        {
            "type": "tool_execution_start",
            "tool_call_id": "core-call",
            "tool_name": "agent_context_get",
        }
    )
    assert (
        projector.observe(
            {
                "type": "tool_result",
                "tool_call_id": "core-call",
                "tool_name": "agent_context_get",
                "ok": True,
                "result": {"revision": 1},
            },
            turn_id="run-1-t001",
        )
        is None
    )

    assert current.grid_authority.admit_calls == []
    assert current.inventory_authority.admit_calls == []
    assert current.store.snapshot.domains["grid"].revision == 0
    assert current.store.snapshot.domains["inventory"].revision == 0


def test_projector_integrity_failure_adds_no_result_evidence_or_state(
    tmp_path: Path,
) -> None:
    current = _harness(tmp_path, fail_admit=True)
    projector = ApplicationInvocationProjector(
        store=current.store,
        catalog=_catalog(),
        bindings=current.bindings,
    )
    before = current.store.snapshot
    before_lines = current.workspace.context_events_path.read_text(encoding="utf-8")

    with pytest.raises(AuthorityIntegrityError, match="admission"):
        projector.observe(
            {
                "type": "tool_result",
                "tool_name": "grid_asset_read",
                "capability_key": CapabilityKey("grid", "asset.read"),
                "projector_id": "state-v1",
                "ok": True,
                "result": {"value": 1},
                "evidence_refs": [EVIDENCE_REF],
            },
            turn_id="run-1-t001",
        )

    assert current.store.snapshot == before
    assert current.workspace.context_events_path.read_text(encoding="utf-8") == before_lines
    assert current.grid_projector.calls == []
    assert current.grid_adapter.merge_calls == []


def test_projector_rejects_unmatched_binding_without_mutation(tmp_path: Path) -> None:
    current = _harness(tmp_path)
    catalog = CompositeToolCatalog(
        core_tools=_catalog().core_tools,
        domain_tools=(
            BoundToolDocument(
                name="missing_asset_read",
                key=CapabilityKey("missing", "asset.read"),
                description="A capability for an unprepared binding.",
                input_schema={"type": "object"},
                authority_id="missing-authority",
                protocol="missing-capability",
                protocol_version="1.0",
            ),
        ),
    )
    projector = ApplicationInvocationProjector(
        current.store, catalog, current.bindings
    )
    before = current.store.snapshot
    before_lines = current.workspace.context_events_path.read_text(encoding="utf-8")

    with pytest.raises(CapabilityRoutingError, match="binding"):
        projector.observe(
            {
                "type": "tool_result",
                "tool_name": "missing_asset_read",
                "capability_key": CapabilityKey("missing", "asset.read"),
                "projector_id": "state-v1",
                "ok": True,
                "result": {"value": 1},
            },
            turn_id="run-1-t001",
        )

    assert current.store.snapshot == before
    assert current.workspace.context_events_path.read_text(encoding="utf-8") == before_lines
    assert current.grid_authority.admit_calls == []
    assert current.grid_adapter.merge_calls == []


def test_projector_sanitizes_authority_errors_and_keeps_context_unchanged(
    tmp_path: Path,
) -> None:
    current = _harness(tmp_path, fail_admit=True)
    projector = ApplicationInvocationProjector(
        current.store, _catalog(), current.bindings
    )
    before = current.store.snapshot

    with pytest.raises(AuthorityIntegrityError) as error:
        projector.observe(
            {
                "type": "tool_result",
                "tool_name": "grid_asset_read",
                "capability_key": CapabilityKey("grid", "asset.read"),
                "projector_id": "state-v1",
                "ok": True,
                "result": {"value": 1},
                "evidence_refs": [EVIDENCE_REF],
            },
            turn_id="run-1-t001",
        )

    assert "foreign backend secret" not in str(error.value)
    assert current.store.snapshot == before


def test_projector_does_not_swallow_base_exception_from_authority(
    tmp_path: Path,
) -> None:
    current = _harness(tmp_path)
    current.grid_authority.raise_base_exception = True
    projector = ApplicationInvocationProjector(
        current.store, _catalog(), current.bindings
    )
    before = current.store.snapshot

    with pytest.raises(KeyboardInterrupt):
        projector.observe(
            {
                "type": "tool_result",
                "tool_name": "grid_asset_read",
                "capability_key": CapabilityKey("grid", "asset.read"),
                "projector_id": "state-v1",
                "ok": True,
                "result": {"value": 1},
                "evidence_refs": [EVIDENCE_REF],
            },
            turn_id="run-1-t001",
        )

    assert current.store.snapshot == before


def test_projector_rejects_unstructured_capability_alias(tmp_path: Path) -> None:
    current = _harness(tmp_path)
    projector = ApplicationInvocationProjector(
        current.store, _catalog(), current.bindings
    )
    before = current.store.snapshot

    with pytest.raises(CapabilityRoutingError, match="structured key"):
        projector.observe(
            {
                "type": "tool_result",
                "capability": "asset.read",
                "ok": True,
                "result": {"value": 1},
            },
            turn_id="run-1-t001",
        )

    assert current.store.snapshot == before
    assert current.grid_authority.admit_calls == []


def test_projector_rejects_domain_tool_name_without_structured_key(
    tmp_path: Path,
) -> None:
    current = _harness(tmp_path)
    projector = ApplicationInvocationProjector(
        current.store, _catalog(), current.bindings
    )
    before = current.store.snapshot

    with pytest.raises(CapabilityRoutingError, match="structured key"):
        projector.observe(
            {
                "type": "tool_result",
                "tool_name": "grid_asset_read",
                "projector_id": "state-v1",
                "ok": True,
                "result": {"value": 1},
            },
            turn_id="run-1-t001",
        )

    assert current.store.snapshot == before
    assert current.grid_authority.admit_calls == []


def test_projector_rejects_sibling_artifact_when_authority_uses_run_root(
    tmp_path: Path,
) -> None:
    current = _harness(tmp_path)
    current.grid_authority.workspace_root = current.workspace.root
    current.grid_authority.admitted_references = References(
        results=(
            Artifact(
                RESULT_REF,
                current.workspace.domain_roots["inventory"] / "result.json",
            ),
        ),
        evidence=(
            Artifact(
                EVIDENCE_REF,
                current.workspace.domain_roots["inventory"] / "evidence.json",
            ),
        ),
    )
    projector = ApplicationInvocationProjector(
        current.store, _catalog(), current.bindings
    )
    before = current.store.snapshot

    with pytest.raises(AuthorityIntegrityError, match="outside"):
        projector.observe(
            {
                "type": "tool_result",
                "tool_name": "grid_asset_read",
                "capability_key": CapabilityKey("grid", "asset.read"),
                "projector_id": "state-v1",
                "ok": True,
                "result": {"value": 1},
                "evidence_refs": [EVIDENCE_REF],
            },
            turn_id="run-1-t001",
        )

    assert current.store.snapshot == before
    assert current.grid_adapter.merge_calls == []


def test_projector_rejects_symlinked_artifact_escape(
    tmp_path: Path,
) -> None:
    current = _harness(tmp_path)
    foreign = current.workspace.domain_roots["inventory"] / "foreign.json"
    foreign.write_text("foreign", encoding="utf-8")
    escaped = current.workspace.domain_roots["grid"] / "escaped.json"
    escaped.symlink_to(foreign)
    current.grid_authority.admitted_references = References(
        results=(Artifact(RESULT_REF, escaped),)
    )
    projector = ApplicationInvocationProjector(
        current.store, _catalog(), current.bindings
    )
    before = current.store.snapshot

    with pytest.raises(AuthorityIntegrityError, match="outside"):
        projector.observe(
            {
                "type": "tool_result",
                "tool_name": "grid_asset_read",
                "capability_key": CapabilityKey("grid", "asset.read"),
                "projector_id": "state-v1",
                "ok": True,
                "result": {"value": 1},
            },
            turn_id="run-1-t001",
        )

    assert current.store.snapshot == before
    assert current.grid_adapter.merge_calls == []


def test_projector_rejects_foreign_event_turn_even_when_explicit_turn_is_current(
    tmp_path: Path,
) -> None:
    current = _harness(tmp_path)
    projector = ApplicationInvocationProjector(
        current.store, _catalog(), current.bindings
    )
    before = current.store.snapshot

    with pytest.raises(CapabilityRoutingError, match="turn"):
        projector.observe(
            {
                "type": "tool_result",
                "tool_name": "grid_asset_read",
                "capability_key": CapabilityKey("grid", "asset.read"),
                "turn_id": "run-foreign-t001",
                "ok": True,
                "result": {"value": 1},
            },
            turn_id="run-1-t001",
        )

    assert current.store.snapshot == before
    assert current.grid_authority.admit_calls == []


def test_projector_rolls_back_all_context_events_when_store_fails_mid_projection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    current = _harness(tmp_path)
    projector = ApplicationInvocationProjector(
        current.store, _catalog(), current.bindings
    )
    before = current.store.snapshot
    before_lines = current.workspace.context_events_path.read_bytes()
    real_replace = context_store_module._replace_snapshot

    def replace_then_fail(source: Path, destination: Path) -> None:
        real_replace(source, destination)
        raise RuntimeError("storage backend secret")

    monkeypatch.setattr(context_store_module, "_replace_snapshot", replace_then_fail)

    with pytest.raises(DomainProjectionError, match="persistence") as error:
        projector.observe(
            {
                "type": "tool_result",
                "tool_name": "grid_asset_read",
                "capability_key": CapabilityKey("grid", "asset.read"),
                "projector_id": "state-v1",
                "ok": True,
                "result": {"value": 1},
                "evidence_refs": [EVIDENCE_REF],
            },
            turn_id="run-1-t001",
        )

    assert "storage backend secret" not in str(error.value)
    assert current.store.snapshot == before
    assert current.workspace.context_events_path.read_bytes() == before_lines
    assert current.store.snapshot.domains["grid"].revision == 0
