from __future__ import annotations

from pathlib import Path

import pytest

from capability_agent.runtime.environment import (
    RuntimePaths,
    build_pi_environment,
    build_pi_launch,
)
from capability_agent.runtime.models import ResolvedLLM, ResolvedLLMConfig, SecretValue
from capability_agent.runtime.lock import PiCommand, PiRuntimeIdentity


def test_launch_environment_binds_endpoint_path_and_scrubs_controller_values(
    tmp_path: Path,
) -> None:
    command = PiCommand(
        argv=("node", "/opt/pi/cli.js"),
        identity=PiRuntimeIdentity(
            path=Path("/opt/pi/cli.js"),
            source="fixture",
            package_version="1.0.0",
            lock_sha256="lock",
        ),
    )
    resolved = ResolvedLLM(
        config=ResolvedLLMConfig(
            provider="alpha",
            model="alpha-model",
            base_url="https://provider.example/v1",
            auth_kind="api_key_env",
            credential_reference="ALPHA_KEY",
            timeout_seconds=10.0,
            max_retries=0,
            pi_provider="alpha",
            compatibility_profile="generic",
            descriptor_version="fixture-1",
            public_headers={},
            field_sources={},
            supports_tools=True,
        ),
        secret=SecretValue("secret"),
    )
    paths = RuntimePaths(
        command=command,
        project_pi_dir=tmp_path / "pi",
        session_dir=tmp_path / "session",
        workspace=tmp_path,
        domain_search_path=Path("/opt/domain/bin"),
        runtime_descriptor_path=tmp_path / "descriptor.json",
        binding_id="alpha",
    )

    environment = build_pi_environment(
        resolved,
        paths,
        base_environment={
            "PATH": "/usr/bin",
            "HOME": "/tmp/home",
            "CAPABILITY_AGENT_FORGED": "must-not-pass",
            "UNRELATED_SECRET": "must-not-pass",
        },
    )

    assert environment["PATH"].split(":", 1)[0] == "/opt/domain/bin"
    assert environment["CAPABILITY_AGENT_RUNTIME_DESCRIPTOR"] == str(
        tmp_path / "descriptor.json"
    )
    assert "CAPABILITY_AGENT_FORGED" not in environment
    assert environment["CAPABILITY_AGENT_SECRET_ENV_NAMES"] == "ALPHA_KEY"
    assert environment["ALPHA_KEY"] == "secret"


def test_environment_preserves_binding_search_path_precedence_without_injection(
    tmp_path: Path,
) -> None:
    command = PiCommand(
        argv=("pi",),
        identity=PiRuntimeIdentity(
            path=Path("pi"),
            source="fixture",
            package_version="1.0.0",
            lock_sha256="lock",
        ),
    )
    resolved = ResolvedLLM(
        config=ResolvedLLMConfig(
            provider="alpha",
            model="alpha-model",
            base_url="https://provider.example/v1",
            auth_kind="api_key_env",
            credential_reference="CUSTOM_SECRET",
            timeout_seconds=10.0,
            max_retries=0,
            pi_provider="alpha",
            compatibility_profile="generic",
            descriptor_version="fixture-1",
            public_headers={},
            field_sources={},
            supports_tools=True,
        ),
        secret=SecretValue("secret-value"),
    )
    paths = RuntimePaths(
        command=command,
        project_pi_dir=tmp_path / "pi",
        session_dir=tmp_path / "session",
        workspace=tmp_path,
        domain_search_paths=(Path("/opt/one/bin"), Path("/opt/two/bin")),
        binding_id="alpha",
        extra_controller_values={"CAPABILITY_AGENT_ALLOWED": "yes"},
    )

    environment = build_pi_environment(
        resolved,
        paths,
        base_environment={
            "PATH": "/usr/bin",
            "HOME": "/tmp/home",
            "CAPABILITY_AGENT_FORGED": "no",
            "CUSTOM_SECRET": "attacker-value",
            "UNRELATED_SECRET": "must-not-pass",
        },
    )

    assert environment["PATH"] == "/opt/one/bin:/opt/two/bin:/usr/bin"
    assert environment["CUSTOM_SECRET"] == "secret-value"
    assert environment["CAPABILITY_AGENT_ALLOWED"] == "yes"
    assert "CAPABILITY_AGENT_FORGED" not in environment
    assert "UNRELATED_SECRET" not in environment


