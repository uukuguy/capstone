import json
from hashlib import sha256

import pytest

from capstone_agent.attempt_research import AttemptResearch
from capstone_agent.thread_protocol import ModelContextSnapshot
from test_thread_postgres import postgres_thread_service


def research(tmp_path, active=lambda: True):
    return AttemptResearch(tmp_path, thread_id='thr_bridge', run_id='run_bridge',
        attempt_id='attempt_bridge', model_context=ModelContextSnapshot(
            'ctx_bridge', 'model', 'revision:1', 'pandapower', 'sel_1'),
        is_active=active, admit_reference=lambda ref: ref == 'material:verified')


def test_binding_preserves_debug_mode_and_rejects_unknown_mode(tmp_path):
    from capstone_agent.native_research_bridge import checked_binding, read_json
    binding = read_json(research(tmp_path).channel.root / 'binding.json')
    assert checked_binding({**binding, 'runtime_limit_mode': 'debug'})['runtime_limit_mode'] == 'debug'
    with pytest.raises(ValueError, match='mode'):
        checked_binding({**binding, 'runtime_limit_mode': 'ignore'})


def test_bridge_file_capacity_keeps_debug_terminal_metadata(tmp_path):
    from capstone_agent.application_capacity import CapacityExceeded, initialize_capacity
    from capstone_agent.native_research_bridge import read_text, write_text
    source = tmp_path / 'large.txt'
    source.write_text('oversized')
    initialize_capacity(mode='debug')
    try:
        for action in (lambda: read_text(source, maximum=2),
                       lambda: write_text(tmp_path / 'output.txt', 'large', maximum=2)):
            with pytest.raises(CapacityExceeded) as caught:
                action()
            assert caught.value.to_document()['fatal'] is True
    finally:
        initialize_capacity()


def test_actual_host_returns_only_registered_research_integrity_error(tmp_path, monkeypatch):
    import threading
    from capstone_agent.general_pi_server import GeneralPiHost, make_server
    from capstone_agent.pi_delegation import HttpGeneralPiExecutor, PiHTTPFailure
    host = GeneralPiHost(root=tmp_path / 'host', identity={'engine': 'pi'}, run_task=lambda *_: ('unused', {}))
    def invalid(*_):
        raise ValueError('research transport file changed')
    monkeypatch.setattr(host, 'research_control', invalid)
    server = make_server(host, control_token='fixture-private', address=('127.0.0.1', 0))
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        executor = HttpGeneralPiExecutor(f'http://127.0.0.1:{server.server_port}',
            identity=host.identity, capability=host.capability, control_token='fixture-private')
        with pytest.raises(PiHTTPFailure) as caught:
            executor._call('POST', '/tasks/task_one/research', document={'operation': 'pending'},
                total_timeout=2, checkpoint=lambda: None, timeout=1, research_transport=True)
        assert caught.value.diagnostic['http_status'] == 400
        assert caught.value.diagnostic['protocol_code'] == 'research_transport_file_changed'
    finally:
        server.shutdown(); server.server_close(); thread.join(2)


def test_cycle_owner_binding_is_optional_exact_and_research_bound(tmp_path):
    from capstone_agent.native_research_bridge import checked_binding, read_json
    binding = read_json(research(tmp_path).channel.root / 'binding.json')
    assert 'cycle_owner' not in checked_binding(binding)
    owner = {'thread_id': 'thr_cycle', 'work_id': 'work_cycle',
             'research_id': binding['research_id'], 'goal_revision': 3}
    assert checked_binding({**binding, 'cycle_owner': owner})['cycle_owner'] == owner
    for invalid in [None, {**owner, 'research_id': 'other'}, {**owner, 'goal_revision': True},
                    {**owner, 'goal_revision': 0}, {**owner, 'work_id': ''},
                    {**owner, 'thread_id': '../escape'}, {**owner, 'extra': 'field'}]:
        with pytest.raises(ValueError):
            checked_binding({**binding, 'cycle_owner': invalid})


def _cycle_progress_fixture(tmp_path, worker=None):
    from capstone_agent.native_research_bridge import read_json
    binding = read_json((worker or research(tmp_path)).channel.root / 'binding.json')
    binding['cycle_owner'] = {'thread_id': 'thr_cycle', 'work_id': 'work_cycle',
                              'research_id': binding['research_id'], 'goal_revision': 1}
    call, task = 'cycle-call', 'cycle-task'
    ref = 'runtime.checkpoint.' + sha256(task.encode()).hexdigest()[:20] + '.' + sha256(('call:' + call).encode()).hexdigest()[:24]
    progress = {'step_id': 'read-sources', 'phase': 'started', 'text': 'Read the admitted sources'}
    action = 'cycle-' + 'a' * 64
    checkpoint = {'schema': 'capstone-enterprise-cycle-checkpoint/1', 'runId': task,
                  'snapshot': {'owner': binding['cycle_owner'], 'attempt_id': binding['attempt_id']},
                  'cycleCall': {'id': call, 'progress': [{'action_id': action, 'progress': progress}]}}
    view = {'research_revision': 2, 'state': {'notes': [{'note_id': ref, 'text': json.dumps(checkpoint)}]}}
    event = {'type': 'enterprise_cycle_progress', 'owner': binding['cycle_owner'],
             'attempt_id': binding['attempt_id'], 'action_id': action,
             'checkpoint': {'ref': ref, 'revision': 2}, 'progress': progress}
    return binding, task, view, event


