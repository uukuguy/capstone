"""Reusable verified Pi runtime setup extracted from the grid application."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

from dotenv import dotenv_values
from capability_agent.runtime.environment import RuntimeHost
from capability_agent.runtime.extension import ExtensionSpec, PiExtensionLocator
from capability_agent.runtime.locator import PiRuntimeLocator
from capability_agent.runtime.lock import PiRuntimeLock


_LLM_ENV_ALIASES = {
    "GRID_AGENT_LLM_PROVIDER": "CAPABILITY_AGENT_LLM_PROVIDER",
    "GRID_AGENT_LLM_MODEL": "CAPABILITY_AGENT_LLM_MODEL",
    "GRID_AGENT_LLM_BASE_URL": "CAPABILITY_AGENT_LLM_BASE_URL",
    "GRID_AGENT_LLM_API_KEY_ENV": "CAPABILITY_AGENT_LLM_API_KEY_ENV",
    "GRID_AGENT_LLM_TIMEOUT_SECONDS": "CAPABILITY_AGENT_LLM_TIMEOUT_SECONDS",
    "GRID_AGENT_LLM_MAX_RETRIES": "CAPABILITY_AGENT_LLM_MAX_RETRIES",
}


def load_runtime_environment(
    repo_root: Path, environment: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Load the project .env layer and expose legacy LLM settings to Kernel."""

    root = Path(repo_root).resolve()
    dotenv_layer = {
        key: value
        for key, value in dotenv_values(root / ".env").items()
        if value is not None
    }
    merged = {**dotenv_layer, **dict(os.environ if environment is None else environment)}
    for source, target in _LLM_ENV_ALIASES.items():
        value = merged.get(source)
        if value is not None:
            merged[target] = value
    return merged


def build_runtime_host(
    repo_root: Path, profile: object, environment: Mapping[str, str] | None = None,
) -> RuntimeHost:
    """Resolve the existing pinned Pi assets for any registered application."""

    root = Path(repo_root).resolve()
    domains = getattr(profile, "domains", ())
    if not domains:
        raise ValueError("application profile has no domain binding")
    runtime_environment = load_runtime_environment(root, environment)
    runtime_lock = PiRuntimeLock.load(root / "configs/runtime/pi-runtime.lock.json")
    command = PiRuntimeLocator(
        root / ".grid-agent/runtime/pi", runtime_environment,
        runtime_lock=runtime_lock, command_env_name="GRID_AGENT_PI_COMMAND",
    ).resolve()
    extension = PiExtensionLocator(
        root,
        spec=ExtensionSpec(
            package_name="@capability-agent/pi-tools",
            package_version="0.1.0",
            candidates=(Path("packages/pi-capability-tools"),),
        ),
    ).resolve()
    manifest = domains[0].profile.manifest
    model_library_dir = runtime_environment.get("CAPSTONE_PYPSA_MODEL_LIBRARY_DIR")
    if not model_library_dir:
        model_library_dir = str(root / ".grid-agent/runtime/pypsa-models")
    return RuntimeHost(
        command=command,
        project_pi_dir=root / ".grid-agent/auth/pi",
        extension_path=extension,
        system_policy_path=manifest.system_policy_path,
        extra_environment={"CAPSTONE_PYPSA_MODEL_LIBRARY_DIR": model_library_dir},
    )
