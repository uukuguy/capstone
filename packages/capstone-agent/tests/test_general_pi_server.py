from pathlib import Path
import threading
import time

import httpx
import pytest

from capstone_agent.pi_delegation import PiTaskRequest, HttpGeneralPiExecutor
from capstone_agent.request_intent import NodeControl


@pytest.mark.parametrize('tool_name,grant,accepted', [
    ('agent_tool_search', True, True),
    ('agent_tool_load', True, True),
    ('agent_tool_search', False, False),
    ('agent_tool_load', False, False),
    ('agent_tool_unpublished', True, False),
    ('agent_tool_search', 'gateway', True),
    ('agent_tool_load', 'gateway', True),
    ('agent_tool_search', 'gateway-unavailable', False),
    ('agent_tool_unpublished', 'gateway', False),
])
def test_child_tool_discovery_observation_requires_its_exact_application_grant(tmp_path, monkeypatch, tool_name, grant, accepted):
    from dataclasses import replace
    from capstone_agent import general_pi_server as module
    from capstone_agent.native_task_context import POLICY_TEXT
    from test_native_graph_progress import test_task_return_observation_crosses_the_host_only_for_the_exact_child_lease

    class DiscoveryHost(module.GeneralPiHost):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.capability['native_tools'] = [tool_name]
            if isinstance(grant, str):
                self.gateway = object() if grant == 'gateway' else None
                self.capability['data_gateway'] = {'available': True, 'catalog': {'tools': {'data_gateway_fixture': {}}}}

        def submit(self, request):
            native = {'policy': {'schema': 'capstone-conversation-policy/1', 'system_policy': POLICY_TEXT,
                'allowed_tools': ['data_gateway_fixture'] if isinstance(grant, str) else [tool_name] if grant else [], 'external_lookup_enabled': False},
                'selected_task_records': [], 'selected_task_source': None, 'records_truncated': False}
            return super().submit(replace(request, native_context=native))

    monkeypatch.setattr(module, 'GeneralPiHost', DiscoveryHost)
    test_task_return_observation_crosses_the_host_only_for_the_exact_child_lease(
        tmp_path, 'child', tool_name, accepted)


@pytest.mark.parametrize('tool_name,publication,grant,accepted', [
    ('agent_diagnosis_guide', True, True, True),
    ('agent_diagnosis_record', True, True, True),
    ('agent_diagnosis_guide', False, False, False),
    ('agent_diagnosis_record', False, False, False),
    ('agent_diagnosis_guide', True, False, False),
    ('agent_diagnosis_record', True, False, False),
    ('agent_diagnosis_guide', 'host_mismatch', True, False),
    ('agent_diagnosis_record', 'host_mismatch', True, False),
    ('agent_diagnosis_unpublished', True, False, False),
])
def test_child_diagnosis_observation_uses_exact_host_publication_and_grant(
        tmp_path, monkeypatch, tool_name, publication, grant, accepted):
    from dataclasses import replace
    from capstone_agent import general_pi_server as module
    from capstone_agent.native_diagnosis import DIAGNOSIS_POLICY
    from capstone_agent.native_task_context import POLICY_TEXT
    from capstone_agent.native_research_bridge import SourceReceiptCache
    from test_native_graph_progress import test_task_return_observation_crosses_the_host_only_for_the_exact_child_lease

    # Reuse the full real-host sequence: committed checkpoint, delegated child
    # start, bound tool call, saved bytes, tool end, observation and source grant.
    hosts = []
    class DiagnosticHost(module.GeneralPiHost):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            if publication == 'host_mismatch':
                self.capability['systematic_diagnosis'] = {}
            hosts.append(self)

        def submit(self, request):
            native = {'policy': {'schema': 'capstone-conversation-policy/1', 'system_policy': POLICY_TEXT,
                'allowed_tools': [tool_name] if grant else [], 'external_lookup_enabled': False},
                'selected_task_records': [], 'selected_task_source': None, 'records_truncated': False,
                **({'systematic_diagnosis': DIAGNOSIS_POLICY} if publication else {})}
            return super().submit(replace(request, native_context=native))

    monkeypatch.setattr(module, 'GeneralPiHost', DiagnosticHost)
    test_task_return_observation_crosses_the_host_only_for_the_exact_child_lease(
        tmp_path, 'child', tool_name, accepted)
    host = hosts[0]
    result = host.read('task_graph')['result']
    pending = host.research_control('task_graph', {'operation': 'pending', 'owner': 'b' * 64})
    assert len(pending['source_refs']) == int(accepted)
    # This is the same source-receipt admission used by WorkerResearchBridge.
    # It has no tool-name bypass: only exact task-bound observation receipts pass.
    cache = SourceReceiptCache(tmp_path / 'accepted-sources.json', {'thread_id': 'thread_graph'})
    cache.accept(pending['source_refs'])
    assert len(cache.records) == int(accepted)
    if accepted:
        observation = result['sources'][0]
        assert observation['kind'] == 'native_tool_observation'
        assert observation['metadata']['tool_name'] == tool_name
        assert observation['metadata']['source_ref'] in cache.records