def test_cycle_progress_requires_exact_host_owner_and_committed_checkpoint(tmp_path):
    from copy import deepcopy
    from capstone_agent.native_research_bridge import checked_cycle_progress
    binding, task, view, event = _cycle_progress_fixture(tmp_path)
    assert checked_cycle_progress(event, binding=binding, task_id=task,
                                  attempt_id=binding['attempt_id'], view=view) == event
    invalid = []
    for mutate in [lambda e: e['owner'].update(work_id='other'),
                   lambda e: e['owner'].update(goal_revision=True),
                   lambda e: e.update(attempt_id='other'),
                   lambda e: e['checkpoint'].update(revision=3),
                   lambda e: e['checkpoint'].update(revision=True),
                   lambda e: e['checkpoint'].update(ref='runtime.checkpoint.forged'),
                   lambda e: e['progress'].update(text='Uncommitted text'),
                   lambda e: e['progress'].update(phase='completed'),
                   lambda e: e.update(action_id='cycle-' + 'b' * 64),
                   lambda e: e.update(raw_context='PRIVATE'),
                   lambda e: e['progress'].update(raw_output='PRIVATE')]:
        changed = deepcopy(event)
        mutate(changed)
        invalid.append(changed)
    for changed in invalid:
        with pytest.raises(ValueError):
            checked_cycle_progress(changed, binding=binding, task_id=task,
                                   attempt_id=binding['attempt_id'], view=view)
    with pytest.raises(ValueError):
        checked_cycle_progress(event, binding=binding, task_id=task,
                               attempt_id=binding['attempt_id'], view={'research_revision': 2, 'state': None})


def test_cycle_progress_metadata_is_exactly_checkpoint_bound_and_capacity_checked(tmp_path):
    from copy import deepcopy
    from capstone_agent.native_research_bridge import checked_cycle_progress
    from capstone_agent.application_capacity import CapacityExceeded
    binding, task, view, event = _cycle_progress_fixture(tmp_path)
    metadata = {'questions': ['Which source is current?', 'Which rows are absent?'],
                'expected_outputs': ['A comparison with explicit gaps'], 'derived_from': ['finding-one'],
                'result_summary': 'The two supplied versions differ.',
                'next_action_reason': 'Resolve the source conflict before a recommendation.'}
    event['progress'].update(metadata)
    saved = json.loads(view['state']['notes'][0]['text'])
    saved['cycleCall']['progress'][0]['progress'] = deepcopy(event['progress'])
    view['state']['notes'][0]['text'] = json.dumps(saved)
    assert checked_cycle_progress(event, binding=binding, task_id=task,
        attempt_id=binding['attempt_id'], view=view)['progress'] == event['progress']
    for key, value in [('questions', 'not-an-array'), ('expected_outputs', [1]),
                       ('derived_from', [None]), ('result_summary', {}),
                       ('next_action_reason', ''), ('unknown_context', 'PRIVATE')]:
        forged = deepcopy(event)
        forged['progress'][key] = value
        with pytest.raises(ValueError):
            checked_cycle_progress(forged, binding=binding, task_id=task,
                attempt_id=binding['attempt_id'], view=view)
    changed = deepcopy(event)
    changed['progress']['questions'] = ['An uncommitted different question']
    with pytest.raises(ValueError, match='not committed'):
        checked_cycle_progress(changed, binding=binding, task_id=task,
            attempt_id=binding['attempt_id'], view=view)
    smaller = {**binding, 'runtime_limits': {**binding.get('runtime_limits', {}), 'research_question_count': 1}}
    with pytest.raises(CapacityExceeded) as raised:
        checked_cycle_progress(event, binding=smaller, task_id=task,
            attempt_id=binding['attempt_id'], view=view)
    assert raised.value.dimension == 'research_question_count'


def _branch_progress_fixture(tmp_path, worker=None):
    binding, task, view, cycle = _cycle_progress_fixture(tmp_path, worker=worker)
    saved = json.loads(view['state']['notes'][0]['text'])
    saved['snapshot']['pending_action'] = {'id': cycle['action_id'], 'kind': 'execute',
        'objective_id': 'read-sources', 'questions': ['Which source is current?', 'Which rows are absent?'],
        'expected_outputs': ['An integrated recommendation']}
    view['state']['notes'][0]['text'] = json.dumps(saved)
    branch = {'type': 'delegation_child_started', 'subordinate': True, 'owner': binding['cycle_owner'],
              'attempt_id': binding['attempt_id'], 'parent_action_id': cycle['action_id'],
              'parent_step_id': 'read-sources', 'parent_tool_call_id': 'delegate-call', 'child_id': 'source-version',
              'title': 'Compare source versions', 'questions': ['Which source is current?'],
              'expected_outputs': ['A local comparison, not the parent recommendation'], 'checkpoint': cycle['checkpoint']}
    return binding, task, view, branch


def test_child_diagnostics_are_projected_without_raw_frames_or_secrets(tmp_path):
    from capstone_agent.native_research_bridge import checked_branch_progress
    binding, task, view, branch = _branch_progress_fixture(tmp_path)
    kwargs = dict(binding=binding, task_id=task, attempt_id=binding['attempt_id'], view=view)
    event = {**branch, 'type': 'delegation_child_tool', 'activity': 'end',
             'tool_name': 'bash', 'tool_call_id': 'child-call', 'is_error': True,
             'args': {'command': 'python analysis.py'},
             'result': {'content': [{'type': 'text', 'text': 'ModuleNotFoundError: scipy'}]}}
    projected = checked_branch_progress(event, **kwargs)
    assert projected['tool_activity'] == {'operation': 'python analysis.py',
                                         'output_excerpt': 'ModuleNotFoundError: scipy'}
    assert 'args' not in projected and 'result' not in projected
    event['result']['content'][0]['text'] = 'api_key=private-value'
    assert 'private-value' not in json.dumps(checked_branch_progress(event, **kwargs))
    finished = {**branch, 'type': 'delegation_child_finished', 'status': 'failed',
                'result_summary': '', 'error': {'code': 'child_failed',
                'message': 'Connection reset; api_key=private-value'}}
    diagnostic = checked_branch_progress(finished, **kwargs)['error']['message']
    assert 'Connection reset' in diagnostic and 'private-value' not in diagnostic


