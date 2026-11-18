from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest

from capstone_agent.agent_delegation import AgentDelegations, DelegationConflict, DelegationRevoked
from capstone_agent.agent_delegation_store import MemoryDelegations, PostgresDelegations
from test_thread_postgres import postgres_thread_service


def delegation():
    token = uuid4().hex
    return dict(schema='capstone-agent-delegation/1', delegation_id='delegation_' + token,
        operation_id='delegation_' + token, goal_id='goal_test', goal_revision=1,
        task_id='draft', task_revision=1, generation=1, agent_id='capstone',
        binding=None, requested_control=None, objective='Save a draft',
        delivery_requirements=['draft.txt'], mode='single', max_attempts=1,
        deadline_at='2099-01-01T00:00:00Z', context_products=[])


def test_revocation_before_admission_is_persistent_and_does_not_create_thread():
    class NoThread:
        def create_thread(self, *args, **kwargs):
            pytest.fail('revoked delegation must not create a Thread')
    registry = MemoryDelegations()
    agent = AgentDelegations(NoThread(), registry)
    d = delegation()
    ack = agent.control('enterprise', d, 'cancel', 'cancel-1')
    assert ack['state'] == 'cancelled'
    restarted = AgentDelegations(NoThread(), registry)
    assert restarted.control('enterprise', d, 'cancel', 'cancel-1') == ack
    with pytest.raises(DelegationRevoked):
        restarted.delegate('enterprise', d)


def test_public_delegation_replays_after_restart_and_concurrent_calls(postgres_thread_service):
    threads, _ = postgres_thread_service
    registry = PostgresDelegations(threads.dsn)
    registry.initialize()
    agent = AgentDelegations(threads, registry)
    d = delegation()
    binding = None
    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            bindings = list(pool.map(lambda _: agent.delegate('enterprise', d), range(8)))
        binding = bindings[0]
        assert all(b == binding for b in bindings)
        restarted = AgentDelegations(threads, PostgresDelegations(threads.dsn))
        assert restarted.delegate('enterprise', d) == binding
        works = threads.snapshot(binding['thread_id']).works
        assert len(works) == 1 and works[0]['work_id'] == binding['work_id']
        # No runtime configured: a public blocked Work remains observable.
        assert restarted.observe('enterprise', {**d, 'binding': binding})['state'] == 'waiting'
        with pytest.raises(DelegationConflict):
            restarted.delegate('enterprise', {**d, 'objective': 'Changed objective'})
        with pytest.raises(DelegationConflict):
            restarted.observe('enterprise', {**d, 'binding': {**binding, 'work_id': 'forged'}})
        from test_thread_work_execution import command
        work = threads.snapshot(binding['thread_id']).works[0]
        changed = threads.submit_command(command(threads, binding['thread_id'], 'revise_goal', 'external-change',
            work_id=binding['work_id'], revision=work['revision'], payload={'text': 'Changed outside Control'}))
        assert changed.status == 'accepted'
        assert restarted.observe('enterprise', {**d, 'binding': binding})['state'] == 'unknown'
        ack = restarted.control('enterprise', {**d, 'binding': binding}, 'cancel', 'cancel-1')
        assert ack['state'] == 'cancelled'
    finally:
        if binding:
            threads.delete_thread(binding['thread_id'])
        registry.delete('enterprise', d['operation_id'])


def test_cross_workspace_delegation_identity_has_separate_thread(postgres_thread_service):
    threads, _ = postgres_thread_service
    registry = PostgresDelegations(threads.dsn)
    registry.initialize()
    agent = AgentDelegations(threads, registry)
    d = delegation()
    bindings = []
    try:
        for workspace in ['enterprise', 'other']:
            bindings.append((workspace, agent.delegate(workspace, d)))
        assert bindings[0][1]['thread_id'] != bindings[1][1]['thread_id']
        with pytest.raises(DelegationConflict):
            agent.observe('other', {**d, 'binding': bindings[0][1]})
    finally:
        for workspace, binding in bindings:
            threads.delete_thread(binding['thread_id'])
            registry.delete(workspace, d['operation_id'])


