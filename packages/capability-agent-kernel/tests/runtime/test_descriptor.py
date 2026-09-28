from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import cast

import pytest

from capability_agent.runtime.descriptor import (
    CompositeRuntimeDescriptor,
    RuntimeDescriptor,
    RuntimeDescriptorError,
    descriptor_from_endpoint,
    write_runtime_descriptor,
)


def _binding_descriptor(
    tmp_path: Path, binding_id: str, **overrides: object
) -> RuntimeDescriptor:
    application = tmp_path / "run"
    workspace = application / "domains" / binding_id
    workspace.mkdir(parents=True, exist_ok=True)
    catalog = workspace / "catalog.json"
    catalog.write_text("{}\n", encoding="utf-8")
    index = workspace / "index.json"
    index.write_text("{}\n", encoding="utf-8")
    guides = workspace / "guides"
    guides.mkdir(exist_ok=True)
    values: dict[str, object] = {
        "binding_id": binding_id,
        "workspace": workspace,
        "application_workspace_path": application,
        "protocol": f"{binding_id}-capability",
        "protocol_version": "1.0",
        "authority_id": f"{binding_id}-authority",
        "tool_catalog_path": catalog,
        "guide_index_path": index,
        "guide_root_path": guides,
        "application_id": "fixture-app",
        "run_id": "run-1",
        "active_turn_path": application / "core" / "active.json",
        "context_view_path": application / "core" / "context.json",
    }
    endpoint_fields = {
        name: overrides[name]
        for name in ("guide_tool_name", "core_tool_names")
        if name in overrides
    }
    values["endpoint"] = {"executable": "domainctl", **endpoint_fields}
    values.update({key: value for key, value in overrides.items() if key not in endpoint_fields})
    return descriptor_from_endpoint(**values)


def test_composite_descriptor_serializes_two_bindings_and_preserves_v1(
    tmp_path: Path,
) -> None:
    grid = _binding_descriptor(tmp_path, "grid")
    inventory = _binding_descriptor(tmp_path, "inventory")
    composite = CompositeRuntimeDescriptor(domains=(grid, inventory))

    payload = composite.as_json()
    assert payload["schema"] == "capability-agent-runtime/1.1"
    assert payload["application"] == grid.as_json()["application"]
    assert payload["core"] == grid.as_json()["core"]
    assert [item["bindingId"] for item in payload["domains"]] == [
        "grid", "inventory"
    ]
    assert grid.as_json()["schema"] == "capability-agent-runtime/1.0"
    target = write_runtime_descriptor(tmp_path / "composite.json", composite)
    expected_bytes = (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode()
    assert target.read_bytes() == expected_bytes


@pytest.mark.parametrize(
    ("override", "expected"),
    [
        ({"application_id": "other"}, "application"),
        ({"run_id": "other"}, "application"),
        ({"application_workspace_path": "other"}, "application"),
        ({"active_turn_path": "other"}, "core"),
        ({"core_tool_names": ("agent_decide", "agent_context_get")}, "core"),
    ],
)
def test_composite_descriptor_rejects_inconsistent_shared_fields(
    tmp_path: Path, override: dict[str, object], expected: str
) -> None:
    grid = _binding_descriptor(tmp_path, "grid")
    if "application_workspace_path" in override:
        override = {
            "application_workspace_path": tmp_path / "other",
            "active_turn_path": tmp_path / "other" / "core" / "active.json",
            "context_view_path": tmp_path / "other" / "core" / "context.json",
        }
    elif "active_turn_path" in override:
        override = {"active_turn_path": tmp_path / "run" / "core" / "other.json"}
    inventory = _binding_descriptor(tmp_path, "inventory", **override)
    with pytest.raises(RuntimeDescriptorError, match=expected):
        CompositeRuntimeDescriptor(domains=(grid, inventory)).as_json()


@pytest.mark.parametrize(
    ("override", "expected"),
    [
        ({"same_binding": True}, "binding"),
        (
            {"guide_tool_name": "grid_guide_open", "tool_name_prefix": "grid_"},
            "guide",
        ),
        (
            {"guide_tool_name": "grid_other_guide_open", "tool_name_prefix": "grid_"},
            "prefix",
        ),
    ],
)
def test_composite_descriptor_rejects_duplicate_domain_names(
    tmp_path: Path, override: dict[str, object], expected: str
) -> None:
    grid = _binding_descriptor(tmp_path, "grid")
    inventory = (
        _binding_descriptor(tmp_path, "grid")
        if override.get("same_binding", False)
        else _binding_descriptor(tmp_path, "inventory", **override)
    )
    with pytest.raises(RuntimeDescriptorError, match=expected):
        CompositeRuntimeDescriptor(domains=(grid, inventory)).as_json()


def test_composite_descriptor_rejects_escaping_domain_path(tmp_path: Path) -> None:
    grid = _binding_descriptor(tmp_path, "grid")
    with pytest.raises(RuntimeDescriptorError, match="outside workspace"):
        inventory = _binding_descriptor(
            tmp_path, "inventory", tool_catalog_path=tmp_path / "elsewhere.json"
        )
        CompositeRuntimeDescriptor(domains=(grid, inventory)).as_json()


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
    assert payload["domains"] == [{
        "bindingId": "alpha",
        "protocol": "alpha-capability",
        "protocolVersion": "1.0",
        "executable": "domainctl",
        "executableArgs": ["request"],
        "toolCatalogPath": str(catalog),
        "guideToolName": "alpha_guide_open",
        "guideIndexPath": str(guide_index),
        "guideRootPath": str(guide_root),
        "guideIndexSha256": sha256(guide_index.read_bytes()).hexdigest(),
        "workspacePath": str(tmp_path),
        "authorityId": "alpha-authority",
    }]
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


def test_runtime_descriptor_allows_arguments_to_reference_sibling_domain_workspace(
    tmp_path: Path,
) -> None:
    application_root = tmp_path / "run"
    domain_root = application_root / "domains" / "operations"
    source_root = application_root / "domains" / "source"
    domain_root.mkdir(parents=True)
    source_root.mkdir(parents=True)

    RuntimeDescriptor(
        binding_id="operations",
        workspace_path=domain_root,
        application_workspace_path=application_root,
        executable="opsctl",
        executable_args=("--source-workspace", str(source_root)),
    )


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