def test_branch_response_timing_validates_host_binding_and_numeric_values(tmp_path):
    from capstone_agent.native_research_bridge import checked_branch_progress
    binding, task, view, branch = _branch_progress_fixture(tmp_path)
    event = {**branch, 'type': 'delegation_child_response', 'response_number': 1, 'response_ms': 1234}
    kwargs = dict(binding=binding, task_id=task, attempt_id=binding['attempt_id'], view=view)
    assert checked_branch_progress(event, **kwargs) == event
    for field, value in [('response_number', 0), ('response_number', True), ('response_ms', -1), ('response_ms', '12')]:
        with pytest.raises(ValueError, match='timing'):
            checked_branch_progress({**event, field: value}, **kwargs)


def test_review_branch_can_assess_only_with_host_review_grant(tmp_path):
    from capstone_agent.native_research_bridge import checked_branch_progress
    binding, task, view, branch = _branch_progress_fixture(tmp_path)
    saved = json.loads(view['state']['notes'][0]['text'])
    saved['snapshot']['pending_action']['kind'] = 'assess'
    view['state']['notes'][0]['text'] = json.dumps(saved)
    review = {**branch, 'review_mode': 'delivery'}
    kwargs = dict(binding=binding, task_id=task, attempt_id=binding['attempt_id'], view=view)
    assert checked_branch_progress(review, **kwargs, allow_delivery_review=True) == review
    finished = {**review, 'type': 'delegation_child_finished', 'status': 'completed',
                'result_summary': 'An independent textual review.'}
    assert checked_branch_progress(finished, **kwargs, allow_delivery_review=True) == finished
    for invalid in (branch, {**review, 'review_mode': 'arbitrary'},
                    {**review, 'questions': ['Unaccepted question']},
                    {**review, 'type': 'delegation_child_tool', 'activity': 'start',
                     'tool_name': 'bash', 'tool_call_id': 'tool-call'}):
        with pytest.raises(ValueError):
            checked_branch_progress(invalid, **kwargs, allow_delivery_review=True)
    with pytest.raises(ValueError):
        checked_branch_progress(review, **kwargs)


def test_branch_progress_requires_committed_parent_action_and_accepted_questions(tmp_path):
    from copy import deepcopy
    from capstone_agent.native_research_bridge import checked_branch_progress
    binding, task, view, branch = _branch_progress_fixture(tmp_path)
    assert checked_branch_progress(branch, binding=binding, task_id=task,
        attempt_id=binding['attempt_id'], view=view) == branch
    finished = {**branch, 'type': 'delegation_child_finished', 'status': 'failed',
                'result_summary': 'Partial child findings retained.',
                'error': {'code': 'child_failed', 'message': 'Child model response failed (model_transport).'}}
    assert checked_branch_progress(finished, binding=binding, task_id=task,
        attempt_id=binding['attempt_id'], view=view)['result_summary'] == finished['result_summary']
    for mutate in [lambda e: e['owner'].update(work_id='other'), lambda e: e.update(parent_action_id='cycle-' + 'b' * 64),
                   lambda e: e.update(parent_step_id='other'), lambda e: e.update(questions=['Unaccepted question']),
                   lambda e: e.update(expected_outputs=[]), lambda e: e.update(args='PRIVATE'),
                   lambda e: e['checkpoint'].update(revision=99), lambda e: e.update(subordinate=False)]:
        invalid = deepcopy(branch)
        mutate(invalid)
        with pytest.raises(ValueError):
            checked_branch_progress(invalid, binding=binding, task_id=task,
                attempt_id=binding['attempt_id'], view=view)


@pytest.mark.parametrize('kind,forged', [('cycle', False), ('cycle', True), ('branch', False), ('branch', True),
                                       ('branch-response', False), ('branch-response', True),
                                       ('branch-missing-parent', False), ('branch-changed-identity', False)])
def test_cycle_progress_crosses_real_committed_channel_and_host_projection(tmp_path, forged, kind):
    import time
    from copy import deepcopy
    from capstone_agent.business_context import BusinessContext
    from capstone_agent.general_pi_server import GeneralPiHost
    from capstone_agent.native_research_bridge import WorkerResearchBridge
    from capstone_agent.pi_delegation import PiTaskRequest
    branch_event = kind.startswith('branch')
    worker = research(tmp_path / 'worker')
    fixture = _branch_progress_fixture if branch_event else _cycle_progress_fixture
    binding, task, view, event = fixture(tmp_path / 'fixture', worker=worker)
    if kind == 'branch-response':
        event = {**event, 'type': 'delegation_child_response', 'response_number': 1, 'response_ms': 1200}
    worker.controller.update({'request_id': 'commit-cycle', 'expected_revision': 0,
        'changes': {'goal': 'Read sources', 'notes': [{**view['state']['notes'][0], 'refs': []}]}})
    bridge = WorkerResearchBridge(worker.channel, owner_id='a' * 64, producer_binding=binding)
    sent = deepcopy(event)
    sent['checkpoint']['revision'] = 1
    if forged:
        sent['owner']['work_id'] = 'other-work'
    def run(request, cancelled, emit):
        if branch_event and kind != 'branch-missing-parent':
            emit({'type': 'tool_execution_start', 'toolName': 'agent_delegate', 'toolCallId': sent['parent_tool_call_id']})
        emit(sent)
        if kind == 'branch-changed-identity':
            emit({**sent, 'title': 'A changed child task under the same identity'})
        return 'Answer', {}
    host = GeneralPiHost(root=tmp_path / 'host', identity={'engine': 'pi'}, run_task=run)
    request = PiTaskRequest(task, binding['attempt_id'], 'direct', 'Read sources', (), (), host.identity, 3,
        business_context=BusinessContext.empty('workspace', 0),
        resource_profile={'profile_id': 'direct_pi', 'revision': 'test'},
        input={'kind': 'text', 'text': 'Read sources'}, research_binding=binding)
    host.submit(request)
    host.research_mirror(task).bootstrap('a' * 64, bridge.bootstrap())
    deadline = time.monotonic() + 3
    while host.read(task)['status'] == 'running' and time.monotonic() < deadline:
        time.sleep(.005)
    record = host.read(task)
    progress = [item for item in record['events'] if item['type'] == sent['type']]
    assert record['result']['status'] == ('failed' if forged or kind in {'branch-missing-parent', 'branch-changed-identity'} else 'completed')
    if forged or kind == 'branch-missing-parent':
        assert progress == []
    else:
        assert [{key: value for key, value in item.items() if key != 'event_id'} for item in progress] == [sent]
        assert 'snapshot' not in str(progress) and 'raw_context' not in str(progress)


