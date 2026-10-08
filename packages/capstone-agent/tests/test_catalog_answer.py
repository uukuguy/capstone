from __future__ import annotations

import pytest

from capstone_agent.catalog_answer import complete_catalog_answer


def _catalog():
    return {"models": [
        {"model_id": "example-alpha", "display_name": "Alpha", "implementation_family": "pypsa", "available": True},
        {"model_id": "alpha", "display_name": "Alpha extra", "implementation_family": "pypsa", "available": False},
        {"model_id": "unrelated-model", "display_name": "Other", "implementation_family": "pandapower", "available": True},
    ]}


@pytest.mark.parametrize("instruction", ["列出 PyPSA 模型", "List models", "推荐几个模型", "List models and calculate voltages"])
def test_catalog_projection_needs_explicit_full_scope(instruction):
    assert complete_catalog_answer(instruction, "example-alpha", _catalog()) is None


@pytest.mark.parametrize("instruction", ["无关文本", "List only PyPSA models", "List some models"])
def test_explicit_full_scope_uses_all_catalog_families_without_interpreting_prose(instruction):
    answer = complete_catalog_answer(instruction, "example-alpha", _catalog(), full_catalog_requested=True)
    assert answer is not None
    assert "`example-alpha`" in answer and "`alpha`" in answer and "`unrelated-model`" in answer
    assert "3" in answer and "暂不可用" in answer


def test_complete_answer_keeps_model_wording_when_full_scope_is_explicit():
    answer = "Registered models: example-alpha, alpha, unrelated-model."
    assert complete_catalog_answer("ignored", answer, _catalog(), full_catalog_requested=True) is None


@pytest.mark.parametrize("catalog", [None, {"models": []}, {"models": [{}]}, {"models": [{"model_id": "alpha"}]}])
def test_incomplete_catalog_is_not_projected(catalog):
    assert complete_catalog_answer("ignored", "example-alpha", catalog, full_catalog_requested=True) is None
