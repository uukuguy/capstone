from __future__ import annotations

import json
import hashlib
from pathlib import Path

import pytest

from capstone_agent.runtime_resources import resolve_resource_profile


def config(tmp_path: Path) -> Path:
    root = tmp_path / "configs/runtime"
    root.mkdir(parents=True)
    (root / "native").mkdir()
    (root / "native/settings.json").write_text(json.dumps({"skills": ["skill"], "extensions": [], "packages": []}))
    skill = root / "native/skill"
    skill.mkdir()
    (skill / "SKILL.md").write_text("---\nname: sample\ndescription: sample workflow\n---\nRead the model.\n")
    (root / "agent-resources.json").write_text(json.dumps({
        "schema": "capstone-agent-resources/1",
        "profile_id": "project-resources",
        "roles": {role: {"settings": "native/settings.json", "adapters": {}} for role in ("harness_engine", "delegated_pi", "direct_pi")},
        "resources": [{"id": "sample", "kind": "skill", "version": "commit-1", "source": "https://example.org/sample", "roles": ["direct_pi"], "enabled": True, "native_name": "sample", "required_tools": [], "adapter": None}],
    }))
    return root


def test_native_skill_profile_is_immutable_and_catalog_has_no_private_paths(tmp_path: Path) -> None:
    root = config(tmp_path)
    profile = resolve_resource_profile(root, "direct_pi")
    assert profile.resources[0].ready
    assert profile.resources[0].installed
    assert profile.native_settings_paths == (root / "native/settings.json",)
    document = profile.to_document()
    assert document["resources"][0]["id"] == "sample"
    assert str(tmp_path) not in json.dumps(document)
    document["resources"][0]["ready"] = False
    assert profile.to_document()["resources"][0]["ready"]
    with pytest.raises((AttributeError, TypeError)):
        profile.resources[0].ready = False


def test_roles_disabled_missing_dependencies_and_adapter_are_distinct(tmp_path: Path) -> None:
    root = config(tmp_path)
    assert not resolve_resource_profile(root, "harness_engine").resources
    path = root / "agent-resources.json"
    data = json.loads(path.read_text())
    data["resources"][0]["enabled"] = False
    path.write_text(json.dumps(data))
    assert resolve_resource_profile(root, "direct_pi").resources[0].reason == "disabled"
    data["resources"][0].update(enabled=True, required_tools=["missing-tool"])
    path.write_text(json.dumps(data))
    assert "required tool" in resolve_resource_profile(root, "direct_pi").resources[0].reason
    data["resources"][0].update(required_tools=[], adapter="native-sample/1")
    path.write_text(json.dumps(data))
    assert "adapter" in resolve_resource_profile(root, "direct_pi").resources[0].reason
    (root / "native/skill/SKILL.md").unlink()
    assert not resolve_resource_profile(root, "direct_pi").resources[0].installed


def test_revision_tracks_native_bytes_and_declared_version(tmp_path: Path) -> None:
    root = config(tmp_path)
    first = resolve_resource_profile(root, "direct_pi").revision
    skill = root / "native/skill/SKILL.md"
    skill.write_text(skill.read_text() + "More guidance.\n")
    second = resolve_resource_profile(root, "direct_pi").revision
    assert first != second
    path = root / "agent-resources.json"
    data = json.loads(path.read_text())
    data["resources"][0]["version"] = "commit-2"
    path.write_text(json.dumps(data))
    assert resolve_resource_profile(root, "direct_pi").revision != second


@pytest.mark.parametrize("path", ["../../outside", "/tmp/outside"])
def test_native_path_escape_is_rejected(tmp_path: Path, path: str) -> None:
    root = config(tmp_path)
    (root / "native/settings.json").write_text(json.dumps({"skills": [path]}))
    with pytest.raises(ValueError, match="path"):
        resolve_resource_profile(root, "direct_pi")


def test_symlink_escape_and_duplicate_skill_names_are_rejected(tmp_path: Path) -> None:
    root = config(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "native/link").symlink_to(outside, target_is_directory=True)
    settings = root / "native/settings.json"
    settings.write_text(json.dumps({"skills": ["link"]}))
    with pytest.raises(ValueError, match="path"):
        resolve_resource_profile(root, "direct_pi")
    settings.write_text(json.dumps({"skills": ["skill", "skill"]}))
    with pytest.raises(ValueError, match="duplicate skill"):
        resolve_resource_profile(root, "direct_pi")


def test_unknown_role_fails(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="role"):
        resolve_resource_profile(config(tmp_path), "operator")


