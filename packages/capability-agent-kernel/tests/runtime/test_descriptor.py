from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

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
    assert payload["application"] == {"applicationId": "fixture-app", "runId": "run-1"}
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
