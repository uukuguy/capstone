from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from capability_agent.application.profile import CredentialScope, DomainBinding
from pandapower_domain.provisioning import (
    PandapowerProvisioningError,
    PandapowerRuntimeProvisioner,
)


class _Lease:
    scope_id = "empty"
    credentials: dict[str, str] = {}


def _binding() -> DomainBinding:
    profile = SimpleNamespace(
        manifest=SimpleNamespace(
            domain_id="pandapower-static-analysis",
            version="1.0.1",
            executable_name="gridctl",
            protocol="grid-capability",
            protocol_version="1.0",
        )
    )
    return DomainBinding(
        binding_id="grid",
        tool_namespace="grid_",
        profile=profile,  # type: ignore[arg-type]
        credential_scope=CredentialScope(scope_id="empty"),
        sharing_policy=SimpleNamespace(mode="deny"),  # type: ignore[arg-type]
    )


def test_provisioner_resolves_gridctl_with_fixed_arguments_and_scrubbed_environment(
    tmp_path: Path,
) -> None:
    executable = tmp_path / "source-gridctl"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    workspace = tmp_path / "run" / "domains" / "grid"
    provisioner = PandapowerRuntimeProvisioner(
        executable=executable,
        environ={"GRID_AGENT_SECRET": "secret", "PATH": os.environ["PATH"]},
    )

    endpoint = provisioner.prepare(
        binding=_binding(), workspace=workspace, credentials=_Lease()
    )

    assert endpoint.executor.workspace == workspace
    assert endpoint.executor.timeout_seconds == 60
    assert endpoint.metadata["executable_args"] == (
        "request",
        "--workspace",
        str(workspace),
    )
    assert endpoint.metadata["search_path"] == str(workspace / "bin")
    assert endpoint.metadata["max_output_bytes"] == 2 * 1024 * 1024
    assert endpoint.metadata["environment"] ["GRID_AGENT_SECRET"] == "<scrubbed>"
    assert endpoint.metadata["environment"] ["PATH"]
    assert endpoint.executor.executable == workspace / "bin" / "gridctl"
    assert endpoint.executor.executable.is_file()


def test_provisioner_rejects_nonempty_domain_credentials(tmp_path: Path) -> None:
    executable = tmp_path / "gridctl"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    lease = SimpleNamespace(scope_id="empty", credentials={"TOKEN": "secret"})

    with pytest.raises(PandapowerProvisioningError, match="credentials"):
        PandapowerRuntimeProvisioner(executable=executable).prepare(
            binding=_binding(), workspace=tmp_path / "run", credentials=lease
        )


def test_provisioner_rejects_a_symlinked_binding_workspace(tmp_path: Path) -> None:
    executable = tmp_path / "gridctl"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    outside = tmp_path / "outside"
    outside.mkdir()
    workspace = tmp_path / "run"
    workspace.symlink_to(outside, target_is_directory=True)

    with pytest.raises(PandapowerProvisioningError, match="workspace"):
        PandapowerRuntimeProvisioner(executable=executable).prepare(
            binding=_binding(), workspace=workspace, credentials=_Lease()
        )


def test_provisioner_rejects_a_credential_scope_mismatch(tmp_path: Path) -> None:
    executable = tmp_path / "gridctl"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    lease = SimpleNamespace(scope_id="foreign", credentials={})

    with pytest.raises(PandapowerProvisioningError, match="scope"):
        PandapowerRuntimeProvisioner(executable=executable).prepare(
            binding=_binding(), workspace=tmp_path / "run", credentials=lease
        )