@pytest.mark.parametrize('has_owner', [False, True])
@pytest.mark.parametrize('profile_version,variant', [(None, 'default'), ('1.1.0', 'default'),
    ('1.2.0', 'default'), ('1.3.0', 'default'), ('1.3.0', 'initial-review'), ('1.4.0', 'default'), ('1.5.0', 'default'), ('1.6.0', 'default')])
def test_native_sdk_receives_only_accepted_cycle_owner_and_attempt(tmp_path, monkeypatch, has_owner, profile_version, variant):
    from threading import Event
    from types import SimpleNamespace
    import capstone_agent.general_pi_server as module
    from capstone_agent.business_context import BusinessContext
    from capstone_agent.pi_delegation import PiTaskRequest
    binding, task, _, _ = _cycle_progress_fixture(tmp_path / 'fixture')
    if not has_owner:
        del binding['cycle_owner']
    mirror = tmp_path / 'mirror'
    (mirror / 'requests').mkdir(parents=True)
    ready = Event()
    ready.set()
    monkeypatch.setattr(module.os, 'geteuid', lambda: 0)
    monkeypatch.setattr(module.os, 'chown', lambda *args: None)
    monkeypatch.setattr(module.os, 'chmod', lambda *args, **kwargs: None)
    captured = []
    def launch(**kwargs):
        kwargs['workspace'].mkdir(parents=True)
        (kwargs['workspace'].parent / ('.inputs-' + kwargs['workspace'].name)).mkdir()
        captured.append(kwargs['sdk_config'])
        return ('fixture',), {}
    class Process:
        def __init__(self, *args, **kwargs):
            self.usage = {}
        def run(self, *args, **kwargs):
            return 'Answer'
        def stop(self):
            pass
    monkeypatch.setattr(module, 'native_pi_launch', launch)
    monkeypatch.setattr(module, 'GeneralPiProcess', Process)
    root = tmp_path / 'host'
    (root / 'receipts').mkdir(parents=True)
    runner = module.NativeTaskRunner(root=root, config_root=tmp_path, command=('node', '/opt/pi/dist/cli.js'),
        model='offline', relay_origin='http://127.0.0.1:1')
    selected_settings = {'researchRuntime': {'deliveryReview': {'enabled': True, 'sourceExcerptChars': 31000}, 'gracefulExecutionClosure': True, 'custom_setting': 'retained'}}
    runner.resources = SimpleNamespace(profiles={'direct_pi': SimpleNamespace(revision='test')},
        task_config=lambda *args, **kwargs: {'settings': selected_settings, 'mcp': None})
    runner.bind_research_reader(lambda _: SimpleNamespace(root=mirror, ready=ready))
    native = None
    if profile_version is not None:
        from capstone_agent.native_conversation import executor_binding
        from capstone_agent.native_task_context import native_context_for
        from test_enterprise_normal_chat import native_executor
        from test_research_policy_compatibility import registered_binding
        selected = registered_binding(profile_version, variant)
        native = native_context_for(SimpleNamespace(submission=None, selected_task_reader=None), selected)
    request = PiTaskRequest(task, binding['attempt_id'], 'direct', 'Read sources', (), (), {'engine': 'pi'}, 3,
        business_context=BusinessContext.empty('workspace', 0),
        resource_profile={'profile_id': 'direct_pi', 'revision': 'test'},
        input={'kind': 'text', 'text': 'Read sources'}, research_binding=binding, native_context=native)
    runner(request, lambda: False, lambda _: None)
    if profile_version is not None:
        from enterprise_research import ResearchPolicy
        assert captured[0]['researchGuidance'] == ResearchPolicy(
            {'1.1.0': '1.0.0', '1.2.0': '1.1.0', '1.3.0': '1.2.0', '1.4.0': '1.3.0', '1.5.0': '1.4.0', '1.6.0': '1.5.0'}[profile_version],
            variant=variant).progress_guidance()
        assert captured[0]['applicationPolicy']['allowed_tools'] == native['policy']['allowed_tools']
        assert captured[0]['researchRuntime']['deliveryReview']['enabled'] is (profile_version in {'1.3.0', '1.4.0', '1.5.0', '1.6.0'})
        assert captured[0]['researchRuntime']['gracefulExecutionClosure'] is (profile_version in {'1.5.0', '1.6.0'})
        assert captured[0]['researchRuntime']['deliveryReview']['sourceExcerptChars'] == 31000
        assert captured[0]['researchRuntime']['custom_setting'] == 'retained'
        assert selected_settings['researchRuntime']['deliveryReview']['enabled'] is True
    if has_owner:
        assert captured[0]['researchOwner'] == binding['cycle_owner']
        assert captured[0]['researchAttemptId'] == binding['attempt_id']
        assert captured[0]['researchSources'] == []
    else:
        assert 'researchOwner' not in captured[0] and 'researchAttemptId' not in captured[0]


