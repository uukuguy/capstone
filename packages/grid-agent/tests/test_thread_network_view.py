from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from capstone_agent.thread_protocol import AttemptSnapshot, ModelContextSnapshot
from capstone_agent.thread_service import AttemptClaim
from capstone_model_capability_spi import ModelCapabilitySelection
from grid_agent.application.thread_capabilities import (
    PANDAPOWER_PROFILE_DESCRIPTOR, build_pandapower_thread_application,
)
from grid_agent.thread_network_view import build_pandapower_thread_network_provider
from grid_simulator.engine import Pandapower340Engine
from grid_simulator.models import ModelRegistry


class _Grid:
    def __init__(self, claim, context, runtime, binding):
        self.values = (claim, context, runtime, binding)
        self.endpoints = {}
        self.responses = {}

    def __iter__(self):
        return iter(self.values)

    def invoke(self, capability, arguments):
        key = (capability, tuple(sorted(arguments.items())))
        if key not in self.responses:
            self.responses[key] = self.values[2].executor.invoke(capability, arguments)
        return self.responses[key]


def _provider(grid):
    provider = build_pandapower_thread_network_provider(grid.values[1])
    provider._executor = SimpleNamespace(invoke=grid.invoke)
    return provider


def _claim(model_id: str, revision: str) -> AttemptClaim:
    context = ModelContextSnapshot(
        "ctx_network", model_id, revision, "pandapower", "sel_1",
        (PANDAPOWER_PROFILE_DESCRIPTOR.reference,),
    )
    return AttemptClaim(
        "thr_network", "run_network",
        AttemptSnapshot("turn_1", "attempt_1", "running", context.id),
        "send_professional", "inspect", context.id, context.selection_revision,
        "lease_1", context,
    )