def test_mission_upload_grant_reads_frozen_version_after_replacement(postgres_thread_service):
    from capstone_agent.artifacts import MemoryObjectStore
    from capstone_agent.continuation_resources import resource_reader_for
    from capstone_agent.thread_resources import ResourceUploads
    from test_enterprise_normal_chat import native_executor
    from test_thread_postgres import _snapshot

    threads, origin = postgres_thread_service
    threads.create_thread(_snapshot(origin))
    threads.set_native_executor(native_executor())
    threads._material_objects = MemoryObjectStore()
    uploads = ResourceUploads(threads, threads._material_objects, chunk_bytes=4)
    uid = uploads.begin(origin, 'source.txt', 4, 'origin')['upload_id']
    uploads.part(origin, uid, 0, b'old!')
    source = uploads.complete(origin, uid)
    ref = dict(schema='capstone-mission-equipment-reference/1', kind='resource',
               id=source['resource_id'], revision='1')
    request = {**delegation(), 'schema': 'capstone-agent-delegation/2',
               'mission_origin': {'thread_id': origin}, 'equipment': [ref], 'restrictions': []}
    agent = AgentDelegations(threads, MemoryDelegations())
    with pytest.raises(KeyError):
        agent.delegate('other', request)
    binding = agent.delegate('enterprise', request)
    claim = None
    try:
        newer = uploads.begin(origin, 'source.txt', 4, 'new', resource_id=ref['id'],
                              expected_version=1)['upload_id']
        uploads.part(origin, newer, 0, b'new!')
        uploads.complete(origin, newer)
        claim = threads.claim_attempt('mission-version-test', 60)
        assert claim is not None and claim.thread_id == binding['thread_id']
        manifest, = claim.submission['_resource_manifests']
        assert manifest['resource_id'] == ref['id'] and manifest['version'] == 1
        assert b''.join(resource_reader_for(threads, claim)(manifest)) == b'old!'
        with pytest.raises(ValueError, match='not admitted'):
            list(resource_reader_for(threads, claim)({**manifest, 'version': 2}))
    finally:
        if claim is not None:
            threads.finish_attempt(claim, phase='cancelled', payload={})
        threads.delete_thread(binding['thread_id'])


def test_mission_skill_delegation_uses_typed_invocation(postgres_thread_service):
    from test_enterprise_normal_chat import native_executor
    from test_thread_postgres import _snapshot

    threads, origin = postgres_thread_service
    threads.create_thread(_snapshot(origin))
    executor = native_executor()
    profile = executor.capability['resource_profiles']['delegated_pi']
    profile['resources'] = [{'id': 'write-clear', 'kind': 'skill', 'version': '1.0.0',
        'source': 'registered-fixture', 'roles': ['delegated_pi'], 'enabled': True,
        'installed': True, 'ready': True, 'reason': None, 'required_tools': [], 'loaded_identity': 'c' * 64}]
    profile['load_receipt']['skills'] = {'write-clear': 'c' * 64}
    threads.set_native_executor(executor)
    ref = dict(schema='capstone-mission-equipment-reference/1', kind='skill', id='write-clear', revision='1.0.0')
    req = {**delegation(), 'schema': 'capstone-agent-delegation/2',
           'mission_origin': {'thread_id': origin}, 'equipment': [ref], 'restrictions': []}
    agent = AgentDelegations(threads, MemoryDelegations())
    binding = agent.delegate('enterprise', req)
    try:
        assert agent.delegate('enterprise', req) == binding
        from capstone_agent.intent_runtime import IntentRuntimeFactory
        from capstone_agent.thread_worker import run_pending_attempt

        outcome = run_pending_attempt(threads, IntentRuntimeFactory(None, None, None, general_executor=executor),
            worker_id='mission-skill-test', implementation_family='native')
        assert outcome.status == 'completed'
        native = executor.requests[0].to_document()
        assert native['input']['kind'] == 'skill_invocation'
        assert native['input']['skill_id'] == ref['id']
        assert native['input']['skill_version'] == ref['revision']
        assert native['resource_profile']['revision'] == profile['revision']
    finally:
        threads.delete_thread(binding['thread_id'])


def test_goal_pause_resume_retains_work_and_consumed_budget(postgres_thread_service):
    from test_enterprise_normal_chat import native_executor
    threads, _ = postgres_thread_service
    threads.set_native_executor(native_executor())
    registry = PostgresDelegations(threads.dsn)
    registry.initialize()
    agent = AgentDelegations(threads, registry)
    d = {**delegation(), 'mode': 'goal', 'max_attempts': 3}
    binding = agent.delegate('enterprise', d)
    d['binding'] = binding
    try:
        first = threads.claim_attempt('pause-test', 60)
        assert first is not None
        assert agent.control('enterprise', d, 'pause', 'pause-1')['state'] == 'running'
        threads.finish_attempt(first, phase='cancelled', payload={})
        paused = agent.control('enterprise', d, 'pause', 'pause-1')
        assert paused['state'] == 'paused'
        resumed = agent.control('enterprise', d, 'resume', 'resume-1')
        assert resumed['state'] == 'running'
        assert agent.control('enterprise', d, 'resume', 'resume-1') == resumed
        second = threads.claim_attempt('resume-test', 60)
        assert second is not None and second.attempt.attempt_id != first.attempt.attempt_id
        goal = threads.snapshot(binding['thread_id']).works[0]['goal_mode']
        assert goal['attempts_admitted'] == 2
        assert goal['max_attempts'] == 3
        assert second.task_context.binding.work_id == binding['work_id']
        agent.control('enterprise', d, 'cancel', 'cancel-1')
        threads.finish_attempt(second, phase='cancelled', payload={})
        assert agent.control('enterprise', d, 'cancel', 'cancel-1')['state'] == 'cancelled'
    finally:
        threads.delete_thread(binding['thread_id'])
        registry.delete('enterprise', d['operation_id'])
