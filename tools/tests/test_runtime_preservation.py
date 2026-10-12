from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _module():
    spec = importlib.util.spec_from_file_location("preserve_runtime", ROOT / "deploy/preserve_local_runtime.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_restore_preserves_nested_records_and_is_idempotent(tmp_path):
    module = _module()
    source, target = tmp_path / "source", tmp_path / "target"
    (source / "research").mkdir(parents=True)
    (source / "research/state.json").write_text('{"revision":7}')
    target.mkdir()
    module.restore(source, target, "container-one")
    module.restore(source, target, "container-one")
    assert (target / "research/state.json").read_text() == '{"revision":7}'


def test_restore_never_overwrites_existing_records(tmp_path):
    module = _module()
    source, target = tmp_path / "source", tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (target / "existing.json").write_text("keep")
    with pytest.raises(RuntimeError, match="not empty"):
        module.restore(source, target, "container-two")
    assert (target / "existing.json").read_text() == "keep"


def test_each_compose_role_has_a_separate_project_scoped_runtime_volume():
    import re
    config = (ROOT / "compose.yaml").read_text()
    names = []
    for role in ("api", "worker", "worker-pypsa"):
        block = re.split(r"\n  \S", config.split(f"\n  {role}:\n", 1)[1], maxsplit=1)[0]
        names.append(re.search(r"- ([a-z-]+):/app/runs", block).group(1))
    assert len(set(names)) == 3
    assert all(f"  {name}:\n" in config.split("\nvolumes:\n", 1)[1] for name in names)


def test_migration_helper_is_in_the_backend_image():
    assert "COPY deploy/preserve_local_runtime.py deploy/preserve_local_runtime.py" in (ROOT / "Dockerfile").read_text()


def test_migration_stops_writers_before_copy_and_uses_selected_project(monkeypatch, tmp_path):
    import json
    module = _module()
    roles = ("api", "worker", "worker-pypsa")
    config = {"name": "test-project", "services": {
        role: {"image": "tested-image", "volumes": [{"source": f"{role}-runs", "target": "/app/runs"}]} for role in roles},
        "volumes": {f"{role}-runs": {"name": f"test-project_{role}-runs"} for role in roles}}
    calls = []
    def docker(args):
        calls.append(args)
        if "config" in args:
            return json.dumps(config)
        if "ps" in args:
            return f"old-{args[-1]}"
        if args[0] == "inspect":
            return json.dumps([{"Id": args[1], "Mounts": []}])
        return ""
    monkeypatch.setattr(module, "_docker", docker)
    module.preserve(tmp_path / "compose.yaml", tmp_path / "local.env", tmp_path / "backups")
    stop = next(i for i, call in enumerate(calls) if "stop" in call)
    copies = [i for i, call in enumerate(calls) if call[0] == "cp"]
    assert len(copies) == 3 and all(i > stop for i in copies)
    runs = [call for call in calls if call[0] == "run"]
    assert len(runs) == 3
    assert all("none" in call and "0" in call and "tested-image" in call for call in runs)
    assert all(any("source=test-project_" in arg for arg in call) for call in runs)
