from pathlib import Path

import pytest

from pandapower_domain.authority import PandapowerArtifactAuthority


@pytest.fixture
def authority(tmp_path: Path):
    from grid_simulator.operations import dispatch
    from grid_simulator.protocol import GridCapabilityRequest
    def invoke(capability, arguments):
        response = dispatch(GridCapabilityRequest(protocol="grid-capability", protocol_version="1.0",
                            request_id="coverage", capability=capability, arguments=arguments), tmp_path)
        if not response.ok:
            from pandapower_domain.execution import SimulatorCapabilityError
            raise SimulatorCapabilityError(response.error.model_dump())
        return response.result
    context = invoke("context.open", {"model_id": "ieee39"})
    return invoke, context, PandapowerArtifactAuthority(tmp_path)


def proposal(**changes):
    return {"operation": "powerflow", "objects": [], "changes": [], "measure": None,
            "direction": "descending", "scenario": "baseline", "scope": "full", **changes}


@pytest.mark.parametrize("invalid", ["identifier-length", "object-count", "change-count", "factor-limit", "all-identifier"])
def test_published_schema_enforces_decoder_bounds(invalid):
    from jsonschema import Draft202012Validator
    from pandapower_domain.task_coverage import PandapowerTaskProvider, _decode
    selector = {"kind": "bus", "namespace": "name", "identifier": "x" * 512}
    change = {"target": selector, "fields": ["p_mw", "q_mvar"], "factor": 100}
    payload = proposal(objects=[selector] * 64, changes=[change] * 16)
    validator = Draft202012Validator(PandapowerTaskProvider.schema_document["payload_schema"])
    assert validator.is_valid(payload)
    _decode(payload)
    if invalid == "identifier-length":
        selector["identifier"] += "x"
    elif invalid == "object-count":
        payload["objects"].append(selector)
    elif invalid == "change-count":
        payload["changes"].append(change)
    elif invalid == "factor-limit":
        change["factor"] = 101
    else:
        selector["namespace"] = "all"
    assert not validator.is_valid(payload)
    with pytest.raises(ValueError):
        _decode(payload)


@pytest.mark.parametrize("operation", ["contingency", "ranking"])
@pytest.mark.parametrize("direction", ["descending", None])
def test_generator_contingency_is_unsupported_before_authority_call(operation, direction):
    from pandapower_domain.task_coverage import PandapowerTaskProvider
    calls = []
    result = PandapowerTaskProvider().resolve("g", proposal(operation=operation, direction=direction, scenario="contingency",
        objects=[{"kind": "gen", "namespace": "all", "identifier": "*"}]),
        context_ref="context", revision_ref="revision", invoke=lambda *args: calls.append(args))
    assert result.status == "unsupported"
    assert calls == []


def test_baseline_cannot_certify_changed_scenario(authority):
    from pandapower_domain.task_coverage import PandapowerTaskProvider
    invoke, context, verifier = authority
    provider = PandapowerTaskProvider()
    task = provider.resolve("g", proposal(scenario="changed", changes=[{
        "target": {"kind": "bus", "namespace": "pandapower_index", "identifier": "3"},
        "fields": ["p_mw", "q_mvar"], "factor": 1.2}]),
        context_ref=context["context_ref"], revision_ref=context["revision_ref"], invoke=invoke)
    result = invoke("analysis.powerflow.ac.run", {"context_ref": context["context_ref"]})
    conclusion = provider.conclude(task, authority=verifier, result_refs=(result["result_ref"],),
                                  evidence_refs=tuple(result["evidence_refs"]))
    assert conclusion.status == "unresolved"


def test_rejects_unknown_requirement_fields():
    from pandapower_domain.task_coverage import PandapowerTaskProvider
    with pytest.raises(ValueError):
        PandapowerTaskProvider().resolve("g", proposal(shell="python"), context_ref="c", revision_ref="r", invoke=None)


@pytest.mark.parametrize("direction", ["descending", None])
def test_overview_describes_selected_authority_model_without_calculation(authority, direction):
    from pandapower_domain.task_coverage import PandapowerTaskProvider
    invoke, context, verifier = authority
    calls = []
    def recorded(capability, arguments):
        calls.append(capability)
        return invoke(capability, arguments)
    provider = PandapowerTaskProvider()
    task = provider.resolve("g", proposal(operation="overview", direction=direction), context_ref=context["context_ref"],
                            revision_ref=context["revision_ref"], invoke=recorded, answer_policy={"language": "zh", "scale": "concise"})
    answer = provider.conclude(task, authority=verifier, result_refs=(), evidence_refs=())
    text = provider.render_conclusion(answer, language="zh", scale="concise")
    assert calls == ["context.get"]
    assert "ieee39" in text and "39" in text and "35" in text and "11" in text
    assert "母线" in text and "线路" in text and "变压器" in text and "潮流" in text
    assert answer.status == "supported" and not answer.result_refs and not answer.evidence_refs


