from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path

import pytest

from capability_agent import (
    ApplicationConfigurationError,
    ApplicationProfile,
    CredentialScope,
    DomainProvisioningError,
    DomainRegistrationError,
    DomainRegistry,
    PolicyConflictError,
    prepare_application,
)


@dataclass(frozen=True)
class CredentialLease:
    scope_id: str
    credentials: Mapping[str, str]


class EmptyCredentialBroker:
    def __init__(self) -> None:
        self.calls: list[tuple[str, CredentialScope]] = []

    def issue(
        self, *, binding_id: str, scope: CredentialScope
    ) -> CredentialLease:
        self.calls.append((binding_id, scope))
        return CredentialLease(scope_id=scope.scope_id, credentials={})


class StaticCredentialBroker(EmptyCredentialBroker):
    def __init__(self, lease: CredentialLease) -> None:
        super().__init__()
        self.lease = lease

    def issue(
        self, *, binding_id: str, scope: CredentialScope
    ) -> CredentialLease:
        self.calls.append((binding_id, scope))
        return self.lease


@dataclass(frozen=True)
class Policy:
    fragment: str

    def load(self) -> str:
        return self.fragment


def _registry_for(profile: ApplicationProfile) -> DomainRegistry:
    domain_profile = profile.domains[0].profile
    registry = DomainRegistry()
    registry.register(
        domain_profile.manifest.domain_id,
        domain_profile.manifest.version,
        lambda: domain_profile,
    )
    return registry


def _unsafe_domains(
    profile: ApplicationProfile, domains: tuple[object, ...]
) -> ApplicationProfile:
    object.__setattr__(profile, "domains", domains)
    return profile


def test_prepare_application_resolves_only_explicit_registration(
    complete_profile: ApplicationProfile, tmp_path: Path
) -> None:
    registered_profile = replace(
        complete_profile.domains[0].profile,
        tool_description_builder=lambda document: str(document["purpose"]),
    )
    registry = DomainRegistry()
    registry.register(
        "fixture-domain",
        "1.0.0",
        lambda: registered_profile,
    )

    prepared = prepare_application(
        complete_profile,
        registry=registry,
        workspace=tmp_path / "run",
        credentials=EmptyCredentialBroker(),
    )

    assert tuple(prepared.bindings) == ("fixture",)
    assert prepared.bindings["fixture"].binding.profile is registered_profile
    assert prepared.profile.domains[0].profile is registered_profile
    assert prepared.bindings["fixture"].runtime.executor.calls == [
        ("environment.describe", {})
    ]
    assert prepared.bindings["fixture"].runtime.tool_catalog_path == (
        tmp_path / "run/domains/fixture/tool-catalog.json"
    )


def test_prepare_application_rejects_unregistered_domain(
    complete_profile: ApplicationProfile, tmp_path: Path
) -> None:
    with pytest.raises(DomainRegistrationError, match="not registered"):
        prepare_application(
            complete_profile,
            registry=DomainRegistry(),
            workspace=tmp_path / "run",
            credentials=EmptyCredentialBroker(),
        )


def test_prepare_application_rejects_version_mismatch(
    complete_profile: ApplicationProfile, tmp_path: Path
) -> None:
    registry = DomainRegistry()
    registry.register(
        "fixture-domain",
        "2.0.0",
        lambda: complete_profile.domains[0].profile,
    )

    with pytest.raises(DomainRegistrationError, match="not registered"):
        prepare_application(
            complete_profile,
            registry=registry,
            workspace=tmp_path / "run",
            credentials=EmptyCredentialBroker(),
        )


def test_prepare_application_rejects_wrong_factory_manifest(
    complete_profile: ApplicationProfile, tmp_path: Path
) -> None:
    registry = DomainRegistry()
    registry.register(
        "fixture-domain",
        "1.0.0",
        lambda: replace(
            complete_profile.domains[0].profile,
            manifest=replace(
                complete_profile.domains[0].profile.manifest,
                domain_id="different-domain",
            ),
        ),
    )

    with pytest.raises(DomainRegistrationError, match="manifest does not match"):
        prepare_application(
            complete_profile,
            registry=registry,
            workspace=tmp_path / "run",
            credentials=EmptyCredentialBroker(),
        )


