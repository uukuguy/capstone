from types import SimpleNamespace
import json

import pytest

from pypsa_agent.thread_binding import bind_thread_tool_catalog, verify_bound_model_reference


def test_verified_descendant_chain_remains_bound_to_selected_model():
    documents = {
        "base": {"catalog_id": "regional-six-bus", "parent_ref": None},
        "child": {"catalog_id": "regional-six-bus", "parent_ref": "base"},
        "grandchild": {"catalog_id": "regional-six-bus", "parent_ref": "child"},
    }
    calls = []

    def verify(reference):
        calls.append(reference)
        return SimpleNamespace(document=documents[reference])

    assert verify_bound_model_reference(SimpleNamespace(verify_model=verify), "grandchild",
                                       model_id="regional-six-bus", base_ref="base")
    assert calls == ["grandchild", "child", "base"]


@pytest.mark.parametrize("documents", [
    {"child": {"catalog_id": "two-bus", "parent_ref": "base"}},
    {"child": {"catalog_id": "regional-six-bus", "parent_ref": None}},
    {"child": {"catalog_id": "regional-six-bus", "parent_ref": "child"}},
    {"child": {"catalog_id": "regional-six-bus", "parent_ref": 7}},
])
def test_foreign_unrelated_or_invalid_models_do_not_inherit_binding(documents):
    authority = SimpleNamespace(verify_model=lambda ref: SimpleNamespace(document=documents[ref]))
    assert not verify_bound_model_reference(authority, "child", model_id="regional-six-bus", base_ref="base")


def test_corrupted_model_verification_remains_fatal():
    def verify(reference):
        raise ValueError("model integrity failure")

    with pytest.raises(ValueError, match="integrity"):
        verify_bound_model_reference(SimpleNamespace(verify_model=verify), "child",
                                    model_id="regional-six-bus", base_ref="base")


def test_lineage_walk_is_bounded():
    calls = []

    def verify(reference):
        calls.append(reference)
        return SimpleNamespace(document={"catalog_id": "regional-six-bus", "parent_ref": reference + "x"})

    assert not verify_bound_model_reference(SimpleNamespace(verify_model=verify), "child",
                                           model_id="regional-six-bus", base_ref="base")
    assert len(calls) == 64


def test_thread_catalog_only_restricts_opening_another_model(tmp_path):
    path = tmp_path / "tool-catalog.json"
    derive = {"capability": "model.derive", "input_schema": {"properties": {"model_ref": {"type": "string"}}}}
    path.write_text(json.dumps({"tools": [
        {"capability": "model.open", "input_schema": {"properties": {"catalog_id": {"type": "string"}}}}, derive,
    ]}))
    bind_thread_tool_catalog(path, "regional-six-bus")
    tools = json.loads(path.read_text())["tools"]
    assert tools[0]["input_schema"]["properties"]["catalog_id"]["enum"] == ["regional-six-bus"]
    assert tools[1] == derive