@pytest.mark.parametrize('version', ['1.12.0', '1.13.0', '1.14.0', '1.15.0', '1.16.0', '1.17.0', '1.18.0', '1.19.0', '1.20.0'])
def test_selected_work_publication_reaches_actual_native_sdk_config_with_trusted_attempt_origin(tmp_path, monkeypatch, version):
    import json
    from types import SimpleNamespace
    from capstone_agent import general_pi_server as module
    from capstone_agent.business_context import BusinessContext
    from capstone_agent.native_task_context import native_context_for, research_policy_capabilities
    from capstone_agent.native_conversation import executor_binding
    from test_enterprise_normal_chat import native_executor
    from test_native_graph_progress import graph_fixture
    executor = native_executor()
    gateway_publication = {'available': True, 'catalog': {'instructions': 'SERVICE_GUIDANCE_SENTINEL', 'revision': 'catalog-revision', 'tool_hashes': {
        'data_gateway_discover_network_models': 'hash-one', 'data_gateway_other': 'hash-two'}, 'tools': {
        'data_gateway_discover_network_models': {'name': 'discover_network_models'},
        'data_gateway_other': {'name': 'other'}}}}
    executor.capability = {**executor.capability, 'research_bridge_schemas': ['capstone-research-bridge/1'],
        'research_graph_schemas': ['capstone-enterprise-graph/2'], 'research_policy_profiles': research_policy_capabilities(),
        'data_gateway': gateway_publication}
    selected = executor_binding(executor, profile_version=version)
    native = native_context_for(SimpleNamespace(submission=None, selected_task_reader=None,
        started_at='2026-10-21T06:00:00Z'), selected)
    native['policy']['allowed_tools'].remove('data_gateway_other')
    binding, task, _, _ = graph_fixture()
    binding['graph_work_edition'] = 'capstone-graph-work/1'
    captured = []
    class Captured(Exception):
        pass
    def launch(**kwargs):
        captured.append(json.loads(json.dumps(kwargs['sdk_config'])))
        raise Captured()
    monkeypatch.setattr(module, 'native_pi_launch', launch)
    monkeypatch.setattr(module.os, 'geteuid', lambda: 0)
    root = tmp_path / 'private'
    (root / 'receipts').mkdir(parents=True)
    runner = module.NativeTaskRunner(root=root, config_root=tmp_path, command=('node', '/opt/pi/dist/cli.js'),
        model='fixture', relay_origin='http://127.0.0.1:8790')
    # Exercise the checked-in settings through the actual publication overlay,
    # rather than constructing researchRuntime flags only inside a fixture.
    settings_path = Path(__file__).resolve().parents[3] / 'configs/runtime/general-pi/settings.json'
    published_settings = json.loads(settings_path.read_text())
    runner.resources = SimpleNamespace(
        profiles={'direct_pi': SimpleNamespace(revision='test')},
        task_config=lambda *args, **kwargs: {'settings': published_settings, 'mcp': None})
    runner.environment_context = 'HOST VERIFIED ENVIRONMENT: offline libraries and report renderer'
    gateway_bindings = []
    runner.gateway = SimpleNamespace(publication=lambda: gateway_publication,
        bind=lambda *args: gateway_bindings.append(args), revoke=lambda *_: None)
    ready = threading.Event()
    ready.set()
    runner.bind_research_reader(lambda _: SimpleNamespace(root=tmp_path / 'channel', ready=ready))
    runner.bind_graph_context_provider(lambda *_: SimpleNamespace(root=tmp_path / 'contexts'))
    request = PiTaskRequest(task, binding['attempt_id'], 'direct', 'Prepare the useful requested output', (), (), {'engine': 'pi'}, 1800,
        business_context=BusinessContext.empty('workspace', 0), resource_profile={'profile_id': 'direct_pi', 'revision': 'test'},
        input={'kind': 'text', 'text': 'Prepare the useful requested output'}, native_context=native, research_binding=binding)
    with pytest.raises(Captured):
        runner(request, lambda: False, lambda _: None)
    actual = captured[0]['researchRuntime']
    gateway_context = next(item['content'] for item in captured[0]['contextFiles'] if item['path'] == 'registered-production-data')
    assert gateway_bindings == [(task, binding['attempt_id'], {'data_gateway_discover_network_models'})]
    catalog = captured[0]['dataGateway']['catalog']
    assert captured[0]['dataGateway']['onDemandTools'] is True
    guidance = next(item['content'] for item in captured[0]['contextFiles'] if item['path'] == 'registered-data-gateway-guidance')
    assert 'SERVICE_GUIDANCE_SENTINEL' in guidance
    assert 'data_gateway_' in guidance
    assert {'agent_tool_search', 'agent_tool_load'} <= set(captured[0]['applicationPolicy']['allowed_tools'])
    assert set(catalog['tools']) == {'data_gateway_discover_network_models'}
    assert catalog['tool_hashes'] == {'data_gateway_discover_network_models': 'hash-one'}
    assert catalog['revision'] == 'catalog-revision'
    assert 'data_gateway_other' in gateway_publication['catalog']['tools']
    assert 'Use prepare_data_query before execute_data_query' not in gateway_context
    assert 'then reopen after success' not in gateway_context
    assert 'Read groups first' not in gateway_context
    assert 'power-flow' not in gateway_context
    assert 'source view' not in gateway_context
    assert 'topology' not in gateway_context
    assert 'For an inventory request' in gateway_context
    assert 'summary/default arguments' in gateway_context
    assert 'Use discover_data_capabilities and discover_business_services first' not in gateway_context
    assert 'Model operations are not enabled.' not in gateway_context
    assert actual.get('nodeReviewMode') == 'advisory'
    assert 'nodeReviewMode' not in captured[0]['settings'].get('retry', {})
    assert captured[0]['runtimeEnvironment'] == runner.environment_context
    assert actual['adaptiveAgentLoop'] is (version in {'1.19.0', '1.20.0'})
    assert actual['isolatedTaskExecution'] is (version in {'1.14.0', '1.15.0', '1.16.0', '1.17.0', '1.18.0', '1.19.0', '1.20.0'})
    assert actual['goalDrivenExecution'] is (version in {'1.16.0', '1.17.0', '1.18.0', '1.19.0', '1.20.0'})
    assert actual['lightweightTaskNodes'] is (version in {'1.17.0', '1.18.0', '1.19.0', '1.20.0'})
    assert actual['graphWorkEdition'] == 'capstone-graph-work/1'
    assert actual['graphWorkStartedAt'] == native['graph_work']['started_at_ms']
    assert actual['graphWork'] == {'schema': 'capstone-graph-work/1', 'mode': 'off' if version in {'1.16.0', '1.17.0', '1.18.0', '1.19.0', '1.20.0'} else 'usable_draft',
        'target_seconds': 240, 'integration_reserve_seconds': 60, 'child_wrapup_seconds': 15}
    assert captured[0]['deadlineAt'] > actual['graphWorkStartedAt']


@pytest.mark.parametrize('version,controls', [
    ('1.1.0', ['agent_research_cycle']),
    ('1.2.0', ['agent_research_plan', 'agent_research_record', 'agent_research_assess']),
])
def test_host_retains_selected_control_interface_and_requires_research_binding(tmp_path, version, controls):
    from dataclasses import replace
    from types import SimpleNamespace
    from capstone_agent.business_context import BusinessContext
    from capstone_agent.general_pi_server import GeneralPiHost
    from capstone_agent.native_task_context import native_context_for
    from capstone_agent.native_conversation import executor_binding
    from test_enterprise_normal_chat import native_executor
    from test_native_research_bridge import _cycle_progress_fixture, research
    from capstone_agent.native_research_bridge import WorkerResearchBridge
    worker = research(tmp_path / 'research')
    binding, _, _, _ = _cycle_progress_fixture(tmp_path / 'fixture', worker=worker)
    bridge = WorkerResearchBridge(worker.channel, owner_id='a' * 64, producer_binding=binding)
    from test_research_policy_compatibility import registered_binding
    selected = registered_binding(version)
    context = native_context_for(SimpleNamespace(submission=None, selected_task_reader=None), selected)
    context['policy']['allowed_tools'] = controls
    received = []
    host = GeneralPiHost(root=tmp_path / 'host', identity={'engine': 'pi'},
        run_task=lambda request, *_: received.append(request) or ('Answer', {}))
    request = PiTaskRequest('control-interface', binding['attempt_id'], 'direct', 'Explain', (), (), host.identity, 2,
        business_context=BusinessContext.empty('workspace', 0),
        resource_profile={'profile_id': 'direct_pi', 'revision': 'test'},
        input={'kind': 'text', 'text': 'Explain'}, native_context=context)
    with pytest.raises(ValueError, match='unpublished tool'):
        host.submit(request)
    admitted = replace(request, research_binding=binding)
    host.submit(admitted)
    host.research_mirror(admitted.task_id).bootstrap('a' * 64, bridge.bootstrap())
    deadline = time.monotonic() + 2
    while host.read(admitted.task_id)['status'] == 'running' and time.monotonic() < deadline:
        time.sleep(.005)
    host.submit(admitted)
    assert len(received) == 1
    assert received[0].to_document()['native_context']['policy']['allowed_tools'] == controls
    assert host.read(admitted.task_id)['result']['status'] == 'completed'


@pytest.mark.parametrize('version,variant,expected', [('1.3.0', 'default', 'completed'),
    ('1.3.0', 'initial-review', 'completed'), ('1.4.0', 'default', 'completed'), ('1.2.0', 'default', 'failed')])
