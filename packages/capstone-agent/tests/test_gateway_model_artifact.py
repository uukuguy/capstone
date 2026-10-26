"""Application transfer checks use the published gateway metadata/chunk shape."""
import asyncio
import base64
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import stat
import zipfile
import warnings

import pytest

from capstone_agent.gateway_model_artifact import (
    GatewayModelArtifactBroker, ModelArtifactError, install_binding,
)


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(',', ':'), allow_nan=False).encode()


def fixture_bundle(*, member=None, demo=False):
    mapping = {'schema': 'gateway-element-map/1', 'artifact_ref': 'a' * 64,
               'engine': 'pandapower', 'engine_version': '3.4.0',
               'model_ref': 'grid:arbitrary', 'model_revision': 'b' * 64,
               'scenario_revision': 'c' * 64, 'elements': []}
    map_bytes = encoded(mapping)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        archive.writestr('element-map.json', map_bytes)
        archive.writestr('model.pandapower.json', '{}')
        if member is not None:
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', UserWarning)
                archive.writestr(member, 'unsafe')
    data = buffer.getvalue()
    metadata = {'artifact_ref': 'a' * 64, 'sha256': hashlib.sha256(data).hexdigest(),
                'bytes': len(data), 'target_format': 'pandapower', 'engine_version': '3.4.0',
                'package_format': 'zip', 'model_file': 'model.pandapower.json',
                'transport': {'tool': 'read_network_model_artifact', 'encoding': 'base64',
                              'max_chunk_bytes': 196608},
                'baseline': {'model_ref': mapping['model_ref'], 'model_revision': mapping['model_revision']},
                'element_map': {'schema': 'gateway-element-map/1', 'file': 'element-map.json',
                                'sha256': hashlib.sha256(map_bytes).hexdigest()},
                'quality': {'demo_only': demo, 'power_flow_ready': False, 'real_power_flow_ready': False},
                'source_gaps': ['source_connections'],
                'expires_at': (datetime.now(timezone.utc) + timedelta(days=2)).timestamp()}
    return data, metadata


class Transport:
    def __init__(self, data, metadata, *, change=None, fail=None):
        self.data, self.metadata, self.change, self.fail = data, metadata, change, fail
        self.calls = []

    async def __call__(self, tool, arguments):
        self.calls.append((tool, deepcopy(arguments)))
        if tool == 'get_network_model_artifact':
            return {'status': 'partial', 'data': deepcopy(self.metadata), 'gaps': ['source gap']}
        assert tool == 'read_network_model_artifact'
        if self.fail:
            raise self.fail
        offset = arguments['offset']
        part = self.data[offset:offset + arguments['length']]
        chunk = {'artifact_ref': self.metadata['artifact_ref'], 'offset': offset,
                 'bytes': len(part), 'total_bytes': len(self.data),
                 'sha256': self.metadata['sha256'], 'base64': base64.b64encode(part).decode(),
                 'next_offset': offset + len(part) if offset + len(part) < len(self.data) else None}
        if self.change:
            self.change(chunk)
        return {'status': 'ok', 'data': chunk}


def stage(tmp_path, transport, **kwargs):
    install_binding(tmp_path, 'task', 'attempt')
    expiry = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    return asyncio.run(GatewayModelArtifactBroker(transport, chunk_bytes=80).stage(
        'a' * 64, tmp_path, 'task', 'attempt', expires_at=expiry, **kwargs))


def test_streams_exact_archive_and_issues_task_bound_content_addressed_grant(tmp_path):
    data, metadata = fixture_bundle()
    transport = Transport(data, metadata)
    result = stage(tmp_path, transport)
    digest = result['input_ref'].removeprefix('input:sha256:')
    grant = json.loads((tmp_path / 'inputs/grants' / (digest + '.json')).read_text())
    assert grant['input_ref'] == result['input_ref']
    assert hashlib.sha256(encoded({k: v for k, v in grant.items() if k != 'input_ref'})).hexdigest() == digest
    assert grant['model_id'] == 'grid:arbitrary'
    assert grant['scenario_revision'] == 'c' * 64
    assert grant['authority'] == 'grid-simulator'
    assert grant['task_id'] == 'task' and grant['attempt_id'] == 'attempt'
    assert grant['quality'] == metadata['quality']
    assert (tmp_path / 'inputs/objects' / (metadata['sha256'] + '.zip')).read_bytes() == data
    assert all(c[1]['length'] == 80 for c in transport.calls[1:])
    assert result['status'] == 'partial' and result['gap_count'] == 1
    assert result['receipt_ref'] == 'input-transfer:sha256:' + digest
    receipt = json.loads((tmp_path / 'inputs/receipts' / (digest + '.json')).read_text())
    assert receipt['metadata_response']['gaps'] == ['source gap']
    assert not list(tmp_path.rglob('*.part'))
    assert (tmp_path / 'inputs/grants' / (digest + '.json')).stat().st_mode & 0o077 == 0


