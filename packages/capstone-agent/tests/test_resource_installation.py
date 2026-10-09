from __future__ import annotations

import json
import hashlib
import subprocess
import sys
import platform
from pathlib import Path

import pytest

from capstone_agent.resource_installation import install_managed_resources, inspect_installation, verify_source_tree
from capstone_agent.runtime_resources import content_hash

BASE_IDENTITY = {"python": platform.python_version(), "implementation": platform.python_implementation(),
                 "platform": platform.system(), "machine": platform.machine(),
                 "base_interpreter_sha256": hashlib.sha256(Path(sys.executable).resolve().read_bytes()).hexdigest()}
DEPENDENCIES = {"pandapower": "3.4.0"}
PROBE_OUTPUT = json.dumps({"dependencies": DEPENDENCIES, "runtime_identity": BASE_IDENTITY})


def test_failed_install_keeps_prior_pointer_and_rejects_untrusted_source(tmp_path: Path) -> None:
    managed = tmp_path / ".grid-agent/runtime/agent-resources"
    managed.mkdir(parents=True)
    pointer = managed / "current.json"
    pointer.write_text('{"install_id":"prior"}')
    config = tmp_path / "configs/runtime"
    config.mkdir(parents=True)
    (config / "power-samples.lock.json").write_text(json.dumps({"schema": "capstone-resource-lock/1", "sources": [{"id": "PowerSkills", "url": "https://example.org/bad", "commit": "a" * 40, "files": {"../escape": "b" * 64}}], "dependencies": {}}))
    with pytest.raises(ValueError, match="path"):
        install_managed_resources(config, source_root=tmp_path / "sources", fetch=False)
    assert pointer.read_text() == '{"install_id":"prior"}'


def test_source_hash_and_symlink_verification(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "file").write_text("wrong bytes")
    with pytest.raises(ValueError, match="hash"):
        verify_source_tree(source, {"file": "a" * 64})
    outside = tmp_path / "outside"
    outside.write_text("external")
    (source / "link").symlink_to(outside)
    with pytest.raises(ValueError, match="link|path"):
        verify_source_tree(source, {"link": "a" * 64})


def prepared(tmp_path: Path) -> tuple[Path, Path, dict]:
    managed = tmp_path / ".grid-agent/runtime/agent-resources"
    install_id = "installs/" + "a" * 32
    install = managed / install_id
    install.mkdir(parents=True)
    source = install / "sources/PowerMCP/pandapower/panda_mcp.py"
    source.parent.mkdir(parents=True)
    source.write_text("# fixed source\n")
    sha = hashlib.sha256(source.read_bytes()).hexdigest()
    config = tmp_path / "configs/runtime"
    config.mkdir(parents=True)
    schema = config / "prepared-mcp-v1.schema.json"
    schema_bytes = (Path(__file__).resolve().parents[3] / "configs/runtime/prepared-mcp-v1.schema.json").read_bytes()
    schema.write_bytes(schema_bytes)
    (install / "descriptor-schema.json").write_bytes(schema_bytes)
    skill = install / "sources/PowerSkills/powerskills-tool/skills/pandapower/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: pandapower\ndescription: sample\n---\nRead the model.\n")
    sources = [{"id": "PowerSkills", "url": "https://github.com/Power-Agent/PowerSkills", "commit": "b" * 40,
                "files": {"powerskills-tool/skills/pandapower/SKILL.md": hashlib.sha256(skill.read_bytes()).hexdigest()}},
               {"id": "PowerMCP", "url": "https://github.com/Power-Agent/PowerMCP", "commit": "a" * 40,
                "files": {"pandapower/panda_mcp.py": sha}}]
    tool_schemas = {name: {"type": "object"} for name in json.loads(schema_bytes)["properties"]["tool_schemas"]["required"]}
    lock = {"sources": sources, "dependencies": DEPENDENCIES,
            "tool_schema_hashes": {name: content_hash(value) for name, value in tool_schemas.items()}}
    (config / "power-samples.lock.json").write_text(json.dumps(lock))
    (install / "installation-lock.json").write_text(json.dumps(lock))
    smoke = install / "smoke.json"
    smoke.write_text('{}')
    (install / "venv/bin").mkdir(parents=True)
    (install / "venv/bin/python").symlink_to(sys.executable)
    document = {"schema": "capstone-prepared-mcp/1", "install_id": install_id, "transport": "stdio", "interpreter": "venv/bin/python", "server": "sources/PowerMCP/pandapower/panda_mcp.py", "sources": [{key: value for key, value in source.items() if key != "files"} for source in sources], "source_files": {"sources/" + source["id"] + "/" + name: digest for source in sources for name, digest in source["files"].items()}, "dependencies": DEPENDENCIES, "runtime_identity": {}, "tool_schemas": tool_schemas, "tool_schema_hashes": lock["tool_schema_hashes"], "smoke_sha256": hashlib.sha256(smoke.read_bytes()).hexdigest(), "lock_sha256": content_hash(lock), "descriptor_schema_sha256": hashlib.sha256(schema.read_bytes()).hexdigest()}
    document["runtime_identity"] = dict(BASE_IDENTITY)
    (install / "prepared-mcp.json").write_text(json.dumps(document))
    (managed / "current.json").write_text(json.dumps({"install_id": install_id, "descriptor_sha256": content_hash(document)}))
    return managed, install, document


