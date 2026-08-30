"""Construct a minimal child environment and model transport command."""

from __future__ import annotations

import ipaddress
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence
from urllib.parse import urlparse

from capability_agent.runtime.lock import PiCommand
from capability_agent.runtime.models import ResolvedLLM


_PASSTHROUGH_ENVIRONMENT = frozenset(
    {
        "PATH",
        "HOME",
        "TMPDIR",
        "LANG",
        "LC_ALL",
        "SSL_CERT_FILE",
        "HTTPS_PROXY",
        "HTTP_PROXY",
        "NO_PROXY",
    }
)
_RUNTIME_ENVIRONMENT_NAMES = _PASSTHROUGH_ENVIRONMENT | frozenset(
    {
        "PI_CODING_AGENT_DIR",
        "PI_CODING_AGENT_SESSION_DIR",
        "PI_OFFLINE",
    }
)


@dataclass(frozen=True, slots=True)
class RuntimePaths:
    command: PiCommand
    project_pi_dir: Path
    session_dir: Path
    workspace: Path
    domain_search_path: Path | None = None
    extension_path: Path | None = None
    tool_catalog_path: Path | None = None
    guide_index_path: Path | None = None
    system_policy_path: Path | None = None
    runtime_descriptor_path: Path | None = None
    binding_id: str | None = None
    active_turn_path: Path | None = None
    context_view_path: Path | None = None
    trajectory_requests_path: Path | None = None
    trajectory_capture_state_path: Path | None = None
    trajectory_allowed_refs_path: Path | None = None
    trajectory_acks_path: Path | None = None
    extra_controller_values: Mapping[str, str] = field(default_factory=dict, repr=False)
    domain_search_paths: tuple[Path, ...] = ()

    def __post_init__(self) -> None:
        if self.domain_search_path is not None and self.domain_search_paths:
            raise ValueError("provide domain_search_path or domain_search_paths, not both")
        if self.domain_search_path is not None:
            object.__setattr__(self, "domain_search_paths", (Path(self.domain_search_path),))
        else:
            object.__setattr__(
                self, "domain_search_paths", tuple(Path(path) for path in self.domain_search_paths)
            )
        object.__setattr__(
            self, "extra_controller_values", dict(self.extra_controller_values)
        )


@dataclass(frozen=True, slots=True)
class PiLaunch:
    argv: tuple[str, ...]
    environment: dict[str, str]


def build_pi_launch(
    resolved: ResolvedLLM,
    paths: RuntimePaths,
    *,
    base_environment: Mapping[str, str] | None = None,
) -> PiLaunch:
    environment = build_pi_environment(
        resolved, paths, base_environment=base_environment
    )
    argv: list[str] = [
        *paths.command.argv,
        "--mode",
        "rpc",
        "--provider",
        resolved.config.pi_provider,
        "--model",
        resolved.config.model,
        "--session-dir",
        str(paths.session_dir),
        "--no-extensions",
        "--no-skills",
        "--no-prompt-templates",
        "--no-context-files",
        "--no-builtin-tools",
    ]
    if paths.system_policy_path is not None:
        argv.extend(("--system-prompt", str(paths.system_policy_path)))
    if paths.extension_path is not None:
        argv.extend(("--extension", str(paths.extension_path)))
    return PiLaunch(argv=tuple(argv), environment=environment)


