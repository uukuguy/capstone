from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from types import MappingProxyType
from typing import Protocol

from capability_agent.application.errors import (
    ApplicationConfigurationError,
    CapabilityTransportError,
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
_BINDING_ID = re.compile(r"^[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?$")
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


@dataclass(frozen=True, slots=True, repr=False)
class _CredentialSnapshot:
    scope_id: str
    credentials: Mapping[str, str]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "credentials",
            MappingProxyType(dict(self.credentials)),
        )


class _CredentialScreeningExecutor:
    __slots__ = ("_executor", "_lease")

    def __init__(
        self, executor: CapabilityExecutor, lease: CredentialLease
    ) -> None:
        self._executor = executor
        self._lease = lease

    def invoke(
        self, capability: str, arguments: dict[str, object]
    ) -> dict[str, object]:
        invocation_failed = False
        try:
            result = self._executor.invoke(capability, arguments)
        except Exception:
            invocation_failed = True
        if invocation_failed:
            raise CapabilityTransportError("capability transport failed")

        result_rejected = False
        result_screening_failed = False
        try:
            _reject_credential_leak(
                result,
                self._lease,
                location="runtime result",
            )
        except DomainProvisioningError:
            result_rejected = True
        except Exception:
            result_screening_failed = True
        if result_rejected:
            raise CapabilityTransportError(
                "credential-bearing capability result rejected"
            )
        if result_screening_failed:
            raise CapabilityTransportError("capability result screening failed")
        return result


class _PreparedEndpointView:
    __slots__ = ("_close", "_closed", "_executor", "_metadata")

    def __init__(
        self,
        endpoint: PreparedDomainEndpoint,
        executor: CapabilityExecutor,
        metadata: Mapping[str, object],
    ) -> None:
        self._close = endpoint.close
        self._closed = False
        self._executor = executor
        self._metadata = metadata

    @property
    def executor(self) -> CapabilityExecutor:
        return self._executor

    @property
    def metadata(self) -> Mapping[str, object]:
        return self._metadata

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        close_failed = False
        try:
            self._close()
        except Exception:
            close_failed = True
        if close_failed:
            raise DomainProvisioningError("prepared endpoint cleanup failed")


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
    binding_workspaces = _validate_application_profile(profile, workspace=workspace)
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
            binding_workspace = binding_workspaces[binding.binding_id]
            endpoint = _prepare_endpoint(binding, binding_workspace, lease)
            endpoints.append(endpoint)
            endpoint_metadata = _prepare_endpoint_metadata(endpoint, lease)
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
                endpoint=_PreparedEndpointView(
                    endpoint,
                    runtime.executor,
                    endpoint_metadata,
                ),
                runtime=runtime,
            )
    except BaseException:
        _close_prepared_endpoints(endpoints)
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
    runtime_executor: CapabilityExecutor = executor
    if credential_lease is not None:
        runtime_executor = _CredentialScreeningExecutor(
            executor,
            credential_lease,
        )
    environment_description = runtime_executor.invoke("environment.describe", {})
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
        executor=runtime_executor,
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


def _validate_application_profile(
    profile: ApplicationProfile, *, workspace: Path
) -> dict[str, Path]:
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
    return {
        binding.binding_id: _resolve_binding_workspace(
            workspace,
            binding.binding_id,
        )
        for binding in domains
    }


def _resolve_binding_workspace(workspace: Path, binding_id: str) -> Path:
    if not _BINDING_ID.fullmatch(binding_id):
        raise ApplicationConfigurationError(
            f"binding identifier {binding_id!r} is not portable"
        )
    try:
        workspace_root = workspace.resolve(strict=False)
        domains_path = workspace / "domains"
        domains_root = domains_path.resolve(strict=False)
        domains_root.relative_to(workspace_root)
        binding_workspace = (domains_path / binding_id).resolve(strict=False)
        binding_workspace.relative_to(domains_root)
    except (OSError, ValueError):
        raise ApplicationConfigurationError(
            f"binding {binding_id!r} workspace escapes the application workspace"
        ) from None
    return binding_workspace


