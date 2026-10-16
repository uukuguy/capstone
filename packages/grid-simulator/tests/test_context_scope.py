import json
from types import SimpleNamespace

import pytest

from grid_simulator.context_scope import SCOPE_FILE, require_context_scope


def test_scope_accepts_descendants_but_rejects_foreign_and_independent_models(tmp_path):
    (tmp_path / SCOPE_FILE).write_text(json.dumps({"schema": "grid-context-scope/1", "root_context_ref": "root"}))
    contexts = {
        "root": SimpleNamespace(context_ref="root", model_id="grid", parent_context_ref=None),
        "child": SimpleNamespace(context_ref="child", model_id="grid", parent_context_ref="root"),
        "foreign": SimpleNamespace(context_ref="foreign", model_id="other", parent_context_ref="root"),
        "unrelated": SimpleNamespace(context_ref="unrelated", model_id="grid", parent_context_ref=None),
    }
    store = SimpleNamespace(require=lambda reference: contexts[reference])
    require_context_scope(tmp_path, store, "analysis.run", {"context_ref": "child"})
    require_context_scope(tmp_path, store, "context.open", {"model_id": "grid"})
    for capability, arguments in (
        ("analysis.run", {"context_ref": "foreign"}),
        ("analysis.run", {"context_ref": "unrelated"}),
        ("context.open", {"model_id": "other"}),
        ("model.create", {}),
    ):
        with pytest.raises(ValueError):
            require_context_scope(tmp_path, store, capability, arguments)


@pytest.mark.parametrize("kind", ["bad-json", "wrong-schema", "symlink"])
def test_scope_rejects_invalid_host_configuration(tmp_path, kind):
    scope = tmp_path / SCOPE_FILE
    if kind == "symlink":
        scope.symlink_to(tmp_path / "missing")
    else:
        scope.write_text("{" if kind == "bad-json" else '{}')
    with pytest.raises(ValueError):
        require_context_scope(tmp_path, SimpleNamespace(), "environment.describe", {})
