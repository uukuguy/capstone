from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from capstone_agent.runtime_resources import ResolvedResourceProfile, ResourceDescriptor, content_hash


def binding(tmp_path, *, available=True, missing=False):
    guide = "Original adapter with diagnostic.structural."
    root = tmp_path / "guides"
    (root / "references").mkdir(parents=True)
    path = root / "references/powerskills-pandapower-adapter.md"
    path.write_text(guide)
    capability_ids = ["model.list", "context.open", "context.get", "model.element.get", "analysis.run", "analysis.operation.describe", "analysis.powerflow.ac.run", "result.dataset.describe", "result.dataset.query",
                      "model.dataset.list", "model.dataset.describe", "model.dataset.query", "model.constraints.describe",
                      "analysis.result.violations.evaluate", "analysis.contingency.n_minus_one.run"]
    missing_id = "analysis.run" if missing is True else missing
    documents = [{"id": c} for c in capability_ids if c != missing_id]
    class Executor:
        def invoke(self, capability, arguments):
            assert capability == "analysis.operation.describe"
            assert arguments == {"operation": "diagnostic.structural"}
            return {"availability": {"status": "available" if available else "unavailable", "descriptor_sha256": content_hash({})}}
    return SimpleNamespace(runtime=SimpleNamespace(guide_root_path=root, capability_documents=documents, executor=Executor()))


def installed_profile():
    return ResolvedResourceProfile("project", "source-revision", "harness_engine", (),
        (ResourceDescriptor("powerskills-pandapower", "skill", "v1", "upstream", ("harness_engine",), True, True, False,
                            "execution adapter is unavailable", (), "native-sha"),
         ResourceDescriptor("powermcp-pandapower", "mcp", "v2", "upstream-mcp", ("harness_engine",), True, True, False,
                            "execution adapter is unavailable", (), "descriptor-sha")), (), "installs/fixed", "{}", "{}")


def test_harness_profile_requires_real_operation_and_loads_bound_guide(tmp_path, monkeypatch):
    from capstone_agent import professional_resources as module
    monkeypatch.setattr(module, "resolve_resource_profile", lambda *args: installed_profile())
    bindings = {"grid": binding(tmp_path)}
    profile = module.resolve_harness_resource_profile(tmp_path, bindings)
    assert all(r["ready"] for r in profile.to_document()["resources"])
    selected = module.bind_harness_skill(profile, skill_id="powerskills-pandapower", skill_version="v1", profile_revision=profile.revision)
    guide, receipt = module.load_harness_skill(selected, bindings)
    assert guide["text"] == "Original adapter with diagnostic.structural."
    assert receipt["guide_sha256"] == hashlib.sha256(guide["text"].encode()).hexdigest()
    assert receipt["native_loaded_identity"] == "native-sha"
    assert receipt["backend_descriptor_sha256"] == content_hash({})
    assert "native-sha" not in json.dumps(profile.to_document().get("private", {}))


@pytest.mark.parametrize("available,missing", [(False, False), (True, True)])
def test_unavailable_backend_or_semantic_tool_cannot_publish_ready(tmp_path, monkeypatch, available, missing):
    from capstone_agent import professional_resources as module
    monkeypatch.setattr(module, "resolve_resource_profile", lambda *args: installed_profile())
    profile = module.resolve_harness_resource_profile(tmp_path, {"grid": binding(tmp_path, available=available, missing=missing)})
    assert not any(r["ready"] for r in profile.to_document()["resources"])
    with pytest.raises(ValueError, match="unavailable"):
        module.bind_harness_skill(profile, skill_id="powerskills-pandapower", skill_version="v1", profile_revision=profile.revision)


def test_selected_skill_rejects_version_revision_and_guide_drift(tmp_path, monkeypatch):
    from capstone_agent import professional_resources as module
    monkeypatch.setattr(module, "resolve_resource_profile", lambda *args: installed_profile())
    bindings = {"grid": binding(tmp_path)}
    profile = module.resolve_harness_resource_profile(tmp_path, bindings)
    with pytest.raises(ValueError):
        module.bind_harness_skill(profile, skill_id="powerskills-pandapower", skill_version="other", profile_revision=profile.revision)
    with pytest.raises(ValueError):
        module.bind_harness_skill(profile, skill_id="powerskills-pandapower", skill_version="v1", profile_revision="other")
    selected = module.bind_harness_skill(profile, skill_id="powerskills-pandapower", skill_version="v1", profile_revision=profile.revision)
    (bindings["grid"].runtime.guide_root_path / "references/powerskills-pandapower-adapter.md").write_text("changed")
    with pytest.raises(ValueError, match="guide"):
        module.load_harness_skill(selected, bindings)


@pytest.mark.parametrize("missing_id", ["model.dataset.list", "model.dataset.describe", "model.dataset.query",
    "model.constraints.describe", "analysis.result.violations.evaluate", "analysis.contingency.n_minus_one.run"])
