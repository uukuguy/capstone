"""Selected registered capabilities reach the admitted native tool policy."""
from copy import deepcopy
from dataclasses import replace
import pytest

from capstone_agent.control_host import configure_control
from capstone_agent.mission_equipment import catalog, resolve
from capstone_agent.native_task_context import native_context_for
from test_enterprise_normal_chat import chat_store, native_executor
from test_thread_postgres import postgres_thread_service, _snapshot
from test_thread_work_execution import command
from test_mission_origin import request


def test_skill_selection_checks_exact_version_and_effective_tools():
    from capstone_agent.mission_equipment import resolve_skill

    skill = {'id': 'registered-check', 'kind': 'skill', 'version': 'v1',
             'ready': True, 'required_tools': ['read']}
    binding = {'capability': {'resource_profiles': {
        'delegated_pi': {'profile_id': 'delegated_pi', 'revision': 'catalog1', 'resources': [skill]},
    }}}
    assert resolve_skill(binding, {'id': skill['id'], 'revision': 'v1'}, {'read'}) == skill
    with pytest.raises(ValueError, match='version'):
        resolve_skill(binding, {'id': skill['id'], 'revision': 'other'}, {'read'})
    with pytest.raises(ValueError, match='tools'):
        resolve_skill(binding, {'id': skill['id'], 'revision': 'v1'}, {'write'})


def test_skill_publication_keeps_space_when_tools_fill_catalog(chat_store, monkeypatch):
    from capstone_agent import mission_equipment

    threads, thread = chat_store
    binding = {'capability': {'native_builtin_tools': [f'tool_{n}' for n in range(70)],
        'resource_profiles': {'delegated_pi': {'profile_id': 'delegated_pi', 'revision': 'r1',
            'resources': [{'id': 'registered-check', 'kind': 'skill', 'version': 'v1', 'ready': True}]}}}}
    monkeypatch.setattr(mission_equipment, 'origin_binding', lambda *_: (binding, None))
    published = catalog(threads, 'enterprise', {'thread_id': thread})
    assert len(published) == 64
    assert any(ref['kind'] == 'skill' and ref['id'] == 'registered-check' for ref in published)


def test_registry_selection_is_exact_and_unknown_revisions_fail(chat_store):
    threads, thread_id = chat_store
    threads.set_native_executor(native_executor())
    origin = {'thread_id': thread_id}
    entries = catalog(threads, 'enterprise', origin)
    read = next(ref for ref in entries if ref['kind'] == 'capability' and ref['id'] == 'read')
    selected = resolve(threads, 'enterprise', origin, [read], [])
    assert selected['allowed_tools'] == ['read']
    changed = {**read, 'revision': 'stale'}
    with pytest.raises(ValueError):
        resolve(threads, 'enterprise', origin, [changed], [])
    with pytest.raises(ValueError):
        resolve(threads, 'enterprise', origin, [{**read, 'kind': 'skill'}], [])
    with pytest.raises(ValueError):
        resolve(threads, 'enterprise', origin, [{**read, 'kind': 'resource'}], [])
    with pytest.raises(ValueError):
        resolve(threads, 'enterprise', origin, [read], [read])


def test_frozen_equipment_limits_real_native_context(chat_store):
    from capstone_agent.mission_equipment import bind_work
    threads, thread_id = chat_store
    threads.set_native_executor(native_executor())
    threads.submit_command(command(threads, thread_id, 'work_message', 'equipment_work',
        payload={'text': 'Read the supplied text only.'}))
    work = threads.snapshot(thread_id).works[0]
    origin = {'thread_id': thread_id, 'work_id': work['work_id']}
    read = next(ref for ref in catalog(threads, 'enterprise', origin)
                if ref['kind'] == 'capability' and ref['id'] == 'read')
    selected = resolve(threads, 'enterprise', origin, [read], [])
    bind_work(threads, 'enterprise', thread_id, work['work_id'], selected)
    work = threads.snapshot(thread_id).works[0]
    threads.submit_command(command(threads, thread_id, 'start_work', 'equipment_start',
        work_id=work['work_id'], revision=work['revision']))
    claim = threads.claim_attempt('selected_worker', 30)
    assert claim.submission['_mission_equipment'] == selected
    context = native_context_for(claim, claim.submission['_native_execution'])
    assert context['policy']['allowed_tools'] == ['read']
    assert context['mission_equipment'] == selected
    assert not {'bash', 'write', 'edit'} & set(context['policy']['allowed_tools'])
    drifted = deepcopy(claim.submission['_native_execution'])
    drifted['identity']['registry_revision'] = 'changed'
    with pytest.raises(ValueError):
        native_context_for(claim, drifted)
    from capstone_agent.thread_protocol import ThreadSnapshot
    snapshot = threads.snapshot(thread_id)
    assert ThreadSnapshot.from_document(snapshot.to_document()).works == snapshot.works
    with pytest.raises(ValueError):
        bind_work(threads, 'enterprise', thread_id, work['work_id'], {**selected, 'allowed_tools': ['bash']})


