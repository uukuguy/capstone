from dataclasses import replace

import pytest

from capability_agent.application.composition import prepare_application
from capability_agent.application.errors import ApplicationConfigurationError
from capability_agent.application.profile import ReferenceGrant
from capability_agent.application.registry import DomainRegistry
from capability_agent.application.native import NativePreparationReceipt, PreparedNativeBinding
from capability_agent.domain.manifest import PackManifest
from capability_agent.domain.profile import NativeDomainRuntimeProfile, NativeExecutionConfig
from types import SimpleNamespace


@pytest.fixture
def mixed_profile(complete_profile):
    original = complete_profile.domains[0]
    native = NativeDomainRuntimeProfile(
        PackManifest('enterprise-resources', '1', 'Enterprise resources'),
        NativeExecutionConfig('direct_pi', 'capstone-pi-task-result/1'),
        SimpleNamespace(load=lambda: 'allow: generic-file-access'), original.profile.guide_provider,
    )
    binding = replace(original, binding_id='native', tool_namespace='native_', profile=native)
    return replace(complete_profile, domains=(*complete_profile.domains, binding),
        reference_grants=(ReferenceGrant('fixture', 'native', 'public-material', 'analysis', 'read'),))


class EmptyCredentials:
    def issue(self, *, binding_id, scope):
        return SimpleNamespace(scope_id=scope.scope_id, credentials={})


class NativePreparer:
    def __init__(self):
        self.closed = False

    def prepare(self, *, binding, profile, workspace, credentials):
        return SimpleNamespace(receipt=NativePreparationReceipt(
            profile.execution.resource_profile_id, 'revision-1', profile.execution.result_contract,
            'identity-1', profile.execution.required_resources), close=self.close)

    def close(self):
        self.closed = True


def test_native_selection_preserves_grants_without_resolving_authority(mixed_profile, tmp_path):
    registry = DomainRegistry()
    native = mixed_profile.domains[1].profile
    registry.register(native.manifest.domain_id, native.manifest.version, lambda: native)
    prepared = prepare_application(mixed_profile, registry=registry, workspace=tmp_path,
        credentials=EmptyCredentials(), required_binding_ids=('native',), native_preparer=NativePreparer())
    assert tuple(prepared.bindings) == ('native',)
    assert isinstance(prepared.bindings['native'], PreparedNativeBinding)
    assert prepared.profile.domains == mixed_profile.domains
    assert prepared.profile.reference_grants == mixed_profile.reference_grants


def test_authority_selection_does_not_require_native_preparer(mixed_profile, tmp_path):
    registry = DomainRegistry()
    authority = mixed_profile.domains[0].profile
    registry.register(authority.manifest.domain_id, authority.manifest.version, lambda: authority)
    prepared = prepare_application(mixed_profile, registry=registry, workspace=tmp_path,
        credentials=EmptyCredentials(), required_binding_ids=('fixture',))
    assert tuple(prepared.bindings) == ('fixture',)
    assert prepared.profile.reference_grants == mixed_profile.reference_grants


def test_invalid_native_receipt_closes_prepared_endpoint(mixed_profile, tmp_path):
    from capability_agent.application.errors import DomainProvisioningError
    registry = DomainRegistry()
    native = mixed_profile.domains[1].profile
    registry.register(native.manifest.domain_id, native.manifest.version, lambda: native)
    preparer = NativePreparer()
    original = preparer.prepare
    def prepare(**kwargs):
        endpoint = original(**kwargs)
        endpoint.receipt = replace(endpoint.receipt, result_contract='wrong')
        return endpoint
    preparer.prepare = prepare
    with pytest.raises(DomainProvisioningError, match='receipt'):
        prepare_application(mixed_profile, registry=registry, workspace=tmp_path,
            credentials=EmptyCredentials(), required_binding_ids=('native',), native_preparer=preparer)
    assert preparer.closed


def test_legacy_runner_rejects_native_before_preparation(mixed_profile):
    from capability_agent.application.runner import AgentApplication
    with pytest.raises(ApplicationConfigurationError, match='native'):
        AgentApplication(profile=mixed_profile, credentials=NoCredentials())


@pytest.mark.parametrize('field,value', [('resource_revision', {'version': '1'}),
    ('executor_identity_digest', True), ('required_resources', ['resource'])])
def test_native_receipt_rejects_mutable_or_untyped_identity(field, value):
    values = dict(resource_profile_id='direct_pi', resource_revision='revision-1',
        result_contract='result/1', executor_identity_digest='digest-1', required_resources=())
    values[field] = value
    with pytest.raises(ValueError):
        NativePreparationReceipt(**values)


