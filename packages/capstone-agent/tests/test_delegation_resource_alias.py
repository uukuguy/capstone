"""Stable source aliases identify bytes; frozen target grants authorize reads."""
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
import json
from uuid import uuid4
import pytest

from capstone_agent.artifacts import MemoryObjectStore
from capstone_agent.continuation_resources import resource_reader_for
from capstone_agent.delegation_resources import grant_resources, granted_manifest, read_granted_resource
from capstone_agent.enterprise_context import WorkBinding
from capstone_agent.native_artifact_projection import artifact_object_key, project_native_artifact_capture
from capstone_agent.native_product_roles import file_artifact_id
from capstone_agent.pi_delegation import PiTaskRequest
from capstone_agent.thread_protocol import RunSnapshot
from capstone_agent.thread_service import InMemoryThreadService, ThreadNotFound
from test_enterprise_normal_chat import native_executor
from test_mission_continuation import reserved_review
from test_thread_postgres import _snapshot, postgres_thread_service
from test_thread_work_execution import command


@pytest.fixture(params=['memory', 'postgres'])
def resource_targets(request):
    """Memory storage uses real per-Thread ledgers behind their public read port."""
    workspace = 'resource_alias_' + uuid4().hex[:12]
    executor = native_executor()
    executor.capability['mission_schemas'] = ['capstone-native-mission/1']
    objects = MemoryObjectStore()
    stores = {}
    created = []
    if request.param == 'postgres':
        postgres, fixture_thread = request.getfixturevalue('postgres_thread_service')
    class MemoryThread(InMemoryThreadService):
        def require_workspace(self, thread_id, workspace_name='enterprise'):
            target = stores.get(thread_id)
            if target is None:
                raise ThreadNotFound(thread_id)
            return InMemoryThreadService.require_workspace(target, thread_id, workspace_name)
        def read_attempt_records(self, thread_id, attempt_id, **kwargs):
            target = stores.get(thread_id)
            if target is None:
                raise ThreadNotFound(thread_id)
            return InMemoryThreadService.read_attempt_records(target, thread_id, attempt_id, **kwargs)
    def create(name):
        thread_id = 'thr_alias_' + name + '_' + uuid4().hex[:10]
        snapshot = replace(_snapshot(thread_id), active_model_context=None, active_grid_page_id=None,
            minimum_protocol_version=2, run=RunSnapshot('run_alias_' + uuid4().hex[:16], 'open'))
        if request.param == 'memory':
            service = MemoryThread(snapshot, workspace_name=workspace)
            stores[thread_id] = service
        else:
            postgres.create_thread(snapshot, workspace_name=workspace)
            service = postgres
        service.set_native_executor(executor)
        service.set_material_store(objects)
        created.append((service, thread_id))
        return service, thread_id
    yield create, workspace, executor, objects
    if request.param == 'postgres':
        # This disposable fixture owns these exact rows, including unfinished
        # leased test Attempts. Never apply application deletion to active work.
        with postgres._connect() as connection:
            connection.execute('DELETE FROM capstone_threads WHERE workspace_name=%s AND thread_id=ANY(%s)',
                (workspace, [thread_id for _, thread_id in created]))
            connection.execute('DELETE FROM capstone_control_goals WHERE workspace=%s', (workspace,))


def saved_source(targets):
    create, workspace, executor, objects = targets
    service, thread_id = create('source')
    service.submit_command(command(service, thread_id, 'send_message', 'save_source',
        payload={'text': 'Save the immutable findings.'}))
    claim = service.claim_attempt('source_worker', 60)
    data = b'Immutable original bytes ' + uuid4().hex.encode()
    request = PiTaskRequest('task_alias_source', claim.attempt.attempt_id, 'direct', 'Save', (), (), executor.identity, 60)
    capture = project_native_artifact_capture(claim, request, {
        'type': 'native_artifact_captured', 'schema': 'capstone-pi-artifact-capture/1',
        'task_id': request.task_id, 'parent_attempt_id': request.parent_attempt_id,
        'executor_identity': dict(executor.identity), 'artifact': {
            'artifact_id': file_artifact_id('findings.txt', sha256(data).hexdigest()),
            'task_id': request.task_id, 'parent_attempt_id': request.parent_attempt_id,
            'kind': 'workspace_file', 'metadata': {'path': 'findings.txt',
                'sha256': sha256(data).hexdigest(), 'size_bytes': len(data)}}})[0]
    source = {**capture, 'source_status': 'completed'}
    objects.put(artifact_object_key(source), data, 'text/plain')
    service.append_runtime_event(claim, event_type='native_artifact_published', payload={'artifact': source})
    service.finish_attempt(claim, phase='completed', payload={'answer': 'Saved findings.'})
    return source, data


