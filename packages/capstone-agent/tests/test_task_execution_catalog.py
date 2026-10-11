import json
from types import SimpleNamespace

from capability_agent.domain.task import ResolvedTaskGoal
from capability_agent.tools.catalog import ToolCatalog, ToolDocument


def test_reuse_execution_catalog_does_not_expose_calculation_or_mutation(tmp_path):
    from capstone_agent.task_execution_catalog import task_execution_catalog
    source = ToolCatalog(tuple(ToolDocument("grid_" + name, capability, name, {"type": "object"})
                               for name, capability in [("read", "result.dataset.query"), ("calculate", "analysis.run"), ("mutate", "model.derive")]))
    domain = tmp_path / "domains/domain"
    domain.mkdir(parents=True)
    original = source.materialize(domain / "original.json")
    provider = SimpleNamespace(execution_capabilities=lambda goal: ("result.dataset.query",))
    runtime = SimpleNamespace(profile=SimpleNamespace(task_provider=provider))
    goal = ResolvedTaskGoal("g", "ready", "{}", binding_id="domain")
    claim = SimpleNamespace(task_resolutions=(goal,), attempt=SimpleNamespace(attempt_id="attempt_reuse"))
    selected = task_execution_catalog(claim, "domain", runtime, original)
    assert selected.is_relative_to(domain)
    document = json.loads(selected.read_text())
    assert [tool["capability"] for tool in document["tools"]] == ["result.dataset.query"]
    assert document["fingerprint"] != json.loads(original.read_text())["fingerprint"]
    assert len(json.loads(original.read_text())["tools"]) == 3
    from capability_agent.runtime.descriptor import RuntimeDescriptor
    guides = domain / "guides"
    guides.mkdir()
    index = domain / "guide-index.json"
    index.write_text("{}")
    descriptor = RuntimeDescriptor(binding_id="domain", workspace_path=domain,
        application_workspace_path=tmp_path, executable="gridctl", tool_name_prefix="grid_",
        tool_catalog_path=selected, guide_index_path=index, guide_root_path=guides)
    assert descriptor.tool_catalog_path == selected
    unrestricted = SimpleNamespace(task_resolutions=(), attempt=claim.attempt)
    assert task_execution_catalog(unrestricted, "domain", runtime, original) == original


def test_a_calculating_goal_preserves_the_registered_catalog(tmp_path):
    from capstone_agent.task_execution_catalog import task_execution_catalog
    provider = SimpleNamespace(execution_capabilities=lambda goal: None)
    runtime = SimpleNamespace(profile=SimpleNamespace(task_provider=provider))
    goal = ResolvedTaskGoal("g", "ready", "{}", binding_id="domain")
    claim = SimpleNamespace(task_resolutions=(goal,), attempt=SimpleNamespace(attempt_id="attempt_compute"))
    path = tmp_path / "original.json"
    assert task_execution_catalog(claim, "domain", runtime, path) == path