@pytest.mark.parametrize('field,value', [
    ('artifact_ref', 'd' * 64), ('offset', 1), ('bytes', 0), ('total_bytes', 1),
    ('sha256', 'e' * 64), ('next_offset', 0), ('next_offset', None), ('base64', '!'),
])
def test_rejects_chunk_drift_without_grant_or_retry(tmp_path, field, value):
    data, metadata = fixture_bundle()
    transport = Transport(data, metadata, change=lambda row: row.update({field: value}))
    with pytest.raises(ModelArtifactError):
        stage(tmp_path, transport)
    assert len(transport.calls) == 2
    assert not list(tmp_path.glob('inputs/grants/*.json'))
    assert not list(tmp_path.rglob('*.part'))


@pytest.mark.parametrize('error', [RuntimeError('private upstream text'), asyncio.CancelledError()])
def test_interrupted_transfer_has_no_grant_and_no_retry(tmp_path, error):
    data, metadata = fixture_bundle()
    transport = Transport(data, metadata, fail=error)
    with pytest.raises(asyncio.CancelledError if isinstance(error, asyncio.CancelledError) else ModelArtifactError):
        stage(tmp_path, transport)
    assert len(transport.calls) == 2
    assert not list(tmp_path.glob('inputs/grants/*.json'))
    assert not list(tmp_path.rglob('*.part'))


@pytest.mark.parametrize('member', ['../bad', '/bad', 'C:/bad', 'a\\bad', 'element-map.json'])
def test_rejects_unsafe_or_duplicate_zip_members(tmp_path, member):
    data, metadata = fixture_bundle(member=member)
    with pytest.raises(ModelArtifactError):
        stage(tmp_path, Transport(data, metadata))
    assert not list(tmp_path.glob('inputs/grants/*.json'))


@pytest.mark.parametrize('mutation', ['bundle_hash', 'map_hash', 'model_revision', 'engine'])
def test_rejects_bundle_map_and_metadata_identity_drift(tmp_path, mutation):
    data, metadata = fixture_bundle()
    if mutation == 'bundle_hash': metadata['sha256'] = '0' * 64
    elif mutation == 'map_hash': metadata['element_map']['sha256'] = '0' * 64
    elif mutation == 'model_revision': metadata['baseline']['model_revision'] = '0' * 64
    else: metadata['target_format'] = 'pypsa'
    with pytest.raises(ModelArtifactError):
        stage(tmp_path, Transport(data, metadata))
    assert not list(tmp_path.glob('inputs/grants/*.json'))


def test_demo_requires_explicit_host_grant(tmp_path):
    data, metadata = fixture_bundle(demo=True)
    with pytest.raises(ModelArtifactError):
        stage(tmp_path, Transport(data, metadata))
    result = stage(tmp_path, Transport(data, metadata), allow_demo=True)
    assert result['quality']['demo_only'] is True


def test_binding_is_installed_separately_and_cannot_be_replaced(tmp_path):
    data, metadata = fixture_bundle()
    broker = GatewayModelArtifactBroker(Transport(data, metadata))
    with pytest.raises(ModelArtifactError):
        asyncio.run(broker.stage('a' * 64, tmp_path, 'task', 'attempt', expires_at='2099-01-01T00:00:00Z'))
    install_binding(tmp_path, 'other-task', 'other-attempt')
    before = (tmp_path / 'application-model-input-binding.json').read_bytes()
    with pytest.raises(ModelArtifactError): install_binding(tmp_path, 'task', 'attempt')
    with pytest.raises(ModelArtifactError):
        asyncio.run(broker.stage('a' * 64, tmp_path, 'task', 'attempt', expires_at='2099-01-01T00:00:00Z'))
    assert (tmp_path / 'application-model-input-binding.json').read_bytes() == before


