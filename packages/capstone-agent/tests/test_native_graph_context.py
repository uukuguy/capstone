"""Host context seals actual version bytes, never mutable workspace aliases."""
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess

import pytest

from test_native_graph_progress import graph_fixture
from capstone_agent.general_pi_storage import GeneralPiStorage


def test_actual_runtime_inspection_bindings_match_host_leases_after_record_and_restore():
    from capstone_agent.native_graph_events import NativeGraphEvents
    from capstone_agent.native_research_bridge import checked_graph_progress
    root = Path(__file__).resolve().parents[3]
    fixture = Path(__file__).parent / 'fixtures' / 'graph-reference-binding.mjs'
    run = subprocess.run(['node', str(fixture)], cwd=root, text=True, capture_output=True, timeout=30)
    assert run.returncode == 0, run.stderr
    result = json.loads(run.stdout)
    binding = graph_fixture()[0]
    binding.update(cycle_owner=result['owner'], attempt_id=result['attempt_id'], research_id=result['owner']['research_id'])
    def verify(progress):
        return checked_graph_progress(progress, binding=binding, task_id=result['task_id'], attempt_id=result['attempt_id'], view=result['view'])
    guard = NativeGraphEvents(owner=result['owner'], attempt_id=result['attempt_id'], task_id=result['task_id'])
    stages = []
    for event in result['timeline']:
        if event['kind'] == 'progress':
            guard.admit_progress(verify(event['value']))
        else:
            assert guard.admit(event['value']) == event['value']
            assert guard.action_for_call(event['stage'], 'agent_research_read') == event['value']['action_id']
            stages.append(event['stage'])
    assert stages == ['before-record', 'after-record', 'after-continuation', 'after-assess', 'after-restore']
    progress = [event['value'] for event in result['timeline'] if event['kind'] == 'progress']
    restored_binding = result['timeline'][-1]['value']
    fresh = NativeGraphEvents(owner=result['owner'], attempt_id=result['attempt_id'], task_id=result['task_id'])
    fresh.admit_progress(verify(progress[-1]))
    with pytest.raises(ValueError, match='no committed lease'):
        fresh.admit(restored_binding)  # Latest assess-only state cannot mint an old execution lease.
    for retained in progress:
        fresh.admit_progress(verify(retained))
    assert fresh.admit(restored_binding) == restored_binding


def assert_sdk_reads_granted_handle(action, inputs, checkpoint, expected, kind, *, parent=False, inspection=None):
    root = Path(__file__).resolve().parents[3]
    fixture = Path(__file__).parent / 'fixtures' / 'general-sdk-graph-handle-read.mjs'
    action = {**action, 'input_bindings': [{**item, 'name': 'prior'} for item in action['input_bindings']]}
    run = subprocess.run(['node', str(fixture)], cwd=root, text=True, capture_output=True, timeout=30,
        input=json.dumps({'action': action, 'inputs': {'manifests': inputs['manifests'], 'handles': inputs['handles']},
                         'checkpoint': checkpoint, 'expected': expected, 'kind': kind, 'parent': parent, 'inspection': inspection}))
    assert run.returncode == 0, run.stderr
    result = {'read': True, 'kind': kind, 'receipts': 1}
    if parent:
        result.update(parent=True, inspection_only=True, consumed_results=[item['result_ref'] for item in inputs['manifests']])
    assert json.loads(run.stdout) == result


def complete_result(request, *, result_ref, kind, observation_refs=(), artifact_refs=()):
    return {'schema': 'capstone-task-result/1', 'result_ref': result_ref, 'owner': request['owner'],
        'producer': {'step_id': 'A', 'action_id': 'action-1', 'attempt_id': request['attempt_id'], 'execution_revision': 1, 'definition_ref': 'definition-A'},
        'slot': 'retained', 'kind': kind, 'source_versions': [], 'method': {'unavailable': 'Test-only retained bytes'},
        'consumed_results': [], 'observation_refs': list(observation_refs), 'artifact_refs': list(artifact_refs),
        'supersedes': [], 'summary': 'Actual retained bytes', 'scope': 'Granted fixture output', 'recompute_reason': None}


