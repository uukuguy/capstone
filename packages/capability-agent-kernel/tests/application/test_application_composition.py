from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path

import pytest

from capability_agent import (
    ApplicationConfigurationError,
    ApplicationProfile,
    CapabilityTransportError,
    CredentialScope,
    DomainProvisioningError,
    DomainRegistrationError,
    DomainRegistry,
    PolicyConflictError,
    prepare_application,
)
from capability_agent.application import composition


@dataclass(frozen=True)
class CredentialLease:
    scope_id: str
    credentials: Mapping[str, str]


@dataclass
class MutableCredentialLease:
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


class FailingCredentialBroker(EmptyCredentialBroker):
    def __init__(self, failure: Exception) -> None:
        super().__init__()
        self.failure = failure

    def issue(
        self, *, binding_id: str, scope: CredentialScope
    ) -> CredentialLease:
        self.calls.append((binding_id, scope))
        raise self.failure


class PrefixContractSource:
    def __init__(self, delegate, old_prefix: str, new_prefix: str) -> None:
        self.delegate = delegate
        self.old_prefix = old_prefix
        self.new_prefix = new_prefix

    def load(self):
        return tuple(
            {
                **document,
                "tool_name": self.new_prefix
                + document["tool_name"].removeprefix(self.old_prefix),
            }
            for document in self.delegate.load()
        )


class CredentialMutatingProvisioner:
    def __init__(self, delegate) -> None:
        self.delegate = delegate
        self.mutation_blocked = False

    def prepare(self, *, binding, workspace, credentials):
        try:
            credentials.credentials["token"] = "provisioner-replacement"
        except TypeError:
            self.mutation_blocked = True
        return self.delegate.prepare(
            binding=binding,
            workspace=workspace,
            credentials=credentials,
        )


class ExplodingTextKey(str):
    def __new__(cls, value: str, secret: str):
        key = super().__new__(cls, value)
        key.secret = secret
        return key

    def __str__(self) -> str:
        raise RuntimeError(self.secret)


class HostileMapping(Mapping[object, object]):
    def __init__(self, failure_kind: str, secret: str) -> None:
        self.failure_kind = failure_kind
        self.secret = secret

    def __getitem__(self, key: object) -> object:
        raise KeyError(key)

    def __iter__(self):
        return iter(())

    def __len__(self) -> int:
        return 0

    def items(self):
        if self.failure_kind == "items":
            raise RuntimeError(self.secret)
        if self.failure_kind == "iteration":
            return self._failing_items()
        return ((ExplodingTextKey("safe", self.secret), "safe"),)

    def _failing_items(self):
        yield from ()
        raise RuntimeError(self.secret)


class ExplodingMetadataEndpoint:
    def __init__(self, executor: object, secret: str) -> None:
        self.executor = executor
        self.secret = secret
        self.close_calls = 0

    @property
    def metadata(self) -> Mapping[str, object]:
        raise RuntimeError(self.secret)

    def close(self) -> None:
        self.close_calls += 1


@dataclass(frozen=True)
class Policy:
    fragment: str

    def load(self) -> str:
        return self.fragment


def _registry_for(profile: ApplicationProfile) -> DomainRegistry:
    registry = DomainRegistry()
    for binding in profile.domains:
        domain_profile = binding.profile
        registry.register(
            domain_profile.manifest.domain_id,
            domain_profile.manifest.version,
            lambda domain_profile=domain_profile: domain_profile,
        )
    return registry


def _second_binding(profile: ApplicationProfile):
    binding = profile.domains[0]
    provisioner = binding.profile.provisioner
    assert provisioner is not None
    endpoint = provisioner.endpoint
    second_endpoint = replace(
        endpoint,
        executor=replace(endpoint.executor, calls=[]),
        closed=False,
        close_calls=0,
    )
    second_profile = replace(
        binding.profile,
        manifest=replace(
            binding.profile.manifest,
            domain_id="second-domain",
            tool_name_prefix="second_",
        ),
        contract_source=PrefixContractSource(
            binding.profile.contract_source, binding.tool_namespace, "second_"
        ),
        provisioner=replace(provisioner, endpoint=second_endpoint, calls=[]),
    )
    return replace(
        binding,
        binding_id="second",
        tool_namespace="second_",
        profile=second_profile,
    )


