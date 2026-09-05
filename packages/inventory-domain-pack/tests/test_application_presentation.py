import pytest

from inventory_domain.presentation import InventoryPresentationProvider
from inventory_domain.state import INVENTORY_STATE_SCHEMA, InventoryStateAdapter


def test_presentation_renders_empty_detached_inventory_context() -> None:
    context = InventoryStateAdapter().build_context(binding_id="inventory", state={})

    rendered = InventoryPresentationProvider().render_context(context)

    assert rendered["binding_id"] == "inventory"
    assert rendered["active_catalog"] is None


def test_presentation_selects_exactly_one_inventory_snapshot_envelope() -> None:
    envelope = {"schema_id": INVENTORY_STATE_SCHEMA, "state": {}}
    snapshot = type("Snapshot", (), {"model_dump": lambda self, **_: {"domains": {"inventory": envelope}}})()
    assert InventoryPresentationProvider().render_context(snapshot)["binding_id"] == "inventory"
    with pytest.raises(ValueError, match="ambiguous"):
        InventoryPresentationProvider().render_context(type("Snapshot", (), {"model_dump": lambda self, **_: {"domains": {}}})())
