import pytest
from capability_agent.application.runner import _with_report_reference

from inventory_domain.output import InventoryOutputContract
from inventory_domain.state import InventoryStateAdapter


def test_output_accepts_only_empty_payload_without_context() -> None:
    contract = InventoryOutputContract()
    payload = contract.build(
        binding_id="inventory",
        context=InventoryStateAdapter().build_context(binding_id="inventory", state={}),
        committed_answers=(),
    )

    contract.validate(payload)
    with pytest.raises(ValueError):
        contract.validate({**payload, "context_ref": "inventory-context:sha256:" + "a" * 64})


def test_output_unions_inventory_and_report_admission_scopes() -> None:
    contract = InventoryOutputContract()
    report_ref = "artifact:sha256:" + "a" * 64
    context = _with_report_reference(
        InventoryStateAdapter().build_context(binding_id="inventory", state={}),
        report_ref,
    )
    payload = {"catalog_id": None, "context_ref": None, "revision_ref": None, "asset_result_refs": [], "stock_summary_refs": [], "report_artifact_ref": report_ref}

    contract.validate_with_context(payload, context=context)