def setup_context(tmp_path, *, delegated=False):
    from capstone_agent.native_graph_context import NativeGraphContext
    binding, task, view, event = graph_fixture()
    action = {'id': 'action-1', 'kind': 'execute', 'step_id': 'A',
              'owner': binding['cycle_owner'], 'attempt_id': binding['attempt_id'],
              'input_bindings': [], 'execution_revision': 1, 'definition_ref': 'definition-A'}
    saved = json.loads(view['state']['notes'][0]['text'])
    saved['snapshot'].update(actions=[action], nodes=[{'id': 'A', 'execution': 'delegated' if delegated else 'parent'}],
        node_states={'A': {'execute_action_id': action['id'], 'execution_revision': 1, 'definition_ref': 'definition-A'}}, results=[], external_results=[])
    view['state']['notes'][0]['text'] = json.dumps(saved)
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    storage = GeneralPiStorage(tmp_path / 'storage')
    context = NativeGraphContext(root=tmp_path / 'contexts' / task, workspace=workspace,
        uid=65534, task_id=task, attempt_id=binding['attempt_id'], owner=binding['cycle_owner'],
        view_provider=lambda: {'binding': binding, 'view': view}, storage=storage)
    request = {'type': 'enterprise_graph_context_request', 'schema': 'capstone-enterprise-graph-context/1',
        'owner': binding['cycle_owner'], 'attempt_id': binding['attempt_id'], 'task_id': task,
        'action_id': action['id'], 'checkpoint': event['checkpoint'], 'request_id': 'freeze-A',
        'operation': 'freeze', 'selection': {'products': [{'path': 'report.txt', 'role': 'primary'}]}}
    return context, request, workspace, storage, view


def test_definite_context_rejections_retain_safe_categories_and_never_repeat_filesystem_work(tmp_path, monkeypatch):
    context, request, workspace, _, _ = setup_context(tmp_path)
    (workspace / 'report.txt').write_text('actual report')
    rejected = context.handle({**request, 'selection': {'products': [{'path': '../private/secret', 'role': 'primary'}]}})
    assert rejected['ok'] is False
    assert rejected['code'] == 'selection_invalid'
    assert '/private/' not in rejected['error']
    assert rejected['diagnostic'] == {'operation': 'freeze', 'action_id': request['action_id'], 'checkpoint': request['checkpoint'],
        'selection': {'products': [{'path': '../private/secret', 'role': 'primary'}]}}
    monkeypatch.setattr(context, '_freeze', lambda *_: pytest.fail('Retained rejection must replay without filesystem work'))
    assert context.handle({**request, 'selection': {'products': [{'path': '../private/secret', 'role': 'primary'}]}}) == rejected
    owner = context.handle({**request, 'request_id': 'foreign-owner', 'owner': {}})
    assert owner['ok'] is False and owner['code'] == 'owner_invalid'


def test_freeze_retains_saved_bytes_after_source_overwrite_and_replay(tmp_path, monkeypatch):
    context, request, workspace, storage, _ = setup_context(tmp_path)
    (workspace / 'report.txt').write_bytes(b'original report')
    receipt = context.handle(request)
    assert receipt['ok'] is True
    product = receipt['result']['products'][0]
    assert product['path'].startswith('context-results/')
    assert product['sha256'] == sha256(b'original report').hexdigest()
    row = context.artifacts()[0]
    assert row['metadata']['path'] == product['path']
    assert (storage.root / 'artifacts' / request['task_id'] / row['artifact_id']).read_bytes() == b'original report'
    (workspace / 'report.txt').write_bytes(b'changed')
    monkeypatch.setattr(storage, 'artifact_file', lambda *args, **kwargs: pytest.fail('replayed copy'))
    assert context.handle(request) == receipt
    assert context.handle({**request, 'selection': {'products': []}})['ok'] is False
    assert context.handle(request) == receipt
    assert context.root.stat().st_mode & 0o022 == 0
    assert (context.root / 'responses' / 'freeze-A.json').stat().st_mode & 0o222 == 0


def test_research_freeze_retains_available_files_and_records_missing_reproduction(tmp_path):
    context, request, workspace, _, _ = setup_context(tmp_path)
    (workspace / 'report.txt').write_text('Retained useful finding')
    request['selection'] = {'products': [{'path': 'missing.py', 'role': 'reproduction'},
        {'path': 'report.txt', 'role': 'primary'}], 'retain_available': True}
    receipt = context.handle(request)
    assert receipt['ok'], receipt
    result = receipt['result']
    assert len(result['products']) == 1
    assert result['unavailable'] == [{'path': 'missing.py', 'code': 'source_missing'}]
    assert result['selections'][0]['path'] == 'report.txt'
    assert Path(next(iter(context.grants.values()))['path']).read_text() == 'Retained useful finding'
    assert context.handle(request) == receipt


