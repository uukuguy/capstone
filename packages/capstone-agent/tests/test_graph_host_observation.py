"""Exercise the protected host path from committed lease to sealed observation."""
from hashlib import sha256
import json
import time
from pathlib import Path
import pytest

from test_native_graph_progress import graph_fixture


def run_graph_host(tmp_path, delegated, exercise, *, pre_progress=(), gateway=None, direct=False, native_context=None):
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
    binding, task, view, event = graph_fixture(read_json(worker.channel.root / 'binding.json'), revision=1)
    action = {'id': 'execute:A', 'kind': 'execute', 'step_id': 'A', 'owner': binding['cycle_owner'],
              'attempt_id': binding['attempt_id'], 'execution_revision': 1, 'definition_ref': 'definition:A'}
    saved = json.loads(view['state']['notes'][0]['text'])
    node = {'id': 'A', 'execution': 'delegated' if delegated else 'parent'}
    saved['snapshot'].update(actions=[action], nodes=[node], node_states={'A': {
        'execute_action_id': action['id'], 'execution_revision': 1, 'definition_ref': 'definition:A'}})
    event['graph'].update(nodes=[node], actions=[action])
    saved['public_progress'] = {key: value for key, value in event.items() if key != 'checkpoint'}
    view['state']['notes'][0]['text'] = json.dumps(saved)
    worker.controller.update({'request_id': 'commit-graph', 'expected_revision': 0,
        'changes': {'goal': 'Compare sources', 'notes': [{**view['state']['notes'][0], 'refs': []}]}})
    bridge = WorkerResearchBridge(worker.channel, owner_id='b' * 64, producer_binding=binding)

    class Runner:
        def __init__(self): self.gateway = gateway
        def bind_graph_context_provider(self, provider): self.provider = provider
        def __call__(self, request, cancelled, emit):
            if gateway is not None: gateway.bind(request.task_id, request.parent_attempt_id)
            for frame in pre_progress:
                emit(frame)
            workspace = tmp_path / 'host' / 'tasks' / task
            workspace.mkdir(parents=True, exist_ok=True)
            context = self.provider(request, workspace, 65534)
            if not direct: emit(event)
            base = {'owner': binding['cycle_owner'],
                  'attempt_id': binding['attempt_id'], 'task_id': task,
                  'action_id': action['id'], 'step_id': 'A', 'checkpoint': event['checkpoint']}
            if delegated:
                emit({**base, 'type': 'enterprise_graph_child_started', 'child_id': 'A'})
            private_handle = str(context.root / 'observations' / 'opaque')
            def call(call_id, *, error=False, bind=True, source='valid', text=None, status=None, result_error=False, tool_name='read', arguments=None, start=True, tamper=False):
                if direct and start:
                    emit({'type': 'tool_execution_start', 'toolCallId': call_id, 'toolName': tool_name})
                if bind and not direct:
                    emit({**base, 'type': 'enterprise_graph_tool_binding',
                          'tool_call_id': call_id, 'tool_name': tool_name})
                ref = 'native-observation:' + task + ':' + sha256(call_id.encode()).hexdigest()
                result = {'content': [{'type': 'text', 'text': text or 'Actual source bytes from ' + private_handle}]}
                if gateway is not None and tool_name.startswith('data_gateway_'):
                    import asyncio
                    response = asyncio.run(gateway.call(task, {'call_id': call_id, 'name': tool_name,
                                                             'arguments': {'scope_id': 'north'} if arguments is None else arguments}))
                    result = {'content': [{'type': 'text', 'text': response['result_json']}],
                              'details': response['observation']}
                    if tamper: result['content'][0]['text'] = 'Invented gateway output'
                if result_error:
                    result['isError'] = True
                if source != 'missing':
                    result.setdefault('details', {})['native_research_source'] = {'task_id': task,
                        'tool_call_id': call_id, 'source_ref': ref if source == 'valid' else 'forged'}
                if status:
                    emit({**base, 'type': 'enterprise_graph_tool_failure', 'tool_call_id': call_id,
                          'tool_name': tool_name, 'status': status})
                if delegated:
                    emit({**base, 'type': 'enterprise_graph_child_tool', 'child_id': 'A',
                          'activity': 'end', 'tool_call_id': call_id, 'tool_name': tool_name,
                          'args': {'path': private_handle}, 'result': result, 'is_error': error})
                else:
                    emit({'type': 'tool_execution_end', 'toolCallId': call_id, 'toolName': tool_name,
                          'args': {'path': private_handle}, 'result': result, 'isError': error})
                return ref, result
            exercise(call, context, action, private_handle)
            return 'Answer', {}

    host = GeneralPiHost(root=tmp_path / 'host', identity={'engine': 'pi'}, run_task=Runner())
    if direct: host.capability['native_tools'] = ['read', 'bash']
    request = PiTaskRequest(task, binding['attempt_id'], 'direct', 'Compare sources', (), (), host.identity, 3,
        business_context=BusinessContext.empty('workspace', 0),
        resource_profile={'profile_id': 'direct_pi', 'revision': 'test'},
        input={'kind': 'text', 'text': 'Compare sources'}, research_binding=binding, native_context=native_context)
    host.submit(request)
    host.research_mirror(task).bootstrap('b' * 64, bridge.bootstrap())
    deadline = time.monotonic() + 3
    while host.read(task)['status'] == 'running' and time.monotonic() < deadline: time.sleep(.005)
    return host, task, action


