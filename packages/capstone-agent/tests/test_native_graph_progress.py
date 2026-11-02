"""Graph paths must come from the exact protected graph checkpoint."""
from copy import deepcopy
from hashlib import sha256
import json

import pytest


def graph_fixture(channel_binding=None, revision=2):
    task, command = 'task_graph', 'plan-graph'
    owner = {'thread_id': 'thread_graph', 'work_id': 'work_graph',
             'research_id': 'research_graph', 'goal_revision': 1}
    binding = {'schema_version': 'capability-research-channel/1.0',
               'run_id': 'run_graph', 'turn_id': 'turn_graph',
               'attempt_id': 'attempt_graph', 'research_id': 'research_graph',
               'cycle_owner': owner, 'graph_schema': 'capstone-enterprise-graph/2',
               **{name + '_tool_schema': {'additionalProperties': False}
                  for name in ('read', 'update', 'depth', 'progress')}}
    if channel_binding is not None:
        binding = {**channel_binding, 'cycle_owner': {**owner, 'research_id': channel_binding['research_id']},
                   'graph_schema': 'capstone-enterprise-graph/2'}
        owner = binding['cycle_owner']
    graph = {'schema': 'capstone-enterprise-graph/2', 'graph_ref': 'graph-version',
             'graph_revision': 1, 'goal': 'Compare sources', 'output_mode': 'text',
             'model_revision_reason': None, 'nodes': [], 'actions': [], 'results': []}
    public = {'type': 'enterprise_graph_progress', 'owner': owner,
              'attempt_id': binding['attempt_id'], 'task_id': task,
              'graph': graph, 'events': [{'kind': 'graph_committed', 'nodes': []}]}
    ref = ('runtime.checkpoint.' + sha256(task.encode()).hexdigest()[:20] + '.'
           + sha256(('call:' + command).encode()).hexdigest()[:24])
    saved = {'schema': 'capstone-enterprise-graph-checkpoint/1', 'runId': task,
             'command_id': command, 'committed_revision': revision,
             'snapshot': {'schema': 'capstone-enterprise-graph/2', 'owner': owner,
                          'attempt_id': binding['attempt_id']},
             'public_progress': public}
    view = {'research_revision': revision, 'state': {'notes': [
        {'note_id': ref, 'text': json.dumps(saved)}]}}
    event = {**public, 'checkpoint': {'ref': ref, 'revision': revision}}
    return binding, task, view, event


def test_graph_progress_requires_exact_committed_public_path():
    from capstone_agent.native_research_bridge import checked_graph_progress
    binding, task, view, event = graph_fixture()
    assert checked_graph_progress(event, binding=binding, task_id=task,
                                  attempt_id='attempt_graph', view=view) == event
    for field, value in [('graph', {**event['graph'], 'nodes': [{'id': 'invented'}]}),
                         ('events', []), ('attempt_id', 'another_attempt'),
                         ('task_id', 'another_task'),
                         ('checkpoint', {**event['checkpoint'], 'revision': 3})]:
        with pytest.raises(ValueError):
            checked_graph_progress({**event, field: value}, binding=binding,
                                   task_id=task, attempt_id='attempt_graph', view=view)
    missing = deepcopy(view)
    missing['state']['notes'] = []
    with pytest.raises(ValueError):
        checked_graph_progress(event, binding=binding, task_id=task,
                               attempt_id='attempt_graph', view=missing)


def test_graph_progress_cannot_enter_a_frozen_legacy_binding_or_alias_a_note():
    from capstone_agent.native_research_bridge import checked_graph_progress
    binding, task, view, event = graph_fixture()
    legacy = {key: value for key, value in binding.items() if key != 'graph_schema'}
    with pytest.raises(ValueError):
        checked_graph_progress(event, binding=legacy, task_id=task,
                               attempt_id='attempt_graph', view=view)
    forged = deepcopy(view)
    saved = json.loads(forged['state']['notes'][0]['text'])
    saved['command_id'] = 'another-command'
    forged['state']['notes'][0]['text'] = json.dumps(saved)
    with pytest.raises(ValueError):
        checked_graph_progress(event, binding=binding, task_id=task,
                               attempt_id='attempt_graph', view=forged)