def test_storage_failure_allows_new_request_retry_without_changing_granted_bytes(tmp_path, monkeypatch):
    context, request, workspace, storage, _ = setup_context(tmp_path)
    original = b'original report after storage recovery'
    (workspace / 'report.txt').write_bytes(original)
    save = storage.artifact_file
    def unavailable(*args):
        raise OSError('temporary storage failure')
    monkeypatch.setattr(storage, 'artifact_file', unavailable)
    failed = context.handle(request)
    assert failed['ok'] is False
    assert context.artifacts() == []
    monkeypatch.setattr(storage, 'artifact_file', save)
    assert context.handle(request) == failed
    recovered = context.handle({**request, 'request_id': 'retry-after-storage-recovery'})
    assert recovered['ok'] is True
    product = recovered['result']['products'][0]
    assert product['sha256'] == sha256(original).hexdigest()
    assert len(context.grants) == len(context.artifacts()) == 1
    row = context.artifacts()[0]
    assert (storage.root / 'artifacts' / request['task_id'] / row['artifact_id']).read_bytes() == original
    sealed = list((context.root / 'results').iterdir())
    assert len(sealed) == 1 and sealed[0].read_bytes() == original
    stamp = sealed[0].stat().st_ino
    assert context.handle({**request, 'request_id': 'repeat-granted-product'})['ok'] is True
    assert sealed[0].stat().st_ino == stamp
    assert len(context.grants) == len(context.artifacts()) == 1


def test_failed_later_product_save_preserves_earlier_grant_and_retry(tmp_path, monkeypatch):
    context, request, workspace, storage, _ = setup_context(tmp_path)
    (workspace / 'report.txt').write_bytes(b'already granted report')
    (workspace / 'second.txt').write_bytes(b'second report')
    request['selection']['products'].append({'path': 'second.txt', 'role': 'support'})
    save, calls = storage.artifact_file, []
    def fail_second(*args):
        calls.append(args)
        if len(calls) == 2:
            raise OSError('temporary second save failure')
        return save(*args)
    monkeypatch.setattr(storage, 'artifact_file', fail_second)
    assert context.handle(request)['ok'] is False
    assert len(context.artifacts()) == 1
    first_grant = next(iter(context.grants.values()))
    first_path = Path(first_grant['path'])
    first_inode = first_path.stat().st_ino
    assert len(list((context.root / 'results').iterdir())) == 1
    monkeypatch.setattr(storage, 'artifact_file', save)
    recovered = context.handle({**request, 'request_id': 'retry-partial-save'})
    assert recovered['ok'] is True
    assert len(context.grants) == len(context.artifacts()) == 2
    assert first_path.stat().st_ino == first_inode
    assert first_path.read_bytes() == b'already granted report'


@pytest.mark.parametrize('fault', ['target_protect', 'grant_write', 'grant_write_after_publish', 'grant_protect'])
def test_publication_fault_cleans_only_new_ungranted_files_and_allows_retry(tmp_path, monkeypatch, fault):
    import capstone_agent.native_graph_context as module
    context, request, workspace, storage, _ = setup_context(tmp_path)
    original, second = b'earlier granted immutable bytes', b'new bytes retained after publication failure'
    (workspace / 'report.txt').write_bytes(original)
    assert context.handle(request)['ok'] is True
    first_grant = deepcopy(next(iter(context.grants.values())))
    first_path = Path(first_grant['path'])
    first_inode = first_path.stat().st_ino
    (workspace / 'second.txt').write_bytes(second)
    request = {**request, 'request_id': 'fault-' + fault, 'selection': {'products': [
        {'path': 'report.txt', 'role': 'primary'}, {'path': 'second.txt', 'role': 'support'}]}}
    protect, write_json = context._protect, module.write_json
    def fail_protect(path, *args, **kwargs):
        if ((fault == 'target_protect' and path.parent == context.root / 'results' and path != first_path)
                or (fault == 'grant_protect' and path.parent == context.root / 'grants')):
            protect(path, *args, **kwargs)
            raise OSError('temporary protection failure')
        return protect(path, *args, **kwargs)
    def fail_write(path, *args, **kwargs):
        if path.parent == context.root / 'grants' and fault in {'grant_write', 'grant_write_after_publish'}:
            if fault == 'grant_write_after_publish':
                write_json(path, *args, **kwargs)
            raise OSError('temporary grant publication failure')
        return write_json(path, *args, **kwargs)
    monkeypatch.setattr(context, '_protect', fail_protect)
    monkeypatch.setattr(module, 'write_json', fail_write)
    failed = context.handle(request)
    assert failed['ok'] is False
    assert context.artifacts() == [first_grant['artifact']]
    assert list(context.grants.values()) == [first_grant]
    assert first_path.stat().st_ino == first_inode
    assert first_path.read_bytes() == original
    assert len(list((context.root / 'results').iterdir())) == 1
    assert len(list((context.root / 'grants').iterdir())) == 1
    saved_blobs = {path.name: (path.stat().st_ino, path.read_bytes())
                   for path in (storage.root / 'artifacts' / request['task_id']).iterdir()}
    assert len(saved_blobs) == (1 if fault == 'target_protect' else 2)
    assert all(data in {original, second} for _, data in saved_blobs.values())
    monkeypatch.setattr(context, '_protect', protect)
    monkeypatch.setattr(module, 'write_json', write_json)
    assert context.handle(request) == failed
    recovered = context.handle({**request, 'request_id': 'recovered-' + fault})
    assert recovered['ok'] is True
    assert len(context.artifacts()) == len(context.grants) == 2
    assert first_path.stat().st_ino == first_inode and first_path.read_bytes() == original
    product = recovered['result']['products'][1]
    assert product['sha256'] == sha256(second).hexdigest()
    assert len(list((context.root / 'results').iterdir())) == 2
    assert len(list((context.root / 'grants').iterdir())) == 2
    for identity, (inode, data) in saved_blobs.items():
        saved = storage.root / 'artifacts' / request['task_id'] / identity
        assert saved.stat().st_ino == inode and saved.read_bytes() == data