def test_host_assess_review_requires_reviewed_profile(tmp_path, version, variant, expected):
    import json
    from types import SimpleNamespace
    from capstone_agent.business_context import BusinessContext
    from capstone_agent.general_pi_server import GeneralPiHost
    from capstone_agent.native_task_context import native_context_for
    from capstone_agent.native_conversation import executor_binding
    from capstone_agent.native_research_bridge import WorkerResearchBridge, write_json
    from test_enterprise_normal_chat import native_executor
    from test_native_research_bridge import _branch_progress_fixture, research
    worker = research(tmp_path / 'research')
    binding, task, view, branch = _branch_progress_fixture(tmp_path / 'fixture', worker=worker)
    saved = json.loads(view['state']['notes'][0]['text'])
    saved['snapshot']['pending_action']['kind'] = 'assess'
    view['state']['notes'][0]['text'] = json.dumps(saved)
    branch['review_mode'] = 'delivery'
    bridge = WorkerResearchBridge(worker.channel, owner_id='a' * 64, producer_binding=binding)
    from test_research_policy_compatibility import registered_binding
    selected = registered_binding(version, variant)
    context = native_context_for(SimpleNamespace(submission=None, selected_task_reader=None), selected)
    context['policy']['allowed_tools'] = ['agent_delegate']
    def run(request, cancelled, emit):
        write_json(host.research_mirror(task).root / 'view.json', view)
        emit({'type': 'tool_execution_start', 'toolName': 'agent_delegate', 'toolCallId': 'delegate-call'})
        emit(branch)
        emit({**branch, 'type': 'delegation_child_finished', 'status': 'completed',
              'result_summary': 'Text review completed.'})
        return 'Reviewed answer', {}
    host = GeneralPiHost(root=tmp_path / 'host', identity={'engine': 'pi'}, run_task=run)
    request = PiTaskRequest(task, binding['attempt_id'], 'direct', 'Review', (), (), host.identity, 2,
        business_context=BusinessContext.empty('workspace', 0),
        resource_profile={'profile_id': 'direct_pi', 'revision': 'test'},
        input={'kind': 'text', 'text': 'Review'}, native_context=context, research_binding=binding)
    host.submit(request)
    host.research_mirror(task).bootstrap('a' * 64, bridge.bootstrap())
    deadline = time.monotonic() + 2
    while host.read(task)['status'] == 'running' and time.monotonic() < deadline:
        time.sleep(.005)
    result = host.read(task)
    assert result['status'] == expected
    if expected == 'completed':
        branches = [event for event in result['events'] if event['type'].startswith('delegation_child_')]
        assert len(branches) == 2
        assert all(event['review_mode'] == 'delivery' for event in branches)
    else:
        assert result['result']['failure']['code'] == 'native_research_branch_invalid'


def test_no_progress_rpc_failure_retains_actual_files_and_safe_public_reason(tmp_path):
    import json
    import sys
    from capstone_agent.general_pi_executor import GeneralPiProcess
    from capstone_agent.general_pi_server import GeneralPiHost
    script = tmp_path / 'no_progress.py'
    script.write_text("import json,sys\nfrom pathlib import Path\nsys.stdin.readline()\n"
                      "Path('retained.md').write_text('Previously generated actual output')\n"
                      "print(json.dumps({'type':'response','success':False,'code':'continuation_no_progress',"
                      "'message':'PRIVATE model diagnostics'}),flush=True)\n")
    def run(request, cancelled, emit):
        workspace = tmp_path / 'tasks' / request.task_id
        workspace.mkdir(parents=True)
        process = GeneralPiProcess((sys.executable, str(script)), {'PATH': '/usr/bin'}, workspace)
        return process.run(request.instruction, timeout=2, cancelled=cancelled, on_event=emit), process.usage
    host = GeneralPiHost(root=tmp_path, identity={'engine': 'pi'}, run_task=run)
    request = PiTaskRequest('no-progress', 'attempt', 'direct', 'Explain', (), (), host.identity, 2)
    host.submit(request)
    deadline = time.monotonic() + 2
    while host.read(request.task_id)['status'] == 'running' and time.monotonic() < deadline:
        time.sleep(.01)
    result = host.read(request.task_id)['result']
    assert result['status'] == 'failed'
    assert result['failure'] == {'code': 'native_continuation_no_progress', 'phase': 'execution'}, (
        result['failure'], (tmp_path / 'receipts/failures/no-progress.json').read_text())
    assert any(artifact['metadata']['path'] == 'retained.md' for artifact in result['artifacts'])
    assert 'PRIVATE' not in str(result)


@pytest.mark.parametrize('cancel', [False, True])
def test_actual_usage_receipt_survives_host_failure_cancellation_and_restart(tmp_path, cancel):
    from capstone_agent.general_pi_server import GeneralPiHost
    ready = threading.Event()
    usage = {'parent_model_responses': 3, 'child_model_responses': None,
             'parent_input': 12, 'child_input': None, 'total_input': None,
             'usage_complete': False, 'cost_status': 'unknown'}
    def run(request, cancelled, emit):
        ready.set()
        if cancel:
            while not cancelled():
                time.sleep(.005)
        error = InterruptedError() if cancel else RuntimeError('private transport details')
        error.saved_usage = usage
        raise error
    host = GeneralPiHost(root=tmp_path, identity={'engine': 'pi'}, run_task=run)
    request = PiTaskRequest('usage-task', 'attempt', 'direct', 'Explain', (), (), host.identity, 2)
    host.submit(request)
    assert ready.wait(1)
    if cancel:
        host.cancel(request.task_id)
    deadline = time.monotonic() + 2
    while host.read(request.task_id)['status'] == 'running' and time.monotonic() < deadline:
        time.sleep(.005)
    result = host.read(request.task_id)['result']
    assert result['status'] == ('cancelled' if cancel else 'failed')
    assert result['usage'] == usage
    restarted = GeneralPiHost(root=tmp_path, identity=host.identity, run_task=lambda *_: pytest.fail('must not replay'))
    restarted.submit(request)
    assert restarted.read(request.task_id)['result']['usage'] == usage


def test_isolated_runtime_projection_needs_only_python_standard_library():
    import subprocess
    import sys
    root = Path(__file__).resolve().parents[2]
    source = root / 'capability-agent-kernel/src/capability_agent/runtime/step_events.py'
    code = ("import runpy,sys; m=runpy.run_path(sys.argv[1]); "
            "assert m['project_runtime_action']({'type':'turn_start'}) == "
            "{'type':'runtime_action','phase':'started'}; "
            "assert not any(k.startswith('capability_agent') for k in sys.modules)")
    subprocess.run([sys.executable, '-I', '-S', '-c', code, str(source)], check=True)


def test_native_turn_boundaries_survive_bounded_host_projection(tmp_path):
    from capstone_agent.general_pi_server import GeneralPiHost
    def run(request, cancelled, emit):
        emit({'type': 'turn_start'})
        emit({'type': 'message_end', 'message': {'role': 'assistant',
            'content': [{'type': 'thinking', 'thinking': 'PRIVATE'},
                        {'type': 'toolCall', 'name': 'bash', 'arguments': {'secret': 'PRIVATE'}}],
            'usage': {'input': 23, 'output': 4, 'cost': {'private': 'PRIVATE'}}}})
        emit({'type': 'turn_end'})
        return 'Answer', {}
    host = GeneralPiHost(root=tmp_path, identity={'engine': 'pi'}, run_task=run)
    request = PiTaskRequest('turns', 'attempt', 'direct', 'Explain', (), (), host.identity, 2)
    host.submit(request)
    deadline = time.monotonic() + 2
    while host.read(request.task_id)['status'] == 'running' and time.monotonic() < deadline:
        time.sleep(.01)
    events = host.read(request.task_id)['events']
    assert [e.get('phase') for e in events] == ['started', 'response_completed', 'completed']
    assert events[1]['response_kind'] == 'tools'
    assert events[1]['usage'] == {'input': 23, 'output': 4}
    assert 'PRIVATE' not in str(events)


