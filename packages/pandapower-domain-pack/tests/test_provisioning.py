from __future__ import annotations

from hashlib import sha256
import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from capability_agent.application.profile import (
    CredentialScope,
    DomainBinding,
)
from capability_agent.domain.provisioning import CredentialLease
from capability_agent.runtime.descriptor import descriptor_from_endpoint
from pandapower_domain.execution import GridctlExecutor
from pandapower_domain.provisioning import (
    PandapowerProvisioningError,
    PandapowerRuntimeProvisioner,
)


class _Lease:
    scope_id = "empty"
    credentials: Mapping[str, str] = {}


def _lease(
    *, scope_id: str = "empty", credentials: Mapping[str, str] | None = None
) -> CredentialLease:
    return cast(
        CredentialLease,
        SimpleNamespace(
            scope_id=scope_id,
            credentials={} if credentials is None else dict(credentials),
        ),
    )


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


def test_provisioner_resolves_gridctl_with_fixed_arguments_and_sanitized_environment(
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

    executor = cast(GridctlExecutor, endpoint.executor)
    assert executor.workspace == workspace
    assert executor.executable.is_absolute()
    assert executor.timeout_seconds == 60
    assert endpoint.metadata["executable"] == "gridctl"
    assert endpoint.metadata["executable_args"] == (
        "request",
        "--workspace",
        str(workspace),
    )
    assert endpoint.metadata["search_path"] == (str(workspace / "bin"),)
    assert endpoint.metadata["max_output_bytes"] == 2 * 1024 * 1024
    environment = cast(Mapping[str, object], endpoint.metadata["environment"])
    assert "GRID_AGENT_SECRET" not in environment
    assert environment["PATH"]
    assert executor.executable == workspace / "bin" / "gridctl"
    assert executor.executable.is_file()


def test_provisioner_hides_credential_shaped_environment_from_metadata_and_child(
    tmp_path: Path,
) -> None:
    environment_path = tmp_path / "child-environment.json"
    executable = tmp_path / "source-gridctl"
    executable.write_text(
        f"#!{sys.executable}\n"
        "import json, os, pathlib, sys\n"
        f"pathlib.Path({str(environment_path)!r}).write_text(json.dumps(dict(os.environ)), encoding='utf-8')\n"
        "request=json.loads(sys.stdin.read())\n"
        "print(json.dumps({'protocol':'grid-capability','protocol_version':'1.0',"
        "'request_id':request['request_id'],'ok':True,'result':{}},separators=(',',':')))\n",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    ambient_values = {
        name: f"secret-value-{index}"
        for index, name in enumerate(
            (
                "AWS_ACCESS_KEY_ID",
                "ALIYUN_ACCESS_KEY_ID",
                "GOOGLE_APPLICATION_CREDENTIALS",
                "OPENAI_API_KEY",
                "APIKEY",
                "SERVICE_SECRETKEY",
                "PASSPHRASE",
                "SERVICE_TOKEN",
                "SECRET",
                "AUTHORIZATION",
                "CREDENTIAL",
                "PASSWORD",
                "PRIVATE_KEY",
                "CUSTOM_BUSINESS_FLAG",
                "GRID_AGENT_GRIDCTL_EXECUTABLE",
                "PYTHONPATH",
                "LC_SECRET",
                "LC_BUSINESS_FLAG",
                "LC_UNKNOWN",
            )
        )
    }
    source_environment = {
        **ambient_values,
        "PATH": os.environ["PATH"],
        "LANG": "C.UTF-8",
        "LANGUAGE": "en_US",
        "LC_ALL": "C.UTF-8",
        "LC_COLLATE": "C",
        "LC_CTYPE": "C.UTF-8",
        "LC_MESSAGES": "C",
        "LC_MONETARY": "C",
        "LC_NUMERIC": "C",
        "LC_TIME": "C",
        "TZ": "UTC",
        "TMPDIR": str(tmp_path),
        "TEMP": str(tmp_path),
        "TMP": str(tmp_path),
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
        "PYTHONUNBUFFERED": "1",
        "PYTHONHASHSEED": "123",
        "SYSTEMROOT": "C:\\Windows",
        "WINDIR": "C:\\Windows",
        "PATHEXT": ".COM;.EXE",
        "__CF_USER_TEXT_ENCODING": os.environ.get(
            "__CF_USER_TEXT_ENCODING", "0x1F5:0x19:0x34"
        ),
    }

    endpoint = PandapowerRuntimeProvisioner(
        executable=executable,
        environ=source_environment,
    ).prepare(binding=_binding(), workspace=tmp_path / "run", credentials=_Lease())

    metadata_environment = cast(
        Mapping[str, str], endpoint.metadata["environment"]
    )
    executor = cast(GridctlExecutor, endpoint.executor)
    executor.invoke("model.list", {})
    child_environment = json.loads(environment_path.read_text(encoding="utf-8"))

    expected_runtime_environment = {
        name: value
        for name, value in source_environment.items()
        if name not in ambient_values
    }
    assert metadata_environment == expected_runtime_environment
    assert child_environment == expected_runtime_environment
    for name, value in ambient_values.items():
        assert name not in metadata_environment
        assert name not in child_environment
        assert value not in metadata_environment.values()
        assert value not in child_environment.values()


def test_prepared_endpoint_materializes_a_serializable_runtime_descriptor(
    tmp_path: Path,
) -> None:
    executable = tmp_path / "source-gridctl"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    workspace = tmp_path / "run" / "domains" / "grid"
    endpoint = PandapowerRuntimeProvisioner(executable=executable).prepare(
        binding=_binding(), workspace=workspace, credentials=_Lease()
    )

    catalog = workspace / "tool-catalog.json"
    catalog.write_text("{}\n", encoding="utf-8")
    guide_index = workspace / "guide-index.json"
    guide_index.write_text("{}\n", encoding="utf-8")
    guide_root = workspace / "guides"
    guide_root.mkdir()

    descriptor_endpoint = SimpleNamespace(
        metadata={
            **endpoint.metadata,
            "guide_index_sha256": sha256(guide_index.read_bytes()).hexdigest(),
        }
    )
    descriptor = descriptor_from_endpoint(
        binding_id="grid",
        workspace=workspace,
        endpoint=descriptor_endpoint,
        protocol="grid-capability",
        protocol_version="1.0",
        authority_id="gridctl",
        tool_catalog_path=catalog,
        guide_index_path=guide_index,
        guide_root_path=guide_root,
        application_id="pandapower-static-analysis",
        run_id="run-1",
    )

    payload = descriptor.as_json()
    domains = payload["domains"]
    assert isinstance(domains, list) and domains
    domain = domains[0]
    assert isinstance(domain, Mapping)
    assert domain["executable"] == "gridctl"
    assert domain["executableArgs"] == [
        "request",
        "--workspace",
        str(workspace),
    ]
    json.dumps(payload)


def test_provisioner_rejects_nonempty_domain_credentials(tmp_path: Path) -> None:
    executable = tmp_path / "gridctl"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    lease = _lease(credentials={"TOKEN": "secret"})

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
    lease = _lease(scope_id="foreign")

    with pytest.raises(PandapowerProvisioningError, match="scope"):
        PandapowerRuntimeProvisioner(executable=executable).prepare(
            binding=_binding(), workspace=tmp_path / "run", credentials=lease
        )