def test_graph_control_tool_is_bound_to_its_own_saved_command():
    from capstone_agent.native_research_bridge import checked_graph_progress
    binding, task, view, event = graph_fixture()
    saved = json.loads(view['state']['notes'][0]['text'])
    control = {'tool_call_id': saved['command_id'], 'tool_name': 'agent_research_plan'}
    event['control'] = control
    saved['public_progress']['control'] = deepcopy(control)
    saved['commands'] = [{'id': saved['command_id'], 'operation': 'plan'}]
    view['state']['notes'][0]['text'] = json.dumps(saved)
    assert checked_graph_progress(event, binding=binding, task_id=task,
        attempt_id=binding['attempt_id'], view=view)['control'] == control
    saved['commands'][0]['operation'] = 'revise'
    view['state']['notes'][0]['text'] = json.dumps(saved)
    with pytest.raises(ValueError, match='control'):
        checked_graph_progress(event, binding=binding, task_id=task,
            attempt_id=binding['attempt_id'], view=view)


@pytest.mark.parametrize('forged', [False, True])
def test_graph_progress_crosses_the_actual_protected_host_channel(tmp_path, forged):
    import time
    from capstone_agent.attempt_research import AttemptResearch
    from capstone_agent.business_context import BusinessContext
    from capstone_agent.general_pi_server import GeneralPiHost
    from capstone_agent.native_research_bridge import WorkerResearchBridge, read_json
    from capstone_agent.pi_delegation import PiTaskRequest
    from capstone_agent.thread_protocol import ModelContextSnapshot
    worker = AttemptResearch(tmp_path / 'worker', thread_id='thread_graph', run_id='run_graph',
        attempt_id='attempt_graph', model_context=ModelContextSnapshot(
            'context_graph', 'model', 'revision:1', 'pandapower', 'selected_graph'),
        is_active=lambda: True, admit_reference=lambda _: False)
    binding, task, view, event = graph_fixture(
        read_json(worker.channel.root / 'binding.json'), revision=1)
    worker.controller.update({'request_id': 'commit-graph', 'expected_revision': 0,
        'changes': {'goal': 'Compare sources', 'notes': [{**view['state']['notes'][0], 'refs': []}]}})
    bridge = WorkerResearchBridge(worker.channel, owner_id='b' * 64, producer_binding=binding)
    sent = deepcopy(event)
    if forged:
        sent['graph']['nodes'] = [{'id': 'invented'}]
    def run(request, cancelled, emit):
        emit(sent)
        return 'Answer', {}
    host = GeneralPiHost(root=tmp_path / 'host', identity={'engine': 'pi'}, run_task=run)
    request = PiTaskRequest(task, binding['attempt_id'], 'direct', 'Compare sources', (), (), host.identity, 3,
        business_context=BusinessContext.empty('workspace', 0),
        resource_profile={'profile_id': 'direct_pi', 'revision': 'test'},
        input={'kind': 'text', 'text': 'Compare sources'}, research_binding=binding)
    host.submit(request)
    host.research_mirror(task).bootstrap('b' * 64, bridge.bootstrap())
    deadline = time.monotonic() + 3
    while host.read(task)['status'] == 'running' and time.monotonic() < deadline:
        time.sleep(.005)
    record = host.read(task)
    progress = [item for item in record['events'] if item['type'] == 'enterprise_graph_progress']
    assert record['result']['status'] == ('failed' if forged else 'completed'), record['result']
    assert [{key: value for key, value in item.items() if key != 'event_id'}
            for item in progress] == ([] if forged else [event])
    assert 'snapshot' not in str(progress) and 'public_progress' not in str(progress)