def build_pi_environment(
    resolved: ResolvedLLM,
    paths: RuntimePaths,
    *,
    base_environment: Mapping[str, str] | None = None,
) -> dict[str, str]:
    source = dict(os.environ if base_environment is None else base_environment)
    environment = {
        key: value for key, value in source.items() if key in _PASSTHROUGH_ENVIRONMENT
    }
    _merge_loopback_no_proxy(environment, resolved.config.base_url)

    inherited_path = environment.get("PATH", "")
    search_entries = [str(path) for path in paths.domain_search_paths if str(path)]
    if inherited_path:
        search_entries.append(inherited_path)
    environment["PATH"] = os.pathsep.join(search_entries)
    environment["PI_CODING_AGENT_DIR"] = str(paths.project_pi_dir)
    environment["PI_CODING_AGENT_SESSION_DIR"] = str(paths.session_dir)
    identity = paths.command.identity
    if identity.pi_ai_version and identity.commit and identity.patches_sha256:
        environment["CAPABILITY_AGENT_PI_CODING_AGENT_VERSION"] = (
            identity.package_version
        )
        environment["CAPABILITY_AGENT_PI_AI_VERSION"] = identity.pi_ai_version
        environment["CAPABILITY_AGENT_PI_SOURCE_COMMIT"] = identity.commit
        environment["CAPABILITY_AGENT_PI_PATCH_SET_SHA256"] = identity.patches_sha256
    if source.get("CAPABILITY_AGENT_PI_OFFLINE") == "1":
        environment["PI_OFFLINE"] = "1"

    if paths.runtime_descriptor_path is not None:
        environment["CAPABILITY_AGENT_RUNTIME_DESCRIPTOR"] = str(
            paths.runtime_descriptor_path
        )
    else:
        _set_path(environment, "CAPABILITY_AGENT_WORKSPACE", paths.workspace)
        _set_path(environment, "CAPABILITY_AGENT_TOOL_CATALOG", paths.tool_catalog_path)
        _set_path(environment, "CAPABILITY_AGENT_GUIDE_INDEX", paths.guide_index_path)
        _set_path(environment, "CAPABILITY_AGENT_ACTIVE_TURN", paths.active_turn_path)
        _set_path(environment, "CAPABILITY_AGENT_CONTEXT_VIEW", paths.context_view_path)
        _set_path(
            environment,
            "CAPABILITY_AGENT_TRAJECTORY_REQUESTS",
            paths.trajectory_requests_path,
        )
        _set_path(
            environment,
            "CAPABILITY_AGENT_TRAJECTORY_CAPTURE_STATE",
            paths.trajectory_capture_state_path,
        )
        _set_path(
            environment,
            "CAPABILITY_AGENT_TRAJECTORY_ALLOWED_REFS",
            paths.trajectory_allowed_refs_path,
        )
        _set_path(
            environment,
            "CAPABILITY_AGENT_TRAJECTORY_ACKS",
            paths.trajectory_acks_path,
        )
    if paths.binding_id is not None:
        environment["CAPABILITY_AGENT_BINDING_ID"] = paths.binding_id

    for key, value in paths.extra_controller_values.items():
        if key.startswith("CAPABILITY_AGENT_") and key not in environment:
            environment[key] = value

    if resolved.secret is not None:
        credential_name = resolved.config.credential_reference
        if (
            credential_name in _RUNTIME_ENVIRONMENT_NAMES
            or credential_name.startswith("CAPABILITY_AGENT_")
        ):
            raise ValueError(
                "credential environment variable conflicts with a runtime channel"
            )
        environment[credential_name] = resolved.secret.value
        environment["CAPABILITY_AGENT_SECRET_ENV_NAMES"] = (
            credential_name
        )
    return environment


def _set_path(environment: dict[str, str], key: str, value: Path | None) -> None:
    if value is not None:
        environment[key] = str(value)


def _merge_loopback_no_proxy(environment: dict[str, str], base_url: str) -> None:
    hostname = urlparse(base_url).hostname
    if hostname is None or not _is_loopback_host(hostname):
        return
    entries = [
        entry.strip()
        for entry in environment.get("NO_PROXY", "").split(",")
        if entry.strip()
    ]
    if hostname.lower() not in {entry.lower() for entry in entries}:
        entries.append(hostname)
    environment["NO_PROXY"] = ",".join(entries)


def _is_loopback_host(hostname: str) -> bool:
    if hostname.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


def _prepare_owner_only_directory(path: Path | None) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)


__all__ = [
    "PiLaunch",
    "RuntimePaths",
    "build_pi_environment",
    "build_pi_launch",
]