def test_research_capacity_override_crosses_worker_mirror_and_committed_channel(tmp_path):
    from capability_agent.application.research import ResearchController
    from capability_agent.runtime.research_channel import ResearchRequestChannel
    from capstone_agent.native_research_bridge import WorkerResearchBridge,ResearchMirror
    owner=research(tmp_path/'worker')
    limits={'research_goal_chars':2400000,'research_request_bytes':3000000,'research_response_bytes':3500000}
    controller=ResearchController(owner.controller.store,research_id=owner.controller.research_id,
        turn_id=owner.controller.turn_id,admit_reference=lambda _:False,runtime_limits=limits)
    channel=ResearchRequestChannel(controller,attempt_id='attempt-large',is_active=lambda:True,channel_root=tmp_path/'channel')
    bridge=WorkerResearchBridge(channel,owner_id='a'*64)
    mirror=ResearchMirror(tmp_path/'mirror',bridge.binding)
    mirror.bootstrap('a'*64,bridge.bootstrap())
    raw=json.dumps({'request_id':'large','expected_revision':0,'changes':{'goal':'x'*2200000}})+'\n'
    (mirror.root/'requests'/'large.json').write_text(raw)
    response=bridge.process(mirror.pending('a'*64))
    mirror.acknowledge('a'*64,response)
    assert controller.read().goal=='x'*2200000
    assert json.loads((mirror.root/'view.json').read_text())['state']['goal']==controller.read().goal
    assert response['receipts'][0]['status']=='committed'


def test_bridge_uses_original_channel_receipt_and_publishes_committed_view_first(tmp_path):
    from capstone_agent.native_research_bridge import WorkerResearchBridge, ResearchMirror
    owner = research(tmp_path / 'worker')
    bridge = WorkerResearchBridge(owner.channel, owner_id='a' * 64)
    mirror = ResearchMirror(tmp_path / 'mirror', bridge.binding)
    with pytest.raises(RuntimeError, match='not ready'):
        mirror.pending('a' * 64)
    mirror.bootstrap('a' * 64, bridge.bootstrap())
    raw = json.dumps({'request_id': 'request-one', 'expected_revision': 0,
        'changes': {'goal': 'Compare sources', 'claims': [{'claim_id': 'claim-one',
            'statement': 'First source agrees', 'status': 'supported', 'refs': ['material:verified']}]}}) + '\n'
    (mirror.root / 'requests' / 'request-one.json').write_text(raw)
    pending = mirror.pending('a' * 64)
    assert pending == [{'request_id': 'request-one', 'raw': raw}]
    response = bridge.process(pending)
    mirror.acknowledge('a' * 64, response)
    view = json.loads((mirror.root / 'view.json').read_text())
    ack = json.loads((mirror.root / 'receipts/request-one.json').read_text())
    assert view['research_revision'] == ack['receipt']['research_revision'] == 1
    assert ack['request_sha256'] == sha256(raw.encode()).hexdigest()
    assert owner.controller.read().claims[0].statement == 'First source agrees'
    assert bridge.process(pending) == response
    assert owner.controller.read().revision == 1
    owner.close(failed=False)
    assert bridge.process(pending) == response
    (mirror.root / 'requests/request-one.json').write_text(raw.replace('Compare sources', 'Changed goal'))
    with pytest.raises(ValueError, match='changed'):
        mirror.pending('a' * 64)
    with pytest.raises(RuntimeError, match='owner'):
        mirror.bootstrap('b' * 64, bridge.bootstrap())


def test_bridge_rejects_unadmitted_sources_and_closed_lease_without_new_revision(tmp_path):
    from capstone_agent.native_research_bridge import WorkerResearchBridge, ResearchMirror
    active = [True]
    owner = research(tmp_path / 'worker', lambda: active[0])
    bridge = WorkerResearchBridge(owner.channel, owner_id='a' * 64)
    mirror = ResearchMirror(tmp_path / 'mirror', bridge.binding)
    mirror.bootstrap('a' * 64, bridge.bootstrap())
    def submit(identity, changes):
        raw = json.dumps({'request_id': identity, 'expected_revision': 0, 'changes': changes}) + '\n'
        (mirror.root / 'requests' / (identity + '.json')).write_text(raw)
        response = bridge.process(mirror.pending('a' * 64))
        mirror.acknowledge('a' * 64, response)
        return json.loads((mirror.root / 'receipts' / (identity + '.json')).read_text())
    assert submit('request-forged', {'goal': 'Check', 'condition_refs': ['forged']})['code'] == 'research_reference_not_admitted'
    active[0] = False
    assert submit('request-closed', {'goal': 'Check'})['code'] == 'attempt_closed'
    assert owner.controller.read() is None


def test_mirror_rejects_changed_request_and_same_revision_content(tmp_path):
    from capstone_agent.native_research_bridge import WorkerResearchBridge, ResearchMirror
    owner = research(tmp_path / 'worker')
    bridge = WorkerResearchBridge(owner.channel, owner_id='a' * 64)
    mirror = ResearchMirror(tmp_path / 'mirror', bridge.binding)
    mirror.bootstrap('a' * 64, bridge.bootstrap())
    changed = bridge.bootstrap()
    changed['view']['state'] = {'invented': True}
    with pytest.raises(ValueError):
        mirror.bootstrap('a' * 64, changed)