@pytest.mark.parametrize('channel,tool_name,accepted', [
    ('child', 'agent_task_return', True),
    ('parent', 'agent_task_return', False),
    ('child', 'unpublished_return', False),
])
def test_task_return_observation_crosses_the_host_only_for_the_exact_child_lease(tmp_path, channel, tool_name, accepted):
    import time
    from capstone_agent.attempt_research import AttemptResearch
    from capstone_agent.business_context import BusinessContext
    from capstone_agent.general_pi_server import GeneralPiHost
    from capstone_agent.native_research_bridge import WorkerResearchBridge, read_json
    from capstone_agent.pi_delegation import PiTaskRequest
    from capstone_agent.thread_protocol import ModelContextSnapshot
    worker = AttemptResearch(tmp_path / 'worker', thread_id='thread_graph', run_id='run_graph',
        attempt_id='attempt_graph', model_context=ModelContextSnapshot(
            'context_graph', 'model', 'revision:1', 'pandapower', 'selected_graph'),
        is_active=lambda: True, admit_reference=lambda _: False)
    binding, task, view, progress = graph_fixture(read_json(worker.channel.root / 'binding.json'), revision=1)
    owner = binding['cycle_owner']
    action = {'id': 'action-A', 'step_id': 'A', 'kind': 'execute', 'owner': owner,
              'attempt_id': binding['attempt_id'], 'execution_revision': 1, 'definition_ref': 'definition-A'}
    graph = progress['graph']
    graph.update(nodes=[{'id': 'A', 'execution': 'delegated' if channel == 'child' else 'parent'}], actions=[action])
    saved = json.loads(view['state']['notes'][0]['text'])
    saved['public_progress'] = {key: value for key, value in progress.items() if key != 'checkpoint'}
    saved['snapshot'].update(nodes=graph['nodes'], actions=[action], node_states={
        'A': {'execute_action_id': action['id'], 'execution_revision': 1, 'definition_ref': 'definition-A'}})
    view['state']['notes'][0]['text'] = json.dumps(saved)
    worker.controller.update({'request_id': 'commit-graph', 'expected_revision': 0,
        'changes': {'goal': 'Return useful work', 'notes': [{**view['state']['notes'][0], 'refs': []}]}})
    bridge = WorkerResearchBridge(worker.channel, owner_id='b' * 64, producer_binding=binding)
    source = 'native-observation:' + task + ':' + sha256(b'return-call').hexdigest()
    def run(request, cancelled, emit):
        workspace = tmp_path / 'native-workspace'
        workspace.mkdir()
        context = host.graph_context(request, workspace, 65534)
        emit(progress)
        output_dir = workspace / '.research-workers' / sha256(action['id'].encode()).hexdigest() if channel == 'child' else workspace
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / 'retained.txt').write_bytes(b'Useful files survive an observation failure')
        frozen = context.handle({'type': 'enterprise_graph_context_request', 'schema': 'capstone-enterprise-graph-context/1',
            'owner': owner, 'attempt_id': binding['attempt_id'], 'task_id': task, 'action_id': action['id'],
            'checkpoint': progress['checkpoint'], 'request_id': 'retain-before-return', 'operation': 'freeze',
            'selection': {'products': [{'path': 'retained.txt', 'role': 'support'}]}})
        assert frozen['ok'], frozen
        base = {key: progress[key] for key in ('owner', 'attempt_id', 'task_id', 'checkpoint')}
        base.update(action_id=action['id'], step_id='A')
        if channel == 'child':
            emit({**base, 'type': 'enterprise_graph_child_started', 'child_id': 'A'})
        emit({**base, 'type': 'enterprise_graph_tool_binding', 'tool_call_id': 'return-call', 'tool_name': tool_name})
        result = {'content': [{'type': 'text', 'text': 'Producer statement; independent review not performed'}],
                  'details': {'native_research_source': {'task_id': task, 'tool_call_id': 'return-call', 'source_ref': source}}}
        if channel == 'child':
            emit({**base, 'type': 'enterprise_graph_child_tool', 'child_id': 'A', 'activity': 'end',
                  'tool_call_id': 'return-call', 'tool_name': tool_name, 'result': result, 'is_error': False})
        else:
            emit({'type': 'tool_execution_end', 'toolName': tool_name, 'toolCallId': 'return-call',
                  'result': result, 'isError': False})
        return 'Retained with a limitation', {}
    failures = []
    def tracked_run(*args):
        try:
            return run(*args)
        except Exception as error:
            failures.append((type(error).__name__, str(error)))
            raise
    host = GeneralPiHost(root=tmp_path / 'host', identity={'engine': 'pi'}, run_task=tracked_run)
    request = PiTaskRequest(task, binding['attempt_id'], 'direct', 'Return useful work', (), (), host.identity, 3,
        business_context=BusinessContext.empty('workspace', 0), resource_profile={'profile_id': 'direct_pi', 'revision': 'test'},
        input={'kind': 'text', 'text': 'Return useful work'}, research_binding=binding)
    host.submit(request)
    host.research_mirror(task).bootstrap('b' * 64, bridge.bootstrap())
    deadline = time.monotonic() + 3
    while host.read(task)['status'] == 'running' and time.monotonic() < deadline:
        time.sleep(.005)
    record = host.read(task)
    assert record['result']['status'] == ('completed' if accepted else 'failed'), (record['result'], failures)
    assert len(record['result'].get('sources', [])) == int(accepted)
    artifacts = record['result']['artifacts']
    assert len(artifacts) == 1
    assert host.read_artifact(task, artifacts[0]['artifact_id']) == b'Useful files survive an observation failure'
    assert 'delivery_status' not in artifacts[0]['metadata']
    if accepted:
        assert record['result']['sources'][0]['metadata']['source_ref'] == source