@pytest.mark.parametrize('fails', [False, True])
def test_host_streams_only_displayable_sdk_thinking_with_bounded_ordered_chunks(tmp_path, fails):
    from capstone_agent.general_pi_server import GeneralPiHost
    thought = '核对当前任务。' * 900
    tail = '再选择工具。'
    def run(request, cancelled, emit):
        emit({'type': 'turn_start'})
        emit({'type': 'message_end', 'message': {'role': 'assistant', 'content': [
            {'type': 'thinking', 'thinking': 'PRIVATE_RAW_THINKING', 'signature': 'PRIVATE_SIGNATURE'}]}})
        for char in thought:
            emit({'type': 'message_update', 'assistantMessageEvent': {'type': 'thinking_delta', 'delta': char}})
        emit({'type': 'message_update', 'assistantMessageEvent': {'type': 'text_delta', 'delta': 'DRAFT_ANSWER'}})
        for kind in ('thinking_end', 'thinking_signature', 'redacted_thinking'):
            emit({'type': 'message_update', 'assistantMessageEvent': {'type': kind, 'delta': 'PRIVATE'}})
        emit({'type': 'message_update', 'assistantMessageEvent': {'type': 'thinking_delta', 'delta': tail}})
        emit({'type': 'tool_execution_start', 'toolName': 'read', 'toolCallId': 'read-1'})
        if fails:
            raise RuntimeError('PRIVATE_DIAGNOSTIC')
        return 'Final answer', {}
    host = GeneralPiHost(root=tmp_path, identity={'engine': 'pi'}, run_task=run)
    request = PiTaskRequest('thinking-task', 'thinking-attempt', 'direct', 'Explain', (), (), host.identity, 3)
    host.submit(request)
    deadline = time.monotonic() + 3
    while host.read(request.task_id)['status'] == 'running' and time.monotonic() < deadline:
        time.sleep(.005)
    receipt = host.read(request.task_id)
    events = receipt['events']
    thinking = [event for event in events if event['type'] == 'assistant_thinking_delta']
    assert ''.join(event['text'] for event in thinking) == thought + tail
    assert all(0 < len(event['text']) <= 1024 for event in thinking)
    assert [event['event_id'] for event in events] == ['event-' + str(index + 1) for index in range(len(events))]
    draft_index = next(index for index, event in enumerate(events) if event['type'] == 'assistant_delta')
    assert ''.join(event['text'] for event in events[:draft_index] if event['type'] == 'assistant_thinking_delta') == thought
    tool_index = next(index for index, event in enumerate(events) if event['type'] == 'tool_execution_start')
    assert all(events.index(event) < tool_index for event in thinking)
    assert 'PRIVATE' not in str(receipt)
    assert receipt['result']['answer'] == ('Final answer' if not fails else '')
    assert receipt['result']['sources'] == []


def test_cancelled_native_thinking_drops_pending_and_late_text(tmp_path):
    from capstone_agent.general_pi_server import GeneralPiHost
    ready, release = threading.Event(), threading.Event()
    def run(request, cancelled, emit):
        emit({'type': 'message_update', 'assistantMessageEvent': {'type': 'thinking_delta', 'delta': 'Visible before cancel'}})
        emit({'type': 'message_update', 'assistantMessageEvent': {'type': 'thinking_delta', 'delta': 'PENDING'}})
        ready.set()
        release.wait(2)
        if cancelled():
            raise InterruptedError('cancelled')
        emit({'type': 'message_update', 'assistantMessageEvent': {'type': 'thinking_delta', 'delta': 'LATE'}})
        return 'Answer', {}
    host = GeneralPiHost(root=tmp_path, identity={'engine': 'pi'}, run_task=run)
    request = PiTaskRequest('cancel-thinking', 'attempt-cancel', 'direct', 'Explain', (), (), host.identity, 3)
    host.submit(request)
    assert ready.wait(2)
    host.cancel(request.task_id)
    release.set()
    deadline = time.monotonic() + 3
    while host.read(request.task_id)['status'] == 'running' and time.monotonic() < deadline:
        time.sleep(.005)
    receipt = host.read(request.task_id)
    assert receipt['result']['status'] == 'cancelled'
    assert ''.join(event.get('text', '') for event in receipt['events']) == 'Visible before cancel'


@pytest.mark.parametrize('fails', [False, True])
def test_host_coalesces_text_before_sequence_assignment_and_flushes_before_tools_and_failure(tmp_path, fails):
    from capstone_agent.general_pi_server import GeneralPiHost
    prefix = '甲乙丙丁' * 100
    tail = '结束前的最后一段'
    def run(request, cancelled, emit):
        emit({'type': 'turn_start'})
        for index, char in enumerate(prefix):
            emit({'type': 'message_update', 'assistantMessageEvent': {'type': 'text_delta', 'delta': char}})
            if index == 0:
                assert host.read(request.task_id)['events'][-1]['text'] == char
        emit({'type': 'tool_execution_start', 'toolName': 'read', 'toolCallId': 'read-1'})
        for char in tail:
            emit({'type': 'message_update', 'assistantMessageEvent': {'type': 'text_delta', 'delta': char}})
        if fails:
            raise RuntimeError('PRIVATE runtime failure')
        return 'Answer', {}
    host = GeneralPiHost(root=tmp_path, identity={'engine': 'pi'}, run_task=run)
    request = PiTaskRequest('stream-task', 'attempt', 'direct', 'Explain', (), (), host.identity, 2)
    host.submit(request)
    deadline = time.monotonic() + 2
    while host.read(request.task_id)['status'] == 'running' and time.monotonic() < deadline:
        time.sleep(.01)
    result = host.read(request.task_id)
    assert result['status'] == ('failed' if fails else 'completed')
    events = result['events']
    assert [e['event_id'] for e in events] == ['event-' + str(n) for n in range(1, len(events) + 1)]
    text_events = [e for e in events if e['type'] == 'assistant_delta']
    assert ''.join(e['text'] for e in text_events) == prefix + tail
    assert len(text_events) < 10
    tool_index = next(i for i, e in enumerate(events) if e['type'] == 'tool_execution_start')
    assert ''.join(e.get('text', '') for e in events[:tool_index]) == prefix
    assert 'PRIVATE' not in str(result)


@pytest.mark.parametrize('error,code', [
    ('continuation_no_progress', 'native_continuation_no_progress'),
    ('task_goal_blocked', 'native_goal_blocked'),
    ('model_rate_limit', 'native_model_rate_limit'),
    ('model_output_rejected', 'native_model_output_rejected'),
    ('General Pi did not complete', 'native_model_turn_incomplete'),
    (ValueError('research branch does not belong to the committed parent action'), 'native_research_branch_invalid'),
    (ValueError('research branch identity changed'), 'native_research_branch_invalid'),
    ('PRIVATE provider detail', 'native_execution_error'),
    (ModuleNotFoundError('PRIVATE dependency path'), 'native_runtime_dependency_missing'),
])
def test_native_failure_reason_survives_host_result_and_restart(tmp_path, error, code):
    from capstone_agent.general_pi_server import GeneralPiHost
    def fail(*args):
        if isinstance(error, Exception):
            raise error
        raise RuntimeError(error)
    host = GeneralPiHost(root=tmp_path, identity={'engine': 'pi'}, run_task=fail)
    request = PiTaskRequest('failure-task', 'attempt', 'direct', 'Explain', (), (), host.identity, 2)
    host.submit(request)
    deadline = time.monotonic()+2
    while host.read(request.task_id)['status'] == 'running' and time.monotonic() < deadline:
        time.sleep(.01)
    result = host.read(request.task_id)['result']
    assert result['failure'] == {'code': code, 'phase': 'execution'}
    assert 'PRIVATE' not in str(result)
    restarted = GeneralPiHost(root=tmp_path, identity=host.identity,
        run_task=lambda *_: pytest.fail('Task repeated'))
    restarted.submit(request)
    assert restarted.read(request.task_id)['result']['failure'] == result['failure']


