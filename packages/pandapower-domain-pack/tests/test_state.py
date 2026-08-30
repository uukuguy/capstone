from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from pandapower_domain.models import ActiveModelState, DomainStateDelta
from pandapower_domain.state import PandapowerStateAdapter


class _KernelDelta:
    def __init__(self, delta: DomainStateDelta) -> None:
        self._delta = delta

    def model_dump(self, *, mode: str = "python") -> dict[str, Any]:
        return self._delta.model_dump(mode=mode)


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
    model = merged["model"]
    assert isinstance(model, Mapping)
    assert model["model_id"] == "case9"


def test_state_adapter_accepts_kernel_domain_delta_protocol() -> None:
    delta = DomainStateDelta(
        projector="model-context-v1",
        model=ActiveModelState(
            context_ref="context:sha256:" + "a" * 64,
            revision_ref="revision:sha256:" + "b" * 64,
            model_id="case9",
            source="registered",
        ),
    )

    merged = PandapowerStateAdapter().merge(
        binding_id="grid",
        state={},
        delta=_KernelDelta(delta),
    )

    model = merged["model"]
    assert isinstance(model, Mapping)
    assert model["model_id"] == "case9"


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
