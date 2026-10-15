"""Mixed scenario projections retain their Authority-verified model identities."""

import hashlib
from importlib.metadata import version
from types import SimpleNamespace

import pytest

from capstone_agent.kernel_capability_preparation import AuthorityModelBinding
from capstone_agent.kernel_pi_session import _build_result_projections
from capstone_agent.thread_protocol import AttemptSnapshot, ModelContextSnapshot
from capstone_agent.thread_service import AttemptClaim
from capstone_agent.thread_service import _terminal_result_projections
from pypsa_model_authority.store import ModelStore, canonical_bytes
from pypsa_network_modeling.authority import PypsaModelArtifactAuthority
from pypsa_power_operations.profile import OperationsArtifactAuthority
from pypsa_power_operations.result_projection import PypsaOperationsResultProjector
from pypsa_agent.thread_binding import verify_bound_model_reference

REVISION = "revision:sha256:" + "a" * 64


@pytest.fixture
def scenarios(tmp_path):
    root = tmp_path / "context-run" / "domains"
    source = ModelStore(root / "source", run_id="context-run")
    target = ModelStore(root / "operations", run_id="context-run")
    components = {"buses": [], "generators": []}
    model = {
        "schema": "pypsa-model-revision/1.0", "run_id": "context-run",
        "catalog_id": "regional-six-bus", "parent_ref": None,
        "pypsa_version": version("pypsa"), "components": components,
        "component_digest": hashlib.sha256(canonical_bytes(components)).hexdigest(),
    }
    base = source.persist("model", model)
    growth = source.persist("model", {**model, "parent_ref": base, "edits": ["growth"]})
    foreign = source.persist("model", {**model, "catalog_id": "foreign"})
    source_authority = PypsaModelArtifactAuthority(source.root)
    authority = OperationsArtifactAuthority(target.root, "source")

    def operation(model_ref, capability, predecessor=None):
        details = {"status": "ok", "objective": 1300 if model_ref == base else 1900}
        if predecessor:
            details = {"status": "ok", "dispatch_result_ref": predecessor,
                       "bus_voltage_pu": {"center": [1.0, 1.0, 1.0]}}
        doc = {"schema": "pypsa-operation-result/1.0", "run_id": "context-run",
               "source_binding_id": "source", "target_binding_id": "operations",
               "model_ref": model_ref, "capability": capability, "status": "ok",
               "condition": "converged" if predecessor else "optimal",
               "formulation": capability, "details": details}
        result = target.persist("result", doc)
        evidence = target.persist("evidence", {
            "schema": "pypsa-operation-evidence/1.0", "run_id": "context-run",
            "source_binding_id": "source", "target_binding_id": "operations",
            "model_ref": model_ref, "result_ref": result, "formulation": capability,
        })
        return result, evidence

    baseline = operation(base, "operations.dispatch")
    grown = operation(growth, "operations.dispatch")
    pairs = [baseline, grown, operation(base, "operations.ac_validate", baseline[0]),
             operation(growth, "operations.ac_validate", grown[0])]
    unrelated = source.persist("model", {**model, "edits": ["unrelated-root"]})
    return SimpleNamespace(base=base, growth=growth, foreign=foreign, unrelated=unrelated, pairs=pairs,
                           source=source_authority, authority=authority, operation=operation, target=target)


def project(scenarios, pairs=None, *, attempt="attempt-3", resolver=None, events=None):
    from pypsa_agent.thread_binding import resolve_bound_model_revision

    pairs = scenarios.pairs if pairs is None else pairs
    bound = AuthorityModelBinding(
        "source", "regional-six-bus", REVISION, "pypsa", scenarios.base,
        model_reference_verifier=lambda ref: verify_bound_model_reference(
            scenarios.source, ref, model_id="regional-six-bus", base_ref=scenarios.base),
        model_revision_resolver=resolver or (lambda ref: resolve_bound_model_revision(
            scenarios.source, ref, model_id="regional-six-bus", base_ref=scenarios.base,
            base_revision=REVISION)),
    )
    runtime = SimpleNamespace(authority=scenarios.authority, executor=SimpleNamespace(invoke=lambda *_: None),
        profile=SimpleNamespace(id="pypsa-power-operations", projector_registry=SimpleNamespace(
            result_projector=PypsaOperationsResultProjector())))
    bindings = {"operations": SimpleNamespace(runtime=runtime)}
    profile = SimpleNamespace(model_binding=bound, prepared_application=SimpleNamespace(bindings=bindings))
    context = ModelContextSnapshot("ctx", "regional-six-bus", REVISION, "pypsa", "sel")
    claim = AttemptClaim("thread", "run", AttemptSnapshot("turn", attempt, "running", "ctx"),
                         "send_auto", "compare", "ctx", "sel", "lease", context)
    if events is None:
        events = tuple({"binding_id": "operations", "ok": True, "result_refs": [r],
                        "evidence_refs": [e], "capability_id": "operations.dispatch"} for r, e in pairs)
    return _build_result_projections(claim, (profile,), bindings,
                                    tuple(r for r, _ in pairs), tuple(e for _, e in pairs), events)