def test_v2_service_advertises_support_and_retains_public_context(tmp_path):
    from capstone_agent.business_context import BusinessContext
    from capstone_agent.general_pi_server import GeneralPiHost
    received = []
    host = GeneralPiHost(root=tmp_path, identity={'engine': 'pi', 'config_revision': 'test'},
        run_task=lambda request, *_: received.append(request) or ('Answer', {}))
    assert host.capability['task_schemas'] == ['capstone-pi-task/1', 'capstone-pi-task/2']
    request = PiTaskRequest('task-v2', 'attempt', 'direct', 'Explain', (), (), host.identity, 2,
        business_context=BusinessContext.empty('workspace', 0),
        resource_profile={'profile_id': 'direct_pi', 'revision': 'test'},
        input={'kind': 'text', 'text': 'Explain'})
    host.submit(request)
    deadline = time.monotonic() + 2
    while host.read(request.task_id)['status'] == 'running' and time.monotonic() < deadline:
        time.sleep(0.01)
    assert received[0].business_context == request.business_context
    restarted = GeneralPiHost(root=tmp_path, identity=host.identity,
        run_task=lambda *_: pytest.fail('Task repeated'))
    restarted.submit(request)
    assert restarted.read(request.task_id)['result']['answer'] == 'Answer'


def test_native_runner_writes_business_context_as_private_data(tmp_path, monkeypatch):
    import capstone_agent.general_pi_server as module
    from capstone_agent.business_context import BusinessContext
    monkeypatch.setattr(module.os, 'geteuid', lambda: 0)
    monkeypatch.setattr(module.os, 'chown', lambda *_: None)
    captured = []
    def launch(**kwargs):
        assert 'applicationPolicy' not in kwargs['sdk_config'], 'network state must not invent a tool allowlist'
        kwargs['workspace'].mkdir(parents=True)
        (kwargs['workspace'].parent / ('.inputs-' + kwargs['workspace'].name)).mkdir()
        captured.append(__import__('json').dumps(kwargs['sdk_config']['context']))
        return ('pi',), {}
    monkeypatch.setattr(module, 'native_pi_launch', launch)
    class Process:
        def __init__(self, argv, environment, workspace, **kwargs):
            self.usage = {}
        def run(self, *_args, **kwargs):
            return 'Answer'
        def stop(self):
            pass
    monkeypatch.setattr(module, 'GeneralPiProcess', Process)
    root = tmp_path / 'private'
    (root / 'receipts').mkdir(parents=True)
    from capstone_agent.native_network_policy import NativeNetworkPolicy
    network_policy = NativeNetworkPolicy(apply_rules=lambda _: None)
    network_policy.start()
    runner = module.NativeTaskRunner(root=root, config_root=tmp_path, command=('node', '/opt/pi/dist/cli.js'),
        model='fixture', relay_origin='http://127.0.0.1:8790', network_policy=network_policy)
    context = BusinessContext.empty('workspace', 0)
    request = PiTaskRequest('task', 'attempt', 'direct', 'Explain', (), (), {'engine': 'pi'}, 2,
        business_context=context, resource_profile={'profile_id': 'direct_pi', 'revision': 'test'},
        input={'kind': 'text', 'text': 'Explain'})
    runner(request, lambda: False, lambda _: None)
    import json
    assert json.loads(captured[0])['business_context'] == context.to_document()
    state = json.loads(captured[0])['execution_state']
    assert state['task_id'] == request.task_id
    assert state['parent_attempt_id'] == request.parent_attempt_id
    assert state['task_status'] == 'running'
    assert state['scope'] == 'current_native_task_only'
    assert state['operating_system_processes_observed'] is False
    assert state['other_tasks_observed'] is False
    assert isinstance(state['observed_at_ms'], int)


@pytest.mark.parametrize('raw,tamper,completed', [
    ('{"number":1.0,"text":"电网"}', False, True),
    ('{"number":1.0,"text":"电网"}', True, False),
    ('{"number":NaN}', False, False),
])
def test_mcp_observation_is_host_bound_external_data(tmp_path, raw, tamper, completed):
    import json
    from capstone_agent.general_pi_server import GeneralPiHost
    descriptor_sha, tool_sha = 'a' * 64, 'b' * 64
    def run(request, _cancelled, emit):
        emit({'type': 'tool_execution_end', 'toolName': 'audit_network', 'toolCallId': 'call-1',
            'result': {'content': [{'type': 'text', 'text': raw}], 'details': {
                'kind': 'external_mcp_observation', 'task_id': request.task_id,
                'parent_attempt_id': request.parent_attempt_id, 'descriptor_sha256': descriptor_sha,
                'tool': 'audit_network', 'tool_schema_sha256': tool_sha,
                'output_sha256': __import__('hashlib').sha256((raw + ' ' if tamper else raw).encode()).hexdigest()}}})
        return 'Answer', {}
    host = GeneralPiHost(root=tmp_path, identity={'engine': 'pi'}, run_task=run)
    host.capability['resource_profiles'] = {'direct_pi': {'load_receipt': {
        'descriptor_sha256': descriptor_sha, 'tool_schema_hashes': {'audit_network': tool_sha}}}}
    request = PiTaskRequest('task-mcp', 'attempt', 'direct', 'Explain', (), (), host.identity, 2)
    host.submit(request)
    deadline = time.monotonic() + 2
    while host.read(request.task_id)['status'] == 'running' and time.monotonic() < deadline:
        time.sleep(0.01)
    result = host.read(request.task_id)['result']
    if not completed:
        assert result['status'] == 'failed'
        assert not result['sources']
        return
    source = result['sources'][0]
    assert source['kind'] == 'external_mcp_observation'
    assert source['metadata']['tool_schema_sha256'] == tool_sha
    assert 'result_refs' not in json.dumps(result) and 'evidence_refs' not in json.dumps(result)