@pytest.mark.parametrize('mutate', ['owner', 'attempt', 'action', 'checkpoint', 'stale', 'invalidated'])
def test_context_rejects_foreign_or_stale_lease(tmp_path, mutate):
    context, request, workspace, _, view = setup_context(tmp_path)
    (workspace / 'report.txt').write_text('actual')
    request = deepcopy(request)
    if mutate == 'owner': request['owner']['goal_revision'] = 2
    if mutate == 'attempt': request['attempt_id'] = 'foreign'
    if mutate == 'action': request['action_id'] = 'foreign'
    if mutate == 'checkpoint': request['checkpoint']['revision'] += 1
    if mutate == 'stale':
        saved = json.loads(view['state']['notes'][0]['text'])
        saved['snapshot']['node_states']['A']['execute_action_id'] = 'new-action'
        view['state']['notes'][0]['text'] = json.dumps(saved)
    if mutate == 'invalidated':
        saved = json.loads(view['state']['notes'][0]['text'])
        saved['snapshot']['node_states']['A']['applicability'] = 'stale'
        view['state']['notes'][0]['text'] = json.dumps(saved)
    assert context.handle(request)['ok'] is False
    assert context.artifacts() == []


@pytest.mark.parametrize('path', ['../outside', '/tmp/outside', '.agent/config.json', 'nested/link.txt', 'link.txt', 'bad\\name.txt', 'bad\nname.txt'])
def test_context_rejects_escape_private_and_symlinks(tmp_path, path):
    context, request, workspace, _, _ = setup_context(tmp_path)
    outside = tmp_path / 'outside'
    outside.write_text('private')
    (workspace / 'nested').symlink_to(tmp_path, target_is_directory=True)
    (workspace / 'link.txt').symlink_to(outside)
    if path.startswith('bad'):
        (workspace / path).write_text('unsafe name')
    request['selection']['products'][0]['path'] = path
    assert context.handle(request)['ok'] is False


def test_streaming_storage_rejects_changed_blob_and_never_reads_whole_file(tmp_path, monkeypatch):
    storage = GeneralPiStorage(tmp_path / 'storage')
    source = tmp_path / 'large.bin'
    data = b'x' * (3 * 1024 * 1024 + 9)
    source.write_bytes(data)
    row = {'artifact_id': 'file_abc', 'metadata': {'sha256': sha256(data).hexdigest(), 'size_bytes': len(data)}}
    monkeypatch.setattr(Path, 'read_bytes', lambda _: pytest.fail('whole-file read'))
    storage.artifact_file('task_A', source, row)
    storage.artifact_file('task_A', source, row)
    source.write_bytes(b'different')
    with pytest.raises(OSError): storage.artifact_file('task_A', source, row)