@pytest.mark.parametrize('invalid', ['agent', 'skill', 'resource', 'profile_restriction'])
def test_readiness_rejects_unregistered_agent_and_unimplemented_selection(chat_store, invalid):
    threads, thread_id = chat_store
    threads.set_native_executor(native_executor())
    host = configure_control(threads)
    mission = host.create_mission('enterprise', request(thread_id, 'unavailable_' + invalid))
    task = dict(task_id='inspect', objective='Inspect available material', delivery_requirements=['Return findings'],
        depends_on=[], agent_id='unregistered' if invalid == 'agent' else 'capstone', mode='single', max_attempts=1)
    if invalid in {'skill', 'resource'}:
        task['equipment'] = [{'schema': 'capstone-mission-equipment-reference/1', 'kind': invalid,
                              'id': 'unregistered', 'revision': 'unknown'}]
    if invalid == 'profile_restriction':
        task['restrictions'] = [next(ref for ref in catalog(threads, 'enterprise', mission['origin'])
                                     if ref['kind'] == 'resource_profile')]
    host.command_mission('enterprise', dict(schema='capstone-control-mission-command/1',
        operation_id='unavailable_plan', mission_id=mission['mission_id'], expected_revision=1,
        kind='update_plan', payload={'acceptance_criteria': ['Review findings'], 'tasks': [task]}))
    with pytest.raises(ValueError):
        host.command_mission('enterprise', dict(schema='capstone-control-mission-command/1',
            operation_id='unavailable_ready', mission_id=mission['mission_id'], expected_revision=2,
            kind='ready', payload={}))
    assert host.service.read_mission('enterprise', mission['mission_id'])['state'] == 'planning'


def test_postgres_control_dispatch_freezes_equipment_into_child_attempt(postgres_thread_service):
    threads, thread_id = postgres_thread_service
    threads.create_thread(replace(_snapshot(thread_id), active_model_context=None,
        active_grid_page_id=None, minimum_protocol_version=2))
    threads.set_native_executor(native_executor())
    host = configure_control(threads)
    mission = host.create_mission('enterprise', request(thread_id))
    origin = mission['origin']
    read = next(ref for ref in catalog(threads, 'enterprise', origin)
                if ref['kind'] == 'capability' and ref['id'] == 'read')
    task = dict(task_id='inspect', objective='Read existing material', delivery_requirements=['Return a bounded summary'],
        depends_on=[], agent_id='capstone', mode='single', max_attempts=1, equipment=[read])
    def control(kind, revision, payload):
        return host.command_mission('enterprise', dict(schema='capstone-control-mission-command/1',
            operation_id='equip_' + kind, mission_id=mission['mission_id'], expected_revision=revision,
            kind=kind, payload=payload))
    control('update_plan', 1, {'acceptance_criteria': ['Review the summary'], 'tasks': [task]})
    control('ready', 2, {})
    control('delegate_next', 3, {})
    goal = host.service.read('enterprise', mission['goal_id'])
    delegated = host.service.delegation_request('enterprise', mission['goal_id'],
        goal['tasks'][0]['delegation']['delegation_id'])
    assert delegated['schema'] == 'capstone-agent-delegation/2'
    binding = host.agent.delegate('enterprise', delegated)
    try:
        child = threads.snapshot(binding['thread_id'])
        with threads._connect() as connection:
            saved = connection.execute('SELECT submission_snapshot FROM capstone_thread_attempts WHERE attempt_id=%s',
                (child.current_attempt.attempt_id,)).fetchone()['submission_snapshot']
        assert saved['_mission_equipment']['allowed_tools'] == ['read']
        assert '_mission' not in saved  # The child has no Mission-controller grant.
    finally:
        with threads._connect() as connection:
            connection.execute('DELETE FROM capstone_threads WHERE thread_id=%s', (binding['thread_id'],))


