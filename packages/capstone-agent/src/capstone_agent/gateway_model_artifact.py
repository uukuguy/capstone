"""Host-only gateway transfer into a task-bound Authority input store.

The injected transport selects its own fixed endpoint and authentication. No
archive path or file payload is exposed as a model tool argument. The Authority
owns native-model decoding and numerical admission after this transfer.
"""
from __future__ import annotations

import asyncio
import base64
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tempfile
import zipfile


QUALITY_FLAGS = ('demo_only', 'power_flow_ready', 'real_power_flow_ready')


class ModelArtifactError(ValueError):
    """Fixed public diagnostic; upstream messages and credentials are excluded."""


def _require(condition, code='model_artifact_invalid'):
    if not condition:
        raise ModelArtifactError(code)


def _encode(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'),
                      allow_nan=False).encode('utf-8')


def _text(value):
    _require(isinstance(value, str) and 0 < len(value) <= 512 and not any(ord(c) < 32 for c in value))
    return value


def _digest(value):
    _require(isinstance(value, str) and re.fullmatch('[a-f0-9]{64}', value) is not None)
    return value


def _integer(value, minimum=0):
    _require(type(value) is int and value >= minimum)
    return value


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result)
        result[key] = value
    return result


def _json(data):
    return json.loads(data, object_pairs_hook=_pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ModelArtifactError('model_artifact_invalid')))


def _private_dir(path):
    _require(not path.is_symlink(), 'model_input_storage_invalid')
    path.mkdir(mode=0o700, exist_ok=True)
    _require(path.is_dir() and not path.stat().st_mode & 0o077, 'model_input_storage_invalid')


def _binding(task_id, attempt_id):
    return {'schema': 'grid-model-input-binding/1', 'task_id': _text(task_id),
            'attempt_id': _text(attempt_id), 'authority': 'grid-simulator'}


def _read_binding(workspace, expected):
    path = workspace / 'application-model-input-binding.json'
    _require(not path.is_symlink() and path.is_file() and path.stat().st_size <= 4096,
             'model_input_binding_invalid')
    _require(not path.stat().st_mode & 0o077, 'model_input_binding_invalid')
    _require(_json(path.read_bytes()) == expected, 'model_input_binding_invalid')


def _publish(path, data):
    """Publish without replacing an existing grant, receipt, or revoked record."""
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '-', suffix='.part', dir=path.parent)
    temporary = Path(temporary)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            _require(not path.is_symlink() and path.is_file() and path.stat().st_size == len(data),
                     'model_input_storage_conflict')
            _require(path.read_bytes() == data, 'model_input_storage_conflict')
    finally:
        temporary.unlink(missing_ok=True)


def install_binding(workspace, task_id, attempt_id):
    """Provision once from the trusted host; never replace another task binding."""
    workspace = Path(workspace)
    expected = _binding(task_id, attempt_id)
    try:
        _require(not workspace.is_symlink() and workspace.is_dir(), 'model_input_storage_invalid')
        path = workspace / 'application-model-input-binding.json'
        _publish(path, _encode(expected))
        _read_binding(workspace, expected)
    except ModelArtifactError:
        raise
    except Exception:
        raise ModelArtifactError('model_input_binding_invalid') from None