def test_resolve_selects_exact_declared_version_and_frozen_handle(tmp_path):
    context, request, workspace, _, view = setup_context(tmp_path)
    (workspace / 'report.txt').write_bytes(b'v1')
    product = context.handle(request)['result']['products'][0]
    saved = json.loads(view['state']['notes'][0]['text'])
    result = complete_result(request, result_ref='result-v1', kind='artifact', artifact_refs=[product['ref']])
    action = {**saved['snapshot']['actions'][0], 'id': 'consumer', 'step_id': 'C', 'input_bindings': [{'result_ref': 'result-v1'}]}
    saved['snapshot']['actions'].append(action)
    saved['snapshot']['node_states']['C'] = {'execute_action_id': 'consumer', 'execution_revision': 1, 'definition_ref': 'definition-A'}
    saved['snapshot']['nodes'].append({'id': 'C', 'execution': 'delegated'})
    saved['snapshot']['results'] = [result]
    view['state']['notes'][0]['text'] = json.dumps(saved)
    resolve = {**request, 'request_id': 'resolve-C', 'action_id': 'consumer', 'operation': 'resolve',
        'selection': {'result_refs': ['result-v1'], 'product_refs': []}}
    receipt = context.handle(resolve)
    assert receipt['ok'] is True
    assert receipt['result']['manifests'] == [result]
    handle = receipt['result']['handles'][0]
    assert handle['immutable'] and handle['read_only']
    assert handle['file_name'] == 'report.txt'
    assert handle['media_type'] == 'text/plain'
    assert handle['size_bytes'] == 2
    assert handle['sha256'] == product['sha256']
    assert handle['roles'] == ['primary']
    assert handle['output_slot'] == 'retained'
    (workspace / 'report.txt').write_bytes(b'v2')
    assert Path(handle['path']).read_bytes() == b'v1'
    assert Path(handle['path']).stat().st_mode & 0o222 == 0
    assert_sdk_reads_granted_handle(action, receipt['result'], request['checkpoint'], 'v1', 'product')
    inspection = context.handle({**resolve, 'request_id': 'inspect-product', 'operation': 'read',
        'selection': {'ref': handle['ref'], 'offset_bytes': 0, 'length_bytes': 2}})
    assert inspection['ok'], inspection
    assert_sdk_reads_granted_handle(action, receipt['result'], request['checkpoint'], 'v1', 'product', parent=True, inspection=inspection['result'])
    assert context.handle({**resolve, 'request_id': 'bad', 'selection': {'result_refs': ['result-v2'], 'product_refs': []}})['ok'] is False


@pytest.mark.parametrize('research_policy', [False, True])
def test_explicit_limited_acceptance_preserves_historical_sealed_bytes_and_rejects_altered_provenance(tmp_path, research_policy):
    context, request, workspace, _, view = setup_context(tmp_path)
    (workspace / 'report.txt').write_bytes(b'bounded retained version')
    product = context.handle(request)['result']['products'][0]
    document = context.view_provider()
    if not research_policy:
        document['binding']['graph_work_edition'] = 'capstone-graph-work/1'
    saved = json.loads(view['state']['notes'][0]['text'])
    snapshot = saved['snapshot']
    if research_policy:
        snapshot['selected_limited_inputs'] = True
    else:
        snapshot['work_edition'] = 'capstone-graph-work/1'
    manifest = complete_result(request, result_ref='limited-result', kind='artifact', artifact_refs=[product['ref']])
    producer = {'execute_action_id': request['action_id'], 'execution_revision': 1, 'phase': 'limited', 'settled_status': 'completed',
        'assessment_ref': 'assessment:retained', 'record': {'limitations': ['Optional figure not completed']},
        'assessment': {'outcome': 'limited', 'summary': 'The useful table lacks optional visual review', 'checks': [{'description': 'Visual review', 'status': 'not_run', 'refs': [], 'explanation': 'Useful table retained'}]},
        'output_bindings': [{'slot': 'retained', 'result_ref': manifest['result_ref']}]}
    acceptance = {'result_ref': manifest['result_ref'], 'producer_action_id': request['action_id'], 'producer_execution_revision': 1,
        'assessment_ref': producer['assessment_ref'], 'assessment_summary': producer['assessment']['summary'], 'record_limitations': producer['record']['limitations'],
        'unmet_checks': producer['assessment']['checks'], 'rationale': 'Use the table and preserve the omitted review'}
    consumer = {**snapshot['actions'][0], 'id': 'consumer', 'step_id': 'C',
        'input_bindings': [{'input_name': 'prior', 'result_ref': manifest['result_ref'], 'accepted_limitations': acceptance}]}
    snapshot['actions'].append(consumer)
    snapshot['nodes'].append({'id': 'C', 'execution': 'parent'})
    snapshot['node_states']['C'] = {'execute_action_id': 'consumer', 'execution_revision': 1, 'definition_ref': 'definition-A'}
    snapshot['node_states']['A']['execute_action_id'] = 'new-producer-action'
    snapshot.update(results=[manifest], executions=[producer])
    view['state']['notes'][0]['text'] = json.dumps(saved)
    selected = {**request, 'request_id': 'resolve-limited', 'action_id': 'consumer', 'operation': 'resolve',
        'selection': {'result_refs': [manifest['result_ref']], 'product_refs': []}}
    resolved = context.handle(selected)
    assert resolved['ok'], resolved
    assert Path(resolved['result']['handles'][0]['path']).read_bytes() == b'bounded retained version'
    assert_sdk_reads_granted_handle(consumer, resolved['result'], request['checkpoint'], 'bounded retained version', 'product')
    if research_policy:
        snapshot['selected_limited_inputs'] = False
        view['state']['notes'][0]['text'] = json.dumps(saved)
        assert not context.handle({**selected, 'request_id': 'policy-not-selected'})['ok']
        snapshot['selected_limited_inputs'] = True
    for index, status in enumerate(('cancelled', 'failed', 'unknown')):
        producer['settled_status'] = status
        view['state']['notes'][0]['text'] = json.dumps(saved)
        assert not context.handle({**selected, 'request_id': 'invalid-status-' + str(index)})['ok']
    producer['settled_status'] = 'completed'
    acceptance['assessment_ref'] = 'assessment:foreign'
    view['state']['notes'][0]['text'] = json.dumps(saved)
    assert not context.handle({**selected, 'request_id': 'altered-assessment'})['ok']
    acceptance['assessment_ref'] = producer['assessment_ref']
    acceptance['assessment_summary'] = 'A rewritten limitation is not the committed assessment'
    view['state']['notes'][0]['text'] = json.dumps(saved)
    assert not context.handle({**selected, 'request_id': 'altered-summary'})['ok']