def test_real_review_and_child_share_source_alias_but_not_authority(resource_targets):
    create, workspace, executor, objects = resource_targets
    source, data = saved_source(resource_targets)
    review, review_thread = create('review')
    host, mission, intent, original = reserved_review((review, review_thread, workspace, executor), products=[source])
    review.submit_mission_review(intent)
    organizer = review.claim_attempt('review_worker', 60)
    review_manifest, = organizer.submission['_resource_manifests']
    assert b''.join(resource_reader_for(review, organizer)(review_manifest)) == data
    child, child_thread = create('child')
    objective = 'Inspect the admitted resource ' + review_manifest['resource_id']
    child.submit_command(command(child, child_thread, 'work_message', 'child_work', payload={'text': objective}))
    work = child.snapshot(child_thread).works[0]
    grants = grant_resources(child, workspace, child_thread, work['work_id'], 'delegation_alias', [source])
    child.submit_command(command(child, child_thread, 'start_work', 'start_child',
        work_id=work['work_id'], revision=work['revision']))
    following = child.claim_attempt('child_worker', 60)
    manifest, = following.submission['_resource_manifests']
    assert manifest['resource_id'] == review_manifest['resource_id']
    assert manifest['thread_id'] == child_thread != review_manifest['thread_id']
    assert following.instruction == objective
    assert following.task_context.binding.work_id != organizer.task_context.binding.work_id
    assert b''.join(resource_reader_for(child, following)(manifest)) == data
    with pytest.raises(ValueError):
        b''.join(resource_reader_for(child, following)(review_manifest))
    wrong_work = replace(following, task_context=replace(following.task_context,
        binding=WorkBinding(child_thread, 'work_ungranted', 'research-ungranted')))
    with pytest.raises(ValueError):
        b''.join(read_granted_resource(child, wrong_work, manifest))
    with pytest.raises(ValueError):
        b''.join(read_granted_resource(child, replace(following, workspace_name='other'), manifest))
    ungranted = replace(following, submission={**following.submission, '_delegation_resources': []})
    with pytest.raises(ValueError):
        b''.join(read_granted_resource(child, ungranted, manifest))
    with pytest.raises(ValueError):
        b''.join(read_granted_resource(child, following, {**manifest, 'sha256': 'f' * 64}))
    changed = granted_manifest(child_thread, work['work_id'], 'another_operation', {**source, 'sha256': 'f' * 64})
    assert changed['resource_id'] != manifest['resource_id']
    reader = resource_reader_for(child, following)
    reader.record_delivery('task_child_read', manifest)
    reader.record_delivery('task_child_read', manifest)
    assert len([event for event in child.read_events(child_thread, 0).events
                if event.event_type == 'delegation_input_delivered']) == 1


def legacy_manifest(thread_id, work_id, delegation_id, source):
    token = json.dumps([thread_id, work_id, delegation_id, source['thread_id'],
        source['attempt_id'], source['artifact_id'], source['sha256']], separators=(',', ':'))
    return {'schema': 'capstone-resource/1', 'version': 1,
        'resource_id': 'resource_' + sha256(token.encode()).hexdigest()[:32], 'thread_id': thread_id,
        **{key: source[key] for key in ('file_name', 'size_bytes', 'sha256')}}


def test_frozen_legacy_alias_replays_and_reads_without_migration(resource_targets, monkeypatch):
    import capstone_agent.delegation_resources as resources
    create, workspace, executor, objects = resource_targets
    source, data = saved_source(resource_targets)
    target, thread_id = create('legacy')
    target.submit_command(command(target, thread_id, 'work_message', 'legacy_work', payload={'text': 'Read original.'}))
    work = target.snapshot(thread_id).works[0]
    with monkeypatch.context() as patch:
        patch.setattr(resources, 'granted_manifest', legacy_manifest)
        previous = grant_resources(target, workspace, thread_id, work['work_id'], 'legacy_operation', [source])
    expected = legacy_manifest(thread_id, work['work_id'], 'legacy_operation', source)
    assert previous[0]['resource'] == expected
    assert expected['resource_id'] != granted_manifest(thread_id, work['work_id'], 'legacy_operation', source)['resource_id']
    assert grant_resources(target, workspace, thread_id, work['work_id'], 'legacy_operation', [source]) == previous
    assert len([event for event in target.read_events(thread_id, 0).events
                if event.event_type == 'delegation_resources_granted']) == 1
    target.submit_command(command(target, thread_id, 'start_work', 'legacy_start',
        work_id=work['work_id'], revision=work['revision']))
    claim = target.claim_attempt('legacy_reader', 60)
    manifest, = claim.submission['_resource_manifests']
    assert manifest == expected
    assert b''.join(resource_reader_for(target, claim)(manifest)) == data
    resource_reader_for(target, claim).record_delivery('task_legacy_read', manifest)
    assert len([event for event in target.read_events(thread_id, 0).events
                if event.event_type == 'delegation_input_delivered']) == 1
    with pytest.raises(ValueError):
        grant_resources(target, workspace, thread_id, work['work_id'], 'different_operation', [source])


def test_executor_staging_scopes_same_alias_by_task_and_checks_full_manifest(tmp_path):
    from capstone_agent.native_resource_staging import NativeResourceStaging
    store = NativeResourceStaging(tmp_path)
    source = {'thread_id': 'thr_source', 'attempt_id': 'attempt_source', 'artifact_id': 'artifact_source',
              'file_name': 'result.txt', 'size_bytes': 5, 'sha256': sha256(b'bytes').hexdigest()}
    one = granted_manifest('thr_review', 'work_review', 'review_one', source)
    two = granted_manifest('thr_child', 'work_child', 'delegation_two', source)
    assert one['resource_id'] == two['resource_id']
    store.control({'task_id': 'task_review', 'resource': one, 'operation': 'status'})
    store.control({'task_id': 'task_child', 'resource': two, 'operation': 'status'})
    with pytest.raises(ValueError):
        store.control({'task_id': 'task_review', 'resource': two, 'operation': 'status'})
