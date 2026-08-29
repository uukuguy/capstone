from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from types import MappingProxyType
from typing import Protocol

from capability_agent.application.errors import (
    ApplicationConfigurationError,
    DomainProvisioningError,
    PolicyConflictError,
)
from capability_agent.application.profile import (
    ApplicationProfile,
    CredentialScope,
    DomainBinding,
)
from capability_agent.application.registry import DomainRegistry
from capability_agent.domain.authority import ArtifactAuthority
from capability_agent.domain.execution import CapabilityExecutor
from capability_agent.domain.profile import DomainRuntimeProfile
from capability_agent.domain.provisioning import CredentialLease, PreparedDomainEndpoint
from capability_agent.tools.catalog import ToolCatalog
from capability_agent.tools.guide import GuideIndex


_KERNEL_POLICY = "deny: arbitrary-subprocess, generic-file-access, generic-tools"
_SENSITIVE_FIELDS = frozenset(
    {
        "access_token",
        "api_key",
        "apikey",
        "auth_token",
        "authorization",
        "credential",
        "credentials",
        "password",
        "secret",
        "token",
    }
)


class CredentialBroker(Protocol):
    def issue(
        self, *, binding_id: str, scope: CredentialScope
    ) -> CredentialLease: ...


@dataclass(frozen=True, slots=True)
class PreparedDomainRuntime:
    profile: DomainRuntimeProfile
    executor: CapabilityExecutor
    authority: ArtifactAuthority
    environment_description: dict[str, object]
    capability_documents: tuple[dict[str, object], ...]
    tool_catalog_path: Path
    guide_index_path: Path


@dataclass(frozen=True, slots=True)
class PreparedBinding:
    binding: DomainBinding
    endpoint: PreparedDomainEndpoint
    runtime: PreparedDomainRuntime


@dataclass(frozen=True, slots=True)
class PreparedApplication:
    profile: ApplicationProfile
    bindings: Mapping[str, PreparedBinding]


def prepare_domain_runtime(
    profile: DomainRuntimeProfile,
    *,
    executable: Path,
    workspace: Path,
    tool_catalog_path: Path,
    guide_index_path: Path,
    timeout_seconds: float = 60.0,
) -> PreparedDomainRuntime:
    """Materialize the selected domain profile for one workspace."""
    capability_documents = _load_domain_resources(profile)
    executor = profile.create_executor(executable, workspace, timeout_seconds)
    return _materialize_domain_runtime(
        profile,
        executor=executor,
        capability_documents=capability_documents,
        workspace=workspace,
        tool_catalog_path=tool_catalog_path,
        guide_index_path=guide_index_path,
    )


def prepare_application(
    profile: ApplicationProfile,
    *,
    registry: DomainRegistry,
    workspace: Path,
    credentials: CredentialBroker,
) -> PreparedApplication:
    """Prepare explicitly registered bindings without starting a model provider."""
    _validate_application_profile(profile)
    resolved = tuple(
        registry.resolve_binding(binding)
        for binding in sorted(profile.domains, key=lambda item: item.binding_id)
    )
    for binding in resolved:
        _validate_complete_binding(binding)
    _validate_policy(profile, resolved)

    leases = tuple(
        (binding, _issue_credential_lease(credentials, binding))
        for binding in resolved
    )
    endpoints: list[PreparedDomainEndpoint] = []
    prepared: dict[str, PreparedBinding] = {}
    try:
        for binding, lease in leases:
            endpoint = _prepare_endpoint(binding, workspace, lease)
            endpoints.append(endpoint)
            _reject_credential_leak(
                endpoint.metadata,
                lease,
                location="endpoint metadata",
            )
            binding_workspace = workspace / "domains" / binding.binding_id
            capability_documents = _load_domain_resources(
                binding.profile,
                credential_lease=lease,
            )
            runtime = _materialize_domain_runtime(
                binding.profile,
                executor=endpoint.executor,
                capability_documents=capability_documents,
                workspace=binding_workspace,
                tool_catalog_path=binding_workspace / "tool-catalog.json",
                guide_index_path=binding_workspace / "guide-index.json",
                credential_lease=lease,
            )
            prepared[binding.binding_id] = PreparedBinding(
                binding=binding,
                endpoint=endpoint,
                runtime=runtime,
            )
    except BaseException:
        for endpoint in reversed(endpoints):
            endpoint.close()
        raise
    return PreparedApplication(
        profile=replace(profile, domains=resolved),
        bindings=MappingProxyType(prepared),
    )