def test_ranking_cannot_silently_choose_a_missing_direction():
    from pandapower_domain.task_coverage import PandapowerTaskProvider
    calls = []
    task = PandapowerTaskProvider().resolve("g", proposal(operation="ranking", measure="loading_percent", direction=None),
        context_ref="context", revision_ref="revision", invoke=lambda *args: calls.append(args))
    assert task.status == "clarification" and not task.execution_required
    assert "direction" in task.reason and calls == []


def test_overview_rejects_foreign_authority_metadata_revision():
    from pandapower_domain.task_coverage import PandapowerTaskProvider
    with pytest.raises(ValueError, match="metadata"):
        PandapowerTaskProvider().resolve("g", proposal(operation="overview"), context_ref="c", revision_ref="r",
            invoke=lambda *args: {"context_ref": "c", "revision_ref": "foreign", "model": "ieee39",
                                 "counts": {"buses": 39, "lines": 35, "transformers": 11}})


@pytest.mark.parametrize("values", [
    {"operation": "overview", "measure": "loading_percent"},
    {"objects": [{"kind": "line", "namespace": "pandapower_index", "identifier": "0"}]},
    {"measure": "loading_percent"},
    {"operation": "limits", "measure": "risk_score"},
    {"operation": "contingency", "scenario": "contingency", "measure": "loading_percent", "objects": [{"kind": "line", "namespace": "all", "identifier": "*"}]},
    {"operation": "ranking", "scenario": "baseline", "measure": "max_loading_percent", "objects": [{"kind": "line", "namespace": "all", "identifier": "*"}]},
])
def test_operation_contract_never_drops_object_or_measure(values):
    from pandapower_domain.task_coverage import PandapowerTaskProvider
    task = PandapowerTaskProvider().resolve("g", proposal(**values), context_ref="c", revision_ref="r",
        invoke=lambda *_: pytest.fail("invalid combination must be resolved before Authority work"))
    assert task.status == "clarification" and not task.execution_required


def test_answer_scales_use_same_verified_full_ranking_with_bounded_detail(authority):
    import re
    from pandapower_domain.task_coverage import PandapowerTaskProvider
    invoke, context, verifier = authority
    provider = PandapowerTaskProvider()
    result = invoke("analysis.powerflow.ac.run", {"context_ref": context["context_ref"]})
    sizes = []
    for scale, expected in (("concise", 1), ("standard", 5), ("detailed", 20)):
        task = provider.resolve("g", proposal(operation="ranking", measure="loading_percent",
            objects=[{"kind": "line", "namespace": "all", "identifier": "*"}]), context_ref=context["context_ref"],
            revision_ref=context["revision_ref"], invoke=invoke, answer_policy={"language": "en", "scale": scale})
        conclusion = provider.conclude(task, authority=verifier, result_refs=(result["result_ref"],), evidence_refs=tuple(result["evidence_refs"]))
        text = provider.render_conclusion(conclusion, language="en", scale=scale)
        assert conclusion.status == "supported"
        assert len(re.findall(r"line \d+:", text)) == expected
        assert "full values are in the result view" in text
        assert ("Verification basis:" in text) == (scale == "detailed")
        sizes.append(len(text))
    assert sizes[0] < sizes[1] < sizes[2]


def test_changed_load_requires_exact_ordered_patch_lineage(authority):
    from pandapower_domain.task_coverage import PandapowerTaskProvider
    invoke, context, verifier = authority
    provider = PandapowerTaskProvider()
    task = provider.resolve("g", proposal(scenario="changed", changes=[{
        "target": {"kind": "bus", "namespace": "pandapower_index", "identifier": "3"},
        "fields": ["p_mw", "q_mvar"], "factor": 1.2}]),
        context_ref=context["context_ref"], revision_ref=context["revision_ref"], invoke=invoke)
    assert task.status == "ready"
    patches = task.requirement["patches"]
    assert patches[0]["selector"]["indices"]
    changed = invoke("model.revision.derive", {"context_ref": context["context_ref"], "patches": patches})
    result = invoke("analysis.powerflow.ac.run", {"context_ref": changed["context_ref"]})
    conclusion = provider.conclude(task, authority=verifier, result_refs=(result["result_ref"],),
                                  evidence_refs=tuple(result["evidence_refs"]))
    assert conclusion.status == "supported"
    assert conclusion.context_ref == changed["context_ref"]
    extra = invoke("model.revision.derive", {"context_ref": changed["context_ref"], "patches": patches})
    result2 = invoke("analysis.powerflow.ac.run", {"context_ref": extra["context_ref"]})
    assert provider.conclude(task, authority=verifier, result_refs=(result2["result_ref"],),
                            evidence_refs=tuple(result2["evidence_refs"])).status == "unresolved"


