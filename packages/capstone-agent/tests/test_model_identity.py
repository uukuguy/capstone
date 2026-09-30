from __future__ import annotations

import pytest

from capstone_agent.model_identity import is_valid_model_id, page_id_for_model, validate_model_id


@pytest.mark.parametrize("model_id", ["ieee39", "pypsa-example/scigrid_de", "case_2-v1"])
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