def test_graph_delivery_uses_only_selected_current_results_and_inspected_bytes():
    from capstone_agent.native_product_roles import graph_delivery_presentation
    binding, task, view, event = graph_fixture()
    saved = json.loads(view['state']['notes'][0]['text'])
    digest, path, size = 'a' * 64, 'out/report.html', 42
    artifact = 'workspace-product:' + sha256(json.dumps(
        [path, digest, size], separators=(',', ':')).encode()).hexdigest()
    saved['products'] = [{'ref': artifact, 'path': path, 'sha256': digest, 'bytes': size,
                          'status': 'ready', 'owner': binding['cycle_owner'],
                          'attempt_id': binding['attempt_id'], 'action_id': 'make-report', 'roles': ['primary']}]
    product = saved['products'][0]
    saved['products'].insert(0, {**product, 'action_id': 'old-report', 'roles': ['reproduction']})
    saved['snapshot'].update(output_mode='files', results=[{
        'result_ref': 'result-v1', 'owner': binding['cycle_owner'], 'artifact_refs': [artifact],
        'producer': {'step_id': 'report', 'action_id': 'make-report', 'execution_revision': 1,
                     'attempt_id': binding['attempt_id']}}],
        node_states={'report': {'phase': 'success', 'applicability': 'current',
                     'execution_revision': 1, 'output_bindings': [{'result_ref': 'result-v1'}]}})
    saved['delivery'] = {'outcome': 'success', 'delivery_result_refs': ['result-v1'],
                         'delivery_product_refs': [artifact], 'limitations': [], 'summary': 'Report saved'}
    public_delivery = {'kind': 'graph_delivery_committed', **deepcopy(saved['delivery'])}
    saved['public_progress']['events'].append(public_delivery)
    def receipt():
        view['state']['notes'][0]['text'] = json.dumps(saved)
        return graph_delivery_presentation(view, task_id=task,
            attempt_id=binding['attempt_id'], binding=binding)
    result = receipt()
    assert result['delivery_status'] == 'completed'
    assert result['products'][0]['path'] == path
    assert result['products'][0]['sha256'] == digest
    assert result['checkpoint']['revision'] == event['checkpoint']['revision']
    product['owner'] = {**binding['cycle_owner'], 'work_id': 'other_work'}
    with pytest.raises(ValueError):
        receipt()
    product['owner'] = binding['cycle_owner']
    saved['snapshot']['node_states']['report']['applicability'] = 'stale'
    with pytest.raises(ValueError):
        receipt()
    saved['snapshot']['node_states']['report']['applicability'] = 'current'
    product['sha256'] = 'b' * 64
    with pytest.raises(ValueError):
        receipt()
    product['sha256'] = digest
    saved['delivery'].update(outcome='limited', limitations=['Inspect /private/report.txt; token=synthetic-secret'])
    public_delivery.update(outcome='limited', limitations=['Inspect [private reference]; [protected]'])
    assert receipt()['delivery_limitations'] == ['Inspect [private reference]; [protected]']
    diagnostic_path = 'out/diagnostic.txt'
    diagnostic_ref = 'workspace-product:' + sha256(json.dumps(
        [diagnostic_path, digest, size], separators=(',', ':')).encode()).hexdigest()
    saved['products'].append({**product, 'ref': diagnostic_ref, 'action_id': 'make-diagnostic',
                             'path': diagnostic_path, 'roles': ['reproduction']})
    saved['snapshot']['results'].append({'result_ref': 'diagnostic-v1', 'owner': binding['cycle_owner'],
        'artifact_refs': [diagnostic_ref], 'producer': {'step_id': 'diagnostic', 'action_id': 'make-diagnostic', 'execution_revision': 1,
                                                     'attempt_id': binding['attempt_id']}})
    saved['snapshot']['node_states']['diagnostic'] = {'phase': 'failure', 'applicability': 'current',
        'execution_revision': 1, 'output_bindings': [{'result_ref': 'diagnostic-v1'}]}
    for selection in (saved['delivery'], public_delivery):
        selection['delivery_result_refs'].append('diagnostic-v1')
        selection['delivery_product_refs'].append(diagnostic_ref)
    assert [item['presentation_role'] for item in receipt()['products']] == ['primary', 'reproduction']
    saved['products'][-1]['roles'] = ['primary']
    with pytest.raises(ValueError, match='primary'):
        receipt()
