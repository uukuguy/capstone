from __future__ import annotations

import uuid

from pypsa_agent.profile import build_profile
from pypsa_agent.registry import build_trusted_application_registry
from pypsa_agent.worker import _event_ordinal, _prepare


def test_pypsa_application_declares_two_trusted_bindings_and_reference_grant() -> None:
    profile = build_profile()
    assert profile.manifest.application_id == "pypsa-business-cases"
    assert [binding.binding_id for binding in profile.domains] == ["source", "operations"]
    assert len(profile.reference_grants) == 1


def test_pypsa_application_is_selected_from_trusted_registry() -> None:
    profile = build_trusted_application_registry().resolve("pypsa-business-cases")
    assert profile.manifest.version == "1.0"


def test_provider_worker_prepares_without_sending_a_model_request() -> None:
    run_id = "pypsa-provider-preflight-" + uuid.uuid4().hex
    prepared = _prepare({"application_id": "pypsa-business-cases",
                         "run_id": run_id, "mode": "provider",
                         "case_id": None, "provider": None, "model": None}, lambda _: None)
    assert prepared.run_id == run_id
    assert [binding.binding_id for binding in prepared.application.profile.domains] == [
        "source", "operations",
    ]


def test_provider_tool_events_use_the_rpc_correlation_id_for_story_steps() -> None:
    assert _event_ordinal({"turn_id": "run-t002"}) == 2
    assert _event_ordinal({"correlation_id": "run-t003"}) == 3
