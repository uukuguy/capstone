from __future__ import annotations

import pytest
import re

from capstone_agent.model_identity import is_valid_model_id, page_id_for_model, validate_model_id


@pytest.mark.parametrize("model_id", ["ieee39", "pypsa-example/scigrid_de", "case_2-v1", "GBnetwork", "GBreducednetwork"])
def test_model_identity_accepts_registered_hierarchical_ids(model_id: str) -> None:
    assert is_valid_model_id(model_id)
    assert validate_model_id(model_id) == model_id


@pytest.mark.parametrize("model_id", ["", "/scigrid_de", "pypsa-example/", "../escape", "PyPSA/39", "a/b/c"])
def test_model_identity_rejects_unsafe_or_ambiguous_ids(model_id: str) -> None:
    assert not is_valid_model_id(model_id)
    with pytest.raises(ValueError, match="model_id"):
        validate_model_id(model_id)


def test_page_id_is_stable_and_path_safe() -> None:
    assert page_id_for_model("ieee39") == "page_ieee39"
    assert page_id_for_model("pypsa-example/scigrid_de") == "page_pypsa-example__scigrid_de"
    assert "/" not in page_id_for_model("pypsa-example/scigrid_de")


@pytest.mark.parametrize("model_id", ["GBnetwork", "GBreducednetwork"])
def test_uppercase_model_page_uses_a_valid_distinct_protocol_identifier(model_id: str) -> None:
    page_id = page_id_for_model(model_id)
    assert re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", page_id)
    assert page_id == page_id_for_model(model_id)
    assert page_id != page_id_for_model(model_id.lower())


@pytest.mark.parametrize("model_id", ["pypsa-example/grid.v1", "a" * 64 + "/" + "b" * 64])
def test_namespaced_page_key_remains_a_bounded_protocol_identifier(model_id: str) -> None:
    assert re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", page_id_for_model(model_id))


@pytest.mark.parametrize("left,right", [("a/b", "a__b"), ("a__b/c", "a/b__c")])
def test_page_key_does_not_confuse_namespace_separator_with_model_name(left: str, right: str) -> None:
    assert page_id_for_model(left) != page_id_for_model(right)


@pytest.mark.parametrize("model_id", ["GBnetwork", "GBreducednetwork", "ieee39", "pypsa-example/scigrid_de"])
def test_model_page_round_trips_through_thread_snapshot(model_id: str) -> None:
    from capstone_agent.thread_protocol import ModelContextSnapshot, RunSnapshot, ThreadSnapshot

    snapshot = ThreadSnapshot(
        thread_id="thr_model", run=RunSnapshot("run_model", "open"),
        active_model_context=ModelContextSnapshot(
            "ctx_model", model_id, "revision:sha256:" + "a" * 64, "pandapower", "sel_0",
        ),
        active_grid_page_id=page_id_for_model(model_id), current_attempt=None,
        last_event_seq=0, base_event_seq=0,
    )
    restored = ThreadSnapshot.from_document(snapshot.to_document())
    assert restored.active_model_context.model_id == model_id
    assert restored.active_grid_page_id == snapshot.active_grid_page_id