def test_missing_imports_are_unavailable_even_with_receipt(tmp_path: Path) -> None:
    managed, _, _ = prepared(tmp_path)
    descriptor, reason = inspect_installation(managed)
    assert descriptor is None
    assert "dependency" in reason
    assert str(tmp_path) not in reason


@pytest.mark.parametrize("drift", ["source", "schema", "dependencies", "path", "other_server"])
def test_prepared_source_schema_dependency_and_path_drift(tmp_path: Path, monkeypatch, drift: str) -> None:
    managed, install, document = prepared(tmp_path)
    monkeypatch.setattr("capstone_agent.resource_installation._run", lambda *args, **kwargs: PROBE_OUTPUT)
    assert inspect_installation(managed)[0] is not None
    if drift == "source":
        (install / document["server"]).write_text("# changed")
    elif drift == "schema":
        document["tool_schemas"]["audit_network"] = {"type": "string"}
    elif drift == "dependencies":
        monkeypatch.setattr("capstone_agent.resource_installation._run", lambda *args, **kwargs: '{"dependencies":{"pandapower":"other"},"runtime_identity":{}}')
    elif drift == "other_server":
        document["server"] = "alternate.py"
        (install / "alternate.py").write_text("# unpinned server")
    else:
        document["server"] = "../../external.py"
    (install / "prepared-mcp.json").write_text(json.dumps(document))
    (managed / "current.json").write_text(json.dumps({"install_id": document["install_id"], "descriptor_sha256": content_hash(document)}))
    assert inspect_installation(managed)[0] is None


def test_frozen_install_uses_retained_lock_and_accepted_descriptor_hash(tmp_path: Path, monkeypatch) -> None:
    managed, _, document = prepared(tmp_path)
    monkeypatch.setattr("capstone_agent.resource_installation._run", lambda *args, **kwargs: PROBE_OUTPUT)
    accepted = content_hash(document)
    (managed / "current.json").write_text('{"install_id":"foreign"}')
    (tmp_path / "configs/runtime/power-samples.lock.json").write_text('{}')
    (tmp_path / "configs/runtime/prepared-mcp-v1.schema.json").write_text('{"not":{}}')
    assert inspect_installation(managed, install_id=document["install_id"], expected_descriptor_sha256=accepted)[0] is not None
    assert inspect_installation(managed, install_id=document["install_id"], expected_descriptor_sha256="b" * 64)[0] is None


@pytest.mark.parametrize("malformed", ["missing_tool", "extra_runtime_field", "empty_python", "malformed_source", "extra_tool", "hash_keys", "malformed_runtime", "malformed_document"])
def test_closed_descriptor_schema_rejects_changes_before_probe(tmp_path: Path, monkeypatch, malformed: str) -> None:
    managed, install, document = prepared(tmp_path)
    calls = []
    monkeypatch.setattr("capstone_agent.resource_installation._run", lambda *args, **kwargs: calls.append(args) or PROBE_OUTPUT)
    assert inspect_installation(managed)[0] is not None
    calls.clear()
    if malformed == "missing_tool":
        del document["tool_schemas"]["audit_network"]
    elif malformed == "extra_runtime_field":
        document["runtime_identity"]["unexpected"] = True
    elif malformed == "empty_python":
        document["runtime_identity"]["python"] = ""
    elif malformed == "malformed_source":
        document["sources"][0]["unexpected"] = True
    elif malformed == "extra_tool":
        document["tool_schemas"]["unexpected"] = {}
    elif malformed == "hash_keys":
        del document["tool_schema_hashes"]["audit_network"]
    elif malformed == "malformed_runtime":
        document["runtime_identity"] = []
    else:
        document = []
    (install / "prepared-mcp.json").write_text(json.dumps(document))
    (managed / "current.json").write_text(json.dumps({"install_id": install.relative_to(managed).as_posix(), "descriptor_sha256": content_hash(document)}))
    descriptor, reason = inspect_installation(managed)
    assert descriptor is None
    assert not calls
    assert str(tmp_path) not in reason