def _unsafe_domains(
    profile: ApplicationProfile, domains: tuple[object, ...]
) -> ApplicationProfile:
    object.__setattr__(profile, "domains", domains)
    return profile


def _scoped_profile(
    profile: ApplicationProfile,
    *,
    credential_name: str = "token",
) -> ApplicationProfile:
    binding = profile.domains[0]
    return replace(
        profile,
        domains=(
            replace(
                binding,
                credential_scope=replace(
                    binding.credential_scope,
                    credential_names=(credential_name,),
                ),
            ),
        ),
    )


def _assert_sanitized(error: BaseException, secret: str) -> None:
    assert secret not in str(error)
    assert secret not in repr(error)
    assert error.__cause__ is None
    assert error.__context__ is None


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
    prepared_binding = prepared.bindings["fixture"]
    assert prepared_binding.endpoint.executor is prepared_binding.runtime.executor
    assert registered_profile.provisioner is not None
    assert registered_profile.provisioner.endpoint.executor.calls == [
        ("environment.describe", {})
    ]
    assert prepared.bindings["fixture"].runtime.tool_catalog_path == (
        tmp_path / "run/domains/fixture/tool-catalog.json"
    )


@pytest.mark.parametrize(
    "binding_id",
    [
        "../outside",
        "/absolute",
        "nested/binding",
        r"nested\binding",
        ".",
        "..",
        "",
        "Uppercase",
        "under_score",
        "-leading",
        "trailing-",
        "contains space",
        "éxternal",
        "a" * 64,
    ],
)
def test_prepare_application_rejects_unsafe_binding_identifier_before_effects(
    complete_profile: ApplicationProfile,
    tmp_path: Path,
    binding_id: str,
) -> None:
    binding = complete_profile.domains[0]
    profile = replace(
        complete_profile,
        domains=(replace(binding, binding_id=binding_id),),
    )
    provisioner = binding.profile.provisioner
    assert provisioner is not None
    provisioner.failure = RuntimeError("must not provision")
    broker = EmptyCredentialBroker()

    with pytest.raises(ApplicationConfigurationError, match="binding identifier"):
        prepare_application(
            profile,
            registry=_registry_for(profile),
            workspace=tmp_path / "run",
            credentials=broker,
        )

    assert broker.calls == []
    assert provisioner.calls == []
    assert not (tmp_path / "run").exists()


def test_prepare_application_rejects_absolute_binding_identifier_before_effects(
    complete_profile: ApplicationProfile,
    tmp_path: Path,
) -> None:
    binding = complete_profile.domains[0]
    absolute_id = str(tmp_path / "outside")
    profile = replace(
        complete_profile,
        domains=(replace(binding, binding_id=absolute_id),),
    )
    provisioner = binding.profile.provisioner
    assert provisioner is not None
    provisioner.failure = RuntimeError("must not provision")
    broker = EmptyCredentialBroker()

    with pytest.raises(ApplicationConfigurationError, match="binding identifier"):
        prepare_application(
            profile,
            registry=_registry_for(profile),
            workspace=tmp_path / "run",
            credentials=broker,
        )

    assert broker.calls == []
    assert provisioner.calls == []
    assert not (tmp_path / "outside").exists()