def test_mutable_receipt_is_rejected_and_closed(mixed_profile, tmp_path):
    from capability_agent.application.errors import DomainProvisioningError
    registry = DomainRegistry()
    native = mixed_profile.domains[1].profile
    registry.register(native.manifest.domain_id, native.manifest.version, lambda: native)
    preparer = NativePreparer()
    original = preparer.prepare
    def prepare(**kwargs):
        endpoint = original(**kwargs)
        endpoint.receipt = SimpleNamespace(resource_profile_id='direct_pi', resource_revision='1',
            result_contract='capstone-pi-task-result/1', executor_identity_digest='1', required_resources=())
        return endpoint
    preparer.prepare = prepare
    with pytest.raises(DomainProvisioningError, match='receipt type'):
        prepare_application(mixed_profile, registry=registry, workspace=tmp_path,
            credentials=EmptyCredentials(), required_binding_ids=('native',), native_preparer=preparer)
    assert preparer.closed


def test_registry_cannot_change_execution_kind(mixed_profile):
    from capability_agent.application.errors import DomainRegistrationError
    binding = mixed_profile.domains[0]
    native = replace(mixed_profile.domains[1].profile, manifest=PackManifest(
        binding.profile.manifest.domain_id, binding.profile.manifest.version, 'Wrong kind'))
    registry = DomainRegistry()
    registry.register(native.manifest.domain_id, native.manifest.version, lambda: native)
    with pytest.raises(DomainRegistrationError, match='execution kind'):
        registry.resolve_binding(binding)


def test_native_failure_closes_previously_prepared_authority(mixed_profile, tmp_path):
    registry = DomainRegistry()
    for binding in mixed_profile.domains:
        registry.register(binding.profile.manifest.domain_id, binding.profile.manifest.version,
            lambda profile=binding.profile: profile)
    class FailedPreparer:
        def prepare(self, **kwargs):
            raise RuntimeError('preparation failed')
    with pytest.raises(RuntimeError, match='preparation failed'):
        prepare_application(mixed_profile, registry=registry, workspace=tmp_path,
            credentials=EmptyCredentials(), native_preparer=FailedPreparer())
    assert mixed_profile.domains[0].profile.provisioner.endpoint.closed


def test_native_preparation_does_not_weaken_authority_policy(mixed_profile, tmp_path):
    from capability_agent.application.errors import PolicyConflictError
    original = mixed_profile.domains[0]
    authority = replace(original.profile, policy_provider=SimpleNamespace(load=lambda: 'allow: generic-file-access'))
    profile = replace(mixed_profile, domains=(replace(original, profile=authority), mixed_profile.domains[1]))
    registry = DomainRegistry()
    registry.register(authority.manifest.domain_id, authority.manifest.version, lambda: authority)
    with pytest.raises(PolicyConflictError):
        prepare_application(profile, registry=registry, workspace=tmp_path,
            credentials=NoCredentials(), required_binding_ids=('fixture',), native_preparer=NativePreparer())


class NoCredentials:
    def issue(self, **kwargs):
        raise AssertionError('unselected credentials must not be issued')


def test_empty_selection_keeps_complete_profile_without_preparing_resources(complete_profile, tmp_path):
    prepared = prepare_application(complete_profile, registry=DomainRegistry(),
        workspace=tmp_path, credentials=NoCredentials(), required_binding_ids=())
    assert prepared.profile is complete_profile
    assert not prepared.bindings


def test_unknown_selection_fails_before_credentials(complete_profile, tmp_path):
    with pytest.raises(ApplicationConfigurationError, match='not selected'):
        prepare_application(complete_profile, registry=DomainRegistry(),
            workspace=tmp_path, credentials=NoCredentials(), required_binding_ids=('missing',))


def test_native_declaration_does_not_require_authority_or_model(complete_profile):
    from capability_agent.domain.manifest import PackManifest
    from capability_agent.domain.profile import NativeDomainRuntimeProfile, NativeExecutionConfig
    native = NativeDomainRuntimeProfile(
        manifest=PackManifest('enterprise-resources', '1', 'Enterprise resources'),
        execution=NativeExecutionConfig(resource_profile_id='direct_pi', result_contract='capstone-pi-task-result/1'),
        policy_provider=complete_profile.domains[0].profile.policy_provider,
        guide_provider=complete_profile.domains[0].profile.guide_provider,
    )
    binding = replace(complete_profile.domains[0], binding_id='native', tool_namespace='native_', profile=native)
    profile = replace(complete_profile, domains=(*complete_profile.domains, binding),
        reference_grants=(ReferenceGrant('fixture', 'native', 'public-material', 'analysis', 'read'),))
    assert profile.domains[1].profile.execution.kind == 'native'
    assert not hasattr(native, 'authority_factory')
    assert not hasattr(native.manifest, 'authority_id')