class GatewayModelArtifactBroker:
    """Stream published chunks. Processing budgets do not impose upload quotas."""

    def __init__(self, invoke, *, chunk_bytes=196608, max_map_bytes=64 * 1024 * 1024,
                 max_archive_members=64, max_uncompressed_bytes=8 * 1024 ** 3,
                 max_receipt_bytes=4 * 1024 * 1024, max_bundle_bytes=None):
        _require(callable(invoke))
        _require(type(chunk_bytes) is int and 1 <= chunk_bytes <= 196608)
        for limit in (max_map_bytes, max_archive_members, max_uncompressed_bytes, max_receipt_bytes):
            _integer(limit, 1)
        if max_bundle_bytes is not None:
            _integer(max_bundle_bytes, 1)
        self.invoke = invoke
        self.chunk_bytes = chunk_bytes
        self.max_map_bytes = max_map_bytes
        self.max_archive_members = max_archive_members
        self.max_uncompressed_bytes = max_uncompressed_bytes
        self.max_receipt_bytes = max_receipt_bytes
        self.max_bundle_bytes = max_bundle_bytes

    async def _call(self, tool, arguments):
        response = await self.invoke(tool, arguments)
        _require(isinstance(response, dict) and response.get('status') in {'ok', 'partial'})
        _require(isinstance(response.get('data'), dict))
        _require(len(_encode(response)) <= self.max_receipt_bytes, 'model_artifact_receipt_limit')
        return response

    def _metadata(self, data, artifact_ref, allow_demo):
        _require(data.get('artifact_ref') == artifact_ref)
        _digest(data.get('sha256')); _integer(data.get('bytes'), 1)
        _require(self.max_bundle_bytes is None or data['bytes'] <= self.max_bundle_bytes,
                 'model_artifact_storage_limit')
        _require(data.get('package_format') == 'zip' and data.get('target_format') == 'pandapower'
                 and data.get('engine_version') == '3.4.0')
        transport = data.get('transport', {})
        _require(transport.get('tool') == 'read_network_model_artifact' and transport.get('encoding') == 'base64')
        limit = _integer(transport.get('max_chunk_bytes'), 1)
        _require(limit <= 196608)
        expiration = data.get('expires_at')
        _require(type(expiration) in (int, float) and math.isfinite(expiration)
                 and expiration > datetime.now(timezone.utc).timestamp())
        baseline = data.get('baseline', {})
        _text(baseline.get('model_ref')); _digest(baseline.get('model_revision'))
        mapping = data.get('element_map', {})
        _require(mapping.get('schema') == 'gateway-element-map/1' and mapping.get('file') == 'element-map.json')
        _digest(mapping.get('sha256'))
        quality = data.get('quality', {})
        _require(isinstance(quality, dict) and all(type(quality.get(key)) is bool for key in QUALITY_FLAGS))
        _require(allow_demo or not quality['demo_only'], 'model_artifact_demo_not_authorized')
        _require(isinstance(data.get('source_gaps', []), list))
        return min(self.chunk_bytes, limit)

    def _map(self, path, metadata):
        with zipfile.ZipFile(path) as archive:
            members = archive.infolist()
            _require(len(members) <= self.max_archive_members)
            names = set()
            total = 0
            for info in members:
                name = info.filename
                parts = PurePosixPath(name).parts
                mode = info.external_attr >> 16
                _require(name and '\\' not in name and '\x00' not in name
                         and not name.startswith('/') and not re.match('[A-Za-z]:', name)
                         and all(p not in {'.', '..'} for p in name.split('/') if p)
                         and parts and name.rstrip('/') == '/'.join(parts))
                _require(name not in names and not info.flag_bits & 1)
                _require(stat.S_IFMT(mode) in {0, stat.S_IFREG, stat.S_IFDIR})
                names.add(name)
                total += info.file_size
                _require(total <= self.max_uncompressed_bytes, 'model_artifact_processing_limit')
            _require('element-map.json' in names and metadata.get('model_file') in names)
            info = archive.getinfo('element-map.json')
            _require(not info.is_dir() and info.file_size <= self.max_map_bytes,
                     'model_artifact_processing_limit')
            with archive.open(info) as stream:
                raw = stream.read(self.max_map_bytes + 1)
            _require(len(raw) == info.file_size and len(raw) <= self.max_map_bytes)
        _require(hashlib.sha256(raw).hexdigest() == metadata['element_map']['sha256'])
        mapping = _json(raw)
        _require(isinstance(mapping, dict) and mapping.get('schema') == 'gateway-element-map/1')
        for key, expected in {'artifact_ref': metadata['artifact_ref'], 'engine': 'pandapower',
                              'engine_version': '3.4.0', **metadata['baseline']}.items():
            if key in {'artifact_ref', 'engine', 'engine_version', 'model_ref', 'model_revision'}:
                _require(mapping.get(key) == expected)
        _digest(mapping.get('scenario_revision'))
        return mapping

    async def stage(self, artifact_ref, workspace, task_id, attempt_id, *, allow_demo=False, expires_at):
        """Return opaque input_ref only after complete transfer and grant commit."""
        temporary = None
        try:
            _digest(artifact_ref)
            _require(type(allow_demo) is bool)
            expiry = datetime.fromisoformat(_text(expires_at).replace('Z', '+00:00'))
            _require(expiry.utcoffset() is not None and expiry.utcoffset().total_seconds() == 0
                     and expiry > datetime.now(timezone.utc), 'model_input_expiry_invalid')
            workspace = Path(workspace)
            _require(workspace.is_dir() and not workspace.is_symlink(), 'model_input_storage_invalid')
            binding = _binding(task_id, attempt_id)
            _read_binding(workspace, binding)
            for relative in ('inputs', 'inputs/objects', 'inputs/grants', 'inputs/receipts'):
                _private_dir(workspace / relative)
            response = await self._call('get_network_model_artifact', {'artifact_ref': artifact_ref})
            metadata = response['data']
            length = self._metadata(metadata, artifact_ref, allow_demo)
            fd, name = tempfile.mkstemp(prefix='artifact-', suffix='.part', dir=workspace / 'inputs/objects')
            temporary = Path(name)
            offset, digest = 0, hashlib.sha256()
            partial = response['status'] == 'partial'
            observations = {}
            receipt_bytes = len(_encode(response))
            with os.fdopen(fd, 'wb') as stream:
                while offset < metadata['bytes']:
                    chunk_response = await self._call('read_network_model_artifact',
                        {'artifact_ref': artifact_ref, 'offset': offset, 'length': length})
                    partial = partial or chunk_response['status'] == 'partial'
                    observation = {key: value for key, value in chunk_response.items() if key != 'data'}
                    encoded_observation = _encode(observation)
                    observation_id = hashlib.sha256(encoded_observation).hexdigest()
                    if observation_id not in observations:
                        receipt_bytes += len(encoded_observation)
                        _require(receipt_bytes <= self.max_receipt_bytes, 'model_artifact_receipt_limit')
                        observations[observation_id] = observation
                    chunk = chunk_response['data']
                    _require(chunk.get('artifact_ref') == artifact_ref and chunk.get('sha256') == metadata['sha256'])
                    _require(type(chunk.get('offset')) is int and chunk['offset'] == offset)
                    _require(type(chunk.get('total_bytes')) is int and chunk['total_bytes'] == metadata['bytes'])
                    size = _integer(chunk.get('bytes'), 1)
                    _require(size == min(length, metadata['bytes'] - offset))
                    payload = chunk.get('base64')
                    _require(isinstance(payload, str) and len(payload) <= 4 * ((length + 2) // 3))
                    part = base64.b64decode(payload, validate=True)
                    _require(len(part) == size)
                    offset += size
                    expected_next = offset if offset < metadata['bytes'] else None
                    _require(chunk.get('next_offset') == expected_next
                             and (expected_next is None or type(chunk['next_offset']) is int))
                    stream.write(part); digest.update(part)
                stream.flush(); os.fsync(stream.fileno())
            _require(offset == metadata['bytes'] and digest.hexdigest() == metadata['sha256'])
            mapping = self._map(temporary, metadata)
            _read_binding(workspace, binding)
            _require(expiry > datetime.now(timezone.utc), 'model_input_expiry_invalid')
            grant = {'schema': 'grid-model-input-grant/1', 'task_id': task_id, 'attempt_id': attempt_id,
                     'authority': 'grid-simulator', 'artifact_ref': artifact_ref,
                     'bundle_sha256': metadata['sha256'], 'bundle_bytes': metadata['bytes'],
                     'engine': 'pandapower', 'engine_version': '3.4.0', 'model_id': mapping['model_ref'],
                     'model_revision': mapping['model_revision'], 'scenario_revision': mapping['scenario_revision'],
                     'map_sha256': metadata['element_map']['sha256'], 'allow_demo': allow_demo,
                     'quality': {key: metadata['quality'][key] for key in QUALITY_FLAGS},
                     'expires_at': expires_at, 'revoked': False}
            identifier = hashlib.sha256(_encode(grant)).hexdigest()
            grant['input_ref'] = 'input:sha256:' + identifier
            target = workspace / 'inputs/objects' / (metadata['sha256'] + '.zip')
            try:
                os.link(temporary, target)
            except FileExistsError:
                _require(not target.is_symlink() and target.is_file() and target.stat().st_size == metadata['bytes'],
                         'model_input_storage_conflict')
                with target.open('rb') as stream:
                    _require(hashlib.file_digest(stream, 'sha256').hexdigest() == metadata['sha256'],
                             'model_input_storage_conflict')
            receipt = {'schema': 'capstone-model-artifact-transfer/1', 'metadata_response': response,
                       'input_ref': grant['input_ref'], 'status': 'partial' if partial else 'ok',
                       'transfer_observations': list(observations.values())}
            _publish(workspace / 'inputs/receipts' / (identifier + '.json'), _encode(receipt))
            # Grant is the commit point. Cancellation before it leaves no usable input.
            await asyncio.sleep(0)
            _read_binding(workspace, binding)
            _publish(workspace / 'inputs/grants' / (identifier + '.json'), _encode(grant))
            return {key: grant[key] for key in ('input_ref', 'artifact_ref', 'bundle_sha256', 'bundle_bytes',
                    'model_id', 'model_revision', 'scenario_revision', 'map_sha256')} | {
                    'status': receipt['status'], 'quality': {
                        key: value for key, value in metadata['quality'].items()
                        if key in {'demo_only', 'power_flow_ready', 'real_power_flow_ready',
                                   'source_parameters_verified', 'switch_positions_verified',
                                   'operating_scenario_verified'} and type(value) is bool},
                    'gap_count': len(metadata.get('source_gaps', [])),
                    'receipt_ref': 'input-transfer:sha256:' + identifier}
        except ModelArtifactError:
            raise
        except asyncio.CancelledError:
            raise
        except Exception:
            raise ModelArtifactError('model_artifact_transfer_failed') from None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