def test_prepare_application_rejects_domains_root_symlink_escape_before_effects(
    complete_profile: ApplicationProfile,
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "run"
    workspace.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (workspace / "domains").symlink_to(outside, target_is_directory=True)
    provisioner = complete_profile.domains[0].profile.provisioner
    assert provisioner is not None
    provisioner.failure = RuntimeError("must not provision")
    broker = EmptyCredentialBroker()

    with pytest.raises(ApplicationConfigurationError, match="workspace"):
        prepare_application(
            complete_profile,
            registry=_registry_for(complete_profile),
            workspace=workspace,
            credentials=broker,
        )

    assert broker.calls == []
    assert provisioner.calls == []
    assert tuple(outside.iterdir()) == ()


def test_registered_profile_must_own_the_declared_tool_namespace(
    complete_profile: ApplicationProfile,
    tmp_path: Path,
) -> None:
    registered_profile = complete_profile.domains[0].profile
    binding = complete_profile.domains[0]
    declared_profile = replace(
        registered_profile,
        manifest=replace(
            registered_profile.manifest,
            tool_name_prefix="fixture_",
        ),
    )
    profile = replace(
        complete_profile,
        domains=(
            replace(
                binding,
                tool_namespace="fixture_",
                profile=declared_profile,
            ),
        ),
    )
    registry = DomainRegistry()
    registry.register("fixture-domain", "1.0.0", lambda: registered_profile)
    broker = EmptyCredentialBroker()
    provisioner = registered_profile.provisioner
    assert provisioner is not None

    with pytest.raises(ApplicationConfigurationError, match="tool namespace"):
        prepare_application(
            profile,
            registry=registry,
            workspace=tmp_path / "run",
            credentials=broker,
        )

    assert broker.calls == []
    assert provisioner.calls == []
    assert provisioner.endpoint.executor.calls == []


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


def test_prepare_application_sorts_and_isolates_multiple_bindings(
    complete_profile: ApplicationProfile, tmp_path: Path
) -> None:
    first = complete_profile.domains[0]
    second = _second_binding(complete_profile)
    profile = replace(complete_profile, domains=(second, first))
    broker = EmptyCredentialBroker()

    prepared = prepare_application(
        profile,
        registry=_registry_for(profile),
        workspace=tmp_path / "run",
        credentials=broker,
    )

    assert tuple(binding.binding_id for binding in profile.domains) == (
        "second",
        "fixture",
    )
    assert tuple(prepared.bindings) == ("fixture", "second")
    assert tuple(binding.binding_id for binding in prepared.profile.domains) == (
        "fixture",
        "second",
    )
    assert [binding_id for binding_id, _ in broker.calls] == ["fixture", "second"]
    first_provisioner = first.profile.provisioner
    second_provisioner = second.profile.provisioner
    assert first_provisioner is not None and second_provisioner is not None
    assert first_provisioner.calls[0][1] == tmp_path / "run/domains/fixture"
    assert second_provisioner.calls[0][1] == tmp_path / "run/domains/second"
    assert first_provisioner.calls[0][2] is not second_provisioner.calls[0][2]
    assert prepared.bindings["fixture"].runtime.tool_catalog_path != (
        prepared.bindings["second"].runtime.tool_catalog_path
    )


def test_second_endpoint_failure_closes_first_endpoint(
    complete_profile: ApplicationProfile, tmp_path: Path
) -> None:
    first = complete_profile.domains[0]
    second = _second_binding(complete_profile)
    second_provisioner = second.profile.provisioner
    assert second_provisioner is not None
    second_provisioner.failure = RuntimeError("second endpoint unavailable")
    profile = replace(complete_profile, domains=(second, first))

    with pytest.raises(DomainProvisioningError, match="provisioning failed"):
        prepare_application(
            profile,
            registry=_registry_for(profile),
            workspace=tmp_path / "run",
            credentials=EmptyCredentialBroker(),
        )

    first_provisioner = first.profile.provisioner
    assert first_provisioner is not None
    assert first_provisioner.endpoint.close_calls == 1
    assert second_provisioner.endpoint.close_calls == 0


def test_provisioner_failure_occurs_before_runtime_probe(
    complete_profile: ApplicationProfile, tmp_path: Path
) -> None:
    binding = complete_profile.domains[0]
    provisioner = binding.profile.provisioner
    assert provisioner is not None
    provisioner.failure = RuntimeError("endpoint unavailable")

    with pytest.raises(DomainProvisioningError, match="provisioning failed") as caught:
        prepare_application(
            complete_profile,
            registry=_registry_for(complete_profile),
            workspace=tmp_path / "run",
            credentials=EmptyCredentialBroker(),
        )

    assert provisioner.endpoint.executor.calls == []
    _assert_sanitized(caught.value, "endpoint unavailable")


@pytest.mark.parametrize("boundary", ["broker", "provisioner"])
def test_external_preparation_exceptions_are_sanitized_without_a_chain(
    complete_profile: ApplicationProfile,
    tmp_path: Path,
    boundary: str,
) -> None:
    secret = "credential-secret"
    provisioner = complete_profile.domains[0].profile.provisioner
    assert provisioner is not None
    if boundary == "broker":
        broker = FailingCredentialBroker(DomainProvisioningError(secret))
    else:
        broker = EmptyCredentialBroker()
        provisioner.failure = DomainProvisioningError(secret)

    with pytest.raises(DomainProvisioningError) as caught:
        prepare_application(
            complete_profile,
            registry=_registry_for(complete_profile),
            workspace=tmp_path / "run",
            credentials=broker,
        )

    _assert_sanitized(caught.value, secret)


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

    with pytest.raises(CapabilityTransportError, match="credential"):
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


@pytest.mark.parametrize(
    "leaked_result",
    [
        {"payload": "Bearer credential-secret"},
        {"token": "not-even-the-leased-value"},
    ],
)
def test_prepared_runtime_executor_rejects_later_credential_leakage(
    complete_profile: ApplicationProfile,
    tmp_path: Path,
    leaked_result: dict[str, object],
) -> None:
    profile = _scoped_profile(complete_profile)
    provisioner = profile.domains[0].profile.provisioner
    assert provisioner is not None
    broker = StaticCredentialBroker(
        CredentialLease(
            scope_id="isolated",
            credentials={"token": "credential-secret"},
        )
    )
    prepared = prepare_application(
        profile,
        registry=_registry_for(profile),
        workspace=tmp_path / "run",
        credentials=broker,
    )
    runtime_executor = prepared.bindings["fixture"].runtime.executor
    provisioner.endpoint.executor.environment = leaked_result

    with pytest.raises(CapabilityTransportError) as caught:
        runtime_executor.invoke("asset.list", {})

    _assert_sanitized(caught.value, "credential-secret")


def test_prepared_runtime_executor_sanitizes_later_transport_exception(
    complete_profile: ApplicationProfile,
    tmp_path: Path,
) -> None:
    profile = _scoped_profile(complete_profile)
    provisioner = profile.domains[0].profile.provisioner
    assert provisioner is not None
    broker = StaticCredentialBroker(
        CredentialLease(
            scope_id="isolated",
            credentials={"token": "credential-secret"},
        )
    )
    prepared = prepare_application(
        profile,
        registry=_registry_for(profile),
        workspace=tmp_path / "run",
        credentials=broker,
    )
    runtime_executor = prepared.bindings["fixture"].runtime.executor

    def fail(capability: str, arguments: dict[str, object]) -> dict[str, object]:
        raise DomainProvisioningError("credential-secret")

    provisioner.endpoint.executor.invoke = fail

    with pytest.raises(CapabilityTransportError) as caught:
        runtime_executor.invoke("asset.list", {})

    _assert_sanitized(caught.value, "credential-secret")


@pytest.mark.parametrize("failure_kind", ["result", "exception"])
def test_every_public_prepared_executor_uses_the_credential_boundary(
    complete_profile: ApplicationProfile,
    tmp_path: Path,
    failure_kind: str,
) -> None:
    profile = _scoped_profile(complete_profile)
    provisioner = profile.domains[0].profile.provisioner
    assert provisioner is not None
    broker = StaticCredentialBroker(
        CredentialLease(
            scope_id="isolated",
            credentials={"token": "credential-secret"},
        )
    )
    prepared = prepare_application(
        profile,
        registry=_registry_for(profile),
        workspace=tmp_path / "run",
        credentials=broker,
    )
    prepared_binding = prepared.bindings["fixture"]
    assert prepared_binding.endpoint.executor is prepared_binding.runtime.executor
    if failure_kind == "result":
        provisioner.endpoint.executor.environment = {
            "payload": "credential-secret"
        }
    else:
        def fail(
            capability: str, arguments: dict[str, object]
        ) -> dict[str, object]:
            raise RuntimeError("credential-secret")

        provisioner.endpoint.executor.invoke = fail

    with pytest.raises(CapabilityTransportError) as caught:
        prepared_binding.endpoint.executor.invoke("asset.list", {})

    _assert_sanitized(caught.value, "credential-secret")


def test_broker_credential_mutation_cannot_redefine_runtime_screening(
    complete_profile: ApplicationProfile,
    tmp_path: Path,
) -> None:
    profile = _scoped_profile(complete_profile)
    provisioner = profile.domains[0].profile.provisioner
    assert provisioner is not None
    original_credentials = {"token": "original-secret"}
    lease = MutableCredentialLease(
        scope_id="isolated",
        credentials=original_credentials,
    )
    prepared = prepare_application(
        profile,
        registry=_registry_for(profile),
        workspace=tmp_path / "run",
        credentials=StaticCredentialBroker(lease),
    )
    original_credentials["token"] = "mutated-secret"
    original_credentials.clear()
    lease.credentials = {"token": "replacement-secret"}
    runtime_executor = prepared.bindings["fixture"].runtime.executor
    provisioner.endpoint.executor.environment = {
        "payload": "original-secret"
    }

    with pytest.raises(CapabilityTransportError):
        runtime_executor.invoke("asset.list", {})

    provisioner.endpoint.executor.environment = {
        "payload": "replacement-secret"
    }
    assert runtime_executor.invoke("asset.list", {}) == {
        "payload": "replacement-secret"
    }


def test_provisioner_receives_an_immutable_private_credential_snapshot(
    complete_profile: ApplicationProfile,
    tmp_path: Path,
) -> None:
    profile = _scoped_profile(complete_profile)
    binding = profile.domains[0]
    delegate = binding.profile.provisioner
    assert delegate is not None
    mutating_provisioner = CredentialMutatingProvisioner(delegate)
    domain_profile = replace(
        binding.profile,
        provisioner=mutating_provisioner,
    )
    profile = replace(
        profile,
        domains=(replace(binding, profile=domain_profile),),
    )
    prepared = prepare_application(
        profile,
        registry=_registry_for(profile),
        workspace=tmp_path / "run",
        credentials=StaticCredentialBroker(
            MutableCredentialLease(
                scope_id="isolated",
                credentials={"token": "credential-secret"},
            )
        ),
    )
    issued_snapshot = delegate.calls[0][2]

    assert mutating_provisioner.mutation_blocked is True
    with pytest.raises(TypeError):
        issued_snapshot.credentials["token"] = "external-replacement"
    assert "credential-secret" not in repr(issued_snapshot)
    assert "credential-secret" not in str(issued_snapshot)
    assert prepared.bindings["fixture"].runtime.executor is (
        prepared.bindings["fixture"].endpoint.executor
    )


def test_public_endpoint_metadata_is_detached_deeply_read_only_and_safe(
    complete_profile: ApplicationProfile,
    tmp_path: Path,
) -> None:
    provisioner = complete_profile.domains[0].profile.provisioner
    assert provisioner is not None
    raw_metadata = {
        "transport": "fixture",
        "limits": {"timeout": 10},
        "labels": ["initial"],
    }
    provisioner.endpoint.metadata = raw_metadata
    prepared = prepare_application(
        complete_profile,
        registry=_registry_for(complete_profile),
        workspace=tmp_path / "run",
        credentials=EmptyCredentialBroker(),
    )
    public_endpoint = prepared.bindings["fixture"].endpoint
    raw_metadata["transport"] = "mutated"
    raw_metadata["limits"]["timeout"] = 999
    raw_metadata["labels"].append("mutated")
    raw_metadata["api_key"] = "late-secret"

    assert public_endpoint.metadata == {
        "labels": ("initial",),
        "limits": {"timeout": 10},
        "transport": "fixture",
    }
    with pytest.raises(TypeError):
        public_endpoint.metadata["transport"] = "external"
    with pytest.raises(TypeError):
        public_endpoint.metadata["limits"]["timeout"] = 20
    assert "late-secret" not in repr(public_endpoint)
    assert "late-secret" not in str(public_endpoint)

    public_endpoint.close()
    assert provisioner.endpoint.close_calls == 1


def test_public_endpoint_close_sanitizes_failure_and_is_consumed(
    complete_profile: ApplicationProfile,
    tmp_path: Path,
) -> None:
    provisioner = complete_profile.domains[0].profile.provisioner
    assert provisioner is not None
    prepared = prepare_application(
        complete_profile,
        registry=_registry_for(complete_profile),
        workspace=tmp_path / "run",
        credentials=EmptyCredentialBroker(),
    )
    provisioner.endpoint.close_failure = RuntimeError("close-secret")
    public_endpoint = prepared.bindings["fixture"].endpoint

    with pytest.raises(DomainProvisioningError) as caught:
        public_endpoint.close()

    _assert_sanitized(caught.value, "close-secret")
    public_endpoint.close()
    assert provisioner.endpoint.close_calls == 1


def test_public_endpoint_close_is_idempotent_after_success(
    complete_profile: ApplicationProfile,
    tmp_path: Path,
) -> None:
    provisioner = complete_profile.domains[0].profile.provisioner
    assert provisioner is not None
    prepared = prepare_application(
        complete_profile,
        registry=_registry_for(complete_profile),
        workspace=tmp_path / "run",
        credentials=EmptyCredentialBroker(),
    )
    public_endpoint = prepared.bindings["fixture"].endpoint

    public_endpoint.close()
    public_endpoint.close()

    assert provisioner.endpoint.close_calls == 1


@pytest.mark.parametrize(
    "failure_kind",
    ["property", "items", "iteration", "key-conversion"],
)
def test_endpoint_metadata_failures_are_sanitized_and_closed(
    complete_profile: ApplicationProfile,
    tmp_path: Path,
    failure_kind: str,
) -> None:
    provisioner = complete_profile.domains[0].profile.provisioner
    assert provisioner is not None
    raw_endpoint = provisioner.endpoint
    if failure_kind == "property":
        endpoint = ExplodingMetadataEndpoint(
            raw_endpoint.executor,
            "metadata-secret",
        )
        provisioner.endpoint = endpoint
    else:
        endpoint = raw_endpoint
        endpoint.metadata = HostileMapping(failure_kind, "metadata-secret")

    with pytest.raises(DomainProvisioningError) as caught:
        prepare_application(
            complete_profile,
            registry=_registry_for(complete_profile),
            workspace=tmp_path / "run",
            credentials=EmptyCredentialBroker(),
        )

    _assert_sanitized(caught.value, "metadata-secret")
    assert endpoint.close_calls == 1
    assert raw_endpoint.executor.calls == []


@pytest.mark.parametrize(
    "failure_kind",
    ["items", "iteration", "key-conversion"],
)
def test_public_executor_sanitizes_hostile_result_traversal(
    complete_profile: ApplicationProfile,
    tmp_path: Path,
    failure_kind: str,
) -> None:
    provisioner = complete_profile.domains[0].profile.provisioner
    assert provisioner is not None
    prepared = prepare_application(
        complete_profile,
        registry=_registry_for(complete_profile),
        workspace=tmp_path / "run",
        credentials=EmptyCredentialBroker(),
    )
    provisioner.endpoint.executor.environment = HostileMapping(
        failure_kind,
        "result-secret",
    )

    with pytest.raises(CapabilityTransportError) as caught:
        prepared.bindings["fixture"].endpoint.executor.invoke("asset.list", {})

    _assert_sanitized(caught.value, "result-secret")


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


def test_cleanup_failure_preserves_original_preparation_error(
    complete_profile: ApplicationProfile, tmp_path: Path
) -> None:
    provisioner = complete_profile.domains[0].profile.provisioner
    assert provisioner is not None
    provisioner.endpoint.metadata = {"api_key": "unsafe"}
    provisioner.endpoint.close_failure = RuntimeError("cleanup-secret")

    with pytest.raises(DomainProvisioningError, match="credential") as caught:
        prepare_application(
            complete_profile,
            registry=_registry_for(complete_profile),
            workspace=tmp_path / "run",
            credentials=EmptyCredentialBroker(),
        )

    assert provisioner.endpoint.close_calls == 1
    _assert_sanitized(caught.value, "cleanup-secret")


def test_cleanup_attempts_every_endpoint_in_reverse_order() -> None:
    order: list[str] = []

    class Endpoint:
        def __init__(self, endpoint_id: str, *, raises: bool = False) -> None:
            self.endpoint_id = endpoint_id
            self.raises = raises

        def close(self) -> None:
            order.append(self.endpoint_id)
            if self.raises:
                raise RuntimeError(f"cleanup-secret-{self.endpoint_id}")

    endpoints = (
        Endpoint("first", raises=True),
        Endpoint("second", raises=True),
        Endpoint("third"),
    )

    composition._close_prepared_endpoints(endpoints)

    assert order == ["third", "second", "first"]