def test_prepare_application_rejects_multiple_bindings_before_preparation(
    complete_profile: ApplicationProfile, tmp_path: Path
) -> None:
    binding = complete_profile.domains[0]
    second = replace(binding, binding_id="second", tool_namespace="second_")
    provisioner = binding.profile.provisioner
    assert provisioner is not None
    profile = _unsafe_domains(complete_profile, (second, binding))

    with pytest.raises(ApplicationConfigurationError, match="exactly one"):
        prepare_application(
            profile,
            registry=_registry_for(profile),
            workspace=tmp_path / "run",
            credentials=EmptyCredentialBroker(),
        )

    assert provisioner.calls == []


def test_provisioner_failure_occurs_before_runtime_probe(
    complete_profile: ApplicationProfile, tmp_path: Path
) -> None:
    binding = complete_profile.domains[0]
    provisioner = binding.profile.provisioner
    assert provisioner is not None
    provisioner.failure = RuntimeError("endpoint unavailable")

    with pytest.raises(DomainProvisioningError, match="endpoint unavailable"):
        prepare_application(
            complete_profile,
            registry=_registry_for(complete_profile),
            workspace=tmp_path / "run",
            credentials=EmptyCredentialBroker(),
        )

    assert provisioner.endpoint.executor.calls == []


def test_credential_scope_mismatch_aborts_before_provisioning(
    complete_profile: ApplicationProfile, tmp_path: Path
) -> None:
    binding = complete_profile.domains[0]
    provisioner = binding.profile.provisioner
    assert provisioner is not None
    broker = StaticCredentialBroker(
        CredentialLease(scope_id="another-scope", credentials={})
    )

    with pytest.raises(DomainProvisioningError, match="credential scope"):
        prepare_application(
            complete_profile,
            registry=_registry_for(complete_profile),
            workspace=tmp_path / "run",
            credentials=broker,
        )

    assert provisioner.calls == []


@pytest.mark.parametrize(
    ("credential_names", "lease_credentials"),
    [(("token",), {}), ((), {"token": "unexpected"})],
)
def test_credential_names_must_match_the_binding_scope(
    complete_profile: ApplicationProfile,
    tmp_path: Path,
    credential_names: tuple[str, ...],
    lease_credentials: Mapping[str, str],
) -> None:
    binding = complete_profile.domains[0]
    scoped_binding = replace(
        binding,
        credential_scope=replace(
            binding.credential_scope, credential_names=credential_names
        ),
    )
    profile = replace(complete_profile, domains=(scoped_binding,))
    provisioner = scoped_binding.profile.provisioner
    assert provisioner is not None
    broker = StaticCredentialBroker(
        CredentialLease(
            scope_id=scoped_binding.credential_scope.scope_id,
            credentials=lease_credentials,
        )
    )

    with pytest.raises(DomainProvisioningError, match="credential names"):
        prepare_application(
            profile,
            registry=_registry_for(profile),
            workspace=tmp_path / "run",
            credentials=broker,
        )

    assert provisioner.calls == []


def test_secret_bearing_endpoint_metadata_is_rejected_and_closed(
    complete_profile: ApplicationProfile, tmp_path: Path
) -> None:
    binding = complete_profile.domains[0]
    scoped_binding = replace(
        binding,
        credential_scope=replace(
            binding.credential_scope, credential_names=("token",)
        ),
    )
    profile = replace(complete_profile, domains=(scoped_binding,))
    provisioner = scoped_binding.profile.provisioner
    assert provisioner is not None
    provisioner.endpoint.metadata = {"transport": "fixture", "token": "secret"}
    broker = StaticCredentialBroker(
        CredentialLease(scope_id="isolated", credentials={"token": "secret"})
    )

    with pytest.raises(DomainProvisioningError, match="credential"):
        prepare_application(
            profile,
            registry=_registry_for(profile),
            workspace=tmp_path / "run",
            credentials=broker,
        )

    assert provisioner.endpoint.closed is True
    assert provisioner.endpoint.executor.calls == []


def test_sensitive_endpoint_metadata_is_rejected_without_a_domain_credential(
    complete_profile: ApplicationProfile, tmp_path: Path
) -> None:
    provisioner = complete_profile.domains[0].profile.provisioner
    assert provisioner is not None
    provisioner.endpoint.metadata = {
        "transport": "fixture",
        "api_key": "must-not-be-published",
    }

    with pytest.raises(DomainProvisioningError, match="credential"):
        prepare_application(
            complete_profile,
            registry=_registry_for(complete_profile),
            workspace=tmp_path / "run",
            credentials=EmptyCredentialBroker(),
        )

    assert provisioner.endpoint.closed is True
    assert provisioner.endpoint.executor.calls == []