def test_executor_service_binds_identity_and_control_authorization(tmp_path):
    from capstone_agent.general_pi_server import GeneralPiHost, make_server
    host = GeneralPiHost(root=tmp_path, identity={'engine': 'pi', 'config_revision': 'test'},
                         run_task=lambda request, cancelled, emit: ('General answer', {}))
    server = make_server(host, control_token='host-secret', address=('127.0.0.1', 0))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f'http://127.0.0.1:{server.server_port}'
    try:
        assert httpx.get(origin + '/health/ready').status_code == 200
        assert httpx.post(origin + '/tasks', json={}).status_code == 401
        client = HttpGeneralPiExecutor(origin, identity=host.identity, capability=host.capability,
                                      control_token='host-secret')
        request = PiTaskRequest.from_document({'schema': 'capstone-pi-task/1', 'task_id': 't1',
            'parent_attempt_id': 'a1', 'entrypoint': 'direct', 'instruction': 'Explain', 'messages': [],
            'dependency_results': [], 'executor_identity': host.identity, 'timeout_seconds': 2})
        result = client.execute(request, NodeControl(lambda: None, time.monotonic()+2), lambda _: None)
        assert result.answer == 'General answer'
        assert result.status == 'completed'
        assert list(tmp_path.glob('receipts/records/*.json'))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_network_control_requires_host_credential_and_returns_applied_state(tmp_path):
    from capstone_agent.general_pi_server import GeneralPiHost, make_server
    from capstone_agent.native_network_policy import NativeNetworkPolicy
    policy = NativeNetworkPolicy(apply_rules=lambda _: None)
    policy.start()
    host = GeneralPiHost(root=tmp_path, identity={'engine': 'pi', 'config_revision': 'test'},
                         run_task=lambda *_: ('Answer', {}))
    server = make_server(host, control_token='host-secret', address=('127.0.0.1', 0), network_policy=policy)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f'http://127.0.0.1:{server.server_port}'
    try:
        assert httpx.get(origin + '/network-policy').status_code == 401
        assert httpx.post(origin + '/network-policy', json={'external_access': True}).status_code == 401
        headers = {'Authorization': 'Bearer host-secret'}
        assert httpx.get(origin + '/network-policy', headers=headers).json()['external_access'] is False
        response = httpx.post(origin + '/network-policy', headers=headers, json={'external_access': True})
        assert response.status_code == 200
        assert response.json() == {'external_access': True, 'enforced': True}
        audit = (tmp_path / 'receipts' / 'network-policy.jsonl').read_text()
        assert '"external_access": true' in audit
        assert httpx.post(origin + '/network-policy', headers=headers,
                          json={'external_access': 'yes'}).status_code == 400
        def disk_full(*_):
            raise OSError('audit disk is full')
        host.record_network_policy = disk_full
        assert httpx.post(origin + '/network-policy', headers=headers,
                          json={'external_access': False}).status_code == 503
        assert policy.state()['external_access'] is False
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_cancel_service_stops_child_and_duplicate_tasks_do_not_repeat_actions(tmp_path):
    from capstone_agent.general_pi_server import GeneralPiHost
    calls = []
    def run(request, cancelled, emit):
        calls.append(request.task_id)
        while not cancelled():
            time.sleep(0.01)
        raise InterruptedError()
    host = GeneralPiHost(root=tmp_path, identity={'engine': 'pi'}, run_task=run)
    request = PiTaskRequest.from_document({'schema': 'capstone-pi-task/1', 'task_id': 't1',
        'parent_attempt_id': 'a1', 'entrypoint': 'delegated', 'instruction': 'Explain', 'messages': [],
        'dependency_results': [], 'executor_identity': host.identity, 'timeout_seconds': 2})
    host.submit(request)
    host.submit(request)
    host.cancel('t1')
    deadline = time.monotonic()+2
    while host.read('t1')['status'] in {'queued', 'running'} and time.monotonic() < deadline:
        time.sleep(0.01)
    assert calls == ['t1']
    assert host.read('t1')['result']['status'] == 'cancelled'


def test_service_restart_replays_receipt_without_repeating_work(tmp_path):
    from capstone_agent.general_pi_server import GeneralPiHost
    request = PiTaskRequest.from_document({'schema': 'capstone-pi-task/1', 'task_id': 't1',
        'parent_attempt_id': 'a1', 'entrypoint': 'delegated', 'instruction': 'Explain', 'messages': [],
        'dependency_results': [], 'executor_identity': {'engine': 'pi'}, 'timeout_seconds': 2})
    host = GeneralPiHost(root=tmp_path, identity={'engine': 'pi'},
                         run_task=lambda *_: ('Saved answer', {}))
    host.submit(request)
    deadline = time.monotonic()+2
    while host.read('t1')['status'] == 'running' and time.monotonic() < deadline:
        time.sleep(0.01)
    restarted = GeneralPiHost(root=tmp_path, identity={'engine': 'pi'},
        run_task=lambda *_: (_ for _ in ()).throw(AssertionError('repeated work')))
    restarted.submit(request)
    assert restarted.read('t1')['result']['answer'] == 'Saved answer'


def test_task_runner_failure_retains_private_category_without_error_message(tmp_path):
    import json
    from capstone_agent.general_pi_server import GeneralPiHost
    def broken(*args):
        raise OSError(30, 'PRIVATE_SENSITIVE_MESSAGE')
    host = GeneralPiHost(root=tmp_path, identity={'engine': 'pi'}, run_task=broken)
    request = PiTaskRequest('task-private-failure', 'attempt', 'direct', 'Explain', (), (), host.identity, 2)
    host.submit(request)
    deadline = time.monotonic() + 2
    while host.read(request.task_id)['status'] == 'running' and time.monotonic() < deadline:
        time.sleep(.01)
    record = json.loads((tmp_path / 'receipts/failures/task-private-failure.json').read_text())
    assert record == {'schema': 'capstone-pi-private-failure/1', 'task_id': request.task_id,
                      'phase': 'task_runner', 'exception_type': 'OSError', 'errno': 30}
    assert 'PRIVATE_SENSITIVE_MESSAGE' not in json.dumps(record)


@pytest.mark.parametrize('message,reason', [
    ('General Pi frame exceeds bounds', 'rpc_frame_too_large'),
    ('General Pi ended before completion', 'rpc_process_ended'),
    ('General Pi rejected request', 'rpc_request_rejected'),
    ('General Pi did not complete', 'model_turn_incomplete'),
    ('model_context_limit', 'model_context_limit'),
    ('General Pi task deadline exceeded', 'task_deadline_exceeded'),
])
def test_private_frame_failure_has_fixed_operator_reason(tmp_path, message, reason):
    import json
    from capstone_agent.general_pi_server import GeneralPiHost
    def broken(*args):
        raise RuntimeError(message)
    host = GeneralPiHost(root=tmp_path, identity={'engine': 'pi'}, run_task=broken)
    request = PiTaskRequest('task-frame-failure', 'attempt', 'direct', 'Explain', (), (), host.identity, 2)
    host.submit(request)
    deadline = time.monotonic() + 2
    while host.read(request.task_id)['status'] == 'running' and time.monotonic() < deadline:
        time.sleep(.01)
    record = json.loads((tmp_path / 'receipts/failures/task-frame-failure.json').read_text())
    assert record['reason_code'] == reason


def test_sources_reference_actual_host_observed_tool_results(tmp_path):
    from capstone_agent.general_pi_server import GeneralPiHost
    def run(request, cancelled, emit):
        emit({'type': 'tool_execution_end', 'toolName': 'bash', 'toolCallId': 'call-1',
              'isError': True, 'result': {'content': [{'type': 'text', 'text': 'Observed output'}]}})
        return 'Answer', {}
    host = GeneralPiHost(root=tmp_path, identity={'engine': 'pi'}, run_task=run)
    request = PiTaskRequest.from_document({'schema': 'capstone-pi-task/1', 'task_id': 't1',
        'parent_attempt_id': 'a1', 'entrypoint': 'direct', 'instruction': 'Explain', 'messages': [],
        'dependency_results': [], 'executor_identity': host.identity, 'timeout_seconds': 2})
    host.submit(request)
    deadline = time.monotonic()+2
    while host.read('t1')['status'] == 'running' and time.monotonic() < deadline:
        time.sleep(0.01)
    sources = host.read('t1')['result']['sources']
    assert len(sources) == 1
    assert sources[0]['kind'] == 'native_tool_observation'
    assert sources[0]['task_id'] == 't1'
    assert sources[0]['metadata']['tool_name'] == 'bash'
    assert host.read('t1')['events'][0] == {'event_id': 'event-1', 'type': 'tool_execution_end',
        'tool_name': 'bash', 'tool_call_id': 'call-1', 'is_error': True,
        'activity': {'output_excerpt': 'Observed output'}}
    assert list((tmp_path / 'receipts/observations/t1').glob('*.json'))


