"""Running file versions are readable products, never completion receipts."""
import json
import threading
import time
from copy import deepcopy
from hashlib import sha256

import pytest

from capstone_agent.general_pi_server import GeneralPiHost
from capstone_agent.pi_delegation import PiTaskRequest


def wait_until(predicate):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(.01)
    raise AssertionError('expected bounded artifact capture did not arrive')


def test_versions_publish_while_task_is_running_and_survive_a_later_failure(tmp_path):
    next_version, finish = threading.Event(), threading.Event()
    def run(request, cancelled, emit):
        workspace = tmp_path / 'tasks' / request.task_id
        workspace.mkdir(parents=True)
        path = workspace / 'report.md'
        (workspace / '.capstone-products.json').write_text(json.dumps({
            'schema':'capstone-workspace-products/1', 'products':[{'path':'report.md', 'role':'primary'}]}))
        path.write_text('version one')
        emit({'type':'tool_execution_end','toolName':'write','toolCallId':'call_one','result':{}})
        assert next_version.wait(3)
        path.write_text('version two')
        emit({'type':'tool_execution_end','toolName':'edit','toolCallId':'call_two','result':{}})
        assert finish.wait(3)
        raise ValueError('later computation failed')
    identity = {'engine':'pi'}
    host = GeneralPiHost(root=tmp_path, identity=identity, run_task=run)
    request = PiTaskRequest('task_files', 'attempt_files', 'direct', 'Make a report', (), (), identity, 10)
    host.submit(request)
    def captures():
        return [event for event in host.read(request.task_id)['events'] if event.get('type') == 'native_artifact_captured']
    try:
        first = wait_until(lambda: captures() or None)[0]
        assert host.read(request.task_id)['status'] == 'running'
        assert host.read(request.task_id)['result'] is None
        assert host.read_artifact(request.task_id, first['artifact']['artifact_id']) == b'version one'
        assert first['artifact']['metadata']['presentation_role'] == 'primary'
        assert 'delivery_status' not in first['artifact']['metadata']
        next_version.set()
        second = wait_until(lambda: captures() if len(captures()) == 2 else None)[1]
        assert second['artifact']['artifact_id'] != first['artifact']['artifact_id']
        assert host.read_artifact(request.task_id, first['artifact']['artifact_id']) == b'version one'
        assert host.read_artifact(request.task_id, second['artifact']['artifact_id']) == b'version two'
        finish.set()
        wait_until(lambda: host.read(request.task_id)['status'] == 'failed')
        assert host.read_artifact(request.task_id, first['artifact']['artifact_id']) == b'version one'
    finally:
        next_version.set(); finish.set()


def test_capture_crosses_real_http_and_is_retained_on_the_thread_before_completion(tmp_path):
    from capstone_agent.general_pi_server import make_server
    from capstone_agent.pi_delegation import HttpGeneralPiExecutor
    from capstone_agent.request_intent import NodeControl
    from capstone_agent.delegated_runtime import DelegatedRuntime
    from capstone_agent.artifacts import MemoryObjectStore
    from capstone_agent.native_artifact_projection import artifact_object_key
    from test_native_artifact_projection import claim
    delivered = threading.Event()
    def run(request, cancelled, emit):
        workspace = tmp_path / 'tasks' / request.task_id
        workspace.mkdir(parents=True)
        (workspace / 'report.md').write_text('available before completion')
        emit({'type':'tool_execution_end','toolName':'write','toolCallId':'call_file','result':{}})
        assert delivered.wait(3)
        return 'Done', {}
    identity = {'engine':'pi'}
    host = GeneralPiHost(root=tmp_path, identity=identity, run_task=run)
    server = make_server(host, control_token='fixture-control', address=('127.0.0.1', 0))
    thread = threading.Thread(target=server.serve_forever, daemon=True);thread.start()
    request = PiTaskRequest('task_http', 'attempt_files', 'direct', 'Make a report', (), (), identity, 10)
    executor = HttpGeneralPiExecutor(f'http://127.0.0.1:{server.server_port}',
        identity=identity, capability=host.capability, control_token='fixture-control')
    runtime = object.__new__(DelegatedRuntime)
    runtime._claim, runtime._artifact_store, runtime._executor = claim(), MemoryObjectStore(), executor
    runtime.runtime_mode = 'capstone'
    published = []
    control = NodeControl(lambda:None, time.monotonic()+10)
    transfers = runtime._incremental_artifact_transfers(published.append, control)
    def native(event):
        if event.get('type') != 'native_artifact_captured':return
        runtime._publish_captured_artifact(event, request, transfers)
        def verify():
            wait_until(lambda:published)
            artifact = published[-1]['payload']['artifact']
            assert artifact['thread_id'] == 'thr_files' and artifact['attempt_id'] == 'attempt_files'
            assert artifact['source_status'] == 'running' and 'delivery_status' not in artifact
            assert host.read(request.task_id)['result'] is None
            assert runtime._artifact_store.get(artifact_object_key(artifact), 100) == b'available before completion'
            delivered.set()
        threading.Thread(target=verify,daemon=True).start()
    try:
        result = executor.execute(request, control, native)
        assert result.status == 'completed'
        assert len(published) == 1
    finally:
        delivered.set();transfers.close();server.shutdown();server.server_close();thread.join(timeout=2)