def test_custom_origin_gateway_without_adapter_blocks_readiness(chat_store):
    threads, thread_id = chat_store
    threads.set_native_executor(native_executor())
    threads.select_thread_gateway(thread_id, {'connection_id': 'custom_connection',
        'instance_id': 'custom_instance', 'identity': {}})
    host = configure_control(threads)
    mission = host.create_mission('enterprise', request(thread_id, 'custom_source'))
    task = dict(task_id='inspect', objective='Use the selected source', delivery_requirements=['Return findings'],
        depends_on=[], agent_id='capstone', mode='single', max_attempts=1)
    host.command_mission('enterprise', dict(schema='capstone-control-mission-command/1',
        operation_id='custom_plan', mission_id=mission['mission_id'], expected_revision=1,
        kind='update_plan', payload={'acceptance_criteria': ['Review findings'], 'tasks': [task]}))
    with pytest.raises(ValueError):
        host.command_mission('enterprise', dict(schema='capstone-control-mission-command/1',
            operation_id='custom_ready', mission_id=mission['mission_id'], expected_revision=2,
            kind='ready', payload={}))
    assert host.service.read_mission('enterprise', mission['mission_id'])['state'] == 'planning'


    threads._native_executor.thread_gateway_publication = lambda binding=None, refresh=False: {
        'available': True, 'connection_id': 'wrong_connection', 'identity': {'instance_id': 'wrong_instance'}}
    with pytest.raises(ValueError, match='identity changed'):
        catalog(threads, 'enterprise', mission['origin'])


def test_postgres_child_inherits_registered_origin_gateway_not_global_default(postgres_thread_service):
    from capstone_agent.thread_gateway import publication_binding
    threads, thread_id = postgres_thread_service
    threads.create_thread(replace(_snapshot(thread_id), active_model_context=None,
        active_grid_page_id=None, minimum_protocol_version=2))
    def publication(name):
        return {'available': True, 'connection_id': 'connection_' + name,
            'identity': {'instance_id': 'instance_' + name}, 'catalog': {
                'revision': 'catalog_' + name, 'tools': {'source_' + name: {
                    'description': 'Inspect selected registered source',
                    'inputSchema': {'type': 'object', 'properties': {}}}}}}
    default, selected = publication('default'), publication('origin')
    executor = native_executor()
    executor.capability['data_gateway'] = default
    executor.thread_gateway_publication = lambda binding=None, refresh=False: deepcopy(
        selected if (binding or {}).get('connection_id') == selected['connection_id'] else default)
    threads.set_native_executor(executor)
    threads.select_thread_gateway(thread_id, publication_binding(selected, locked=True))
    host = configure_control(threads)
    mission = host.create_mission('enterprise', request(thread_id, 'inherit_source'))
    entries = catalog(threads, 'enterprise', mission['origin'])
    assert any(ref['id'] == 'source_origin' for ref in entries)
    assert not any(ref['id'] == 'source_default' for ref in entries)
    task = dict(task_id='inspect', objective='Use the originating registered source',
        delivery_requirements=['Return source-backed findings'], depends_on=[], agent_id='capstone',
        mode='single', max_attempts=1)
    for kind, revision, payload in [
        ('update_plan', 1, {'acceptance_criteria': ['Review findings'], 'tasks': [task]}),
        ('ready', 2, {}), ('delegate_next', 3, {})]:
        host.command_mission('enterprise', dict(schema='capstone-control-mission-command/1',
            operation_id='origin_' + kind, mission_id=mission['mission_id'], expected_revision=revision,
            kind=kind, payload=payload))
    goal = host.service.read('enterprise', mission['goal_id'])
    delegated = host.service.delegation_request('enterprise', mission['goal_id'],
        goal['tasks'][0]['delegation']['delegation_id'])
    assert delegated['schema'] == 'capstone-agent-delegation/2'
    binding = host.agent.delegate('enterprise', delegated)
    try:
        assert threads.read_thread_gateway(binding['thread_id'])['instance_id'] == 'instance_origin'
        child = threads.snapshot(binding['thread_id'])
        with threads._connect() as connection:
            saved = connection.execute('SELECT submission_snapshot FROM capstone_thread_attempts WHERE attempt_id=%s',
                (child.current_attempt.attempt_id,)).fetchone()['submission_snapshot']
        assert saved['_native_execution']['capability']['data_gateway']['identity']['instance_id'] == 'instance_origin'
        assert saved['_native_execution']['capability']['data_gateway']['catalog']['revision'] == 'catalog_origin'
    finally:
        with threads._connect() as connection:
            connection.execute('DELETE FROM capstone_threads WHERE thread_id=%s', (binding['thread_id'],))