def test_environment_descriptor_mode_drops_path_supplements(tmp_path: Path) -> None:
    command = PiCommand(
        argv=("pi",),
        identity=PiRuntimeIdentity(
            path=Path("pi"), source="fixture", package_version="1.0.0", lock_sha256="lock"
        ),
    )
    resolved = ResolvedLLM(
        config=ResolvedLLMConfig(
            provider="alpha", model="alpha-model", base_url="https://provider.example/v1",
            auth_kind="api_key_env", credential_reference="ALPHA_KEY", timeout_seconds=10.0,
            max_retries=0, pi_provider="alpha", compatibility_profile="generic",
            descriptor_version="fixture-1", public_headers={}, field_sources={}, supports_tools=True,
        ),
        secret=SecretValue("secret"),
    )
    paths = RuntimePaths(
        command=command, project_pi_dir=tmp_path / "pi", session_dir=tmp_path / "session",
        workspace=tmp_path, domain_search_path=Path("/opt/domain/bin"),
        runtime_descriptor_path=tmp_path / "descriptor.json", binding_id="alpha",
        tool_catalog_path=tmp_path / "catalog.json", guide_index_path=tmp_path / "guides.json",
    )

    environment = build_pi_environment(resolved, paths, base_environment={"PATH": "/usr/bin"})

    assert environment["CAPABILITY_AGENT_RUNTIME_DESCRIPTOR"].endswith("descriptor.json")
    assert "CAPABILITY_AGENT_TOOL_CATALOG" not in environment
    assert "CAPABILITY_AGENT_GUIDE_INDEX" not in environment


def test_environment_rejects_credentials_that_overwrite_runtime_channels(
    tmp_path: Path,
) -> None:
    command = PiCommand(
        argv=("pi",),
        identity=PiRuntimeIdentity(
            path=Path("pi"),
            source="fixture",
            package_version="1.0.0",
            lock_sha256="lock",
        ),
    )
    resolved = ResolvedLLM(
        config=ResolvedLLMConfig(
            provider="alpha",
            model="alpha-model",
            base_url="https://provider.example/v1",
            auth_kind="api_key_env",
            credential_reference="PATH",
            timeout_seconds=10.0,
            max_retries=0,
            pi_provider="alpha",
            compatibility_profile="generic",
            descriptor_version="fixture-1",
            public_headers={},
            field_sources={},
            supports_tools=True,
        ),
        secret=SecretValue("secret"),
    )
    paths = RuntimePaths(
        command=command,
        project_pi_dir=tmp_path / "pi",
        session_dir=tmp_path / "session",
        workspace=tmp_path,
    )

    with pytest.raises(ValueError, match="credential environment variable"):
        build_pi_environment(resolved, paths, base_environment={"PATH": "/usr/bin"})


def test_generic_pi_launch_disables_ambient_extensions(tmp_path: Path) -> None:
    command = PiCommand(
        argv=("pi",),
        identity=PiRuntimeIdentity(
            path=Path("pi"),
            source="fixture",
            package_version="1.0.0",
            lock_sha256="lock",
        ),
    )
    resolved = ResolvedLLM(
        config=ResolvedLLMConfig(
            provider="alpha",
            model="alpha-model",
            base_url="https://provider.example/v1",
            auth_kind="pi_oauth",
            credential_reference="profile",
            timeout_seconds=10.0,
            max_retries=0,
            pi_provider="alpha",
            compatibility_profile="generic",
            descriptor_version="fixture-1",
            public_headers={},
            field_sources={},
            supports_tools=True,
        )
    )
    paths = RuntimePaths(
        command=command,
        project_pi_dir=tmp_path / "pi",
        session_dir=tmp_path / "session",
        workspace=tmp_path,
    )

    assert "--no-extensions" in build_pi_launch(resolved, paths).argv
