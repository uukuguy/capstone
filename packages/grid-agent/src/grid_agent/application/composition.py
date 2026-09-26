"""Grid-agent application composition and generic entry points."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Protocol, cast

from capstone_agent.application import build_application

from capability_agent.application import (
    AgentApplication,
    ApplicationOutcome,
    ApplicationRequest,
    ApplicationWorkspace,
    PreparedApplication,
    PreparedDomainRuntime,
    prepare_application,
    prepare_domain_runtime,
)
from capability_agent.application.errors import ApplicationConfigurationError
from capability_agent.application.composition import CredentialBroker
from capability_agent.application.profile import ApplicationProfile
from capability_agent.runtime.catalog import ProviderCatalog
from capability_agent.application.runtime_protocols import (
    PreparedApplicationRuntime,
    LegacyPromptSession,
    ProviderFactory,
    ProviderSession,
)
from capability_agent.runtime.environment import RuntimeHost
from capability_agent.runtime.extension import ExtensionSpec
from capability_agent.runtime.models import CliLLMOptions

from grid_agent.application.registry import (
    ApplicationRegistry,
    build_trusted_application_registry,
)
from grid_agent.application.paths import ProjectPaths


def build_generic_application(
    application_id: str,
    *,
    version: str | None = None,
    registry: ApplicationRegistry | None = None,
    prepared_application: PreparedApplicationRuntime | None = None,
    provider: ProviderSession | LegacyPromptSession | str | None = None,
    provider_factory: ProviderFactory | None = None,
    credentials: CredentialBroker | None = None,
    workspace: ApplicationWorkspace | None = None,
    workspace_root: Path | None = None,
    run_id: str | None = None,
    provider_catalog: ProviderCatalog | None = None,
    cli_options: CliLLMOptions | None = None,
    environment: Mapping[str, str] | None = None,
    runtime_host: RuntimeHost | None = None,
    **application_options: Any,
) -> AgentApplication:
    """Build a generic Kernel application from the trusted registry.

    The helper accepts prepared/injected objects for deterministic acceptance
    tests.  The normal path prepares the registered profile with its own
    explicit Domain Pack binding and never selects a domain by inference.
    """

    return build_application(
        application_id, version=version,
        registry=registry or build_trusted_application_registry(),
        prepared_application=prepared_application,
        provider=provider, provider_factory=provider_factory,
        credentials=credentials, workspace=workspace,
        workspace_root=workspace_root, run_id=run_id,
        provider_catalog=provider_catalog, cli_options=cli_options,
        environment=environment, runtime_host=runtime_host,
        runtime_host_factory=_build_runtime_host,
        **application_options,
    )


def run_generic_application(
    application_id: str,
    questions: Sequence[str],
    *,
    application: AgentApplication | object | None = None,
    **application_options: Any,
) -> ApplicationOutcome:
    """Run ordered questions through ``AgentApplication`` without compatibility."""

    options = dict(application_options)
    provider_name = options.get("provider")
    model_name = options.get("model")
    if isinstance(provider_name, str) or isinstance(model_name, str):
        existing = options.get("cli_options")
        if existing is not None and not isinstance(existing, CliLLMOptions):
            raise TypeError("cli_options must be a CliLLMOptions value")
        options["cli_options"] = CliLLMOptions(
            provider=provider_name if isinstance(provider_name, str) else None,
            model=model_name if isinstance(model_name, str) else None,
            base_url=existing.base_url if isinstance(existing, CliLLMOptions) else None,
            api_key_env=existing.api_key_env if isinstance(existing, CliLLMOptions) else None,
            timeout_seconds=existing.timeout_seconds if isinstance(existing, CliLLMOptions) else None,
            max_retries=existing.max_retries if isinstance(existing, CliLLMOptions) else None,
        )
    options.pop("provider", None)
    options.pop("model", None)
    runner = application or build_generic_application(
        application_id,
        **options,
    )
    if not callable(getattr(runner, "run", None)):
        raise TypeError("generic application must provide run()")
    profile_application_id = getattr(
        getattr(getattr(runner, "profile", None), "manifest", None),
        "application_id",
        None,
    )
    if profile_application_id is not None and profile_application_id != application_id:
        raise ApplicationConfigurationError(
            "generic application identity does not match its selected profile"
        )
    run_id = options.get("run_id")
    request = ApplicationRequest(
        application_id=application_id,
        questions=tuple(questions),
        run_id=run_id if isinstance(run_id, str) else None,
    )
    outcome = cast(_RunnableApplication, runner).run(request)
    if not isinstance(outcome, ApplicationOutcome):
        raise TypeError("generic application returned an invalid outcome")
    return outcome


class _RunnableApplication(Protocol):
    profile: object

    def run(self, request: ApplicationRequest) -> ApplicationOutcome: ...


def _build_runtime_host(
    profile: ApplicationProfile | None,
    environment: Mapping[str, str] | None,
) -> RuntimeHost:
    """Resolve product-owned Pi assets before constructing the generic runner."""

    if profile is None:
        raise ApplicationConfigurationError("generic runtime profile is unavailable")
    if not profile.domains:
        raise ApplicationConfigurationError("generic runtime profile has no domain binding")
    project_paths = ProjectPaths.from_root(Path.cwd())
    runtime_environment = dict(os.environ if environment is None else environment)
    PiExtensionLocator, PiRuntimeLock, PiRuntimeLocator = _runtime_host_dependencies()
    runtime_lock = PiRuntimeLock.load(project_paths.runtime_lock)
    command = PiRuntimeLocator(
        project_paths.pi_runtime_dir,
        runtime_environment,
        runtime_lock=runtime_lock,
    ).resolve()
    extension_path = PiExtensionLocator(
        project_paths.root,
        spec=ExtensionSpec(
            package_name="@capability-agent/pi-tools",
            package_version="0.1.0",
            candidates=(Path("packages/pi-capability-tools"),),
        ),
    ).resolve()
    manifest = profile.domains[0].profile.manifest
    return RuntimeHost(
        command=command,
        project_pi_dir=project_paths.pi_agent_dir,
        extension_path=extension_path,
        system_policy_path=manifest.system_policy_path,
    )


def _runtime_host_dependencies() -> tuple[type, type, type]:
    """Load generic extension and product runtime adapters lazily."""

    from capability_agent.runtime.extension import PiExtensionLocator
    from grid_agent.runtime.lock import PiRuntimeLock
    from grid_agent.runtime.locator import PiRuntimeLocator

    return PiExtensionLocator, PiRuntimeLock, PiRuntimeLocator


__all__ = [
    "PreparedApplication",
    "PreparedDomainRuntime",
    "build_generic_application",
    "prepare_application",
    "prepare_domain_runtime",
    "run_generic_application",
]