def test_rejects_map_processing_budget_and_symlinked_private_storage(tmp_path):
    data, metadata = fixture_bundle()
    install_binding(tmp_path, 'task', 'attempt')
    broker = GatewayModelArtifactBroker(Transport(data, metadata), max_map_bytes=8)
    with pytest.raises(ModelArtifactError):
        asyncio.run(broker.stage('a' * 64, tmp_path, 'task', 'attempt', expires_at='2099-01-01T00:00:00Z'))
    other = tmp_path / 'foreign'; other.mkdir()
    (tmp_path / 'inputs/objects').rmdir()
    (tmp_path / 'inputs/objects').symlink_to(other, target_is_directory=True)
    with pytest.raises(ModelArtifactError): stage(tmp_path, Transport(data, metadata))
    assert not list(other.iterdir())


def test_returns_only_bounded_quality_flags_and_keeps_full_private_gaps(tmp_path):
    data, metadata = fixture_bundle()
    metadata['quality']['source_checks'] = [{'missing_ids': list(range(10000))}]
    transport = Transport(data, metadata, change=None)
    original = transport.__class__.__call__

    async def invoke(tool, arguments):
        response = await original(transport, tool, arguments)
        if tool == 'read_network_model_artifact':
            response.update(status='partial', gaps=['chunk gap'], provenance={'source': 'fixed'})
        return response

    result = stage(tmp_path, invoke)
    assert result['quality'] == {'demo_only': False, 'power_flow_ready': False, 'real_power_flow_ready': False}
    assert len(encoded(result)) < 2048
    receipt = json.loads(next(tmp_path.glob('inputs/receipts/*.json')).read_text())
    assert receipt['metadata_response']['data']['quality'] == metadata['quality']
    assert any(row['gaps'] == ['chunk gap'] for row in receipt['transfer_observations'])
    assert all('data' not in row for row in receipt['transfer_observations'])


def test_raw_data_transport_cannot_skip_status_admission(tmp_path):
    data, metadata = fixture_bundle()
    async def invoke(tool, arguments): return metadata
    with pytest.raises(ModelArtifactError): stage(tmp_path, invoke)


def test_cancellation_after_last_chunk_still_has_no_grant(tmp_path):
    data, metadata = fixture_bundle()
    def cancel(chunk):
        if chunk['next_offset'] is None:
            asyncio.current_task().cancel()
    with pytest.raises(asyncio.CancelledError):
        stage(tmp_path, Transport(data, metadata, change=cancel))
    assert not list(tmp_path.glob('inputs/grants/*.json'))
    assert not list(tmp_path.rglob('*.part'))


def test_zip_link_and_declared_uncompressed_budget_rejected(tmp_path):
    data, metadata = fixture_bundle()
    buffer = io.BytesIO(data)
    with zipfile.ZipFile(buffer, 'a') as archive:
        link = zipfile.ZipInfo('link')
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(link, '/etc/passwd')
    data = buffer.getvalue()
    metadata.update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
    with pytest.raises(ModelArtifactError): stage(tmp_path, Transport(data, metadata))
    install_binding(tmp_path, 'task', 'attempt')
    data, metadata = fixture_bundle()
    broker = GatewayModelArtifactBroker(Transport(data, metadata), max_uncompressed_bytes=1)
    with pytest.raises(ModelArtifactError):
        asyncio.run(broker.stage('a' * 64, tmp_path, 'task', 'attempt', expires_at='2099-01-01T00:00:00Z'))


@pytest.mark.parametrize('expiry', ['2000-01-01T00:00:00Z', '2099-01-01T00:00:00', '2099-01-01T00:00:00+08:00'])
def test_requires_future_utc_grant_expiry(tmp_path, expiry):
    data, metadata = fixture_bundle()
    install_binding(tmp_path, 'task', 'attempt')
    transport = Transport(data, metadata)
    with pytest.raises(ModelArtifactError):
        asyncio.run(GatewayModelArtifactBroker(transport).stage(
            'a' * 64, tmp_path, 'task', 'attempt', expires_at=expiry))
    assert not transport.calls