def test_bus_name_is_resolved_by_name_not_index(authority):
    from pandapower_domain.task_coverage import PandapowerTaskProvider
    invoke, context, _ = authority
    calls = []
    def observed(capability, arguments):
        calls.append((capability, arguments))
        return invoke(capability, arguments)
    task = PandapowerTaskProvider().resolve("g", proposal(scenario="changed", changes=[{
        "target": {"kind": "bus", "namespace": "name", "identifier": "4"},
        "fields": ["p_mw"], "factor": 1.1}]), context_ref=context["context_ref"],
        revision_ref=context["revision_ref"], invoke=observed)
    assert calls[0][0] == "model.dataset.query" and "name" in calls[0][1]["select"]
    assert task.status == "ready"
    assert task.requirement["patches"][0]["selector"]["indices"] == [2]


@pytest.mark.parametrize("non_converged", [False, True])
def test_registered_outage_children_and_non_convergence(authority, non_converged):
    from pandapower_domain.task_coverage import PandapowerTaskProvider
    invoke, context, verifier = authority
    provider = PandapowerTaskProvider()
    task = provider.resolve("g", proposal(operation="contingency", scenario="contingency", scope="subset",
        objects=[{"kind": "line", "namespace": "pandapower_index", "identifier": "0"}]),
        context_ref=context["context_ref"], revision_ref=context["revision_ref"], invoke=invoke)
    arguments = {"context_ref": context["context_ref"], "branch_refs": [task.requirement["targets"][0]["asset_ref"]]}
    if non_converged:
        arguments.update(max_iteration=1, init="flat")
    result = invoke("analysis.contingency.n_minus_one.run", arguments)
    answer = provider.conclude(task, authority=verifier, result_refs=(result["result_ref"],), evidence_refs=tuple(result["evidence_refs"]))
    assert answer.status in {"supported", "partial"}
    assert "1 of 1" in answer.text
    if non_converged:
        assert "1 cases did not converge" in answer.text


def test_full_ranking_requires_every_requested_scalar(authority):
    from pandapower_domain.task_coverage import PandapowerTaskProvider
    from dataclasses import replace
    import json
    invoke, context, verifier = authority
    provider = PandapowerTaskProvider()
    task = provider.resolve("g", proposal(operation="ranking", measure="loading_percent",
        objects=[{"kind": "line", "namespace": "all", "identifier": "*"}]),
        context_ref=context["context_ref"], revision_ref=context["revision_ref"], invoke=invoke)
    result = invoke("analysis.powerflow.ac.run", {"context_ref": context["context_ref"]})
    assert provider.conclude(task, authority=verifier, result_refs=(result["result_ref"],), evidence_refs=tuple(result["evidence_refs"])).status == "supported"
    requirement = task.requirement
    requirement["targets"].append({"asset_ref": "asset:line:sha256:" + "0" * 64, "kind": "line", "index": 900})
    incomplete = replace(task, requirement_json=json.dumps(requirement))
    assert provider.conclude(incomplete, authority=verifier, result_refs=(result["result_ref"],), evidence_refs=tuple(result["evidence_refs"])).status == "unresolved"


def test_limit_result_is_required_and_bound_to_powerflow(authority):
    from pandapower_domain.task_coverage import PandapowerTaskProvider
    invoke, context, verifier = authority
    provider = PandapowerTaskProvider()
    task = provider.resolve("g", proposal(operation="limits"), context_ref=context["context_ref"], revision_ref=context["revision_ref"], invoke=invoke)
    result = invoke("analysis.powerflow.ac.run", {"context_ref": context["context_ref"]})
    refs = (result["result_ref"],)
    evidence = tuple(result["evidence_refs"])
    assert provider.conclude(task, authority=verifier, result_refs=refs, evidence_refs=evidence).status == "unresolved"
    limits = invoke("analysis.result.violations.evaluate", {"result_ref": result["result_ref"]})
    answer = provider.conclude(task, authority=verifier, result_refs=refs+(limits["result_ref"],), evidence_refs=evidence+tuple(limits["evidence_refs"]))
    assert answer.status in {"supported", "partial"}
    assert "limit violations" in answer.text


