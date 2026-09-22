from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import cast

import pytest

from capability_agent.runtime.descriptor import (
    RuntimeDescriptor,
    RuntimeDescriptorError,
    descriptor_from_endpoint,
    write_runtime_descriptor,
)


def test_runtime_descriptor_is_binding_aware_and_versioned(tmp_path: Path) -> None:
    catalog = tmp_path / "tool-catalog.json"
    catalog.write_text("{}\n", encoding="utf-8")
    guide_index = tmp_path / "guide-index.json"
    guide_index.write_text("{}\n", encoding="utf-8")
    guide_root = tmp_path / "guides"
    guide_root.mkdir()
    path = write_runtime_descriptor(
        tmp_path / "descriptor.json",
        RuntimeDescriptor(
            binding_id="alpha",
            workspace_path=tmp_path,
            executable="domainctl",
            executable_args=("request",),
            search_path=("/opt/domain/bin",),
            protocol="alpha-capability",
            protocol_version="1.0",
            authority_id="alpha-authority",
            application_id="fixture-app",
            run_id="run-1",
            tool_name_prefix="alpha_",
            guide_tool_name="alpha_guide_open",
            tool_catalog_path=catalog,
            guide_index_path=guide_index,
            guide_root_path=guide_root,
            guide_index_sha256=sha256(guide_index.read_bytes()).hexdigest(),
        ),
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema"] == "capability-agent-runtime/1.0"
    assert payload["application"] == {
        "applicationId": "fixture-app",
        "runId": "run-1",
        "workspacePath": str(tmp_path),
    }
    assert payload["core"] == {
        "decisionToolName": "agent_record_decision",
        "contextToolName": "agent_context_get",
    }
    assert payload["domains"][0]["bindingId"] == "alpha"
    assert payload["domains"][0]["executable"] == "domainctl"
    assert "search_path" not in payload


def test_descriptor_rejects_schema_override_reserved_and_secret_extensions(
    tmp_path: Path,
) -> None:
    common = {
        "binding_id": "alpha",
        "workspace_path": tmp_path,
        "executable": "domainctl",
    }
    with pytest.raises(RuntimeDescriptorError, match="schema"):
        RuntimeDescriptor(**common, schema="other/1.0")
    with pytest.raises(RuntimeDescriptorError, match="reserved"):
        RuntimeDescriptor(**common, extra={"schema": "forged"})
    with pytest.raises(RuntimeDescriptorError, match="credentials"):
        RuntimeDescriptor(**common, extra={"access_token": "secret"})


def test_descriptor_rejects_partial_model_request_capture_channels(tmp_path: Path) -> None:
    with pytest.raises(RuntimeDescriptorError, match="capture channels"):
        RuntimeDescriptor(
            binding_id="alpha",
            workspace_path=tmp_path,
            executable="domainctl",
            trajectory_requests_path=tmp_path / "requests",
        )
    capture_channels = {
        "trajectory_requests_path": tmp_path / "requests",
        "trajectory_capture_state_path": tmp_path / "capture.json",
        "trajectory_allowed_refs_path": tmp_path / "refs.json",
        "trajectory_acks_path": tmp_path / "acks",
    }
    with pytest.raises(RuntimeDescriptorError, match="capture channels"):
        RuntimeDescriptor(
            binding_id="alpha", workspace_path=tmp_path, executable="domainctl",
            **capture_channels,
        )
    RuntimeDescriptor(
        binding_id="alpha", workspace_path=tmp_path, executable="domainctl",
        active_turn_path=tmp_path / "active.json", **capture_channels,
    )


def test_descriptor_rejects_symlinked_parent_before_writing(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    link = tmp_path / "link"
    link.symlink_to(outside, target_is_directory=True)
    descriptor = RuntimeDescriptor(
        binding_id="alpha", workspace_path=tmp_path, executable="domainctl"
    )

    with pytest.raises(RuntimeDescriptorError, match="symlink"):
        write_runtime_descriptor(link / "nested" / "descriptor.json", descriptor)
    assert not (outside / "nested").exists()


def test_descriptor_endpoint_import_ignores_untrusted_metadata_fields(tmp_path: Path) -> None:
    catalog = tmp_path / "tool-catalog.json"
    catalog.write_text("{}\n", encoding="utf-8")
    guide_index = tmp_path / "guide-index.json"
    guide_index.write_text("{}\n", encoding="utf-8")
    guide_root = tmp_path / "guides"
    guide_root.mkdir()
    endpoint = type(
        "Endpoint",
        (),
        {
            "metadata": {
                "executable": "domainctl",
                "arguments": ["request"],
                "search_paths": ["/opt/domain/bin"],
                "protocol": "alpha-capability",
                "protocol_version": "1.0",
                "authority_id": "alpha-authority",
                "tool_name_prefix": "alpha_",
                "guide_tool_name": "alpha_guide_open",
                "tool_catalog_path": str(catalog),
                "guide_index_path": str(guide_index),
                "guide_root_path": str(guide_root),
                "guide_index_sha256": sha256(guide_index.read_bytes()).hexdigest(),
                "credential": "should-not-be-copied",
            }
        },
    )()

    descriptor = descriptor_from_endpoint(
        binding_id="alpha",
        workspace=tmp_path,
        endpoint=endpoint,
        application_id="fixture-app",
        run_id="run-1",
    )

    payload = descriptor.as_json()
    assert "credential" not in payload
    assert "should-not-be-copied" not in json.dumps(payload)


def test_runtime_descriptor_rejects_a_stale_guide_index_digest(
    tmp_path: Path,
) -> None:
    catalog = tmp_path / "tool-catalog.json"
    catalog.write_text("{}\n", encoding="utf-8")
    guide_index = tmp_path / "guide-index.json"
    guide_index.write_text("{}\n", encoding="utf-8")
    guide_root = tmp_path / "guides"
    guide_root.mkdir()
    descriptor = RuntimeDescriptor(
        binding_id="alpha",
        workspace_path=tmp_path,
        executable="domainctl",
        protocol="alpha-capability",
        protocol_version="1.0",
        authority_id="alpha-authority",
        tool_name_prefix="alpha_",
        tool_catalog_path=catalog,
        guide_index_path=guide_index,
        guide_root_path=guide_root,
        guide_index_sha256="0" * 64,
    )

    with pytest.raises(RuntimeDescriptorError, match="does not match"):
        descriptor.as_json()


def test_runtime_descriptor_separates_binding_workspace_from_application_channels(
    tmp_path: Path,
) -> None:
    application_root = tmp_path / "run"
    domain_root = application_root / "domains" / "alpha"
    domain_root.mkdir(parents=True)
    catalog = domain_root / "tool-catalog.json"
    catalog.write_text("{}\n", encoding="utf-8")
    guide_index = domain_root / "guide-index.json"
    guide_index.write_text("{}\n", encoding="utf-8")
    guide_root = domain_root / "guides"
    guide_root.mkdir()
    context_path = application_root / "core" / "context.json"
    context_path.parent.mkdir()

    descriptor = RuntimeDescriptor(
        binding_id="alpha",
        workspace_path=domain_root,
        application_workspace_path=application_root,
        executable="domainctl",
        executable_args=("--workspace", str(domain_root)),
        protocol="alpha-capability",
        protocol_version="1.0",
        authority_id="alpha-authority",
        tool_catalog_path=catalog,
        guide_index_path=guide_index,
        guide_root_path=guide_root,
        context_view_path=context_path,
    )

    payload = descriptor.as_json()

    application_payload = cast(dict[str, object], payload["application"])
    core_payload = cast(dict[str, object], payload["core"])
    domain_payload = cast(
        dict[str, object], cast(list[object], payload["domains"])[0]
    )
    assert application_payload["workspacePath"] == str(application_root)
    assert domain_payload["workspacePath"] == str(domain_root)
    assert domain_payload["toolCatalogPath"] == str(catalog)
    assert core_payload["analysisContextViewPath"] == str(context_path)


def test_descriptor_endpoint_rejects_explicit_empty_optional_tool_name(
    tmp_path: Path,
) -> None:
    endpoint = type(
        "Endpoint",
        (),
        {"metadata": {"executable": "domainctl", "guide_tool_name": ""}},
    )()

    with pytest.raises(RuntimeDescriptorError, match="guide_tool_name"):
        descriptor_from_endpoint(
            binding_id="alpha", workspace=tmp_path, endpoint=endpoint
        )


def test_descriptor_rejects_paths_and_absolute_arguments_outside_workspace(
    tmp_path: Path,
) -> None:
    with pytest.raises(RuntimeDescriptorError, match="outside workspace"):
        RuntimeDescriptor(
            binding_id="alpha",
            workspace_path=tmp_path / "run",
            executable="domainctl",
            executable_args=("--workspace", str(tmp_path / "elsewhere")),
        )
    with pytest.raises(RuntimeDescriptorError, match="outside workspace"):
        RuntimeDescriptor(
            binding_id="alpha",
            workspace_path=tmp_path / "run",
            executable="domainctl",
            tool_catalog_path=tmp_path / "catalog.json",
        )


def test_descriptor_rejects_absolute_argument_through_workspace_symlink(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "run"
    workspace.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    link = workspace / "link"
    link.symlink_to(outside, target_is_directory=True)

    with pytest.raises(RuntimeDescriptorError, match="symlink"):
        RuntimeDescriptor(
            binding_id="alpha",
            workspace_path=workspace,
            executable="domainctl",
            executable_args=(str(link / "escaped"),),
        )