def test_reference_inspection_reads_only_a_bounded_sealed_grant(tmp_path, monkeypatch):
    context, request, workspace, _, view = setup_context(tmp_path)
    (workspace / 'report.txt').write_bytes(b'original retained bytes')
    product = context.handle(request)['result']['products'][0]
    saved = json.loads(view['state']['notes'][0]['text'])
    saved['products'] = [product]
    saved['dispatches'] = [{'action_id': 'action-1', 'status': 'completed', 'product_refs': [product['ref']], 'receipt_refs': []}]
    view['state']['notes'][0]['text'] = json.dumps(saved)
    read = {**request, 'operation': 'read', 'request_id': 'read-product',
            'selection': {'ref': product['ref'], 'offset_bytes': 9, 'length_bytes': 8}}
    (workspace / 'report.txt').write_bytes(b'changed original')
    receipt = context.handle(read)
    assert receipt['ok'], receipt
    assert receipt['result']['text'] == 'retained'
    assert receipt['result']['ref'] == product['ref']
    assert receipt['result']['sha256'] == product['sha256']
    assert receipt['result']['next_offset_bytes'] == 17
    assert str(context.root) not in json.dumps(receipt)
    with monkeypatch.context() as patch:
        patch.setattr(os, 'pread', lambda *_: pytest.fail('Metadata must not read content'))
        metadata = context.handle({**read, 'request_id': 'metadata-only', 'selection': {'ref': product['ref']}})
        assert metadata['ok'], metadata
        assert metadata['result']['logical_path'] == product['path']
        assert 'text' not in metadata['result']
    for phase in ('recorded', 'assessing', 'success'):
        saved['snapshot']['node_states']['A']['phase'] = phase
        view['state']['notes'][0]['text'] = json.dumps(saved)
        assert context.handle({**read, 'request_id': 'read-' + phase})['ok']
    for index, patch in enumerate([{'ref': '/tmp/file'}, {'ref': 'foreign'}, {'offset_bytes': -1}, {'length_bytes': 10**9}]):
        bad = {**read, 'request_id': 'reject-' + str(index), 'selection': {**read['selection'], **patch}}
        assert not context.handle(bad)['ok']
    for index, patch in enumerate([{'owner': {**request['owner'], 'thread_id': 'foreign'}}, {'attempt_id': 'foreign'},
                                   {'action_id': 'foreign'}, {'checkpoint': {**request['checkpoint'], 'revision': 999}}]):
        assert not context.handle({**read, **patch, 'request_id': 'foreign-read-' + str(index)})['ok']


def test_reference_inspection_binary_grants_return_metadata_only(tmp_path, monkeypatch):
    context, request, workspace, _, view = setup_context(tmp_path)
    request['selection']['products'][0]['path'] = 'image.png'
    (workspace / 'image.png').write_bytes(b'ASCII slice in binary format')
    product = context.handle(request)['result']['products'][0]
    saved = json.loads(view['state']['notes'][0]['text'])
    saved['products'] = [product]
    view['state']['notes'][0]['text'] = json.dumps(saved)
    monkeypatch.setattr(os, 'pread', lambda *_: pytest.fail('Binary inspection must not read content'))
    receipt = context.handle({**request, 'operation': 'read', 'request_id': 'read-binary',
        'selection': {'ref': product['ref'], 'offset_bytes': 0, 'length_bytes': 10}})
    assert receipt['ok'], receipt
    assert receipt['result']['content_status'] == 'metadata_only'
    assert 'text' not in receipt['result']