def direct_native_context(*, adaptive=True):
    context = json.loads((Path(__file__).parent / 'fixtures/research-policy-deployed-context.json').read_text())
    context['policy']['allowed_tools'] = ['read']
    if adaptive:
        from capstone_agent.native_task_context import registered_research_policy
        context['policy']['system_policy'] = registered_research_policy('1.19.0').system_policy
        context['graph_work'] = {'edition': 'capstone-graph-work/1', 'started_at_ms': 1}
    return context


def test_direct_host_seals_success_without_graph_action(tmp_path):
    def exercise(call, context, action, private_handle):
        ref, result = call('direct-call')
        receipt = context.handle({'type': 'enterprise_graph_context_request',
            'schema': 'capstone-enterprise-graph-context/1', 'owner': context.owner,
            'attempt_id': context.attempt_id, 'task_id': context.task_id,
            'request_id': 'selected-direct', 'operation': 'direct_sources', 'selection': {'source_refs': [ref]}})
        assert receipt['ok'], receipt
        source, = receipt['result']['sources']
        assert json.loads(Path(source['path']).read_bytes()) == result
        assert ref not in context.observations
    host, task, _ = run_graph_host(tmp_path, False, exercise, direct=True, native_context=direct_native_context())
    result = host.read(task)['result']
    assert result['status'] == 'completed', result
    source, = result['sources']
    assert source['metadata']['execution_mode'] == 'direct'
    assert 'action_id' not in source['metadata']


@pytest.mark.parametrize('options', [{'source': 'forged'}, {'start': False}, {'tool_name': 'bash'}])
def test_direct_host_rejects_unowned_observations(tmp_path, options):
    host, task, _ = run_graph_host(tmp_path, False, lambda call, *_: call('invalid', **options),
        direct=True, native_context=direct_native_context())
    assert host.read(task)['result']['status'] == 'failed'


def test_direct_host_failure_cannot_be_promoted(tmp_path):
    def exercise(call, context, *_):
        ref, _ = call('failed', error=True, source='missing')
        assert ref not in context.direct_observations
    host, task, _ = run_graph_host(tmp_path, False, exercise, direct=True, native_context=direct_native_context())
    result = host.read(task)['result']
    assert result['status'] == 'completed', result
    assert 'source_ref' not in result['sources'][0]['metadata']


def test_legacy_policy_does_not_enable_direct_graph_observations(tmp_path):
    host, task, _ = run_graph_host(tmp_path, False, lambda call, *_: call('legacy-direct'),
        direct=True, native_context=direct_native_context(adaptive=False))
    assert host.read(task)['result']['status'] == 'failed'


@pytest.mark.parametrize('tamper', [False, True])
def test_direct_gateway_keeps_exact_host_receipt_validation(tmp_path, tamper):
    from capstone_agent.data_gateway_relay import DataGatewayAccess
    from test_grid_source_topology import Gateway
    client = Gateway()
    gateway = DataGatewayAccess(client, client.catalog)
    native = direct_native_context()
    native['policy']['allowed_tools'] = ['data_gateway_get_network_topology_view']
    def exercise(call, context, *_):
        ref, _ = call('direct-gateway', tool_name='data_gateway_get_network_topology_view', tamper=tamper)
        assert ref in context.direct_observations
    host, task, _ = run_graph_host(tmp_path, False, exercise, direct=True, native_context=native, gateway=gateway)
    result = host.read(task)['result']
    assert result['status'] == ('failed' if tamper else 'completed'), result


