from __future__ import annotations

from capability_agent import VerifiedInvocation
from pandapower_domain import build_pandapower_profile
from pandapower_domain.capabilities import CapabilityContextSpec
from pandapower_domain.projection import project_domain_result


def test_pandapower_projector_projects_model_context_to_dumpable_state() -> None:
    profile = build_pandapower_profile()
    invocation = VerifiedInvocation(
        capability="model.open",
        projector_id="model-context-v1",
        result_kind="model-context",
        result={
            "context_ref": "context:sha256:abc",
            "revision_ref": "revision:sha256:def",
            "model": "case9",
            "source": "registered",
        },
        arguments={},
        turn_id="turn-1",
        result_paths={},
        active_revision_ref=None,
    )

    delta = profile.projector_registry.require("model-context-v1").project(invocation)
    dumped = delta.model_dump()

    assert dumped["projector"] == "model-context-v1"
    assert dumped["model"] is not None
    assert dumped["model"]["model_id"] == "case9"


def test_projection_uses_domain_state_delta_model() -> None:
    spec = CapabilityContextSpec(
        capability="model.open",
        availability="published",
        requires_state=(),
        consumes_state=(),
        produces_state=(),
        invalidates_state=(),
        result_kind="model-context",
        projector="model-context-v1",
    )

    delta = project_domain_result(
        spec,
        result={
            "context_ref": "context:sha256:abc",
            "revision_ref": "revision:sha256:def",
            "model": "case9",
        },
        arguments={},
        turn_id="turn-1",
        result_paths={},
        active_revision_ref=None,
    )

    assert delta.model_dump()["model"]["model_id"] == "case9"