@pytest.mark.parametrize('mode',['valid','unpresentable','forged'])
def test_gateway_source_hint_requires_host_receipt_even_after_capture_budget(tmp_path,monkeypatch,mode):
    import asyncio
    from capstone_agent.data_gateway_relay import DataGatewayAccess
    from capstone_agent.general_pi_server import GeneralPiHost
    import capstone_agent.general_pi_server as server_module
    from test_grid_source_topology import Gateway
    original=server_module.limits
    class NoCapture:
        def __getattr__(self,name):
            return 0 if name=='context_references' else getattr(original,name)
    monkeypatch.setattr(server_module,'limits',NoCapture())
    client=Gateway()
    if mode=='unpresentable':client.data['next_node_offset']=0
    gateway=DataGatewayAccess(client,client.catalog)
    class Runner:
        def __call__(self,request,cancelled,emit):
            gateway.bind(request.task_id,request.parent_attempt_id, {'data_gateway_get_network_topology_view'})
            response=asyncio.run(gateway.call(request.task_id,{'call_id':'view-one',
                'name':'data_gateway_get_network_topology_view','arguments':{'scope_id':'north','level':'region'}}))
            details=response['observation']
            if mode=='forged':details={**details,'output_sha256':'forged'}
            emit({'type':'tool_execution_end','toolName':'data_gateway_get_network_topology_view',
                'toolCallId':'view-one','isError':False,'result':{
                    'content':[{'type':'text','text':response['result_json']}],'details':details}})
            return 'Answer',{}
    runner=Runner();runner.gateway=gateway
    host=GeneralPiHost(root=tmp_path,identity={'engine':'pi'},run_task=runner)
    request=PiTaskRequest('hint-task','hint-attempt','direct','Read source',(),(),host.identity,2)
    host.submit(request)
    deadline=time.monotonic()+2
    while host.read(request.task_id)['status']=='running' and time.monotonic()<deadline:time.sleep(.005)
    saved=host.read(request.task_id)
    assert saved['result']['status']==('failed' if mode=='forged' else 'completed')
    hints=[event['source_view'] for event in saved['events'] if 'source_view' in event]
    assert len(hints)==(1 if mode=='valid' else 0)
    if hints:
        assert hints[0]['schema']=='capstone-grid-source-view-request/1'
        assert hints[0]['scope_name']=='North'
        assert 'nodes' not in hints[0]


@pytest.fixture
def small_answer_envelope():
    from capstone_agent.application_capacity import initialize_capacity
    initialize_capacity({'control_document_bytes': 65536})
    yield
    initialize_capacity()


def test_verified_electrical_descriptor_keeps_v2_open_arguments():
    import json
    from capstone_agent.general_pi_server import _electrical_view_from_verified_result
    from test_grid_electrical_view import v2_manifest
    def result(data):
        return {'content': [{'text': json.dumps({'structuredContent': {'status': 'ok', 'data': data}})}]}
    root = _electrical_view_from_verified_result(result(v2_manifest()), {
        'model_ref': 'model:one', 'view_schema': 'gateway-electrical-view/2', 'selection_profile': 'station'})
    assert root['view_schema'] == 'gateway-electrical-view/2'
    assert root['selection_profile'] == 'station'
    child = _electrical_view_from_verified_result(result(v2_manifest(view_ref='child', target='station-one')), {
        'model_ref': 'model:one', 'parent_view_ref': 'actual-parent',
        'expected_model_revision': 'revision-one', 'target': 'station-one'})
    assert child['parent_view_ref'] == 'actual-parent'
    assert 'selection_profile' not in child
    assert _electrical_view_from_verified_result(result(v2_manifest()), {
        'model_ref': 'model:one', 'view_schema': 'gateway-electrical-view/1'}) is None


def test_executor_revision_changes_when_the_published_v2_schema_changes(tmp_path):
    import ast
    from hashlib import sha256
    from pathlib import Path
    import capstone_agent.general_pi_server as server_module
    tree = ast.parse(Path(server_module.__file__).read_text())
    expressions = [value for node in ast.walk(tree) if isinstance(node, ast.Dict)
        for key, value in zip(node.keys, node.values)
        if isinstance(key, ast.Constant) and key.value == 'executor_revision']
    assert len(expressions) == 1
    expression = expressions[0]
    resources = next(node for node in ast.walk(expression) if isinstance(node, ast.Tuple)
        and any(isinstance(item, ast.Constant) and item.value == 'general_pi_server.py' for item in node.elts))
    for item in resources.elts:
        path = tmp_path / item.value
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'fixed-resource')
    schema = tmp_path / 'resources/gateway-electrical-view-v2.schema.json'
    schema.write_bytes(Path(server_module.__file__).parent.joinpath(
        'resources/gateway-electrical-view-v2.schema.json').read_bytes())
    # Exercise the exact production hash expression without starting services.
    compiled = compile(ast.Expression(expression), '<executor_revision>', 'eval')
    namespace = {'sha256': sha256, 'Path': Path, '__file__': str(tmp_path / 'general_pi_server.py')}
    before = eval(compiled, namespace)
    schema.write_bytes(schema.read_bytes() + b'\n')
    assert eval(compiled, namespace) != before


def test_verified_scope_root_descriptor_uses_the_gateway_returned_model_reference():
    import json
    from capstone_agent.general_pi_server import _electrical_view_from_verified_result
    from test_grid_electrical_view import v2_manifest
    result = {'content': [{'text': json.dumps({'structuredContent': {'status': 'ok',
        'data': v2_manifest(model_ref='opaque:gateway-returned-model')}})}]}
    arguments = {'scope': {'source_instance': 'source-one', 'object_type': 'grid', 'object_id': '000123'},
        'view_schema': 'gateway-electrical-view/2', 'selection_profile': 'station'}
    descriptor = _electrical_view_from_verified_result(result, arguments)
    assert descriptor['model_ref'] == 'opaque:gateway-returned-model'
    assert descriptor['selection_profile'] == 'station'
    assert _electrical_view_from_verified_result(result, {**arguments, 'model_ref': 'caller-ref'}) is None
    assert _electrical_view_from_verified_result(result, {**arguments, 'scope': {'object_type': 'grid'}}) is None


def test_invalid_native_answer_finishes_failed_instead_of_stranding_task(tmp_path, small_answer_envelope):
    from capstone_agent.general_pi_server import GeneralPiHost
    host = GeneralPiHost(root=tmp_path, identity={'engine': 'pi'},
                         run_task=lambda *_: ('字' * 64000, {}))
    request = PiTaskRequest.from_document({'schema': 'capstone-pi-task/1', 'task_id': 't1',
        'parent_attempt_id': 'a1', 'entrypoint': 'direct', 'instruction': 'Explain', 'messages': [],
        'dependency_results': [], 'executor_identity': host.identity, 'timeout_seconds': 2})
    host.submit(request)
    deadline = time.monotonic()+0.3
    while host.read('t1')['status'] == 'running' and time.monotonic() < deadline:
        time.sleep(0.01)
    assert host.read('t1')['status'] == 'failed'


