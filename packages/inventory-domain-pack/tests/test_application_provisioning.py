from pathlib import Path
from types import SimpleNamespace
import math
import os
import shutil
import sys

import pytest

from inventory_domain.provisioning import InventoryRuntimeProvisioner


def test_provisioner_rejects_nonempty_or_wrong_scope_before_lookup(tmp_path: Path) -> None:
    lease = SimpleNamespace(scope_id="wrong", credentials={"TOKEN": "secret"})
    binding = SimpleNamespace(binding_id="inventory", credential_scope=SimpleNamespace(scope_id="inventory", credential_names=()))

    with pytest.raises(ValueError, match="credential"):
        InventoryRuntimeProvisioner(executable=tmp_path / "missing").prepare(
            binding=binding, workspace=tmp_path / "run", credentials=lease
        )

    assert not (tmp_path / "run").exists()


def _binding_and_lease():
    return (
        SimpleNamespace(binding_id="inventory", credential_scope=SimpleNamespace(scope_id="inventory")),
        SimpleNamespace(scope_id="inventory", credentials={}),
    )


def _installed():
    executable = shutil.which("inventoryctl")
    assert executable is not None, "inventory test environment must have its real console script"
    return Path(executable)


def test_real_endpoint_protocol_metadata_and_close(tmp_path):
    binding, lease = _binding_and_lease()
    endpoint = InventoryRuntimeProvisioner(
        executable=_installed(), timeout_seconds=17,
        environment={"PATH": os.environ["PATH"], "OPENAI_API_KEY": "must-not-leak"},
    ).prepare(binding=binding, workspace=tmp_path / "run", credentials=lease)
    result = endpoint.executor.invoke("environment.describe", {})
    assert result["protocol"] == "inventory-capability"
    assert endpoint.metadata["executable"] == ("inventoryctl.exe" if os.name == "nt" else "inventoryctl")
    assert endpoint.metadata["executable_args"] == ("request", "--workspace", str((tmp_path / "run").resolve()))
    assert endpoint.metadata["environment"] == {"PATH": os.environ["PATH"]}
    assert endpoint.executor.timeout_seconds == 17
    endpoint.close()
    endpoint.close()
    assert endpoint.closed
    assert (tmp_path / "run" / "bin" / endpoint.metadata["executable"]).is_file()


@pytest.mark.parametrize("lease", [object(), SimpleNamespace(scope_id="inventory"), SimpleNamespace(scope_id=None, credentials={})])
def test_malformed_credential_lease_fails_before_workspace_changes(tmp_path, lease):
    binding, _ = _binding_and_lease()
    with pytest.raises(ValueError, match="credential"):
        InventoryRuntimeProvisioner(executable=_installed()).prepare(
            binding=binding, workspace=tmp_path / "run", credentials=lease
        )
    assert not (tmp_path / "run").exists()


@pytest.mark.parametrize("value", [0, -1, True, math.inf, math.nan])
def test_invalid_timeout_rejected(value):
    with pytest.raises(ValueError, match="timeout"):
        InventoryRuntimeProvisioner(timeout_seconds=value)


@pytest.mark.parametrize("kind", ["workspace_symlink", "bin_symlink", "existing_file", "existing_symlink"])
def test_unsafe_workspace_or_target_is_preserved(tmp_path, kind):
    binding, lease = _binding_and_lease()
    workspace = tmp_path / "run"
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel"
    sentinel.write_text("keep")
    if kind == "workspace_symlink":
        workspace.symlink_to(outside, target_is_directory=True)
    else:
        workspace.mkdir()
        bin_path = workspace / "bin"
        if kind == "bin_symlink":
            bin_path.symlink_to(outside, target_is_directory=True)
        else:
            bin_path.mkdir()
            target = bin_path / ("inventoryctl.exe" if os.name == "nt" else "inventoryctl")
            if kind == "existing_file":
                target.write_text("keep target")
            else:
                target.symlink_to(sentinel)
    with pytest.raises(ValueError):
        InventoryRuntimeProvisioner(executable=_installed()).prepare(
            binding=binding, workspace=workspace, credentials=lease
        )
    assert sentinel.read_text() == "keep"
    assert sorted(p.name for p in outside.iterdir()) == ["sentinel"]
    if kind == "existing_file":
        assert target.read_text() == "keep target"