def test_coalesced_tool_ends_do_not_rehash_or_republish_unchanged_files(tmp_path, monkeypatch):
    from capstone_agent.incremental_artifacts import IncrementalArtifacts
    from capstone_agent.general_pi_storage import GeneralPiStorage
    from capstone_agent import general_pi_executor as files
    workspace = tmp_path / 'work';workspace.mkdir()
    (workspace / 'report.md').write_text('one version')
    request = PiTaskRequest('task_coalesce', 'attempt_files', 'direct', 'Report', (), (), {'engine':'pi'}, 10)
    storage = GeneralPiStorage(tmp_path / 'receipts');storage.save(request.to_document(), None)
    original, opens = files.open_workspace_file, []
    def opened(*args):opens.append(args);return original(*args)
    monkeypatch.setattr(files, 'open_workspace_file', opened)
    events = []
    capture = IncrementalArtifacts(workspace=workspace, request=request, identity={'engine':'pi'}, storage=storage, publish=events.append)
    capture.trigger();wait_until(lambda:len(events)==1)
    for _ in range(100):capture.trigger()
    capture.close()
    assert len(events) == 1 and len(opens) == 2  # hash + sealed copy, no repeated file reads


def test_capture_refuses_a_parent_symlink_swap_and_keeps_prior_versions(tmp_path):
    from capstone_agent.general_pi_storage import GeneralPiStorage
    from capstone_agent.general_pi_executor import collect_artifacts
    workspace = tmp_path / 'work';workspace.mkdir()
    folder = workspace / 'outputs';folder.mkdir()
    path = folder / 'report.md';path.write_text('safe')
    request = PiTaskRequest('task_safe', 'attempt_files', 'direct', 'Report', (), (), {'engine':'pi'}, 10)
    storage = GeneralPiStorage(tmp_path / 'receipts');storage.save(request.to_document(), None)
    first = collect_artifacts(workspace, request.task_id, request.parent_attempt_id)[0]
    storage.capture_artifact(request.task_id, workspace, first)
    path.write_text('new')
    second = collect_artifacts(workspace, request.task_id, request.parent_attempt_id)[0]
    folder.rename(tmp_path / 'moved')
    outside = tmp_path / 'outside';outside.mkdir();(outside / 'report.md').write_text('new')
    folder.symlink_to(outside, target_is_directory=True)
    with pytest.raises(OSError):storage.capture_artifact(request.task_id, workspace, second)
    assert storage.read_artifact(request.task_id, first['artifact_id']) == b'safe'
    assert [item['artifact_id'] for item in storage.captured_artifacts(request.task_id)] == [first['artifact_id']]


def test_restart_retains_captured_files_without_repeating_an_unknown_execution(tmp_path):
    from capstone_agent.general_pi_storage import GeneralPiStorage
    from capstone_agent.general_pi_executor import collect_artifacts
    workspace = tmp_path / 'tasks' / 'task_restart';workspace.mkdir(parents=True)
    (workspace / 'report.md').write_text('persisted before interruption')
    request = PiTaskRequest('task_restart', 'attempt_files', 'direct', 'Report', (), (), {'engine':'pi'}, 10)
    storage = GeneralPiStorage(tmp_path / 'receipts');storage.save(request.to_document(), None)
    captured = collect_artifacts(workspace, request.task_id, request.parent_attempt_id)[0]
    storage.capture_artifact(request.task_id, workspace, captured)
    host = GeneralPiHost(root=tmp_path, identity={'engine':'pi'},
        run_task=lambda *_:pytest.fail('unknown execution was repeated'))
    host.submit(request)
    result = host.read(request.task_id)['result']
    assert result['status'] == 'failed' and result['artifacts'] == [captured]
    assert host.read_artifact(request.task_id, captured['artifact_id']) == b'persisted before interruption'


@pytest.mark.parametrize('change', ['task', 'parent', 'identity', 'completion'])
def test_running_capture_rejects_foreign_identity_and_completion_claims(change):
    from capstone_agent.native_artifact_projection import project_native_artifact_capture
    from capstone_agent.native_product_roles import file_artifact_id
    from test_native_artifact_projection import claim
    request = PiTaskRequest('task_bound', 'attempt_files', 'direct', 'Report', (), (), {'engine':'pi'}, 10)
    digest = sha256(b'report').hexdigest()
    event = {'type':'native_artifact_captured','schema':'capstone-pi-artifact-capture/1',
        'task_id':request.task_id,'parent_attempt_id':request.parent_attempt_id,'executor_identity':{'engine':'pi'},
        'artifact':{'artifact_id':file_artifact_id('report.md', digest),'task_id':request.task_id,
            'parent_attempt_id':request.parent_attempt_id,'kind':'workspace_file',
            'metadata':{'path':'report.md','sha256':digest,'size_bytes':6,'presentation_role':'primary'}}}
    projected = project_native_artifact_capture(claim(), request, event)[0]
    assert projected['source_status'] == 'running' and projected['presentation_role'] == 'primary'
    event = deepcopy(event)
    if change == 'task':event['task_id'] = 'foreign'
    elif change == 'parent':event['parent_attempt_id'] = 'foreign'
    elif change == 'identity':event['executor_identity'] = {'engine':'other'}
    else:event['artifact']['metadata']['delivery_status'] = 'completed'
    with pytest.raises(ValueError):project_native_artifact_capture(claim(), request, event)