def test_research_mirror_uses_existing_writable_task_mount_on_read_only_root(tmp_path, monkeypatch):
    import errno
    from pathlib import Path
    from capstone_agent.general_pi_server import GeneralPiHost
    from capstone_agent.native_research_bridge import WorkerResearchBridge
    from capstone_agent.pi_delegation import PiTaskRequest
    from capstone_agent.business_context import BusinessContext
    owner = research(tmp_path / 'worker')
    bridge = WorkerResearchBridge(owner.channel, owner_id='a' * 64)
    root = tmp_path / 'host'
    mkdir = Path.mkdir
    def mounted_mkdir(path, *args, **kwargs):
        if path == root / 'research' or (root / 'research') in path.parents:
            raise OSError(errno.EROFS, 'Read-only file system')
        return mkdir(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'mkdir', mounted_mkdir)
    host = GeneralPiHost(root=root, identity={'engine': 'pi'}, run_task=lambda *_: pytest.fail('No model execution'))
    request = PiTaskRequest('task-readonly', 'attempt_bridge', 'delegated', 'Check', (), (),
        host.identity, 1, business_context=BusinessContext.empty('workspace', 0),
        resource_profile={'profile_id': 'delegated_pi', 'revision': 'test'},
        input={'kind': 'text', 'text': 'Check'}, research_binding=bridge.binding)
    host.submit(request)
    try:
        assert host.research_mirror(request.task_id).root.parent == root / 'tasks'
    finally:
        host.cancel(request.task_id)


def test_research_image_uses_canonical_tools_and_binds_bridge_to_executor_identity():
    from pathlib import Path
    root = Path(__file__).resolve().parents[3]
    resources = root / 'packages/capstone-agent/src/capstone_agent/resources'
    for name in ('research-tools.mjs', 'model-request-capture.mjs', 'research-context-window.mjs'):
        assert (resources / name).read_bytes() == (root / 'packages/pi-capability-tools/src' / name).read_bytes()
    image = (root / 'deploy/general-pi.Dockerfile').read_text()
    assert 'COPY packages/pi-capability-tools/src/research-tools.mjs' in image
    assert 'COPY packages/capstone-agent/src/capstone_agent/native_document_types.py capstone_agent/native_document_types.py' in image
    source = (resources.parent / 'general_pi_server.py').read_text()
    assert "'native_research_bridge.py'" in source
    assert "'resources/general-research.mjs'" in source


@pytest.mark.parametrize('filler_count', [0, 63])
def test_native_observation_ref_cannot_alias_changed_bytes_with_reused_call_id(tmp_path, filler_count):
    import time
    from capstone_agent.general_pi_server import GeneralPiHost
    from capstone_agent.native_research_bridge import WorkerResearchBridge
    from capstone_agent.pi_delegation import PiTaskRequest
    from capstone_agent.business_context import BusinessContext
    owner = research(tmp_path / 'worker')
    bridge = WorkerResearchBridge(owner.channel, owner_id='a' * 64)
    source_ref = 'native-observation:task-alias:' + sha256(b'call-reused').hexdigest()
    def run(request, cancelled, emit):
        for text in ('original 42', 'changed 84'):
            emit({'type': 'tool_execution_end', 'toolName': 'read', 'toolCallId': 'call-reused',
                'result': {'content': [{'type': 'text', 'text': text}], 'details': {
                    'native_research_source': {'task_id': request.task_id,
                        'tool_call_id': 'call-reused', 'source_ref': source_ref}}}})
            if text == 'original 42':
                for number in range(filler_count):
                    call = 'filler-' + str(number)
                    emit({'type': 'tool_execution_end', 'toolName': 'read', 'toolCallId': call,
                        'result': {'content': [{'type': 'text', 'text': str(number)}], 'details': {
                            'native_research_source': {'task_id': request.task_id, 'tool_call_id': call,
                                'source_ref': 'native-observation:task-alias:' + sha256(call.encode()).hexdigest()}}}})
        return 'must not complete', {}
    host = GeneralPiHost(root=tmp_path / 'host', identity={'engine': 'pi'}, run_task=run)
    request = PiTaskRequest('task-alias', 'attempt_bridge', 'delegated', 'Check', (), (),
        host.identity, 2, business_context=BusinessContext.empty('workspace', 0),
        resource_profile={'profile_id': 'delegated_pi', 'revision': 'test'},
        input={'kind': 'text', 'text': 'Check'}, research_binding=bridge.binding)
    host.submit(request)
    host.research_mirror(request.task_id).bootstrap('a' * 64, bridge.bootstrap())
    deadline = time.monotonic() + 2
    while host.read(request.task_id)['status'] == 'running' and time.monotonic() < deadline:
        time.sleep(.01)
    assert host.read(request.task_id)['status'] == 'failed'
    assert len(host.research_control(request.task_id, {'operation': 'pending', 'owner': 'a' * 64})['source_refs']) == filler_count + 1


def test_research_receipt_is_not_blocked_by_public_event_backlog(tmp_path, monkeypatch):
    import time
    from types import SimpleNamespace
    import capstone_agent.pi_delegation as module
    from capstone_agent.native_research_bridge import WorkerResearchBridge
    from capstone_agent.business_context import BusinessContext
    from capstone_agent.request_intent import NodeControl
    owner = research(tmp_path / 'worker')
    real_bridge = WorkerResearchBridge(owner.channel, owner_id='a' * 64)
    published, acknowledged = [], []
    clock = [100.0]
    monkeypatch.setattr(module, 'time', SimpleNamespace(
        monotonic=lambda: clock[0], sleep=lambda seconds: clock.__setitem__(0, clock[0] + seconds)))
    bridge = SimpleNamespace(owner_id=real_bridge.owner_id, bootstrap=real_bridge.bootstrap,
        admit_sources=lambda refs: None, process=lambda requests: {'receipt': 'saved'})
    request = module.PiTaskRequest('research-task', 'attempt_bridge', 'delegated', 'Check', (), (),
        {'engine': 'pi'}, 30, business_context=BusinessContext.empty('workspace', 0),
        resource_profile={'profile_id': 'delegated_pi', 'revision': 'test'},
        input={'kind': 'text', 'text': 'Check'}, research_binding=real_bridge.binding)

    class Executor(module.HttpGeneralPiExecutor):
        pages = 0
        def _call(self, method, path, **kwargs):
            if path == '/tasks':
                return {'task_id': request.task_id}
            if method == 'GET':
                self.pages += 1
                if self.pages == 1:
                    return {'status': 'running', 'result': None, 'event_cursor': 20,
                        'events': [{'event_id': f'event-{i}', 'type': 'progress'} for i in range(1, 21)]}
                from test_pi_delegation import result_document
                return {'status': 'completed', 'result': result_document(request), 'events': [], 'event_cursor': 20}
            operation = kwargs['document']['operation']
            if operation == 'pending':
                return {'source_refs': [], 'requests': ['pending'] if published and not acknowledged else []}
            if operation == 'acknowledge':
                acknowledged.append(len(published))
            return {}

    def publish(event):
        published.append(event['event_id'])
        clock[0] += .1  # Slow durable projection; no wall-clock sleeps in this test.

    client = Executor('http://127.0.0.1:1', control_token='fixture', identity={'engine': 'pi'}, capability={})
    result = client.execute_with_research(request, NodeControl(lambda: None, time.monotonic() + 30), publish, bridge)
    assert result.status == 'completed'
    assert acknowledged and 0 < acknowledged[0] < 20
    assert published == [f'event-{i}' for i in range(1, 21)]