def test_host_can_set_storage_quota_separate_from_processing_budgets(tmp_path):
    data, metadata = fixture_bundle()
    install_binding(tmp_path, 'task', 'attempt')
    transport = Transport(data, metadata)
    broker = GatewayModelArtifactBroker(transport, max_bundle_bytes=1)
    with pytest.raises(ModelArtifactError, match='storage_limit'):
        asyncio.run(broker.stage('a' * 64, tmp_path, 'task', 'attempt', expires_at='2099-01-01T00:00:00Z'))
    assert len(transport.calls) == 1


def test_binding_change_during_transfer_cannot_issue_grant(tmp_path):
    data, metadata = fixture_bundle()
    def replace_binding(chunk):
        if chunk['next_offset'] is None:
            path = tmp_path / 'application-model-input-binding.json'
            binding = json.loads(path.read_text()); binding['task_id'] = 'foreign'
            path.write_bytes(encoded(binding))
    with pytest.raises(ModelArtifactError, match='binding_invalid'):
        stage(tmp_path, Transport(data, metadata, change=replace_binding))
    assert not list(tmp_path.glob('inputs/grants/*.json'))


def test_existing_revoked_grant_is_never_replaced(tmp_path):
    data, metadata = fixture_bundle()
    install_binding(tmp_path, 'task', 'attempt')
    broker = GatewayModelArtifactBroker(Transport(data, metadata))
    args = ('a' * 64, tmp_path, 'task', 'attempt')
    expiry = '2099-01-01T00:00:00Z'
    result = asyncio.run(broker.stage(*args, expires_at=expiry))
    path = tmp_path / 'inputs/grants' / (result['input_ref'].split(':')[-1] + '.json')
    grant = json.loads(path.read_text()); grant['revoked'] = True
    path.write_bytes(encoded(grant))
    with pytest.raises(ModelArtifactError, match='storage_conflict'):
        asyncio.run(broker.stage(*args, expires_at=expiry))
    assert json.loads(path.read_text())['revoked'] is True


def test_receipt_budget_rejects_instead_of_truncating_source_gaps(tmp_path):
    data, metadata = fixture_bundle()
    install_binding(tmp_path, 'task', 'attempt')
    transport = Transport(data, metadata)
    broker = GatewayModelArtifactBroker(transport, max_receipt_bytes=1)
    with pytest.raises(ModelArtifactError, match='receipt_limit'):
        asyncio.run(broker.stage('a' * 64, tmp_path, 'task', 'attempt', expires_at='2099-01-01T00:00:00Z'))
    assert len(transport.calls) == 1
    assert not list(tmp_path.glob('inputs/grants/*.json'))


@pytest.mark.parametrize('flag', ['demo_only', 'power_flow_ready', 'real_power_flow_ready'])
@pytest.mark.parametrize('value', [None, 0, 'false', 'missing'])
def test_all_grant_quality_flags_require_published_exact_booleans(tmp_path, flag, value):
    data, metadata = fixture_bundle()
    if value == 'missing':
        del metadata['quality'][flag]
    else:
        metadata['quality'][flag] = value
    transport = Transport(data, metadata)
    with pytest.raises(ModelArtifactError): stage(tmp_path, transport, allow_demo=True)
    assert len(transport.calls) == 1
    assert not list(tmp_path.glob('inputs/grants/*.json'))


def test_quality_flags_are_digest_bound_without_source_truth_downgrade(tmp_path):
    data, metadata = fixture_bundle(demo=True)
    metadata['quality'].update(power_flow_ready=True, real_power_flow_ready=False)
    metadata['quality']['source_checks'] = [{'missing_ids': ['unverified-source']}]
    install_binding(tmp_path, 'task', 'attempt')
    expiry = '2099-01-01T00:00:00Z'
    broker = GatewayModelArtifactBroker(Transport(data, metadata))
    result = asyncio.run(broker.stage('a' * 64, tmp_path, 'task', 'attempt', allow_demo=True, expires_at=expiry))
    identifier = result['input_ref'].split(':')[-1]
    grant = json.loads((tmp_path / 'inputs/grants' / (identifier + '.json')).read_text())
    assert grant['quality'] == {'demo_only': True, 'power_flow_ready': True, 'real_power_flow_ready': False}
    original = {key: value for key, value in grant.items() if key != 'input_ref'}
    assert hashlib.sha256(encoded(original)).hexdigest() == identifier
    for flag in grant['quality']:
        changed = deepcopy(original)
        changed['quality'][flag] = not changed['quality'][flag]
        assert hashlib.sha256(encoded(changed)).hexdigest() != identifier