def test_adapter_declaration_does_not_claim_published_tools(tmp_path: Path) -> None:
    root = config(tmp_path)
    path = root / "agent-resources.json"
    data = json.loads(path.read_text())
    data["resources"][0].update(adapter="sample/1", required_tools=["read_sample"])
    adapter = root / "adapter.js"
    adapter.write_text("export const read_sample = () => {};\n")
    sha = hashlib.sha256(adapter.read_bytes()).hexdigest()
    binding = {"path": "adapter.js", "sha256": sha, "tool_ids": ["read_sample"]}
    data["roles"]["direct_pi"]["adapters"] = {"sample/1": binding}
    path.write_text(json.dumps(data))
    assert not resolve_resource_profile(root, "direct_pi").resources[0].ready


    receipt = root / "adapter-check.json"
    receipt.write_text(json.dumps({"schema": "capstone-resource-adapter-check/1", "status": "passed", "role": "direct_pi", "adapter_id": "sample/1", "source_sha256": sha, "published_tool_ids": ["read_sample"]}))
    binding["verification"] = {"path": "adapter-check.json", "sha256": hashlib.sha256(receipt.read_bytes()).hexdigest()}
    path.write_text(json.dumps(data))
    assert resolve_resource_profile(root, "direct_pi").resources[0].ready
    adapter.write_text("different implementation")
    assert not resolve_resource_profile(root, "direct_pi").resources[0].ready


def test_native_default_skill_directory_is_discovered(tmp_path: Path) -> None:
    root = config(tmp_path)
    (root / "native/settings.json").write_text('{"skills":[],"extensions":[],"packages":[]}')
    (root / "native/skills").mkdir()
    (root / "native/skill").rename(root / "native/skills/sample")
    assert resolve_resource_profile(root, "direct_pi").resources[0].ready


def managed_config(tmp_path: Path, monkeypatch) -> tuple[Path, Path]:
    from test_resource_installation import PROBE_OUTPUT, prepared
    _, install, descriptor = prepared(tmp_path)
    root = tmp_path / "configs/runtime"
    native = root / "native"
    native.mkdir()
    (native / "settings.json").write_text('{"skills":[],"extensions":[],"packages":[]}')
    settings = install / "native/direct_pi/settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text(json.dumps({"skills": ["../../sources/PowerSkills/powerskills-tool/skills/pandapower"], "extensions": [], "packages": []}))
    resources = []
    for resource_id, kind, source in zip(("powerskills-pandapower", "powermcp-pandapower"), ("skill", "mcp"), descriptor["sources"], strict=True):
        resources.append({"id": resource_id, "kind": kind, "version": source["commit"], "source": source["url"],
                          "roles": ["direct_pi"], "enabled": True, "managed": True, "native_name": "pandapower",
                          "required_tools": [], "adapter": None})
    (root / "agent-resources.json").write_text(json.dumps({"schema": "capstone-agent-resources/1", "profile_id": "managed",
        "roles": {"direct_pi": {"settings": "native/settings.json", "adapters": {}}}, "resources": resources}))
    monkeypatch.setattr("capstone_agent.resource_installation._run", lambda *args, **kwargs: PROBE_OUTPUT)
    return root, install


@pytest.mark.parametrize("resource_index", [0, 1])
@pytest.mark.parametrize("field,value", [("source", "https://example.org/uninstalled"), ("version", "c" * 40), ("kind", "plugin")])
def test_managed_declaration_must_match_loaded_source(tmp_path: Path, monkeypatch, resource_index: int, field: str, value: str) -> None:
    root, _ = managed_config(tmp_path, monkeypatch)
    assert all(resource.ready and resource.installed for resource in resolve_resource_profile(root, "direct_pi").resources)
    path = root / "agent-resources.json"
    manifest = json.loads(path.read_text())
    manifest["resources"][resource_index][field] = value
    path.write_text(json.dumps(manifest))
    resource = resolve_resource_profile(root, "direct_pi").resources[resource_index]
    assert not resource.installed
    assert not resource.ready
    assert resource.loaded_identity is None
    assert "identity" in resource.reason


@pytest.mark.parametrize("change", ["native_name", "selected_path"])
def test_managed_skill_must_load_selected_skill_path(tmp_path: Path, monkeypatch, change: str) -> None:
    root, install = managed_config(tmp_path, monkeypatch)
    assert resolve_resource_profile(root, "direct_pi").resources[0].ready
    if change == "native_name":
        path = root / "agent-resources.json"
        manifest = json.loads(path.read_text())
        manifest["resources"][0]["native_name"] = "other"
        path.write_text(json.dumps(manifest))
    else:
        alternate = install / "unselected-skill"
        alternate.mkdir()
        alternate.joinpath("SKILL.md").write_bytes((install / "sources/PowerSkills/powerskills-tool/skills/pandapower/SKILL.md").read_bytes())
        (install / "native/direct_pi/settings.json").write_text('{"skills":["../../unselected-skill"]}')
    resource = resolve_resource_profile(root, "direct_pi").resources[0]
    assert not resource.installed
    assert not resource.ready
    assert "identity" in resource.reason


def test_local_resource_source_and_version_remain_operator_metadata(tmp_path: Path) -> None:
    root = config(tmp_path)
    path = root / "agent-resources.json"
    manifest = json.loads(path.read_text())
    manifest["resources"][0].update(source="operator-local", version="local-revision")
    path.write_text(json.dumps(manifest))
    resource = resolve_resource_profile(root, "direct_pi").resources[0]
    assert resource.installed and resource.ready
    assert (resource.source, resource.version) == ("operator-local", "local-revision")