def _validate_complete_binding(binding: DomainBinding) -> None:
    if binding.tool_namespace != binding.profile.manifest.tool_name_prefix:
        raise ApplicationConfigurationError(
            f"domain binding {binding.binding_id!r} tool namespace does not "
            "match its registered profile"
        )
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
) -> _CredentialSnapshot:
    lease_failed = False
    try:
        lease = broker.issue(
            binding_id=binding.binding_id,
            scope=binding.credential_scope,
        )
    except Exception:
        lease_failed = True
    if lease_failed:
        raise DomainProvisioningError(
            f"binding {binding.binding_id!r} credential lease failed"
        )
    snapshot_failed = False
    try:
        scope_id = lease.scope_id
        credential_values = dict(lease.credentials)
    except Exception:
        snapshot_failed = True
    if snapshot_failed:
        raise DomainProvisioningError(
            f"binding {binding.binding_id!r} credential lease failed"
        )
    if scope_id != binding.credential_scope.scope_id:
        raise DomainProvisioningError(
            f"binding {binding.binding_id!r} credential scope does not match"
        )
    expected = set(binding.credential_scope.credential_names)
    actual = set(credential_values)
    if actual != expected:
        raise DomainProvisioningError(
            f"binding {binding.binding_id!r} credential names do not match"
        )
    if any(not isinstance(value, str) for value in credential_values.values()):
        raise DomainProvisioningError(
            f"binding {binding.binding_id!r} credentials must be text"
        )
    return _CredentialSnapshot(scope_id, credential_values)


def _prepare_endpoint(
    binding: DomainBinding, workspace: Path, lease: CredentialLease
) -> PreparedDomainEndpoint:
    provisioner = binding.profile.provisioner
    assert provisioner is not None
    provisioning_failed = False
    try:
        endpoint = provisioner.prepare(
            binding=binding,
            workspace=workspace,
            credentials=lease,
        )
    except Exception:
        provisioning_failed = True
    if provisioning_failed:
        raise DomainProvisioningError(
            f"binding {binding.binding_id!r} provisioning failed"
        )
    return endpoint


def _close_prepared_endpoints(
    endpoints: list[PreparedDomainEndpoint] | tuple[PreparedDomainEndpoint, ...],
) -> None:
    for endpoint in reversed(endpoints):
        try:
            endpoint.close()
        except BaseException:
            continue


def _snapshot_endpoint_metadata(
    metadata: Mapping[str, object],
) -> Mapping[str, object]:
    snapshot = _freeze_metadata_value(metadata, active=set())
    if not isinstance(snapshot, Mapping):
        raise DomainProvisioningError("endpoint metadata is not a mapping")
    return snapshot


def _prepare_endpoint_metadata(
    endpoint: PreparedDomainEndpoint,
    lease: CredentialLease,
) -> Mapping[str, object]:
    metadata_failed = False
    try:
        metadata = _snapshot_endpoint_metadata(endpoint.metadata)
    except Exception:
        metadata_failed = True
    if metadata_failed:
        raise DomainProvisioningError("endpoint metadata preparation failed")

    metadata_rejected = False
    metadata_screening_failed = False
    try:
        _reject_credential_leak(
            metadata,
            lease,
            location="endpoint metadata",
        )
    except DomainProvisioningError:
        metadata_rejected = True
    except Exception:
        metadata_screening_failed = True
    if metadata_rejected:
        raise DomainProvisioningError(
            "credential-bearing endpoint metadata rejected"
        )
    if metadata_screening_failed:
        raise DomainProvisioningError("endpoint metadata screening failed")
    return metadata


def _freeze_metadata_value(value: object, *, active: set[int]) -> object:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Mapping):
        identity = id(value)
        if identity in active:
            raise DomainProvisioningError("endpoint metadata contains a cycle")
        active.add(identity)
        try:
            frozen: dict[str, object] = {}
            for key, nested in value.items():
                if not isinstance(key, str):
                    raise DomainProvisioningError(
                        "endpoint metadata keys must be text"
                    )
                frozen[key] = _freeze_metadata_value(nested, active=active)
            return MappingProxyType(frozen)
        finally:
            active.remove(identity)
    if isinstance(value, (list, tuple)):
        identity = id(value)
        if identity in active:
            raise DomainProvisioningError("endpoint metadata contains a cycle")
        active.add(identity)
        try:
            return tuple(
                _freeze_metadata_value(item, active=active) for item in value
            )
        finally:
            active.remove(identity)
    raise DomainProvisioningError("endpoint metadata value is not safely detachable")


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
