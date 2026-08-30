from __future__ import annotations

import pytest

from pandapower_domain.models import ActiveModelState, DomainStateDelta
from pandapower_domain.state import PandapowerStateAdapter


def test_state_adapter_validates_revision_and_merges_domain_delta() -> None:
    adapter = PandapowerStateAdapter()
    adapter.validate(binding_id="grid", state={})
    delta = DomainStateDelta(
        projector="model-context-v1",
        model=ActiveModelState(
            context_ref="context:sha256:" + "a" * 64,
            revision_ref="revision:sha256:" + "b" * 64,
            model_id="case9",
            source="registered",
        ),
    )

    merged = adapter.merge(binding_id="grid", state={}, delta=delta)

    adapter.validate(binding_id="grid", state=merged)
    assert merged["model"]["model_id"] == "case9"


@pytest.mark.parametrize(
    "state",
    [
        {"state_schema": "wrong/1.0"},
        {"model": {"context_ref": "inventory:context:foreign"}},
        {"model": {"binding_id": "inventory"}},
    ],
)
def test_state_adapter_rejects_schema_or_foreign_binding_state(
    state: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        PandapowerStateAdapter().validate(binding_id="grid", state=state)