@pytest.fixture(scope="module", params=["ieee39", "case24_ieee_rts"])
def grid(request, tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp(request.param)
    model_id = request.param
    revision = ModelRegistry(Pandapower340Engine()).trusted_revision_ref(model_id)
    claim = _claim(model_id, revision)

    def bind(prepared, context):
        from capstone_agent.kernel_capability_preparation import AuthorityModelBinding

        opened = prepared.bindings["grid"].runtime.executor.invoke(
            "context.open", {"model_id": context.model_id},
        )
        return AuthorityModelBinding(
            "grid", context.model_id, opened["revision_ref"],
            context.implementation_family, opened["context_ref"],
        )

    assembly = build_pandapower_thread_application(
        default_model_id=model_id,
        model_resolver=lambda identifier: {
            "model_id": identifier, "revision_ref": revision,
            "implementation_family": "pandapower",
        },
        workspace_root=tmp_path,
        model_binder=bind,
        session_builder=lambda *_args: None,
        default_selection=ModelCapabilitySelection((PANDAPOWER_PROFILE_DESCRIPTOR.reference,)),
    )
    context = assembly.capability_context_owner.prepare(claim)
    prepared = context.contributions[0].prepared
    runtime = prepared.prepared_application.bindings["grid"].runtime
    yield _Grid(claim, context, runtime, prepared.model_binding)
    assembly.capability_context_owner.close()


def _endpoint(grid, *, index: int = 11, kind: str = "line"):
    claim, context, runtime, binding = grid
    if (kind, index) not in grid.endpoints:
        grid.endpoints[(kind, index)] = runtime.executor.invoke("topology.branch.endpoints.get", {
            "context_ref": binding.context_ref, "kind": kind,
            "namespace": "pandapower_index", "identifier": str(index),
        })
    endpoint = grid.endpoints[(kind, index)]
    evidence_ref = endpoint["evidence_ref"]
    runtime.authority.admit("topology.branch.endpoints.get", endpoint, (evidence_ref,))
    event = {
        "binding_id": "grid", "capability": "topology.branch.endpoints.get",
        "ok": True, "result_refs": [], "evidence_refs": [evidence_ref],
    }
    return evidence_ref, event


def test_thread_topology_uses_exact_real_registered_model(grid):
    claim, context, runtime, binding = grid
    projection = build_pandapower_thread_network_provider(context).project(claim, (), (), ())
    source = runtime.executor.invoke("operator.diagram.get", {"context_ref": binding.context_ref})

    assert projection["diagram"]["model"] == {
        "id": claim.model_context.model_id,
        "revision": claim.model_context.model_revision,
        "source": "gridctl",
    }
    assert projection["diagram"]["buses"] == source["buses"]
    assert projection["diagram"]["branches"] == source["branches"]
    assert len(source["buses"]) == (39 if claim.model_context.model_id == "ieee39" else 24)
    assert projection["layer"] == {"focus_ids": [], "next_focus_ids": [], "overlay": None}


def test_thread_ranking_focus_uses_the_exact_authority_subset(grid):
    claim, context, runtime, binding = grid
    flow = grid.invoke("analysis.powerflow.ac.run", {"context_ref": binding.context_ref})
    ranked = grid.invoke("result.branches.rank", {
        "result_ref": flow["result_ref"], "metric": "loading_percent",
        "direction": "descending", "limit": 3, "element_kind": "line",
    })
    provider = _provider(grid)
    native = {"type": "tool_execution_end", "toolCallId": "rank_call", "result": {"details": {
        "event": "tool_result", "capability": "result.branches.rank", "ok": True,
        "capability_key": {"binding_id": "grid", "capability_id": "result.branches.rank"},
        "result": ranked,
    }}}
    observe = getattr(provider, "observe_runtime_event", lambda _event: None)
    observe(native)
    event = {"tool_call_id": "rank_call", "binding_id": "grid", "capability": "result.branches.rank", "ok": True, "result_refs": [flow["result_ref"]]}
    projection = provider.project(claim, (flow["result_ref"],), (), (event,))
    expected = [f"line:{row['pandapower_index']}" for row in ranked["branches"]]
    assert projection["layer"]["focus_ids"] == expected
    assert projection["layer"]["overlay"] == {
        "metric": "loading_percent", "unit": "%", "source_ref": flow["result_ref"],
        "values": [{"id": identifier, "value": row["loading_percent"]} for identifier, row in zip(expected, ranked["branches"], strict=True)],
    }


def test_thread_focus_uses_admitted_endpoint_evidence_for_real_line(grid):
    claim, context, _runtime, _binding = grid
    evidence_ref, event = _endpoint(grid)
    projection = _provider(grid).project(
        claim, (), (evidence_ref,), (event,),
    )
    assert projection["layer"]["focus_ids"] == ["line:11"]
    assert projection["layer"]["next_focus_ids"] == []
    assert projection["layer"]["overlay"] is None


@pytest.mark.parametrize("kind,limit", [("line", 21), ("trafo", 1)])
def test_ranking_obeys_shared_focus_and_overlay_contract(grid, kind, limit):
    from capstone_agent.thread_network import normalize_thread_network_projection

    claim, _context, _runtime, binding = grid
    flow = grid.invoke("analysis.powerflow.ac.run", {"context_ref": binding.context_ref})
    ranked = grid.invoke("result.branches.rank", {
        "result_ref": flow["result_ref"], "metric": "loading_percent",
        "direction": "descending", "limit": limit, "element_kind": kind,
    })
    provider = _provider(grid)
    provider.observe_runtime_event({"type": "tool_result", "event": "tool_result",
        "tool_call_id": "rank_limit", "capability": "result.branches.rank", "ok": True,
        "capability_key": {"binding_id": "grid"}, "result": ranked})
    event = {"tool_call_id": "rank_limit", "binding_id": "grid", "capability": "result.branches.rank",
             "ok": True, "result_refs": [flow["result_ref"]]}
    view = provider.project(claim, (flow["result_ref"],), (), (event,))
    normalized = normalize_thread_network_projection(view, claim, (flow["result_ref"],))
    assert normalized is not None
    layer = normalized["layer"]
    assert len(layer["focus_ids"]) == min(limit, 20)
    if kind == "trafo":
        assert layer["overlay"] is None


@pytest.mark.parametrize("defect", ["not_admitted", "failed", "foreign_context", "wrong_call", "changed_rows"])
def test_ranking_rejects_missing_or_foreign_provenance(grid, defect):
    claim, _context, _runtime, binding = grid
    flow = grid.invoke("analysis.powerflow.ac.run", {"context_ref": binding.context_ref})
    ranked = dict(grid.invoke("result.branches.rank", {"result_ref": flow["result_ref"],
        "metric": "loading_percent", "direction": "descending", "limit": 3, "element_kind": "line"}))
    if defect == "foreign_context": ranked["context_ref"] = "context:sha256:" + "f" * 64
    if defect == "changed_rows": ranked["branches"] = list(reversed(ranked["branches"]))
    provider = _provider(grid)
    provider.observe_runtime_event({"type": "tool_result", "event": "tool_result", "tool_call_id": "rank_private",
        "capability": "result.branches.rank", "ok": True, "capability_key": {"binding_id": "grid"}, "result": ranked})
    event = {"tool_call_id": "wrong" if defect == "wrong_call" else "rank_private", "binding_id": "grid",
        "capability": "result.branches.rank", "ok": defect != "failed", "result_refs": [flow["result_ref"]]}
    admitted = () if defect == "not_admitted" else (flow["result_ref"],)
    view = provider.project(claim, admitted, (), (event,))
    assert view["layer"]["focus_ids"] == []
    assert view["layer"]["overlay"] is None


def test_thread_focus_uses_another_real_line_and_deduplicates(grid):
    claim, context, _runtime, _binding = grid
    evidence_ref, event = _endpoint(grid, index=17)
    projection = _provider(grid).project(
        claim, (), (evidence_ref, evidence_ref), (event, event),
    )
    assert projection["layer"]["focus_ids"] == ["line:17"]


@pytest.mark.parametrize("provenance", [
    "unadmitted", "missing", "failed", "wrong_binding", "wrong_capability",
])
def test_thread_focus_requires_current_admission_and_successful_tool_provenance(grid, provenance):
    claim, context, _runtime, _binding = grid
    evidence_ref, event = _endpoint(grid)
    evidence_refs = (evidence_ref,)
    events = (event,)
    if provenance == "unadmitted":
        evidence_refs = ()
    elif provenance == "missing":
        events = ()
    elif provenance == "failed":
        event["ok"] = False
    elif provenance == "wrong_binding":
        event["binding_id"] = "other"
    elif provenance == "wrong_capability":
        event["capability"] = "model.element.get"
    projection = _provider(grid).project(
        claim, (), evidence_refs, events,
    )
    assert projection["layer"]["focus_ids"] == []


@pytest.mark.parametrize("field,value", [
    ("context_ref", "context:sha256:" + "f" * 64),
    ("revision_ref", "revision:sha256:" + "f" * 64),
    ("evidence_type", "analysis_result"),
    ("capability_id", "model.constraints.describe"),
    ("subject_ref", "asset:bus:sha256:" + "f" * 64),
])
def test_thread_focus_rejects_foreign_or_unrelated_evidence(grid, monkeypatch, field, value):
    claim, context, runtime, _binding = grid
    evidence_ref, event = _endpoint(grid)
    verified = runtime.authority.verify_evidence(evidence_ref)
    monkeypatch.setattr(runtime.authority, "verify_evidence", lambda _reference: replace(
        verified, document={**verified.document, field: value},
    ))
    projection = _provider(grid).project(
        claim, (), (evidence_ref,), (event,),
    )
    assert projection["layer"]["focus_ids"] == []


@pytest.mark.parametrize("field,value", [
    ("context_ref", "context:sha256:" + "f" * 64),
    ("revision_ref", "revision:sha256:" + "f" * 64),
])
def test_thread_topology_rejects_foreign_authority_identity(grid, monkeypatch, field, value):
    claim, context, runtime, binding = grid
    diagram = grid.invoke("operator.diagram.get", {"context_ref": binding.context_ref})
    provider = _provider(grid)
    monkeypatch.setattr(provider, "_executor", SimpleNamespace(invoke=lambda *_args: {**diagram, field: value}))
    with pytest.raises(ValueError, match="another context or revision"):
        provider.project(claim, (), (), ())


@pytest.mark.parametrize("field,value", [
    ("thread_id", "thr_other"), ("run_id", "run_other"),
    ("model_id", "case9"), ("model_revision", "revision:sha256:" + "f" * 64),
    ("implementation_family", "pypsa"), ("id", "ctx_other"),
])
def test_thread_topology_rejects_another_claim_identity(grid, field, value):
    claim, context, _runtime, _binding = grid
    if field in {"thread_id", "run_id"}:
        foreign = replace(claim, **{field: value})
    else:
        snapshot = replace(claim.model_context, **{field: value})
        foreign = replace(claim, model_context=snapshot, model_context_id=snapshot.id,
                          attempt=replace(claim.attempt, target_model_context_id=snapshot.id))
    with pytest.raises(ValueError, match="does not match Attempt"):
        build_pandapower_thread_network_provider(context).project(foreign, (), (), ())


@pytest.mark.parametrize("field,value", [
    ("context_ref", "context:sha256:" + "f" * 64),
    ("revision_ref", "revision:sha256:" + "f" * 64),
    ("asset_ref", "asset:line:sha256:" + "f" * 64),
    ("element", {"kind": "line", "index": 100000}),
])
def test_thread_focus_rejects_foreign_or_unknown_resolved_elements(grid, monkeypatch, field, value):
    claim, context, runtime, _binding = grid
    evidence_ref, event = _endpoint(grid)
    provider = _provider(grid)
    invoke = provider._executor.invoke

    def altered(capability, arguments):
        document = invoke(capability, arguments)
        if capability == "model.element.get" and field == "element":
            return {**document, "element": {**document["element"], **value}}
        return {**document, field: value} if capability == "model.element.get" else document

    monkeypatch.setattr(provider, "_executor", SimpleNamespace(invoke=altered))
    projection = provider.project(
        claim, (), (evidence_ref,), (event,),
    )
    assert projection["layer"]["focus_ids"] == []


@pytest.mark.parametrize("kind", ["trafo", "trafo3w"])
def test_thread_focus_resolves_transformer_assets_and_bounds_focus(grid, monkeypatch, kind):
    claim, context, runtime, binding = grid
    assets = {f"evidence:sha256:{index:064x}": f"asset:{kind}:sha256:{index:064x}"
              for index in range(25)}
    branches = [
        {"id": f"{kind}:{index}" + suffix, "kind": kind}
        for index in range(25)
        for suffix in ((":mv", ":lv") if kind == "trafo3w" else ("",))
    ]
    calls = []

    def invoke(capability, arguments):
        calls.append((capability, arguments))
        document = {"context_ref": binding.context_ref, "revision_ref": binding.model_revision}
        if capability == "operator.diagram.get":
            return {**document, "coordinate_system": "schematic", "buses": [], "branches": branches}
        assert capability == "model.element.get"
        assert arguments["namespace"] == "asset_ref"
        assert arguments["kind"] == kind
        subject = arguments["identifier"]
        return {**document, "asset_ref": subject, "element": {
            "asset_ref": subject, "kind": kind, "index": int(subject.rsplit(":", 1)[1], 16),
        }}

    provider = _provider(grid)
    monkeypatch.setattr(provider, "_executor", SimpleNamespace(invoke=invoke))
    monkeypatch.setattr(runtime.authority, "verify_evidence", lambda ref: SimpleNamespace(document={
        "evidence_type": "network_fact", "capability_id": "topology.branch.endpoints.get",
        "context_ref": binding.context_ref, "revision_ref": binding.model_revision,
        "subject_ref": assets[ref],
    }))
    event = {"binding_id": "grid", "capability": "topology.branch.endpoints.get",
             "ok": True, "evidence_refs": list(assets)}
    projection = provider.project(
        claim, (), tuple(assets), (event,),
    )
    assert projection["layer"]["focus_ids"] == [branch["id"] for branch in branches[:20]]
    assert len(calls) == (11 if kind == "trafo3w" else 21)
