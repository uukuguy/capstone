"""Real reference-service -> admission -> projector -> component path (not full app)."""
from copy import deepcopy
from pathlib import Path
import shutil

from capability_agent.domain import VerifiedInvocation
from capability_agent.application.runner import _with_report_reference
from inventory_domain.authority import InventoryArtifactAuthority
from inventory_domain.execution import InventoryctlExecutor
from inventory_domain.output import InventoryOutputContract
from inventory_domain.presentation import InventoryPresentationProvider
from inventory_domain.profile import build_inventory_profile
from inventory_domain.state import InventoryStateAdapter


def test_real_inventory_authority_projectors_feed_state_output_and_presentation(tmp_path):
    executable = shutil.which("inventoryctl")
    assert executable is not None, "install the inventory project environment first"
    executor = InventoryctlExecutor(executable=Path(executable), workspace=tmp_path)
    authority = InventoryArtifactAuthority(tmp_path)
    profile = build_inventory_profile()
    effects = {item["id"]: item["context_effect"] for item in profile.contract_source.load()}
    adapter = InventoryStateAdapter()
    state = {}
    responses = {}
    previous_context = None
    for ordinal, capability in enumerate(("catalog.open", "asset.list", "stock.summary"), 1):
        arguments = {"catalog_id": "warehouse-a"} if previous_context is None else {"context_ref": previous_context}
        result = executor.invoke(capability, arguments)
        admitted = authority.admit(capability, result, tuple(result.get("evidence_refs", ())))
        effect = effects[capability]
        invocation = VerifiedInvocation(
            capability=capability, projector_id=effect["projector"],
            result_kind=effect["result_kind"], result=result, arguments=arguments,
            turn_id=f"component-{ordinal}",
            result_paths={item.reference: str(item.path) for item in admitted.results},
            active_revision_ref=responses.get("catalog.open", {}).get("revision_ref"),
        )
        delta = profile.projector_registry.require(effect["projector"]).project(invocation)
        before = deepcopy(state)
        next_state = adapter.merge(binding_id="inventory", state=state, delta=delta)
        assert state == before
        state = next_state
        responses[capability] = result
        previous_context = result["context_ref"]

    context = adapter.build_context(binding_id="inventory", state=state)
    expected = {responses["catalog.open"]["context_ref"], responses["catalog.open"]["revision_ref"]}
    for capability in ("asset.list", "stock.summary"):
        expected.add(responses[capability]["result_ref"])
        expected.update(responses[capability]["evidence_refs"])
    assert set(context.admitted_refs) == expected
    assert next(iter(state["stock_summaries"].values()))["total_quantity_on_hand"] == responses["stock.summary"]["total_quantity_on_hand"]

    # The report token is a wrapper fixture, not an authority-generated result.
    report_ref = "artifact:sha256:" + "d" * 64
    wrapped = _with_report_reference(context, report_ref)
    output = InventoryOutputContract()
    payload = output.build(binding_id="inventory", context=wrapped, committed_answers=())
    output.validate_with_context(payload, context=wrapped)
    assert payload["asset_result_refs"] == [responses["asset.list"]["result_ref"]]
    assert payload["stock_summary_refs"] == [responses["stock.summary"]["result_ref"]]
    assert payload["report_artifact_ref"] == report_ref
    assert "artifact_path" not in payload
    rendered = InventoryPresentationProvider().render_report(context)
    assert responses["stock.summary"]["result_ref"] in rendered
    assert str(responses["stock.summary"]["total_quantity_on_hand"]) in rendered