def test_retained_schema_is_applied_before_probe(tmp_path: Path, monkeypatch) -> None:
    managed, install, document = prepared(tmp_path)
    del document["tool_schemas"]["audit_network"]
    (install / "prepared-mcp.json").write_text(json.dumps(document))
    (tmp_path / "configs/runtime/prepared-mcp-v1.schema.json").write_text('{}')
    calls = []
    monkeypatch.setattr("capstone_agent.resource_installation._run", lambda *args, **kwargs: calls.append(args) or PROBE_OUTPUT)
    assert inspect_installation(managed, install_id=document["install_id"], expected_descriptor_sha256=content_hash(document))[0] is None
    assert not calls


def test_retained_schema_bytes_remain_bound_to_accepted_descriptor(tmp_path: Path, monkeypatch) -> None:
    managed, install, document = prepared(tmp_path)
    (install / "descriptor-schema.json").write_text('{}')
    calls = []
    monkeypatch.setattr("capstone_agent.resource_installation._run", lambda *args, **kwargs: calls.append(args) or PROBE_OUTPUT)
    assert inspect_installation(managed, install_id=document["install_id"], expected_descriptor_sha256=content_hash(document))[0] is None
    assert not calls


def test_base_interpreter_link_change_is_rejected_before_execution(tmp_path: Path, monkeypatch) -> None:
    managed, install, _ = prepared(tmp_path)
    monkeypatch.setattr("capstone_agent.resource_installation._run", lambda *args, **kwargs: PROBE_OUTPUT)
    assert inspect_installation(managed)[0] is not None
    interpreter = install / "venv/bin/python"
    interpreter.unlink()
    alternate = tmp_path / "alternate-python"
    alternate.write_text("# untrusted replacement interpreter")
    interpreter.symlink_to(alternate)
    assert inspect_installation(managed)[0] is None


def test_provision_failure_removes_only_new_stage_and_preserves_prior(tmp_path: Path, monkeypatch) -> None:
    config = tmp_path / "configs/runtime"
    config.mkdir(parents=True)
    (config / "prepared-mcp-v1.schema.json").write_text('{}')
    root = tmp_path / "sources"
    sources = []
    for name in ("PowerSkills", "PowerMCP"):
        tree = root / name
        tree.mkdir(parents=True)
        (tree / "file").write_text("fixed source")
        for args in (["init", "-q"], ["add", "file"], ["-c", "user.name=Test", "-c", "user.email=test@example.org", "commit", "-qm", "source"]):
            subprocess.run(["git", "-C", str(tree), *args], check=True)
        commit = subprocess.check_output(["git", "-C", str(tree), "rev-parse", "HEAD"], text=True).strip()
        sources.append({"id": name, "url": "https://example.org/" + name, "commit": commit, "files": {"file": hashlib.sha256((tree / "file").read_bytes()).hexdigest()}})
    (config / "power-samples.lock.json").write_text(json.dumps({"schema": "capstone-resource-lock/1", "sources": sources, "dependencies": {}, "python": "3.12"}))
    managed = tmp_path / ".grid-agent/runtime/agent-resources"
    managed.mkdir(parents=True)
    (managed / "current.json").write_text('{"install_id":"prior"}')
    import capstone_agent.resource_installation as module
    original = module._run
    def fail_provision(args, **kwargs):
        if args[0] == "uv":
            raise subprocess.CalledProcessError(1, args)
        return original(args, **kwargs)
    monkeypatch.setattr(module, "_run", fail_provision)
    with pytest.raises(subprocess.CalledProcessError):
        install_managed_resources(config, source_root=root, fetch=False)
    assert (managed / "current.json").read_text() == '{"install_id":"prior"}'
    assert not list((managed / "installs").iterdir())