@pytest.mark.parametrize('delegated', [False, True])
@pytest.mark.parametrize('mode', ['ready', 'preparing', 'wrong-model', 'tampered'])
def test_electrical_open_hint_requires_ready_receipt_bound_current_call(tmp_path, delegated, mode):
    from capstone_agent.data_gateway_relay import DataGatewayAccess
    from test_grid_source_topology import Gateway
    tool = 'data_gateway_open_network_model_view'
    client = Gateway()
    client.catalog['tools'][tool] = {}
    client.catalog['tool_hashes'][tool] = 'schema-open'
    client.data = {'schema':'gateway-electrical-view/1','state':'ready','model_ref':'grid:test',
        'model_revision':'rev1','selection_ref':'sel1','source_snapshot_ref':'snap1','view_ref':'view1',
        'representation':'source_node_breaker','target':None,'artifact_ref':None,
        'capture':{'source_transaction_consistency_verified':False},
        'streams':{stream:{'total_count':0,'read':{'tool':'read_network_model_view',
            'arguments':{'view_ref':'view1','stream':stream}}} for stream in
            ['devices','ports','connectivity_nodes','connections','device_relations','groups','boundaries','issues']}}
    if mode == 'preparing': client.data.update(state='preparing', preparation_ref='prepare1')
    if mode == 'wrong-model': client.data['model_ref'] = 'grid:other'
    gateway = DataGatewayAccess(client, client.catalog)
    native = direct_native_context()
    native['policy']['allowed_tools'] = [tool]
    def exercise(call, *_):
        call('open-view', tool_name=tool, arguments={'model_ref':'grid:test'}, tamper=mode=='tampered')
    host, task, _ = run_graph_host(tmp_path, delegated, exercise, direct=not delegated,
        native_context=native if not delegated else None, gateway=gateway)
    saved = host.read(task)
    assert saved['result']['status'] == ('failed' if mode == 'tampered' else 'completed'), saved['result']
    hints = [event['source_view'] for event in saved['events'] if 'source_view' in event]
    assert len(hints) == (1 if mode == 'ready' else 0)
    if hints:
        assert hints[0] == {key:client.data[key] for key in ['model_ref','model_revision','selection_ref',
            'source_snapshot_ref','view_ref','representation','target','artifact_ref']} | {
                'schema':'capstone-electrical-view-request/1','source_id':'data-gateway'}


@pytest.mark.parametrize('delegated', [False, True])
@pytest.mark.parametrize('level', ['station','equipment'])
@pytest.mark.parametrize('selectors,expected', [({},None),({'voltage_min_kv':None},None),({'voltage_min_kv':330},330)])
def test_gateway_source_hint_survives_committed_parent_and_child_graph_publication(tmp_path, delegated,level,selectors,expected):
    from capstone_agent.data_gateway_relay import DataGatewayAccess
    from test_grid_source_topology import Gateway
    client=Gateway()
    client.data.update(level=level,selected_object_id='station:01121100000001')
    gateway=DataGatewayAccess(client,client.catalog)
    def exercise(call, context, action, private_handle):
        call('gateway-view',tool_name='data_gateway_get_network_topology_view',arguments={
            'scope_id':'north','level':level,'selected_object_id':'station:01121100000001',**selectors})
    host,task,_=run_graph_host(tmp_path,delegated,exercise,gateway=gateway)
    saved=host.read(task)
    assert saved['result']['status']=='completed',saved['result']
    hints=[event for event in saved['events'] if 'source_view' in event]
    assert len(hints)==1
    assert hints[0]['source_view']['scope_name']=='North'
    assert hints[0]['source_view']['voltage_min_kv']==expected
    assert hints[0]['source_view']['level']==level
    assert hints[0]['source_view']['selected_object_id']=='station:01121100000001'
    assert hints[0]['tool_call_id']=='gateway-view'
    if delegated:
        assert hints[0]['type']=='enterprise_graph_child_tool'
        assert hints[0]['task_id']==task and hints[0]['attempt_id']=='attempt_graph'