def test_reference_inspection_trims_a_partial_utf8_end_without_hiding_invalid_interior(tmp_path):
    context, request, workspace, _, view = setup_context(tmp_path)
    (workspace / 'report.txt').write_text('甲乙丙', encoding='utf-8')
    product = context.handle(request)['result']['products'][0]
    saved = json.loads(view['state']['notes'][0]['text']);saved['products'] = [product]
    view['state']['notes'][0]['text'] = json.dumps(saved)
    read = {**request, 'operation': 'read', 'request_id': 'utf8-boundary',
        'selection': {'ref': product['ref'], 'offset_bytes': 0, 'length_bytes': 7}}
    receipt = context.handle(read)
    assert receipt['ok'], receipt
    assert receipt['result']['text'] == '甲乙'
    assert receipt['result']['read_bytes'] == 6
    assert receipt['result']['next_offset_bytes'] == 6
    assert receipt['result']['utf8_boundary_trimmed'] is True
    leading = context.handle({**read, 'request_id': 'utf8-leading', 'selection': {**read['selection'], 'offset_bytes': 1, 'length_bytes': 4}})
    assert leading['result']['content_reason'] == 'utf8_range_boundary'
    assert 'text' not in leading['result']
    (workspace / 'invalid.txt').write_bytes('甲'.encode() + b'\xffinvalid')
    bad_product = context.handle({**request, 'request_id': 'freeze-invalid-utf8',
        'selection': {'products': [{'path': 'invalid.txt', 'role': 'support'}]}})['result']['products'][0]
    saved['products'].append(bad_product);view['state']['notes'][0]['text'] = json.dumps(saved)
    invalid = context.handle({**read, 'request_id': 'invalid-interior',
        'selection': {'ref': bad_product['ref'], 'offset_bytes': 0, 'length_bytes': 100}})
    assert invalid['result']['content_reason'] == 'invalid_utf8'
    assert 'text' not in invalid['result']


def test_reference_inspection_preserves_explicit_old_input_after_producer_rerun(tmp_path):
    context, request, workspace, _, view = setup_context(tmp_path)
    (workspace / 'report.txt').write_bytes(b'old frozen bytes')
    product = context.handle(request)['result']['products'][0]
    saved = json.loads(view['state']['notes'][0]['text'])
    saved['snapshot']['results'] = [complete_result(request, result_ref='old-result', kind='artifact', artifact_refs=[product['ref']])]
    consumer = {**saved['snapshot']['actions'][0], 'id': 'consumer', 'step_id': 'C',
        'input_bindings': [{'input_name': 'old', 'result_ref': 'old-result'}]}
    saved['snapshot']['actions'].append(consumer)
    saved['snapshot']['nodes'].append({'id': 'C', 'execution': 'parent'})
    saved['snapshot']['node_states']['C'] = {'execute_action_id': 'consumer', 'execution_revision': 1, 'definition_ref': 'definition-A'}
    saved['snapshot']['node_states']['A']['execute_action_id'] = 'producer-new-version'
    view['state']['notes'][0]['text'] = json.dumps(saved)
    read = {**request, 'action_id': 'consumer', 'operation': 'read', 'request_id': 'read-explicit-old',
        'selection': {'ref': product['ref'], 'offset_bytes': 0, 'length_bytes': 16}}
    receipt = context.handle(read)
    assert receipt['ok'], receipt
    assert receipt['result']['text'] == 'old frozen bytes'
    consumer['input_bindings'] = []
    view['state']['notes'][0]['text'] = json.dumps(saved)
    assert not context.handle({**read, 'request_id': 'no-implicit-old'})['ok']
    assert not context.handle({**read, 'action_id': 'action-1', 'request_id': 'stale-producer'})['ok']


def test_delegated_freeze_uses_only_the_host_derived_subtree_and_streams(tmp_path, monkeypatch):
    context, request, workspace, _, _ = setup_context(tmp_path, delegated=True)
    (workspace / 'report.txt').write_text('wrong parent bytes')
    child = workspace / '.research-workers' / sha256(request['action_id'].encode()).hexdigest()
    child.mkdir(parents=True)
    (child / 'report.txt').write_bytes(b'actual child bytes')
    monkeypatch.setattr(Path, 'read_bytes', lambda _: pytest.fail('whole-file read'))
    receipt = context.handle(request)
    assert receipt['ok']
    assert receipt['result']['products'][0]['sha256'] == sha256(b'actual child bytes').hexdigest()
    assert receipt['result']['selections'] == [{'path': 'report.txt', 'ref': receipt['result']['products'][0]['ref']}]
    assert context.root.parent.stat().st_mode & 0o777 == 0o711