def test_artifact_bytes_persist_and_workspaces_are_released(tmp_path):
    from capstone_agent.general_pi_server import GeneralPiHost
    def run(request, cancelled, emit):
        work = tmp_path / 'tasks' / request.task_id
        work.mkdir(parents=True)
        (work / 'output.txt').write_text('Saved product')
        return 'Done', {}
    identity = {'engine': 'pi'}
    host = GeneralPiHost(root=tmp_path, identity=identity, run_task=run)
    request = PiTaskRequest.from_document({'schema': 'capstone-pi-task/1', 'task_id': 't1',
        'parent_attempt_id': 'a1', 'entrypoint': 'direct', 'instruction': 'Explain', 'messages': [],
        'dependency_results': [], 'executor_identity': identity, 'timeout_seconds': 2})
    host.submit(request)
    deadline = time.monotonic()+2
    while host.read('t1')['status'] == 'running' and time.monotonic() < deadline:
        time.sleep(0.01)
    assert not (tmp_path / 'tasks/t1').exists()
    result = host.read('t1')['result']
    artifact = result['artifacts'][0]
    restarted = GeneralPiHost(root=tmp_path, identity=identity, run_task=run)
    assert restarted.read_artifact('t1', artifact['artifact_id']) == b'Saved product'


def test_retention_keeps_tombstone_and_cannot_repeat_expired_side_effect(tmp_path):
    from capstone_agent.general_pi_server import GeneralPiHost
    calls = []
    host = GeneralPiHost(root=tmp_path, identity={'engine': 'pi'},
        run_task=lambda request, *_: (calls.append(request.task_id) or 'Done', {}), retention_seconds=0.05)
    request = PiTaskRequest.from_document({'schema': 'capstone-pi-task/1', 'task_id': 't1',
        'parent_attempt_id': 'a1', 'entrypoint': 'direct', 'instruction': 'Explain', 'messages': [],
        'dependency_results': [], 'executor_identity': host.identity, 'timeout_seconds': 2})
    host.submit(request)
    deadline = time.monotonic()+2
    while host.read('t1')['status'] == 'running' and time.monotonic() < deadline:
        time.sleep(0.01)
    time.sleep(0.06)
    host.sweep()
    host.submit(request)
    assert calls == ['t1']
    assert host.read('t1')['result']['status'] == 'failed'
    assert 'not repeated' in host.read('t1')['result']['answer']


def test_storage_quota_rejects_new_work_without_losing_saved_products(tmp_path):
    from capstone_agent.general_pi_storage import GeneralPiStorage
    storage = GeneralPiStorage(tmp_path, max_bytes=1024, max_receipts=1)
    storage.save({'task_id': 'first'}, {'answer': 'kept'})
    with pytest.raises(OSError, match='capacity'):
        storage.save({'task_id': 'second'}, None)
    from capstone_agent.application_capacity import CapacityExceeded
    with pytest.raises(CapacityExceeded, match='native_storage_bytes'):
        storage.observation('first', 'large', b'x' * 1024)
    assert storage.load('first')['result']['answer'] == 'kept'
    assert storage.load('second') is None


def test_artifact_persistence_failure_settles_failed_and_preserves_workspace(tmp_path, monkeypatch):
    from capstone_agent.general_pi_server import GeneralPiHost
    def run(request, *_):
        workspace = tmp_path / 'tasks' / request.task_id
        workspace.mkdir(parents=True)
        (workspace / 'product.txt').write_text('Product')
        return 'Done', {}
    host = GeneralPiHost(root=tmp_path, identity={'engine': 'pi'}, run_task=run)
    def fail(*_):
        raise OSError('Private storage unavailable')
    monkeypatch.setattr(host.storage, 'artifacts', fail)
    request = PiTaskRequest.from_document({'schema': 'capstone-pi-task/1', 'task_id': 't1',
        'parent_attempt_id': 'a1', 'entrypoint': 'direct', 'instruction': 'Explain', 'messages': [],
        'dependency_results': [], 'executor_identity': host.identity, 'timeout_seconds': 2})
    host.submit(request)
    deadline = time.monotonic()+2
    while host.read('t1')['status'] == 'running' and time.monotonic() < deadline:
        time.sleep(0.01)
    assert host.read('t1')['status'] == 'failed'
    assert (tmp_path / 'tasks/t1/product.txt').read_text() == 'Product'
    assert host.storage.load('t1')['result']['status'] == 'failed'


def test_products_over_eight_megabytes_use_the_configured_storage_quota(tmp_path):
    from capstone_agent.general_pi_storage import GeneralPiStorage
    from capstone_agent.general_pi_executor import collect_artifacts
    storage = GeneralPiStorage(tmp_path / 'receipts', max_bytes=32 * 1024**2)
    workspace = tmp_path / 'work'
    workspace.mkdir()
    for index in range(3):
        (workspace / f'data-{index}.csv').write_bytes(bytes([65 + index]) * (3 * 1024**2))
    artifacts = collect_artifacts(workspace, 'task', 'attempt')
    storage.artifacts('task', workspace, artifacts)
    storage.save({'task_id': 'task'}, {'artifacts': artifacts})
    for artifact in artifacts:
        assert len(storage.read_artifact('task', artifact['artifact_id'])) == 3 * 1024**2


def test_receipt_quota_failure_settles_and_keeps_verified_file_metadata(tmp_path, monkeypatch):
    from capstone_agent.application_capacity import CapacityExceeded
    from capstone_agent.general_pi_server import GeneralPiHost
    def run(request, *_):
        workspace = tmp_path / 'tasks' / request.task_id
        workspace.mkdir(parents=True)
        (workspace / 'product.txt').write_text('Product')
        return 'Done', {}
    host = GeneralPiHost(root=tmp_path, identity={'engine': 'pi'}, run_task=run)
    original = host.storage.save
    def save(request, result):
        if result is not None:
            raise CapacityExceeded('native_storage_bytes', 2049, 2048, 'persistence')
        return original(request, result)
    monkeypatch.setattr(host.storage, 'save', save)
    request = PiTaskRequest.from_document({'schema': 'capstone-pi-task/1', 'task_id': 't1',
        'parent_attempt_id': 'a1', 'entrypoint': 'direct', 'instruction': 'Explain', 'messages': [],
        'dependency_results': [], 'executor_identity': host.identity, 'timeout_seconds': 2})
    host.submit(request)
    deadline = time.monotonic() + 2
    while host.read('t1')['status'] == 'running' and time.monotonic() < deadline:
        time.sleep(.01)
    result = host.read('t1')['result']
    assert result['status'] == 'failed'
    assert result['failure']['capacity']['limit'] == 2048
    assert len(result['artifacts']) == 1
    assert (tmp_path / 'tasks/t1/product.txt').read_text() == 'Product'


def test_partial_persistence_keeps_verified_saved_descriptors(tmp_path, monkeypatch):
    from capstone_agent.general_pi_storage import GeneralPiStorage
    from capstone_agent.general_pi_executor import collect_artifacts
    storage = GeneralPiStorage(tmp_path / 'receipts')
    workspace = tmp_path / 'work'
    workspace.mkdir()
    (workspace / 'a.txt').write_text('first')
    (workspace / 'b.txt').write_text('second')
    original = storage._write
    calls = []
    def write(path, data):
        calls.append(path)
        if len(calls) == 2:
            raise OSError('storage unavailable')
        original(path, data)
    monkeypatch.setattr(storage, '_write', write)
    with pytest.raises(OSError) as failure:
        storage.artifacts('task', workspace, collect_artifacts(workspace, 'task', 'attempt'))
    assert [item['metadata']['path'] for item in failure.value.saved_artifacts] == ['a.txt']