def test_child_unknown_gateway_model_tool_rejection_is_a_failed_diagnostic_not_task_abort(tmp_path):
    """SDK stopUnenteredTools binds unknown-tool failure before any execution."""
    observed={}
    def exercise(call, context, action, private_handle):
        ref,_=call('unknown-model',tool_name='data_gateway_discover_network_models',
            error=True,result_error=True,source='missing',status='failed',text='Tool is not available in this session.')
        assert ref not in context.observations
        valid,_=call('corrective-read')
        observed['valid']=valid
        assert valid in context.observations
    host,task,_=run_graph_host(tmp_path,True,exercise)
    result=host.read(task)['result']
    assert result['status']=='completed',result
    failed=[source for source in result['sources'] if source['metadata'].get('status')=='failed']
    assert len(failed)==1 and 'source_ref' not in failed[0]['metadata']
    assert failed[0]['metadata']['tool_name']=='data_gateway_discover_network_models'
    assert any(event.get('type')=='enterprise_graph_child_tool' and event.get('tool_name')=='data_gateway_discover_network_models'
               and event.get('is_error') is True for event in host.read(task)['events'])


@pytest.mark.parametrize('error,source,status',[(False,'valid',None),(True,'valid','failed'),(True,'missing',None)])
def test_unknown_child_tool_cannot_claim_execution_or_unrecorded_sdk_failure(tmp_path,error,source,status):
    def exercise(call, context, action, private_handle):
        call('unknown-model',tool_name='data_gateway_discover_network_models',
             error=error,result_error=error,source=source,status=status)
    host,task,_=run_graph_host(tmp_path,True,exercise)
    assert host.read(task)['result']['status']=='failed'


@pytest.mark.parametrize('delegated', [False, True])
def test_host_seals_real_call_bound_observation_before_next_frame(tmp_path, delegated):
    def exercise(call, context, action, private_handle):
        source, _ = call('read-source')
        assert source in context.observations
        assert context.observations[source]['action_id'] == action['id']
    host, task, action = run_graph_host(tmp_path, delegated, exercise)
    result = host.read(task)['result']
    assert result['status'] == 'completed', result
    assert len(result['sources']) == 1
    assert result['sources'][0]['metadata']['action_id'] == action['id']
    public_events = host.read(task)['events']
    assert '.contexts' not in json.dumps(public_events)
    assert 'opaque' not in json.dumps(public_events)


@pytest.mark.parametrize('delegated', [False, True])
@pytest.mark.parametrize('corrective', [False, True])
def test_host_retains_failed_diagnostic_without_grant_and_can_continue(tmp_path, delegated, corrective):
    diagnostic = {}
    def exercise(call, context, action, private_handle):
        text = 'ENOENT: ' + private_handle + '\n' + 'complete diagnostic\n' * 300
        ref, result = call('failed-read', error=True, source='missing', text=text)
        diagnostic.update(result=result, ref=ref)
        assert ref not in context.observations
        if corrective:
            good_ref, _ = call('corrective-read')
            assert context.observations[good_ref]['action_id'] == action['id']
    host, task, action = run_graph_host(tmp_path, delegated, exercise)
    result = host.read(task)['result']
    assert result['status'] == 'completed', result
    failed = result['sources'][0]
    assert failed['metadata']['action_id'] == action['id']
    assert failed['metadata']['status'] == 'failed'
    assert 'source_ref' not in failed['metadata']
    body = host.storage.root / 'observations' / task / (failed['source_id'] + '.json')
    assert json.loads(body.read_bytes()) == diagnostic['result']
    assert failed['metadata']['output_sha256'] == sha256(body.read_bytes()).hexdigest()
    assert len(result['sources']) == 1 + corrective
    assert len(host._tasks[task]['research_sources']) == int(corrective)
    public = json.dumps(host.read(task)['events'])
    assert 'ENOENT' in public
    assert '.contexts' not in public and 'opaque' not in public
    assert len(public) < len(body.read_bytes())


def test_host_unexecuted_argument_error_has_no_bogus_action_or_source(tmp_path):
    def exercise(call, context, action, private_handle):
        call('invalid-arguments', error=True, bind=False, source='missing', text='Invalid read offset')
        assert not context.observations
        call('valid-correction')
    host, task, action = run_graph_host(tmp_path, False, exercise)
    result = host.read(task)['result']
    assert result['status'] == 'completed', result
    assert len(result['sources']) == 1
    assert result['sources'][0]['metadata']['tool_call_id'] == 'valid-correction'


def test_host_unexecuted_argument_error_before_first_progress_can_continue(tmp_path):
    frame = {'type': 'tool_execution_end', 'toolCallId': 'before-plan', 'toolName': 'read',
        'isError': True, 'result': {'content': [{'type': 'text', 'text': 'Invalid arguments: path required'}], 'details': {}}}
    host, task, action = run_graph_host(tmp_path, False,
        lambda call, *_: call('corrective-read'), pre_progress=[frame])
    result = host.read(task)['result']
    assert result['status'] == 'completed', result
    assert len(result['sources']) == 1
    assert result['sources'][0]['metadata']['tool_call_id'] == 'corrective-read'
    assert result['sources'][0]['metadata']['action_id'] == action['id']
    assert host._tasks[task]['graph_events'].action_for_call('before-plan', 'read', required=False) is None