def test_foreign_and_tampered_references_are_fatal(authority, tmp_path):
    from pandapower_domain.task_coverage import PandapowerTaskProvider
    from pandapower_domain.authority import SimulatorIntegrityError
    invoke, context, verifier = authority
    provider = PandapowerTaskProvider()
    task = provider.resolve("g", proposal(), context_ref=context["context_ref"], revision_ref=context["revision_ref"], invoke=invoke)
    with pytest.raises(SimulatorIntegrityError):
        provider.conclude(task, authority=verifier, result_refs=("result:sha256:" + "0"*64,), evidence_refs=())
    result = invoke("analysis.powerflow.ac.run", {"context_ref": context["context_ref"]})
    path = verifier.verify_result(result["result_ref"]).path
    path.write_text(path.read_text().replace('"converged":true', '"converged":false'))
    with pytest.raises(SimulatorIntegrityError):
        provider.conclude(task, authority=verifier, result_refs=(result["result_ref"],), evidence_refs=tuple(result["evidence_refs"]))


def test_paired_comparison_requires_both_exact_scenarios(authority):
    from pandapower_domain.task_coverage import PandapowerTaskProvider
    invoke, context, verifier = authority
    provider = PandapowerTaskProvider()
    task = provider.resolve("g", proposal(operation="compare", scenario="comparison", changes=[{
        "target": {"kind": "bus", "namespace": "pandapower_index", "identifier": "3"},
        "fields": ["p_mw", "q_mvar"], "factor": 1.2}]),
        context_ref=context["context_ref"], revision_ref=context["revision_ref"], invoke=invoke)
    baseline = invoke("analysis.powerflow.ac.run", {"context_ref": context["context_ref"]})
    changed = invoke("model.revision.derive", {"context_ref": context["context_ref"], "patches": task.requirement["patches"]})
    result = invoke("analysis.powerflow.ac.run", {"context_ref": changed["context_ref"]})
    refs = (baseline["result_ref"], result["result_ref"])
    evidence = tuple(baseline["evidence_refs"] + result["evidence_refs"])
    answer = provider.conclude(task, authority=verifier, result_refs=refs, evidence_refs=evidence)
    assert answer.status == "supported" and "Baseline" in answer.text and "changed" in answer.text
    assert provider.conclude(task, authority=verifier, result_refs=refs[1:], evidence_refs=evidence).status == "unresolved"


def test_risk_rank_proves_source_and_full_violation_scope(authority):
    from pandapower_domain.task_coverage import PandapowerTaskProvider
    invoke, context, verifier = authority
    provider = PandapowerTaskProvider()
    task = provider.resolve("g", proposal(operation="ranking", measure="risk_score", objects=[{
        "kind": "network", "namespace": "all", "identifier": "*"}]),
        context_ref=context["context_ref"], revision_ref=context["revision_ref"], invoke=invoke)
    baseline = invoke("analysis.powerflow.ac.run", {"context_ref": context["context_ref"]})
    violations = invoke("analysis.result.violations.evaluate", {"result_ref": baseline["result_ref"]})
    risk = invoke("analysis.result.risk.rank", {"result_ref": violations["result_ref"], "limit": 1})
    answer = provider.conclude(task, authority=verifier, result_refs=tuple(row["result_ref"] for row in (baseline, violations, risk)),
        evidence_refs=tuple(ref for row in (baseline, violations, risk) for ref in row["evidence_refs"]))
    assert answer.status in {"supported", "partial"} and "violations" in answer.text


def test_outage_ordering_is_partial_when_requested_cases_are_missing(authority):
    from pandapower_domain.task_coverage import PandapowerTaskProvider
    invoke, context, verifier = authority
    provider = PandapowerTaskProvider()
    task = provider.resolve("g", proposal(operation="ranking", scenario="contingency", scope="subset", measure="max_loading_percent",
        objects=[{"kind": "line", "namespace": "pandapower_index", "identifier": str(index)} for index in (0, 1)]),
        context_ref=context["context_ref"], revision_ref=context["revision_ref"], invoke=invoke)
    assert task.status == "ready"
    result = invoke("analysis.contingency.n_minus_one.run", {"context_ref": context["context_ref"], "branch_refs": [task.requirement["targets"][0]["asset_ref"]]})
    answer = provider.conclude(task, authority=verifier, result_refs=(result["result_ref"],), evidence_refs=tuple(result["evidence_refs"]))
    assert answer.status == "partial" and "1 of 2" in answer.text
    assert "complete ordering" not in answer.text.lower()


