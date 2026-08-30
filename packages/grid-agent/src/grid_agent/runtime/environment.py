"""Legacy environment adapter for the generic Pi runtime environment.

The historical grid names remain at this boundary only.  Child-process
construction, allowlisting, credential handling, and runtime identity export
are implemented by :mod:`capability_agent.runtime.environment`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from capability_agent.runtime.environment import (
    PiLaunch,
    RuntimePaths as _RuntimePaths,
    build_pi_environment as _build_pi_environment,
    build_pi_launch as _build_pi_launch,
)
from capability_agent.runtime.models import ResolvedLLM
from grid_agent.runtime.lock import PiCommand


@dataclass(frozen=True)
class RuntimePaths:
    command: PiCommand
    project_pi_dir: Path
    session_dir: Path
    workspace: Path
    gridctl_dir: Path
    extension_path: Path
    tool_catalog_path: Path
    guide_index_path: Path
    system_policy_path: Path
    domain_runtime_descriptor_path: Path | None = None
    active_turn_path: Path | None = None
    analysis_context_view_path: Path | None = None
    trajectory_requests_path: Path | None = None
    trajectory_capture_state_path: Path | None = None
    trajectory_allowed_refs_path: Path | None = None
    trajectory_acks_path: Path | None = None


def build_pi_launch(
    resolved: ResolvedLLM,
    paths: RuntimePaths,
    *,
    base_environment: Mapping[str, str] | None = None,
) -> PiLaunch:
    launch = _build_pi_launch(
        resolved,
        _as_generic_paths(paths),
        base_environment=_legacy_base_environment(base_environment),
    )
    return PiLaunch(
        argv=_legacy_argv(launch.argv),
        environment=build_pi_environment(
            resolved,
            paths,
            base_environment=base_environment,
        ),
    )


def build_pi_environment(
    resolved: ResolvedLLM,
    paths: RuntimePaths,
    *,
    base_environment: Mapping[str, str] | None = None,
) -> dict[str, str]:
    environment = _build_pi_environment(
        resolved,
        _as_generic_paths(paths),
        base_environment=_legacy_base_environment(base_environment),
    )
    return _legacy_environment(environment, descriptor_mode=paths.domain_runtime_descriptor_path is not None)


def _as_generic_paths(paths: RuntimePaths) -> _RuntimePaths:
    _prepare_capture_directory(paths)
    return _RuntimePaths(
        command=paths.command,
        project_pi_dir=paths.project_pi_dir,
        session_dir=paths.session_dir,
        workspace=paths.workspace,
        domain_search_path=paths.gridctl_dir,
        extension_path=paths.extension_path,
        tool_catalog_path=paths.tool_catalog_path,
        guide_index_path=paths.guide_index_path,
        system_policy_path=paths.system_policy_path,
        runtime_descriptor_path=paths.domain_runtime_descriptor_path,
        active_turn_path=paths.active_turn_path,
        context_view_path=paths.analysis_context_view_path,
        trajectory_requests_path=paths.trajectory_requests_path,
        trajectory_capture_state_path=paths.trajectory_capture_state_path,
        trajectory_allowed_refs_path=paths.trajectory_allowed_refs_path,
        trajectory_acks_path=paths.trajectory_acks_path,
    )


def _legacy_base_environment(
    base_environment: Mapping[str, str] | None,
) -> dict[str, str]:
    source = dict(os.environ if base_environment is None else base_environment)
    if source.get("GRID_AGENT_PI_OFFLINE") == "1":
        source["CAPABILITY_AGENT_PI_OFFLINE"] = "1"
    return source


def _legacy_environment(
    environment: dict[str, str],
    *,
    descriptor_mode: bool,
) -> dict[str, str]:
    translated = dict(environment)
    if descriptor_mode:
        # Descriptor mode intentionally carries only the descriptor and generic
        # identity/credential data; path supplements are not authoritative.
        for key in (
            "CAPABILITY_AGENT_WORKSPACE",
            "CAPABILITY_AGENT_TOOL_CATALOG",
            "CAPABILITY_AGENT_GUIDE_INDEX",
            "CAPABILITY_AGENT_ACTIVE_TURN",
            "CAPABILITY_AGENT_CONTEXT_VIEW",
            "CAPABILITY_AGENT_TRAJECTORY_REQUESTS",
            "CAPABILITY_AGENT_TRAJECTORY_CAPTURE_STATE",
            "CAPABILITY_AGENT_TRAJECTORY_ALLOWED_REFS",
            "CAPABILITY_AGENT_TRAJECTORY_ACKS",
        ):
            translated.pop(key, None)
        return translated

    names = {
        "CAPABILITY_AGENT_WORKSPACE": "GRID_AGENT_WORKSPACE",
        "CAPABILITY_AGENT_TOOL_CATALOG": "GRID_AGENT_TOOL_CATALOG",
        "CAPABILITY_AGENT_GUIDE_INDEX": "GRID_AGENT_GUIDE_INDEX",
        "CAPABILITY_AGENT_ACTIVE_TURN": "GRID_AGENT_ACTIVE_TURN",
        "CAPABILITY_AGENT_CONTEXT_VIEW": "GRID_AGENT_ANALYSIS_CONTEXT_VIEW",
        "CAPABILITY_AGENT_TRAJECTORY_REQUESTS": "GRID_AGENT_TRAJECTORY_REQUESTS",
        "CAPABILITY_AGENT_TRAJECTORY_CAPTURE_STATE": "GRID_AGENT_TRAJECTORY_CAPTURE_STATE",
        "CAPABILITY_AGENT_TRAJECTORY_ALLOWED_REFS": "GRID_AGENT_TRAJECTORY_ALLOWED_REFS",
        "CAPABILITY_AGENT_TRAJECTORY_ACKS": "GRID_AGENT_TRAJECTORY_ACKS",
        "CAPABILITY_AGENT_PI_CODING_AGENT_VERSION": "GRID_AGENT_PI_CODING_AGENT_VERSION",
        "CAPABILITY_AGENT_PI_AI_VERSION": "GRID_AGENT_PI_AI_VERSION",
        "CAPABILITY_AGENT_PI_SOURCE_COMMIT": "GRID_AGENT_PI_SOURCE_COMMIT",
        "CAPABILITY_AGENT_PI_PATCH_SET_SHA256": "GRID_AGENT_PI_PATCH_SET_SHA256",
    }
    for generic_name, legacy_name in names.items():
        value = translated.pop(generic_name, None)
        if value is not None:
            translated[legacy_name] = value
    if "CAPABILITY_AGENT_SECRET_ENV_NAMES" in translated:
        translated["GRID_AGENT_SECRET_ENV_NAMES"] = translated[
            "CAPABILITY_AGENT_SECRET_ENV_NAMES"
        ]
    return translated


def _legacy_argv(argv: tuple[str, ...]) -> tuple[str, ...]:
    # The generic launcher deliberately keeps extension policy explicit.  The
    # legacy Pi invocation also disabled ambient extensions, so retain that
    # safety flag at this compatibility boundary.
    if "--no-extensions" in argv:
        return argv
    insertion = argv.index("--no-skills") if "--no-skills" in argv else len(argv)
    return (*argv[:insertion], "--no-extensions", *argv[insertion:])


def _prepare_capture_directory(paths: RuntimePaths) -> None:
    values = (
        paths.trajectory_requests_path,
        paths.trajectory_capture_state_path,
        paths.trajectory_allowed_refs_path,
        paths.trajectory_acks_path,
    )
    if not all(value is not None for value in values):
        return
    path = paths.trajectory_acks_path
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