def _materialize_domain_runtime(
    profile: DomainRuntimeProfile,
    *,
    executor: CapabilityExecutor,
    capability_documents: tuple[dict[str, object], ...],
    workspace: Path,
    tool_catalog_path: Path,
    guide_index_path: Path,
    credential_lease: CredentialLease | None = None,
) -> PreparedDomainRuntime:
    environment_description = executor.invoke("environment.describe", {})
    if credential_lease is not None:
        _reject_credential_leak(
            environment_description,
            credential_lease,
            location="runtime result",
        )
    profile.manifest.assert_environment_compatible(environment_description)
    ToolCatalog.from_environment(
        capability_documents,
        environment_description,
        tool_name_prefix=profile.manifest.tool_name_prefix,
        protocol=_schema_id_from_prefix(
            profile.manifest.tool_name_prefix, "tool-catalog"
        ),
        description_builder=profile.tool_description_builder,
    ).materialize(tool_catalog_path)
    GuideIndex.load(
        profile.manifest.guide_root,
        protocol=_schema_id_from_protocol(profile.manifest.protocol, "guide-index"),
    ).materialize(guide_index_path)
    authority = profile.create_authority(workspace)
    return PreparedDomainRuntime(
        profile=profile,
        executor=executor,
        authority=authority,
        environment_description=environment_description,
        capability_documents=capability_documents,
        tool_catalog_path=tool_catalog_path,
        guide_index_path=guide_index_path,
    )


def _load_domain_resources(
    profile: DomainRuntimeProfile,
    *,
    credential_lease: CredentialLease | None = None,
) -> tuple[dict[str, object], ...]:
    profile.manifest.assert_resources_present()
    capability_documents = profile.contract_source.load()
    if credential_lease is not None:
        _reject_credential_leak(
            capability_documents,
            credential_lease,
            location="capability descriptors",
        )
    return capability_documents


def _validate_application_profile(profile: ApplicationProfile) -> None:
    domains = profile.domains
    if len(domains) != 1:
        raise ApplicationConfigurationError(
            "application profile requires exactly one domain binding"
        )
    binding_ids = tuple(binding.binding_id for binding in domains)
    if len(set(binding_ids)) != len(binding_ids):
        raise ApplicationConfigurationError("duplicate binding namespace")
    tool_namespaces = tuple(binding.tool_namespace for binding in domains)
    if len(set(tool_namespaces)) != len(tool_namespaces):
        raise ApplicationConfigurationError("duplicate tool namespace")
    for binding in domains:
        _validate_complete_binding(binding)


def _validate_complete_binding(binding: DomainBinding) -> None:
    missing = binding.profile.missing_application_components()
    if missing:
        raise ApplicationConfigurationError(
            f"domain binding {binding.binding_id!r} has missing application "
            f"components: {', '.join(missing)}"
        )


def _validate_policy(
    profile: ApplicationProfile, bindings: tuple[DomainBinding, ...]
) -> None:
    fragments = [_KERNEL_POLICY, profile.application_policy.load()]
    for binding in bindings:
        if binding.sharing_policy.mode != "deny":
            raise PolicyConflictError(
                f"binding {binding.binding_id!r} sharing policy conflicts "
                "with deny-by-default application preparation"
            )
        provider = binding.profile.policy_provider
        assert provider is not None
        fragments.append(provider.load())
    fragments.append("deny: cross-domain-sharing")

    allowed: set[str] = set()
    denied: set[str] = set()
    for fragment in fragments:
        if not isinstance(fragment, str):
            raise PolicyConflictError("policy conflict: fragment must be text")
        fragment_allowed, fragment_denied = _policy_directives(fragment)
        conflict = (allowed | fragment_allowed) & (denied | fragment_denied)
        if conflict:
            raise PolicyConflictError(
                "policy conflict: " + ", ".join(sorted(conflict))
            )
        allowed.update(fragment_allowed)
        denied.update(fragment_denied)