def test_secret_bearing_runtime_result_is_rejected_and_closed(
    complete_profile: ApplicationProfile, tmp_path: Path
) -> None:
    binding = complete_profile.domains[0]
    scoped_binding = replace(
        binding,
        credential_scope=replace(
            binding.credential_scope, credential_names=("token",)
        ),
    )
    profile = replace(complete_profile, domains=(scoped_binding,))
    provisioner = scoped_binding.profile.provisioner
    assert provisioner is not None
    provisioner.endpoint.executor.environment["diagnostic"] = "Bearer secret"
    broker = StaticCredentialBroker(
        CredentialLease(scope_id="isolated", credentials={"token": "secret"})
    )

    with pytest.raises(DomainProvisioningError, match="credential"):
        prepare_application(
            profile,
            registry=_registry_for(profile),
            workspace=tmp_path / "run",
            credentials=broker,
        )

    assert provisioner.endpoint.closed is True


def test_secret_bearing_capability_descriptor_is_rejected_before_runtime_probe(
    complete_profile: ApplicationProfile, tmp_path: Path
) -> None:
    binding = complete_profile.domains[0]
    scoped_binding = replace(
        binding,
        credential_scope=replace(
            binding.credential_scope, credential_names=("token",)
        ),
    )
    profile = replace(complete_profile, domains=(scoped_binding,))
    provisioner = scoped_binding.profile.provisioner
    assert provisioner is not None
    contract_path = scoped_binding.profile.manifest.capability_contract_root / (
        "asset.list.json"
    )
    contract = contract_path.read_text(encoding="utf-8").replace(
        "List versioned inventory assets.",
        "credential secret must not be published",
    )
    contract_path.write_text(contract, encoding="utf-8")
    broker = StaticCredentialBroker(
        CredentialLease(scope_id="isolated", credentials={"token": "secret"})
    )

    with pytest.raises(DomainProvisioningError, match="credential"):
        prepare_application(
            profile,
            registry=_registry_for(profile),
            workspace=tmp_path / "run",
            credentials=broker,
        )

    assert provisioner.endpoint.closed is True
    assert provisioner.endpoint.executor.calls == []


@pytest.mark.parametrize("source", ["application", "domain", "between"])
def test_policy_conflicts_abort_before_provisioning(
    complete_profile: ApplicationProfile, tmp_path: Path, source: str
) -> None:
    binding = complete_profile.domains[0]
    if source == "application":
        profile = replace(
            complete_profile,
            application_policy=Policy("allow: generic-tools"),
        )
    elif source == "domain":
        domain_profile = replace(
            binding.profile,
            policy_provider=Policy("allow: arbitrary-subprocess"),
        )
        profile = replace(
            complete_profile,
            domains=(replace(binding, profile=domain_profile),),
        )
    else:
        domain_profile = replace(
            binding.profile,
            policy_provider=Policy("deny: shared-records"),
        )
        profile = replace(
            complete_profile,
            application_policy=Policy("allow: shared-records"),
            domains=(replace(binding, profile=domain_profile),),
        )
    provisioner = profile.domains[0].profile.provisioner
    assert provisioner is not None

    with pytest.raises(PolicyConflictError, match="policy conflict"):
        prepare_application(
            profile,
            registry=_registry_for(profile),
            workspace=tmp_path / "run",
            credentials=EmptyCredentialBroker(),
        )

    assert provisioner.calls == []


def test_cross_domain_sharing_is_denied_before_provisioning(
    complete_profile: ApplicationProfile, tmp_path: Path
) -> None:
    binding = complete_profile.domains[0]
    profile = replace(
        complete_profile,
        domains=(
            replace(
                binding,
                sharing_policy=replace(binding.sharing_policy, mode="allow"),
            ),
        ),
    )
    provisioner = binding.profile.provisioner
    assert provisioner is not None

    with pytest.raises(PolicyConflictError, match="sharing"):
        prepare_application(
            profile,
            registry=_registry_for(profile),
            workspace=tmp_path / "run",
            credentials=EmptyCredentialBroker(),
        )

    assert provisioner.calls == []


def test_post_provision_runtime_failure_closes_endpoint(
    complete_profile: ApplicationProfile, tmp_path: Path
) -> None:
    binding = complete_profile.domains[0]
    provisioner = binding.profile.provisioner
    assert provisioner is not None
    provisioner.endpoint.executor.environment["protocol_version"] = "wrong"

    with pytest.raises(Exception, match="protocol_version"):
        prepare_application(
            complete_profile,
            registry=_registry_for(complete_profile),
            workspace=tmp_path / "run",
            credentials=EmptyCredentialBroker(),
        )

    assert provisioner.endpoint.closed is True