def test_baseline_then_mixed_dispatch_and_ac_project_each_verified_revision(scenarios):
    first = project(scenarios, scenarios.pairs[:1], attempt="attempt-1")
    assert first[0]["status"] == "completed"
    assert first[0]["model_revision"] == REVISION
    third = project(scenarios)
    assert len(third) == 4
    for index, item in enumerate(third):
        assert item["status"] == "completed"
        assert item["attempt_id"] == "attempt-3"
        assert item["result_ref"] == scenarios.pairs[index][0]
        assert item["evidence_refs"] == [scenarios.pairs[index][1]]
        expected = REVISION if index % 2 == 0 else scenarios.growth.replace("pypsa-model:", "revision:")
        assert item["model_revision"] == expected
        assert item["source"]["domain_pack_id"] == "pypsa-power-operations"
        if index % 2:
            assert item["_verified_context_binding"] == {
                "base_model_revision": REVISION, "result_model_revision": expected,
                "result_ref": item["result_ref"],
            }
        else:
            assert "_verified_context_binding" not in item


@pytest.mark.parametrize("model", ["foreign", "unrelated"])
def test_foreign_model_cannot_gain_a_projection(scenarios, model):
    foreign = scenarios.operation(getattr(scenarios, model), "operations.dispatch")
    assert project(scenarios, [foreign])[0]["status"] == "unavailable"


@pytest.mark.parametrize("bad_revision", [None, "not-a-revision", "revision:sha256:bad"])
def test_invalid_revision_resolver_fails_closed(scenarios, bad_revision):
    assert project(scenarios, scenarios.pairs[1:2], resolver=lambda _: bad_revision)[0]["status"] == "unavailable"


def test_evidence_for_another_result_does_not_get_attached(scenarios):
    mismatched = [(scenarios.pairs[0][0], scenarios.pairs[1][1])]
    assert project(scenarios, mismatched)[0]["status"] == "unavailable"


def test_resolver_exception_fails_closed(scenarios):
    def failed(_):
        raise ValueError("invalid verified lineage")
    assert project(scenarios, scenarios.pairs[1:2], resolver=failed)[0]["status"] == "unavailable"


def test_retained_result_without_current_attempt_provenance_is_rejected(scenarios):
    with pytest.raises(ValueError, match="owner"):
        project(scenarios, scenarios.pairs[:1], events=())


def test_only_currently_admitted_result_and_evidence_are_projected(scenarios):
    projected = project(scenarios, scenarios.pairs[1:2])
    assert len(projected) == 1
    assert projected[0]["result_ref"] == scenarios.pairs[1][0]
    assert projected[0]["evidence_refs"] == [scenarios.pairs[1][1]]


def test_authority_rejects_result_from_another_binding(scenarios):
    original = scenarios.authority.verify_result(scenarios.pairs[0][0]).document
    foreign = scenarios.target.persist("result", {**original, "target_binding_id": "foreign"})
    with pytest.raises(RuntimeError, match="lineage"):
        project(scenarios, [(foreign, scenarios.pairs[0][1])])


def test_corrupted_authority_artifact_is_rejected(scenarios):
    reference = scenarios.pairs[0][0]
    scenarios.target.artifact_path(reference, "result").write_text("{}")
    with pytest.raises(RuntimeError, match="integrity"):
        project(scenarios, scenarios.pairs[:1])


def test_verified_scenario_projections_pass_terminal_attempt_normalization(scenarios):
    projections = project(scenarios)
    context = ModelContextSnapshot("ctx", "regional-six-bus", REVISION, "pypsa", "sel")
    claim = AttemptClaim("thread", "run", AttemptSnapshot("turn", "attempt-3", "running", "ctx"),
                         "send_auto", "compare", "ctx", "sel", "lease", context)
    typed = _terminal_result_projections({
        "result_projections": list(projections),
        "admission": {"mode": "authority_backed", "assurance": "lineage_verified"},
        "result_refs": [r for r, _ in scenarios.pairs],
        "evidence_refs": [e for _, e in scenarios.pairs],
    }, claim=claim, phase="completed")
    assert len(typed) == 4
    assert all(item.status == "completed" for item in typed)
    assert [item.model_revision for item in typed] == [item["model_revision"] for item in projections]


def test_hosted_application_registers_verified_revision_resolver(scenarios, monkeypatch, tmp_path):
    import pypsa_agent.hosted as hosted

    captured = {}
    original = hosted.build_pypsa_thread_application

    def capture(**kwargs):
        captured.update(kwargs)
        return original(**kwargs)

    monkeypatch.setattr(hosted, "build_pypsa_thread_application", capture)
    monkeypatch.setenv("CAPSTONE_RUNS_ROOT", str(tmp_path / "runs"))
    assembly = hosted.build_registered_pypsa_thread_application()
    try:
        catalog = tmp_path / "tool-catalog.json"
        catalog.write_text('{"tools": []}')
        prepared = SimpleNamespace(bindings={"source": SimpleNamespace(runtime=SimpleNamespace(
            authority=scenarios.source, tool_catalog_path=catalog,
            executor=SimpleNamespace(invoke=lambda *_: {"model_ref": scenarios.base})))})
        context = SimpleNamespace(model_id="regional-six-bus", model_revision=REVISION,
                                  implementation_family="pypsa")
        binding = captured["model_binder"](prepared, context)
        assert callable(binding.model_revision_resolver)
        assert binding.revision_for_model_reference(scenarios.base) == REVISION
        assert binding.revision_for_model_reference(scenarios.growth) == scenarios.growth.replace("pypsa-model:", "revision:")
        with pytest.raises(ValueError, match="outside"):
            binding.revision_for_model_reference(scenarios.foreign)
    finally:
        assembly.capability_context_owner.close()
