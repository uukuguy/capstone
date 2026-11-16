from copy import deepcopy
from dataclasses import replace
from hashlib import sha256

import pytest

from capstone_agent.agent_delegation import AgentDelegations
from capstone_agent.agent_delegation_store import PostgresDelegations
from capstone_agent.artifacts import MemoryObjectStore
from capstone_agent.continuation_resources import resource_reader_for
from capstone_agent.delegation_resources import grant_resources
from capstone_agent.native_artifact_projection import artifact_object_key, project_native_artifact_capture
from capstone_agent.native_product_roles import file_artifact_id
from capstone_agent.pi_delegation import PiTaskRequest
from test_agent_delegation import delegation
from test_enterprise_normal_chat import native_executor
from test_thread_postgres import _snapshot, postgres_thread_service
from test_thread_work_execution import command


@pytest.mark.parametrize('mode', ['single', 'goal'])
def test_fresh_thread_admits_original_bytes_without_copying_file_into_goal(postgres_thread_service, mode):
    service, source_thread = postgres_thread_service
    service.create_thread(replace(_snapshot(source_thread), active_model_context=None,
                                 active_grid_page_id=None, minimum_protocol_version=2))
    executor = native_executor()
    service.set_native_executor(executor)
    objects = MemoryObjectStore()
    service.set_material_store(objects)
    assert service.submit_command(command(service, source_thread, 'send_message', 'source',
                                          payload={'text': 'Save original'})).status == 'accepted'
    claim = service.claim_attempt('source-worker', 60)
    data = b'Original random bytes: 8ea41edbdbf30a241f832241d7a4103e'
    request = PiTaskRequest('task_source', claim.attempt.attempt_id, 'direct', 'Save', (), (), executor.identity, 60)
    captured = project_native_artifact_capture(claim, request, {
        'type': 'native_artifact_captured', 'schema': 'capstone-pi-artifact-capture/1',
        'task_id': request.task_id, 'parent_attempt_id': request.parent_attempt_id,
        'executor_identity': dict(executor.identity), 'artifact': {
            'artifact_id': file_artifact_id('draft.txt', sha256(data).hexdigest()),
            'task_id': request.task_id, 'parent_attempt_id': request.parent_attempt_id,
            'kind': 'workspace_file', 'metadata': {'path': 'draft.txt',
                'sha256': sha256(data).hexdigest(), 'size_bytes': len(data)}}})[0]
    source = {**captured, 'source_status': 'completed'}
    objects.put(artifact_object_key(source), data, 'text/plain')
    service.append_runtime_event(claim, event_type='native_artifact_published', payload={'artifact': source})
    service.finish_attempt(claim, phase='completed', payload={'answer': 'Saved original'})
    registry = PostgresDelegations(service.dsn)
    registry.initialize()
    agent = AgentDelegations(service, registry)
    d = {**delegation(), 'context_products': [source], 'mode': mode}
    binding = None
    try:
        binding = agent.delegate('enterprise', d)
        assert binding['thread_id'] != source_thread
        following = service.claim_attempt('next-worker', 60)
        assert following.thread_id == binding['thread_id']
        assert following.submission['input']['text'].startswith(d['objective'])
        manifest, = following.submission['_resource_manifests']
        assert manifest['thread_id'] == following.thread_id
        assert manifest['sha256'] == source['sha256']
        assert b''.join(resource_reader_for(service, following)(manifest)) == data
        # Directly swapping a source is not an admitted reference.
        forged = deepcopy(manifest)
        forged['sha256'] = 'f' * 64
        with pytest.raises(ValueError):
            b''.join(resource_reader_for(service, following)(forged))
        resource_reader_for(service, following).record_delivery('task_read', manifest)
        resource_reader_for(service, following).record_delivery('task_read', manifest)
        events = service.read_events(following.thread_id, 0).events
        delivered = [e for e in events if e.event_type == 'delegation_input_delivered']
        assert len(delivered) == 1
        assert delivered[0].payload['source']['thread_id'] == source_thread
        assert delivered[0].payload['resource'] == manifest
        forged_receipt = deepcopy(delivered[0].payload)
        forged_receipt['source']['sha256'] = 'f' * 64
        with pytest.raises(ValueError):
            service.append_runtime_event(following, event_type='delegation_input_delivered',
                                         payload=forged_receipt)
        service.finish_attempt(following, phase='completed', payload={'answer': 'Verified bytes'})
        # Scope is enforced again when granting another workspace's source.
        with pytest.raises(KeyError):
            grant_resources(service, 'other', binding['thread_id'], binding['work_id'], d['delegation_id'], [source])
    finally:
        if binding:
            service.delete_thread(binding['thread_id'])
        registry.delete('enterprise', d['operation_id'])