@pytest.mark.parametrize("non_converged", [False, True])
def test_full_outage_ordering_keeps_non_converged_cases_visible(authority, non_converged):
    from pandapower_domain.task_coverage import PandapowerTaskProvider
    invoke, context, verifier = authority
    provider = PandapowerTaskProvider()
    task = provider.resolve("g", proposal(operation="ranking", scenario="contingency", scope="subset", measure="max_loading_percent",
        objects=[{"kind": "line", "namespace": "pandapower_index", "identifier": "0"}]),
        context_ref=context["context_ref"], revision_ref=context["revision_ref"], invoke=invoke)
    arguments = {"context_ref": context["context_ref"], "branch_refs": [task.requirement["targets"][0]["asset_ref"]]}
    if non_converged:
        arguments.update(max_iteration=1, init="flat")
    result = invoke("analysis.contingency.n_minus_one.run", arguments)
    answer = provider.conclude(task, authority=verifier, result_refs=(result["result_ref"],), evidence_refs=tuple(result["evidence_refs"]))
    if non_converged:
        assert answer.status == "partial" and "0 of 1 cases have valid" in answer.text
        assert "1 cases did not converge" in answer.text
    else:
        assert "Complete Pack ordering" in answer.text and "max_loading_percent" in answer.text


@pytest.mark.parametrize("operation,scenario", [("compare", "comparison"), ("ranking", "changed")])
def test_changed_branch_measures_use_verified_stable_object_identity(authority, operation, scenario):
    from pandapower_domain.task_coverage import PandapowerTaskProvider
    invoke, context, verifier = authority
    provider = PandapowerTaskProvider()
    task = provider.resolve("g", proposal(operation=operation, scenario=scenario, measure="loading_percent",
        objects=[{"kind": "line", "namespace": "all", "identifier": "*"}], changes=[{
            "target": {"kind": "bus", "namespace": "pandapower_index", "identifier": "3"}, "fields": ["p_mw"], "factor": 1.1}]),
        context_ref=context["context_ref"], revision_ref=context["revision_ref"], invoke=invoke)
    base = invoke("analysis.powerflow.ac.run", {"context_ref": context["context_ref"]})
    changed = invoke("model.revision.derive", {"context_ref": context["context_ref"], "patches": task.requirement["patches"]})
    result = invoke("analysis.powerflow.ac.run", {"context_ref": changed["context_ref"]})
    answer = provider.conclude(task, authority=verifier, result_refs=(base["result_ref"], result["result_ref"]),
                              evidence_refs=tuple(base["evidence_refs"] + result["evidence_refs"]))
    assert answer.status == "supported" and "loading_percent" in answer.text


def test_ambiguous_authority_name_stops_for_clarification(authority):
    from pandapower_domain.task_coverage import PandapowerTaskProvider
    invoke, context, _ = authority
    changed = invoke("model.revision.derive", {"context_ref": context["context_ref"], "patches": [
        {"operation": "set", "kind": "bus", "selector": {"indices": [2, 3]}, "values": {"name": "duplicate"}}]})
    task = PandapowerTaskProvider().resolve("g", proposal(scenario="changed", changes=[{
        "target": {"kind": "bus", "namespace": "name", "identifier": "duplicate"}, "fields": ["p_mw"], "factor": 1.2}]),
        context_ref=changed["context_ref"], revision_ref=changed["revision_ref"], invoke=invoke)
    assert task.status == "clarification" and "ambiguous" in task.reason


def test_foreign_registered_model_cannot_supply_conclusion(authority):
    from pandapower_domain.task_coverage import PandapowerTaskProvider
    from pandapower_domain.authority import SimulatorIntegrityError
    invoke, context, verifier = authority
    task = PandapowerTaskProvider().resolve("g", proposal(), context_ref=context["context_ref"], revision_ref=context["revision_ref"], invoke=invoke)
    foreign = invoke("context.open", {"model_id": "case24_ieee_rts"})
    result = invoke("analysis.powerflow.ac.run", {"context_ref": foreign["context_ref"]})
    with pytest.raises(SimulatorIntegrityError, match="selected model"):
        PandapowerTaskProvider().conclude(task, authority=verifier, result_refs=(result["result_ref"],), evidence_refs=tuple(result["evidence_refs"]))