@pytest.mark.parametrize('error,claimed_source', [(False, False), (False, True), (True, True)])
def test_host_pre_progress_success_or_claimed_source_fails_closed(tmp_path, error, claimed_source):
    result = {'content': [{'type': 'text', 'text': 'Unexecuted result'}], 'details': {}}
    if claimed_source:
        result['details']['native_research_source'] = {'task_id': 'task_graph', 'tool_call_id': 'before-plan',
            'source_ref': 'native-observation:task_graph:' + sha256(b'before-plan').hexdigest()}
    frame = {'type': 'tool_execution_end', 'toolCallId': 'before-plan', 'toolName': 'read', 'isError': error, 'result': result}
    host, task, _ = run_graph_host(tmp_path, False, lambda call, *_: call('corrective-read'), pre_progress=[frame])
    result = host.read(task)['result']
    assert result['status'] == 'failed'
    assert result['failure']['code'] == 'native_execution_error'
    assert result['sources'] == []


def test_host_explicit_parent_error_result_projects_failed_public_status(tmp_path):
    host, task, _ = run_graph_host(tmp_path, False,
        lambda call, *_: call('explicit-error', error=False, result_error=True, source='missing', text='Actual explicit error'))
    result = host.read(task)['result']
    assert result['status'] == 'completed', result
    assert result['sources'][0]['metadata']['status'] == 'failed'
    end = next(event for event in host.read(task)['events'] if event.get('type') == 'tool_execution_end')
    assert end['is_error'] is True


@pytest.mark.parametrize('delegated', [False, True])
@pytest.mark.parametrize('source', ['missing', 'forged'])
def test_host_successful_missing_or_forged_source_still_fails_closed(tmp_path, delegated, source):
    host, task, _ = run_graph_host(tmp_path, delegated,
        lambda call, *_: call('purported-success', source=source))
    result = host.read(task)['result']
    assert result['status'] == 'failed'
    assert result['failure']['code'] == 'native_execution_error'
    assert result['sources'] == []


@pytest.mark.parametrize('delegated', [False, True])
def test_host_abort_retains_exact_cancelled_diagnostic_without_public_private_frame(tmp_path, delegated):
    host, task, action = run_graph_host(tmp_path, delegated,
        lambda call, *_: call('aborted-read', error=True, source='missing', status='cancelled', text='Operation aborted'))
    result = host.read(task)['result']
    assert result['status'] == 'completed', result
    assert result['sources'][0]['metadata']['status'] == 'cancelled'
    assert result['sources'][0]['metadata']['action_id'] == action['id']
    assert 'enterprise_graph_tool_failure' not in json.dumps(host.read(task)['events'])


@pytest.mark.parametrize('delegated', [False, True])
def test_host_failed_call_body_cannot_change_on_replay(tmp_path, delegated):
    def exercise(call, *_):
        call('failed-read', error=True, source='missing', text='ENOENT: original')
        call('failed-read', error=True, source='missing', text='ENOENT: different')
    host, task, _ = run_graph_host(tmp_path, delegated, exercise)
    result = host.read(task)['result']
    assert result['status'] == 'failed'
    assert result['failure']['code'] == 'native_execution_error'


@pytest.mark.parametrize('delegated', [False, True])
def test_host_forged_source_is_rejected_even_for_failed_call(tmp_path, delegated):
    host, task, _ = run_graph_host(tmp_path, delegated,
        lambda call, *_: call('failed-read', error=True, source='forged', text='ENOENT'))
    result = host.read(task)['result']
    assert result['status'] == 'failed'
    assert result['sources'] == []


@pytest.mark.parametrize('delegated', [False, True])
def test_host_same_call_body_cannot_change_failure_to_success(tmp_path, delegated):
    def exercise(call, context, *_):
        ref, _ = call('same-call', error=True, text='Actual diagnostic')
        assert ref not in context.observations
        call('same-call', error=False, text='Actual diagnostic')
    host, task, _ = run_graph_host(tmp_path, delegated, exercise)
    result = host.read(task)['result']
    assert result['status'] == 'failed'
    assert result['failure']['code'] == 'native_execution_error'