def _policy_directives(fragment: str) -> tuple[set[str], set[str]]:
    allowed: set[str] = set()
    denied: set[str] = set()
    for line in fragment.splitlines():
        directive, separator, values = line.partition(":")
        if not separator:
            continue
        targets = {
            value.strip().casefold()
            for value in values.split(",")
            if value.strip()
        }
        if directive.strip().casefold() == "allow":
            allowed.update(targets)
        elif directive.strip().casefold() == "deny":
            denied.update(targets)
    return allowed, denied


def _issue_credential_lease(
    broker: CredentialBroker, binding: DomainBinding
) -> CredentialLease:
    try:
        lease = broker.issue(
            binding_id=binding.binding_id,
            scope=binding.credential_scope,
        )
        if lease.scope_id != binding.credential_scope.scope_id:
            raise DomainProvisioningError(
                f"binding {binding.binding_id!r} credential scope does not match"
            )
        expected = set(binding.credential_scope.credential_names)
        actual = set(lease.credentials)
        if actual != expected:
            raise DomainProvisioningError(
                f"binding {binding.binding_id!r} credential names do not match"
            )
        if any(not isinstance(value, str) for value in lease.credentials.values()):
            raise DomainProvisioningError(
                f"binding {binding.binding_id!r} credentials must be text"
            )
        return lease
    except DomainProvisioningError:
        raise
    except Exception as exc:
        raise DomainProvisioningError(
            f"binding {binding.binding_id!r} credential lease failed: {exc}"
        ) from exc


def _prepare_endpoint(
    binding: DomainBinding, workspace: Path, lease: CredentialLease
) -> PreparedDomainEndpoint:
    provisioner = binding.profile.provisioner
    assert provisioner is not None
    try:
        return provisioner.prepare(
            binding=binding,
            workspace=workspace / "domains" / binding.binding_id,
            credentials=lease,
        )
    except DomainProvisioningError:
        raise
    except Exception as exc:
        raise DomainProvisioningError(
            f"binding {binding.binding_id!r} provisioning failed: {exc}"
        ) from exc


def _reject_credential_leak(
    value: object,
    lease: CredentialLease,
    *,
    location: str,
) -> None:
    secret_values = {secret for secret in lease.credentials.values() if secret}
    credential_names = {
        name.casefold().replace("-", "_") for name in lease.credentials
    }
    stack = [value]
    seen: set[int] = set()
    while stack:
        item = stack.pop()
        if isinstance(item, str):
            if any(secret in item for secret in secret_values):
                raise DomainProvisioningError(
                    f"credential value leaked into {location}"
                )
            continue
        if isinstance(item, Mapping):
            identity = id(item)
            if identity in seen:
                continue
            seen.add(identity)
            for key, nested in item.items():
                normalized = str(key).casefold().replace("-", "_")
                if normalized in credential_names or normalized in _SENSITIVE_FIELDS:
                    raise DomainProvisioningError(
                        f"credential field leaked into {location}"
                    )
                stack.append(nested)
            continue
        if isinstance(item, (list, tuple, set, frozenset)):
            identity = id(item)
            if identity in seen:
                continue
            seen.add(identity)
            stack.extend(item)


def _schema_id_from_prefix(tool_name_prefix: str, suffix: str) -> str:
    namespace = tool_name_prefix.removesuffix("_").replace("_", "-")
    if not namespace or namespace == "tool":
        namespace = "capability"
    return f"{namespace}-{suffix}"


def _schema_id_from_protocol(protocol: str, suffix: str) -> str:
    namespace = protocol.split("-", 1)[0].replace("_", "-").replace(".", "-")
    if not namespace:
        namespace = "capability"
    return f"{namespace}-{suffix}"