def test_synthesis_resolves_inherited_artifact_only_through_explicit_lineage(tmp_path):
    context, request, workspace, _, view = setup_context(tmp_path)
    (workspace / 'report.txt').write_bytes(b'v1')
    product = context.handle(request)['result']['products'][0]
    saved = json.loads(view['state']['notes'][0]['text'])
    origin = {'result_ref': 'origin', 'owner': request['owner'], 'producer': {'action_id': 'action-1', 'attempt_id': request['attempt_id']}, 'artifact_refs': [product['ref']], 'consumed_results': []}
    derived = {**origin, 'result_ref': 'derived', 'producer': {'action_id': 'synthesizer', 'attempt_id': request['attempt_id']}, 'consumed_results': ['origin']}
    action = {**saved['snapshot']['actions'][0], 'id': 'consumer', 'input_bindings': [{'result_ref': 'derived'}]}
    saved['snapshot']['actions'].append(action)
    saved['snapshot']['node_states']['A']['execute_action_id'] = 'consumer'
    saved['snapshot']['results'] = [origin, derived]
    view['state']['notes'][0]['text'] = json.dumps(saved)
    resolve = {**request, 'action_id': 'consumer', 'request_id': 'lineage', 'operation': 'resolve', 'selection': {'result_refs': ['derived'], 'product_refs': []}}
    receipt = context.handle(resolve)
    assert receipt['ok']
    assert receipt['result']['handles'][0]['result_ref'] == 'derived'


def test_observation_handles_use_only_real_persisted_bytes_and_exact_lineage(tmp_path, monkeypatch):
    context, request, workspace, storage, view = setup_context(tmp_path)
    source_ref = 'native-observation:' + request['task_id'] + ':' + sha256(b'actual-call').hexdigest()
    body = b'{"content":[{"type":"text","text":"actual native observation"}]}'
    storage.observation(request['task_id'], 'observation-real', body)
    monkeypatch.setattr(Path, 'read_bytes', lambda _: pytest.fail('whole-file read'))
    context.admit_observation(source_ref, 'observation-real', sha256(body).hexdigest(), action_id='action-1')
    saved = json.loads(view['state']['notes'][0]['text'])
    result = complete_result(request, result_ref='observed', kind='observation', observation_refs=[source_ref])
    saved['receipts'] = [{'ref': source_ref, 'owner': request['owner'], 'attempt_id': request['attempt_id'], 'action_id': 'action-1', 'status': 'completed'}]
    saved['snapshot']['results'] = [result]
    consumer = {**saved['snapshot']['actions'][0], 'id': 'consumer', 'input_bindings': [{'result_ref': 'observed'}]}
    saved['snapshot']['actions'].append(consumer)
    saved['snapshot']['node_states']['A']['execute_action_id'] = 'consumer'
    view['state']['notes'][0]['text'] = json.dumps(saved)
    resolve = {**request, 'action_id': 'consumer', 'request_id': 'observe', 'operation': 'resolve', 'selection': {'result_refs': ['observed'], 'product_refs': []}}
    resolved = context.handle(resolve)
    assert resolved['ok']
    handle = resolved['result']['handles'][0]
    assert handle['ref'] == source_ref and handle['result_ref'] == 'observed'
    with Path(handle['path']).open('rb') as stream: assert stream.read() == body
    assert_sdk_reads_granted_handle(consumer, resolved['result'], request['checkpoint'], body.decode(), 'observation')
    inspection = context.handle({**resolve, 'request_id': 'inspect-observation', 'operation': 'read',
        'selection': {'ref': handle['ref'], 'offset_bytes': 0, 'length_bytes': len(body)}})
    assert inspection['ok'], inspection
    assert_sdk_reads_granted_handle(consumer, resolved['result'], request['checkpoint'], body.decode(), 'observation', parent=True, inspection=inspection['result'])
    assert context.artifacts() == []
    with pytest.raises(ValueError): context.admit_observation(source_ref, 'observation-real', 'f' * 64, action_id='action-1')
    saved['snapshot']['results'][0]['producer']['action_id'] = 'foreign-action'
    view['state']['notes'][0]['text'] = json.dumps(saved)
    assert not context.handle({**resolve, 'request_id': 'foreign-observe'})['ok']


def test_two_equal_basenames_keep_distinct_explicit_product_selections(tmp_path):
    context, request, workspace, _, _ = setup_context(tmp_path)
    for folder in ['first', 'second']:
        (workspace / folder).mkdir()
        (workspace / folder / 'report.txt').write_text('same bytes')
    request['selection']['products'] = [{'path': 'first/report.txt', 'role': 'primary'}, {'path': 'second/report.txt', 'role': 'support'}]
    receipt = context.handle(request)
    assert receipt['ok']
    assert len({item['ref'] for item in receipt['result']['products']}) == 2
    assert len(context.artifacts()) == 2