@pytest.mark.parametrize('receipt_delay', [0, 0.4])
@pytest.mark.parametrize('lost_response', [None, 'admission', 'bootstrap', 'acknowledge'])
def test_protected_http_research_bridge_commits_during_native_task_and_replays_terminal(tmp_path, receipt_delay, lost_response):
    import threading
    import time
    from capstone_agent.general_pi_server import GeneralPiHost, make_server
    from capstone_agent.native_research_bridge import WorkerResearchBridge
    from capstone_agent.pi_delegation import HttpGeneralPiExecutor, PiTaskRequest
    from capstone_agent.request_intent import NodeControl
    from capstone_agent.business_context import BusinessContext
    owner = research(tmp_path / 'worker')
    bridge = WorkerResearchBridge(owner.channel, owner_id='a' * 64)
    calls = []
    def run(request, cancelled, emit):
        calls.append(request.task_id)
        mirror = host.research_mirror(request.task_id)
        assert json.loads((mirror.root / 'view.json').read_text())['research_revision'] == 0
        raw = json.dumps({'request_id': 'request-live', 'expected_revision': 0,
            'changes': {'goal': 'Check uploaded facts'}}) + '\n'
        (mirror.root / 'requests/request-live.json').write_text(raw)
        deadline = time.monotonic() + 2
        while not (mirror.root / 'receipts/request-live.json').exists():
            assert not cancelled() and time.monotonic() < deadline
            time.sleep(.01)
        assert json.loads((mirror.root / 'view.json').read_text())['research_revision'] == 1
        return 'Checked facts', {}
    host = GeneralPiHost(root=tmp_path / 'host', identity={'engine': 'pi'}, run_task=run)
    research_control = host.research_control
    def delayed_control(*args, **kwargs):
        time.sleep(receipt_delay)
        return research_control(*args, **kwargs)
    host.research_control = delayed_control
    server = make_server(host, control_token='test-private', address=('127.0.0.1', 0))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        failures = []
        class CheckedExecutor(HttpGeneralPiExecutor):
            lost = False
            def _call(self, method, path, **kwargs):
                value = super()._call(method, path, **kwargs)
                operation = 'admission' if path == '/tasks' else (kwargs.get('document') or {}).get('operation')
                if lost_response is not None and operation == lost_response and not self.lost:
                    from capstone_agent.pi_delegation import PiTransportTimeout
                    self.lost = True
                    raise PiTransportTimeout('Pi transport deadline expired; task state is unknown')
                return value
            def execute_with_research(self, *args):
                try:
                    return super().execute_with_research(*args)
                except Exception as error:
                    failures.append(repr(error))
                    raise
        executor = CheckedExecutor('http://127.0.0.1:' + str(server.server_port),
            control_token='test-private', identity=host.identity, capability=host.capability, poll_interval_seconds=.01)
        request = PiTaskRequest('research-task', 'attempt_bridge', 'delegated', 'Check', (), (),
            host.identity, 3, business_context=BusinessContext.empty('workspace', 0),
            resource_profile={'profile_id': 'delegated_pi', 'revision': 'test'},
            input={'kind': 'text', 'text': 'Check'}, research_binding=bridge.binding)
        control = NodeControl(lambda: None, time.monotonic() + 5)
        result = executor.execute_with_research(request, control, lambda _: None, bridge)
        assert result.answer == 'Checked facts'
        assert owner.controller.read().revision == 1
        assert executor.execute_with_research(request, control, lambda _: None, bridge) == result
        assert calls == ['research-task']
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.parametrize('storage', ['memory', 'postgres'])
def test_real_sdk_research_updates_reach_next_model_request_and_original_files(tmp_path, monkeypatch, storage, request):
    from dataclasses import replace
    from pathlib import Path
    import shutil
    import threading
    import capstone_agent.general_pi_server as module
    from capstone_agent.general_pi_executor import GeneralPiProcess
    from capstone_agent.pi_delegation import HttpGeneralPiExecutor
    from capstone_agent.native_hosted_worker import native_runtime_factory
    from capstone_agent.thread_service import InMemoryThreadService
    from capstone_agent.thread_worker import run_pending_attempt
    from capstone_agent.artifacts import MemoryObjectStore
    from capstone_agent.thread_materials import upload_material
    from test_thread_postgres import _snapshot
    from test_enterprise_normal_chat import native_executor, command
    from capstone_agent.native_artifact_projection import read_native_artifact
    root = Path(__file__).resolve().parents[3]
    sdk = root / '.grid-agent/runtime/pi/source/packages/coding-agent/dist/index.js'
    assert sdk.is_file(), 'Run make install-pi before the pinned SDK acceptance'
    node = shutil.which('node')
    assert node is not None
    monkeypatch.setattr(module.os, 'geteuid', lambda: 0)
    monkeypatch.setattr(module.os, 'chown', lambda *args: None)
    chmod = module.os.chmod
    def local_chmod(path, mode, **kwargs):
        # macOS fixture has no root UID. Keep the host-owned mirror writable
        # by this test process; production uses real root/task UID separation.
        if '/host/tasks/.research-' in str(path) and mode == 0o550:
            mode = 0o750
        return chmod(path, mode, **kwargs)
    monkeypatch.setattr(module.os, 'chmod', local_chmod)
    class LocalProcess(GeneralPiProcess):
        def __init__(self, command, environment, workspace, *, uid=None):
            super().__init__(command, environment, workspace)
    monkeypatch.setattr(module, 'GeneralPiProcess', LocalProcess)
    launch = module.native_pi_launch
    fixture = Path(__file__).parent / 'fixtures/research-sdk-offline.mjs'
    def offline_launch(**kwargs):
        accepted = kwargs['sdk_config']
        assert set(accepted['researchOwner']) == {'thread_id', 'work_id', 'research_id', 'goal_revision'}
        assert accepted['researchAttemptId']
        assert set(accepted['researchSources']) == {
            *('material:' + item['material_id'] + ':' + item['sha256']
              for item in accepted.get('selectedTaskMaterials', [])),
            *(f"resource:{item['resource_id']}:{item['version']}:{item['sha256']}"
              for item in accepted.get('selectedResourceFiles', []))}
        argv, env = launch(**kwargs)
        return (node, str(fixture), argv[-1], str(Path(module.__file__).parent / 'resources/general-sdk.mjs')), env
    monkeypatch.setattr(module, 'native_pi_launch', offline_launch)
    config = tmp_path / 'config'
    config.mkdir()
    from capstone_agent.workbench_llm_profiles import ProfileRegistry
    runner = module.NativeTaskRunner(root=tmp_path / 'host', config_root=config,
        command=(node, str(sdk.with_name('cli.js'))), model='offline-research', relay_origin='http://127.0.0.1:1',
        llm_profiles=ProfileRegistry())
    published = native_executor()
    host = module.GeneralPiHost(root=tmp_path / 'host', identity=published.identity, run_task=runner)
    host.capability = {**published.capability, 'research_bridge_schemas': ['capstone-research-bridge/1']}
    host_failures = []
    real_control = host.research_control
    def checked_control(*args):
        try:
            return real_control(*args)
        except Exception as error:
            host_failures.append(repr(error))
            raise
    host.research_control = checked_control
    server = module.make_server(host, control_token='test-private', address=('127.0.0.1', 0))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        failures = []
        class CheckedExecutor(HttpGeneralPiExecutor):
            def execute_with_research(self, *args):
                try:
                    return super().execute_with_research(*args)
                except Exception as error:
                    failures.append(repr(error))
                    raise
        executor = CheckedExecutor('http://127.0.0.1:' + str(server.server_port),
            identity=host.identity, capability=host.capability, control_token='test-private', poll_interval_seconds=.01)
        thread_id = 'thr_research'
        if storage == 'postgres':
            store, thread_id = request.getfixturevalue('postgres_thread_service')
        snapshot = replace(_snapshot(thread_id), active_model_context=None,
            active_grid_page_id=None, minimum_protocol_version=2)
        if storage == 'memory':
            store = InMemoryThreadService(snapshot)
        else:
            store.create_thread(snapshot)
        store.set_native_executor(executor)
        objects = MemoryObjectStore()
        store.set_material_store(objects)
        upload_material(store, objects, snapshot.thread_id, 'source-a.csv', b'item,value\nA,42\n')
        upload_material(store, objects, snapshot.thread_id, 'source-b.csv', b'item,value\nA,84\n')
        assert store.submit_command(command(store, snapshot.thread_id, 'send_message', 'research',
            payload={'text': 'Compare the supplied values and write a report'})).status == 'accepted'
        factory = native_runtime_factory(executor, research_root=tmp_path / 'research')
        result = run_pending_attempt(store, factory, worker_id='research', implementation_family='native')
        assert result.status == 'completed', (failures, host_failures)
        assert '42 and 84' in result.answer
        events = store.read_events(snapshot.thread_id, 0).events
        revisions = [event.payload['research_revision'] for event in events if event.event_type == 'research_state_updated']
        assert revisions == [1, 2]
        progress = [event.payload['task_progress'] for event in events
            if event.event_type == 'runtime_event' and 'task_progress' in event.payload]
        assert progress and progress[0]['text'] == 'Compare both source versions'
        event = next(event for event in reversed(events) if event.event_type == 'native_artifact_published'
                     and event.payload['artifact']['file_name'] == 'comparison.md'
                     and event.payload['artifact']['source_status'] == 'completed')
        descriptor, data = read_native_artifact(store, executor, snapshot.thread_id,
            event.attempt_id, event.payload['artifact']['artifact_id'],
            expected_descriptor=event.payload['artifact'])
        assert b'A: 42\nB: 84' in data
        assert descriptor['source_status'] == 'completed'
        work = store.snapshot(snapshot.thread_id).works[0]
        assert store.submit_command(command(store, snapshot.thread_id, 'send_message', 'research-followup',
            work_id=work['work_id'], revision=work['revision'], payload={'text': 'Keep the previous claim and check the second source again'})).status == 'accepted'
        second = run_pending_attempt(store, factory, worker_id='research', implementation_family='native')
        assert second.status == 'completed', (failures, host_failures)
        assert 'Prior source-backed claim retained' in second.answer
        research_events = [event for event in store.read_events(snapshot.thread_id, 0).events
                           if event.event_type == 'research_state_updated']
        assert [event.payload['research_revision'] for event in research_events] == [1, 2, 3]
        claims = research_events[-1].payload['research_snapshot']['claims']
        assert len(claims) == 2 and claims[0]['status'] == 'refuted'
    finally:
        server.shutdown()
        server.server_close()