def test_guide_declared_workflow_tools_are_required_for_readiness(tmp_path, monkeypatch, missing_id):
    from capstone_agent import professional_resources as module
    monkeypatch.setattr(module, "resolve_resource_profile", lambda *args: installed_profile())
    bindings = {"grid": binding(tmp_path, missing=missing_id)}
    profile = module.resolve_harness_resource_profile(tmp_path, bindings)
    assert not any(item["ready"] for item in profile.to_document()["resources"])
    with pytest.raises(ValueError, match="unavailable"):
        module.bind_harness_skill(profile, skill_id="powerskills-pandapower", skill_version="v1", profile_revision=profile.revision)


def test_selected_guide_enters_real_launch_policy_and_receipt(tmp_path, monkeypatch):
    from capstone_agent import professional_resources as module
    from capability_agent.runtime.environment import PiLaunch
    monkeypatch.setattr(module, "resolve_resource_profile", lambda *args: installed_profile())
    bindings = {"grid": binding(tmp_path)}
    profile = module.resolve_harness_resource_profile(tmp_path, bindings)
    selection = module.bind_harness_skill(profile, skill_id="powerskills-pandapower", skill_version="v1", profile_revision=profile.revision)
    policy = tmp_path / "policy.md"
    policy.write_text("Registered tool policy")
    launch = PiLaunch(("pi", "--system-prompt", str(policy), "--no-builtin-tools", "--no-skills"), {"PATH": "/usr/bin"})
    applied = module.apply_harness_skill(launch, selection, bindings, tmp_path / "attempt")
    text = Path(applied.argv[applied.argv.index("--system-prompt") + 1]).read_text()
    assert "Original adapter with diagnostic.structural." in text
    assert "Registered tool policy" in text
    assert "--no-builtin-tools" in applied.argv and "--no-skills" in applied.argv
    receipt = json.loads((tmp_path / "attempt/harness-skill-load.json").read_text())
    assert receipt["skill_id"] == selection.skill_id
    assert receipt["profile_revision"] == profile.revision
    assert policy.read_text() == "Registered tool policy"


def test_unadapted_local_skill_cannot_bind_the_sample_guide(tmp_path, monkeypatch):
    from capstone_agent import professional_resources as module
    from dataclasses import replace
    custom = ResourceDescriptor("local-skill", "skill", "1", "local", ("harness_engine",), True, True, True, None, (), "custom-sha")
    base = installed_profile()
    monkeypatch.setattr(module, "resolve_resource_profile", lambda *args: replace(base, resources=(*base.resources, custom)))
    profile = module.resolve_harness_resource_profile(tmp_path, {"grid": binding(tmp_path)})
    item = next(r for r in profile.to_document()["resources"] if r["id"] == "local-skill")
    assert item["ready"] is False
    with pytest.raises(ValueError):
        module.bind_harness_skill(profile, skill_id="local-skill", skill_version="1", profile_revision=profile.revision)


def test_accepted_private_selection_retains_guide_and_install_after_pointer_move(tmp_path, monkeypatch):
    from capstone_agent import professional_resources as module
    from dataclasses import replace
    base = replace(installed_profile(), installation_id='installs/' + 'a' * 32)
    monkeypatch.setattr(module, 'resolve_resource_profile', lambda *args: base)
    bindings = {'grid': binding(tmp_path)}
    profile = module.resolve_harness_resource_profile(tmp_path, bindings)
    document = profile.private_document()
    (tmp_path / 'agent-resources.json').write_text(json.dumps({'resources': [
        {'id': resource.resource_id, 'enabled': True, 'roles': ['harness_engine'], 'version': 'B'}
        for resource in base.resources]}))
    checked = []
    def inspect(managed, **kwargs):
        checked.append(kwargs)
        return {}, None
    monkeypatch.setattr('capstone_agent.resource_installation.inspect_installation', inspect)
    selection = module.restore_harness_selection(tmp_path, json.loads(json.dumps(document)))
    assert selection.installation_id == base.installation_id
    assert checked[-1]['install_id'] == base.installation_id
    assert checked[-1]['expected_descriptor_sha256'] == content_hash({})
    assert 'Original adapter' in selection.guide_document['text']
    provider = module._AcceptedGuideProvider(SimpleNamespace(load=lambda: ()), selection.guide_document)
    assert provider.load()[0]['resource_id'] == module.GUIDE_ID
    assert provider.open(module.GUIDE_ID)['text'] == selection.guide_document['text']
    malformed = json.loads(json.dumps(document))
    malformed['guide']['text'] = 'different guide'
    with pytest.raises(ValueError, match='guide'):
        module.parse_harness_selection(malformed)
    with pytest.raises(ValueError, match='invalid'):
        module.parse_harness_selection({**document, 'environment': {'PATH': 'untrusted'}})
    for field in ('guide', 'descriptor', 'installation_id'):
        assert field not in profile.to_document()
    manifest = json.loads((tmp_path / 'agent-resources.json').read_text())
    manifest['resources'][0]['enabled'] = False
    (tmp_path / 'agent-resources.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='revoked'):
        module.restore_harness_selection(tmp_path, document)
    manifest['resources'][0]['enabled'] = True
    (tmp_path / 'agent-resources.json').write_text(json.dumps(manifest))
    monkeypatch.setattr('capstone_agent.resource_installation.inspect_installation', lambda *args, **kwargs: (None, 'missing'))
    with pytest.raises(ValueError, match='unavailable'):
        module.restore_harness_selection(tmp_path, document)
