from types import SimpleNamespace

import pytest

from capability_agent.application.errors import DomainProvisioningError
from capability_agent.domain.profile import NativeExecutionConfig


def executor():
    profiles = {}
    for role in ('direct_pi', 'delegated_pi'):
        profiles[role] = dict(schema='capstone-resource-profile/1', profile_id=role,
            revision='a' * 64, role=role, resources=[], load_receipt=dict(
                schema='capstone-resource-adapter-check/1', status='passed', role=role,
                adapter_id='native-pi-resources/1', source_sha256='b' * 64,
                published_tool_ids=[], skills={}, tool_schema_hashes={}, descriptor_sha256=None))
    return SimpleNamespace(identity={'host_id': 'test-host'}, capability=dict(
        capability_id='general-pi', enabled=True, available=True, resource_profiles=profiles))


def prepare(host, tmp_path, *, required=()):
    from capstone_agent.native_pack_preparation import PiNativeBindingPreparer
    return PiNativeBindingPreparer(host).prepare(binding=SimpleNamespace(binding_id='native'),
        profile=SimpleNamespace(execution=NativeExecutionConfig(
            'direct_pi', 'capstone-pi-task-result/1', required)),
        workspace=tmp_path, credentials=SimpleNamespace(credentials={}))


def test_published_resources_produce_detached_native_receipt(tmp_path):
    host = executor()
    endpoint = prepare(host, tmp_path)
    host.capability['resource_profiles']['direct_pi']['revision'] = 'c' * 64
    assert endpoint.receipt.resource_revision == 'a' * 64
    assert len(endpoint.receipt.executor_identity_digest) == 64
    assert not hasattr(endpoint, 'authority')
    assert not list(tmp_path.iterdir())
    endpoint.close()
    endpoint.close()


def test_missing_required_resource_fails_without_execution(tmp_path):
    with pytest.raises(DomainProvisioningError, match='required resource'):
        prepare(executor(), tmp_path, required=('company-data',))


def test_unavailable_host_does_not_claim_prepared(tmp_path):
    host = executor()
    host.capability['available'] = False
    with pytest.raises(DomainProvisioningError, match='unavailable'):
        prepare(host, tmp_path)


def test_failed_load_receipt_does_not_claim_prepared(tmp_path):
    host = executor()
    host.capability['resource_profiles']['direct_pi']['load_receipt']['status'] = 'failed'
    with pytest.raises(DomainProvisioningError, match='publication'):
        prepare(host, tmp_path)