def test_explicit_invalid_source_does_not_fall_back(tmp_path):
    binding, lease = _binding_and_lease()
    with pytest.raises(ValueError):
        InventoryRuntimeProvisioner(executable=tmp_path / "missing").prepare(
            binding=binding, workspace=tmp_path / "run", credentials=lease
        )
    assert not (tmp_path / "run").exists()


def test_adjacent_script_precedes_configured_path_and_explicit_precedes_adjacent(tmp_path, monkeypatch):
    installed = _installed()
    adjacent = tmp_path / "python-bin"
    adjacent.mkdir()
    adjacent_script = adjacent / installed.name
    shutil.copy2(installed, adjacent_script)
    monkeypatch.setattr(sys, "executable", str(adjacent / "python"))
    provisioner = InventoryRuntimeProvisioner(environment={"PATH": "/no-such-path"})
    assert provisioner._resolve_executable() == adjacent_script.resolve()
    assert InventoryRuntimeProvisioner(executable=installed)._resolve_executable() == installed.resolve()


def test_configured_path_fallback_does_not_use_ambient_path(tmp_path, monkeypatch):
    installed = _installed()
    monkeypatch.setattr(sys, "executable", str(tmp_path / "no-python" / "python"))
    assert InventoryRuntimeProvisioner(environment={"PATH": str(installed.parent)})._resolve_executable() == installed.resolve()
    with pytest.raises(ValueError):
        InventoryRuntimeProvisioner(environment={})._resolve_executable()


def test_explicit_console_script_alias_installs_fixed_basename(tmp_path):
    installed = _installed()
    alias = tmp_path / "trusted-alias"
    shutil.copy2(installed, alias)
    binding, lease = _binding_and_lease()
    endpoint = InventoryRuntimeProvisioner(executable=alias).prepare(
        binding=binding, workspace=tmp_path / "run", credentials=lease
    )
    assert endpoint.metadata["executable"] == installed.name


def test_endpoint_and_legacy_executor_drop_non_runtime_environment(tmp_path, monkeypatch):
    from inventory_domain.execution import InventoryctlExecutor, sanitize_environment
    import subprocess

    environment = {
        "PATH": os.environ["PATH"], "LANG": "en_US.UTF-8",
        "AWS_ACCESS_KEY_ID": "not-a-real-key", "GOOGLE_APPLICATION_CREDENTIALS": "/secret/path",
        "GITHUB_PAT": "not-a-real-token", "VISIBLE_SETTING": "business-value",
        "PYTHONPATH": "/untrusted/imports", "CUSTOM_PROVIDER_VALUE": "private",
    }
    expected = {"PATH": environment["PATH"], "LANG": environment["LANG"]}
    assert sanitize_environment(environment) == expected
    binding, lease = _binding_and_lease()
    endpoint = InventoryRuntimeProvisioner(executable=_installed(), environment=environment).prepare(
        binding=binding, workspace=tmp_path / "run", credentials=lease,
    )
    assert endpoint.metadata["environment"] == expected
    original_run = subprocess.run
    child_environments = []

    def observe(*args, **kwargs):
        child_environments.append(kwargs["env"])
        return original_run(*args, **kwargs)

    monkeypatch.setattr(subprocess, "run", observe)
    endpoint.executor.invoke("environment.describe", {})
    InventoryctlExecutor(executable=_installed(), workspace=tmp_path / "legacy", environment=environment).invoke("environment.describe", {})
    assert child_environments == [expected, expected]
