"""Component regressions; synthetic records here are not authority evidence."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from capability_agent.application.runner import _with_report_reference
from inventory_domain.models import ActiveCatalogState, AssetResultState, InventoryStateDelta, StockSummaryState
from inventory_domain.output import InventoryOutputContract
from inventory_domain.presentation import InventoryPresentationProvider
from inventory_domain.state import INVENTORY_STATE_SCHEMA, InventoryStateAdapter


def state_for(seed="a", previous=None):
    context = "inventory-context:sha256:" + seed * 64
    revision = "inventory-revision:sha256:" + seed * 64
    result = "inventory-result:sha256:" + seed * 64
    evidence = "inventory-evidence:sha256:" + seed * 64
    delta = InventoryStateDelta(
        projector="inventory-asset-v1",
        active_catalog=ActiveCatalogState(catalog_id="catalog-" + seed, context_ref=context, revision_ref=revision, asset_count=1, producer_turn_id="first"),
        asset_results=[AssetResultState(result_ref=result, context_ref=context, revision_ref=revision, capability="asset.list", asset_count=1, assets=[{"asset_id": "fixture", "metadata": {"label": "original"}}], artifact_path="evidence/results/fixture.json", evidence_refs=[evidence], producer_turn_id="first")],
    )
    return InventoryStateAdapter().merge(binding_id="inventory", state=previous or {}, delta=delta)


@pytest.mark.parametrize("mutation", [
    lambda s: s["catalogs"][s["active_context_ref"]].update(context_ref="inventory-context:sha256:" + "f" * 64),
    lambda s: s["catalogs"][s["active_context_ref"]].update(revision_ref="grid:bad"),
    lambda s: next(iter(s["asset_results"].values())).update(context_ref="inventory-context:sha256:" + "b" * 64),
    lambda s: next(iter(s["asset_results"].values())).update(revision_ref="inventory-revision:sha256:" + "b" * 64),
    lambda s: next(iter(s["asset_results"].values())).update(result_ref="inventory-result:sha256:" + "b" * 64),
    lambda s: next(iter(s["asset_results"].values())).update(evidence_refs=["inventory-result:sha256:" + "a" * 64]),
    lambda s: next(iter(s["asset_results"].values())).update(extra_field=True),
    lambda s: s["asset_results"].update({"inventory-result:not-a-digest": next(iter(s["asset_results"].values()))}),
])
def test_state_rejects_invalid_record_identity_and_lineage(mutation):
    state = state_for()
    mutation(state)
    with pytest.raises(ValueError):
        InventoryStateAdapter().validate(binding_id="inventory", state=state)


def test_state_context_and_dump_are_deeply_detached():
    state = state_for()
    context = InventoryStateAdapter().build_context(binding_id="inventory", state=state)
    record = next(iter(state["asset_results"].values()))
    record["assets"][0]["metadata"]["label"] = "input changed"
    dumped = context.model_dump(mode="json")
    detached = next(iter(dumped["state"]["asset_results"].values()))
    assert detached["assets"][0]["metadata"]["label"] == "original"
    detached["assets"][0]["metadata"]["label"] = "dump changed"
    assert next(iter(context.model_dump()["state"]["asset_results"].values()))["assets"][0]["metadata"]["label"] == "original"


def test_output_uses_actual_kernel_report_wrapper_and_keeps_inventory_scope():
    context = InventoryStateAdapter().build_context(binding_id="inventory", state=state_for())
    report = "artifact:sha256:" + "c" * 64
    wrapped = _with_report_reference(context, report)
    contract = InventoryOutputContract()
    payload = contract.build(binding_id="inventory", context=wrapped, committed_answers=())
    assert payload["report_artifact_ref"] == report
    assert payload["asset_result_refs"] == ["inventory-result:sha256:" + "a" * 64]
    contract.validate_with_context(payload, context=wrapped)


def test_output_filters_history_and_rejects_admitted_but_wrong_active_result():
    state = state_for("b", state_for("a"))
    context = InventoryStateAdapter().build_context(binding_id="inventory", state=state)
    contract = InventoryOutputContract()
    payload = contract.build(binding_id="inventory", context=context, committed_answers=())
    assert len(state["catalogs"]) == 2
    assert payload["asset_result_refs"] == ["inventory-result:sha256:" + "b" * 64]
    payload = {**payload, "asset_result_refs": ["inventory-result:sha256:" + "a" * 64]}
    with pytest.raises(ValueError):
        contract.validate_with_context(payload, context=context)


@pytest.mark.parametrize("field,value", [("catalog_id", 123), ("asset_result_refs", ""), ("asset_result_refs", {}), ("stock_summary_refs", ""), ("report_artifact_ref", False)])
def test_output_rejects_wrong_field_types(field, value):
    context = InventoryStateAdapter().build_context(binding_id="inventory", state={})
    contract = InventoryOutputContract()
    payload = dict(contract.build(binding_id="inventory", context=context, committed_answers=()))
    payload[field] = value
    with pytest.raises(ValueError):
        contract.validate_with_context(payload, context=context)


def test_presentation_consumes_public_serialized_snapshot_and_source_records():
    state = state_for()
    snapshot = SimpleNamespace(model_dump=lambda **_: {"domains": {"inventory": {"schema_id": INVENTORY_STATE_SCHEMA, "revision": 1, "state": deepcopy(state)}}})
    rendered = InventoryPresentationProvider().render_report(snapshot)
    assert "catalog-a" in rendered
    assert "inventory-result:sha256:" + "a" * 64 in rendered


@pytest.mark.parametrize("mutation", [
    lambda s: s.update(state_schema="foreign/1.0"),
    lambda s: s.update(state_revision=True),
    lambda s: s.update(state_revision=-1),
    lambda s: s.update(unknown_field={}),
    lambda s: s.pop("asset_results"),
])
def test_nonempty_state_rejects_schema_revision_and_missing_fields(mutation):
    state = state_for()
    mutation(state)
    with pytest.raises(ValueError):
        InventoryStateAdapter().validate(binding_id="inventory", state=state)


@pytest.mark.parametrize("binding_id", ["", " ", " inventory", None])
def test_state_rejects_invalid_binding_identity(binding_id):
    with pytest.raises(ValueError):
        InventoryStateAdapter().validate(binding_id=binding_id, state={})


def test_output_rejects_removed_domain_or_report_admission():
    view = InventoryStateAdapter().build_context(binding_id="inventory", state=state_for())
    report = "artifact:sha256:" + "e" * 64
    context = _with_report_reference(view, report)
    contract = InventoryOutputContract()
    payload = contract.build(binding_id="inventory", context=context, committed_answers=())
    for field in ("admitted_refs", "admitted_artifact_refs"):
        raw = context.model_dump(mode="json")
        raw[field] = []
        with pytest.raises(ValueError):
            contract.validate_with_context(payload, context=raw)


@pytest.mark.parametrize("domains", [
    {},
    {"foreign": {"schema_id": "foreign/1.0", "state": {}}},
    {"one": {"schema_id": INVENTORY_STATE_SCHEMA, "state": {}}, "two": {"schema_id": INVENTORY_STATE_SCHEMA, "state": {}}},
])
def test_presentation_rejects_missing_foreign_or_ambiguous_envelopes(domains):
    with pytest.raises(ValueError):
        InventoryPresentationProvider().render_context({"domains": domains})


@pytest.mark.parametrize("operation", ["validate", "merge"])
def test_same_result_reference_cannot_have_conflicting_record_kinds(operation):
    state = state_for()
    original = deepcopy(state)
    asset = next(iter(state["asset_results"].values()))
    summary = StockSummaryState(
        result_ref=asset["result_ref"], context_ref=asset["context_ref"],
        revision_ref=asset["revision_ref"], asset_count=1,
        total_quantity_on_hand=0, reorder_candidate_count=0, reorder_asset_ids=[],
        artifact_path=asset["artifact_path"], evidence_refs=asset["evidence_refs"],
        producer_turn_id="second",
    )
    adapter = InventoryStateAdapter()
    with pytest.raises(ValueError, match="conflict"):
        if operation == "validate":
            malformed = deepcopy(state)
            malformed["stock_summaries"][summary.result_ref] = summary.model_dump(mode="json")
            adapter.validate(binding_id="inventory", state=malformed)
        else:
            adapter.merge(
                binding_id="inventory", state=state,
                delta=InventoryStateDelta(projector="inventory-stock-summary-v1", stock_summaries=[summary]),
            )
    assert state == original
