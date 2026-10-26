"""Normal conversation crosses the real command, worker, and Pi runtime seams."""
from dataclasses import replace

import pytest

from capstone_agent.intent_runtime import IntentRuntimeFactory
from capstone_agent.thread_service import InMemoryThreadService
from capstone_agent.thread_worker import run_pending_attempt
from test_native_pack_preparation import executor as resource_executor
from test_thread_postgres import _snapshot, postgres_thread_service
from test_thread_work_execution import command
from test_delegated_runtime import Executor


@pytest.fixture(params=['memory', 'postgres'])
def chat_store(request):
    if request.param == 'memory':
        thread_id = 'thr_native_chat'
        snapshot = replace(_snapshot(thread_id), active_model_context=None, active_grid_page_id=None,
                           minimum_protocol_version=2)
        return InMemoryThreadService(snapshot), thread_id
    store, thread_id = request.getfixturevalue('postgres_thread_service')
    store.create_thread(replace(_snapshot(thread_id), active_model_context=None, active_grid_page_id=None,
                                minimum_protocol_version=2))
    return store, thread_id


def native_executor():
    executor = Executor()
    executor.capability = {**executor.capability,
        'resource_profiles': resource_executor().capability['resource_profiles'],
        'native_tools': ['read', 'bash', 'edit', 'write'],
        'native_builtin_tools': ['read', 'bash', 'edit', 'write'],
        'native_context_schemas': ['capstone-native-context/1']}
    return executor


def test_send_message_runs_and_followup_uses_same_work_history(chat_store, tmp_path):
    store, thread_id = chat_store
    executor = native_executor()
    store.set_native_executor(executor)
    def forbidden(*args):
        raise AssertionError('normal native conversation must not prepare a business runtime or planner')
    factory = IntentRuntimeFactory(forbidden, forbidden, forbidden, general_executor=executor,
                                   native_research_root=tmp_path)
    first = command(store, thread_id, 'send_message', 'first', payload={'text': 'Hello'})
    receipt = store.submit_command(first)
    assert receipt.status == 'accepted'
    assert store.submit_command(first) == receipt
    queued = store.snapshot(thread_id).to_document()
    assert queued['active_model_context'] is None
    assert queued['current_attempt']['target_model_context_id'] is None
    assert queued['current_attempt']['work_id'] == receipt.target['id']
    result = run_pending_attempt(store, factory, worker_id='native-test', implementation_family='native')
    assert result.status == 'completed', [e.payload for e in store.read_events(thread_id, 0).events if e.event_type == 'attempt_failed']
    work = store.snapshot(thread_id).to_document()['works'][0]
    second = command(store, thread_id, 'send_message', 'second', work_id=work['work_id'],
                     revision=work['revision'], payload={'text': 'Explain that answer'})
    assert store.submit_command(second).status == 'accepted'
    result = run_pending_attempt(store, factory, worker_id='native-test', implementation_family='native')
    assert result.status == 'completed'
    assert len(executor.requests) == 2
    assert any(message['content'] == 'General answer' for message in executor.requests[1].messages)
    assert store.snapshot(thread_id).current_attempt is None
    assert store.snapshot(thread_id).works[0]['task_context']['binding'] == work['task_context']['binding']
    completed = [event for event in store.read_events(thread_id, 0).events if event.event_type == 'attempt_completed']
    assert len(completed) == 2
    assert all(not event.payload.get('result_refs') and not event.payload.get('evidence_refs') for event in completed)
    research = [event for event in store.read_events(thread_id, 0).events if event.event_type == 'research_state_updated']
    assert len(research) == 2
    assert {event.payload['research_id'] for event in research} == {work['task_context']['binding']['research_id']}
    assert executor.requests[1].to_document()['native_context']['selected_task_records']
    assert executor.requests[0].to_document()['native_context']['policy']['external_lookup_enabled'] is False
    extra = store.submit_command(command(store, thread_id, 'send_message', 'second_new', payload={'text': 'New again'}))
    assert extra.status == 'rejected'
    assert extra.rejection == 'conversation_work_exists'
    assert len(store.snapshot(thread_id).works) == 1


def test_unavailable_send_does_not_partially_save_input(chat_store):
    store, thread_id = chat_store
    receipt = store.submit_command(command(store, thread_id, 'send_message', 'unavailable', payload={'text': 'Hello'}))
    assert receipt.status == 'rejected'
    assert receipt.rejection == 'execution_unavailable'
    assert store.snapshot(thread_id).works == ()
    assert store.snapshot(thread_id).current_attempt is None


def test_general_entry_keeps_shared_organization_and_history_for_followup(chat_store, tmp_path):
    from capstone_agent.native_task_context import research_policy_capabilities
    store, thread_id = chat_store
    if isinstance(store, InMemoryThreadService):
        store._snapshot = replace(store._snapshot, session_type='general-chat')
    else:
        import psycopg
        with psycopg.connect(store.dsn) as connection:
            connection.execute('UPDATE capstone_threads SET session_type=%s WHERE thread_id=%s',
                               ('general-chat', thread_id))
    executor = native_executor()
    executor.capability.update({
        'research_bridge_schemas': ['capstone-research-bridge/1'],
        'delivery_review_schemas': ['capstone-delivery-review/1'],
        'research_graph_schemas': ['capstone-enterprise-graph/2'],
        'research_policy_profiles': research_policy_capabilities(),
    })
    executor.execute_with_research = lambda request, control, emit, bridge: executor.execute(request, control, emit)
    store.set_native_executor(executor)
    def forbidden(*args):
        raise AssertionError('native organization must not prepare a scientific model')
    factory = IntentRuntimeFactory(forbidden, forbidden, forbidden, general_executor=executor,
                                   native_research_root=tmp_path)
    first = store.submit_command(command(store, thread_id, 'send_message', 'shared_first',
                                         payload={'text': 'Explain this goal briefly'}))
    assert first.status == 'accepted'
    assert run_pending_attempt(store, factory, worker_id='shared', implementation_family='native').status == 'completed'
    work = store.snapshot(thread_id).works[0]
    second = store.submit_command(command(store, thread_id, 'send_message', 'shared_followup',
        work_id=work['work_id'], revision=work['revision'], payload={'text': 'Now inspect the supplied data and state any gaps'}))
    assert second.status == 'accepted'
    assert run_pending_attempt(store, factory, worker_id='shared', implementation_family='native').status == 'completed'
    assert store.snapshot(thread_id).session_type == 'general-chat'
    assert len(store.snapshot(thread_id).works) == 1
    assert len(executor.requests) == 2
    for request in executor.requests:
        assert request.native_context['policy']['external_lookup_enabled'] is False
        assert 'agent_research_plan' in request.native_context['policy']['allowed_tools']
        assert request.research_binding is not None
    assert any(message['content'] == 'General answer' for message in executor.requests[1].messages)


@pytest.mark.parametrize('phase', ['queued', 'running'])
def test_normal_conversation_stop_uses_existing_cancel_and_keeps_unconsumed_input(chat_store, phase, monkeypatch):
    from itertools import count
    ticks = count(step=.2)
    monkeypatch.setattr('capstone_agent.harness.monotonic', lambda: next(ticks))
    store, thread_id = chat_store
    executor = native_executor()
    store.set_native_executor(executor)
    receipt = store.submit_command(command(store, thread_id, 'send_message', 'stop_send', payload={'text': 'Continue explaining'}))
    def cancel():
        work = store.snapshot(thread_id).works[0]
        result = store.submit_command(command(store, thread_id, 'cancel_work', 'stop',
            work_id=work['work_id'], revision=work['revision']))
        assert result.status == 'accepted'
    if phase == 'queued':
        cancel()
    else:
        def execute(request, control, on_event):
            executor.requests.append(request)
            cancel()
            control.checkpoint()
        executor.execute = execute
    factory = IntentRuntimeFactory(None, None, None, general_executor=executor)
    assert store.claim_attempt('professional', 30, 'pandapower') is None
    result = run_pending_attempt(store, factory, worker_id='native', implementation_family='native')
    assert result.status == 'cancelled'
    assert store.snapshot(thread_id).works[0]['messages'] == ['Continue explaining']
    assert store.snapshot(thread_id).works[0]['status'] == 'cancelled'


def test_native_failure_is_failed_instead_of_a_completed_placeholder(chat_store):
    store, thread_id = chat_store
    executor = native_executor()
    store.set_native_executor(executor)
    def execute(*args):
        raise RuntimeError('offline failure fixture')
    executor.execute = execute
    store.submit_command(command(store, thread_id, 'send_message', 'failed', payload={'text': 'Hello'}))
    result = run_pending_attempt(store, IntentRuntimeFactory(None, None, None, general_executor=executor),
        worker_id='native', implementation_family='native')
    assert result.status == 'failed'
    assert store.snapshot(thread_id).works[0]['status'] == 'failed'
    assert store.snapshot(thread_id).works[0]['messages'] == ['Hello']


@pytest.mark.parametrize('terminal', ['cancelled', 'failed', 'interrupted'])
def test_new_conversation_instruction_does_not_replay_prior_unfinished_input(chat_store, terminal):
    store, thread_id = chat_store
    store.set_native_executor(native_executor())
    old_text = 'Perform the long research task and write its report'
    new_text = 'List active processes in the isolated task environment'
    assert store.submit_command(command(store, thread_id, 'send_message', 'superseded_old',
                                       payload={'text': old_text})).status == 'accepted'
    previous = store.claim_attempt('old', 30)
    assert previous is not None
    store.finish_attempt(previous, phase=terminal, payload={})
    work = store.snapshot(thread_id).works[0]
    assert work['messages'] == [old_text]  # Explicit retry remains possible before a new instruction.
    request = command(store, thread_id, 'send_message', 'superseding_new',
        work_id=work['work_id'], revision=work['revision'], payload={'text': new_text})
    accepted = store.submit_command(request)
    assert accepted.status == 'accepted'
    assert store.submit_command(request) == accepted
    current = store.claim_attempt('new', 30)
    assert current is not None
    assert current.instruction == new_text
    assert current.task_context.binding == previous.task_context.binding
    assert any(message['content'] == old_text and message['status'] == terminal
               for message in current.conversation_context.to_document()['messages'])
    assert previous.instruction == old_text


def test_explicit_work_retry_keeps_the_cancelled_instruction(chat_store):
    store, thread_id = chat_store
    store.set_native_executor(native_executor())
    text = 'Continue the original investigation'
    assert store.submit_command(command(store, thread_id, 'send_message', 'retry_original',
        payload={'text': text})).status == 'accepted'
    old = store.claim_attempt('old', 30)
    assert old is not None
    store.finish_attempt(old, phase='cancelled', payload={})
    work = store.snapshot(thread_id).works[0]
    assert store.submit_command(command(store, thread_id, 'start_work', 'retry_exact',
        work_id=work['work_id'], revision=work['revision'])).status == 'accepted'
    retried = store.claim_attempt('retry', 30)
    assert retried is not None and retried.instruction == text


def test_worker_receives_only_the_new_instruction_after_cancel(chat_store, tmp_path):
    store, thread_id = chat_store
    executor = native_executor()
    store.set_native_executor(executor)
    old_text, new_text = 'Write the previous long research report', 'Show active isolated processes'
    assert store.submit_command(command(store, thread_id, 'send_message', 'worker_old',
        payload={'text': old_text})).status == 'accepted'
    previous = store.claim_attempt('old', 30)
    assert previous is not None
    store.finish_attempt(previous, phase='cancelled', payload={})
    before = store.snapshot(thread_id)
    work = before.works[0]
    stale = command(store, thread_id, 'send_message', 'worker_stale',
        work_id=work['work_id'], revision=0, payload={'text': new_text})
    assert store.submit_command(stale).rejection == 'revision_conflict'
    assert store.snapshot(thread_id).works == before.works
    assert store.submit_command(command(store, thread_id, 'send_message', 'worker_new',
        work_id=work['work_id'], revision=work['revision'], payload={'text': new_text})).status == 'accepted'
    result = run_pending_attempt(store, IntentRuntimeFactory(None, None, None,
        general_executor=executor, native_research_root=tmp_path),
        worker_id='native', implementation_family='native')
    assert result.status == 'completed'
    assert len(executor.requests) == 1 and executor.requests[0].instruction == new_text
    assert any(message['content'] == old_text and message['status'] == 'cancelled'
               for message in executor.requests[0].messages)


def test_native_input_catalog_and_selected_skill_are_consumed(chat_store):
    store, thread_id = chat_store
    executor = native_executor()
    profile = executor.capability['resource_profiles']['delegated_pi']
    profile['resources'] = [{'id': 'write-clear', 'kind': 'skill', 'version': '1.0.0',
        'source': 'registered-fixture', 'roles': ['delegated_pi'], 'enabled': True,
        'installed': True, 'ready': True, 'reason': None, 'required_tools': [], 'loaded_identity': 'c' * 64}]
    profile['load_receipt']['skills'] = {'write-clear': 'c' * 64}
    store.set_native_executor(executor)
    catalog = store.input_catalog(thread_id)
    assert catalog['context_id'] is None
    assert catalog['objects'] == []
    assert catalog['resource_profiles']['delegated_pi']['resources'][0]['ready'] is True
    payload = {'text': 'Rewrite clearly', 'input': {'kind': 'skill_invocation', 'text': 'Rewrite clearly',
        'skill_id': 'write-clear', 'skill_version': '1.0.0'},
        'resource_profile': {'profile_id': 'delegated_pi', 'revision': profile['revision']},
        'context_selection': {'include_refs': [], 'exclude_refs': []}}
    receipt = store.submit_command(command(store, thread_id, 'send_message', 'skill', payload=payload))
    assert receipt.status == 'accepted'
    result = run_pending_attempt(store, IntentRuntimeFactory(None, None, None, general_executor=executor),
        worker_id='native', implementation_family='native')
    assert result.status == 'completed'
    assert executor.requests[0].to_document()['input'] == payload['input']
    assert executor.requests[0].to_document()['resource_profile'] == payload['resource_profile']


@pytest.mark.parametrize('environment,expected_timeout', [
    ({}, 7200),
    ({'CAPSTONE_THREAD_ATTEMPT_TIMEOUT_SECONDS': '1200'}, 7200),
    ({'CAPSTONE_THREAD_ATTEMPT_TIMEOUT_SECONDS': '900',
      'CAPSTONE_ENTERPRISE_RESEARCH_TIMEOUT_SECONDS': '1800'}, 1800),
    ({'CAPSTONE_ENTERPRISE_RESEARCH_TIMEOUT_SECONDS': '7200'}, 7200),
])
def test_real_general_host_http_transport_runs_the_same_worker_chain(chat_store, tmp_path, monkeypatch,
                                                                    environment, expected_timeout):
    import threading
    from capstone_agent.general_pi_server import GeneralPiHost, make_server
    from capstone_agent.pi_delegation import HttpGeneralPiExecutor
    from capstone_agent.native_hosted_worker import native_runtime_factory
    monkeypatch.setenv('NO_PROXY', '127.0.0.1,localhost')
    monkeypatch.setenv('no_proxy', '127.0.0.1,localhost')
    fixture = native_executor()
    received = []
    def native_process_boundary(request, cancelled, emit):
        received.append(request)
        assert not cancelled()
        for index in range(300):
            emit({'type': 'message_update', 'assistantMessageEvent': {
                'type': 'text_delta', 'delta': f'progress {index}\n'}})
        emit({'type': 'text_delta', 'text': 'Offline HTTP reply'})
        return 'Offline HTTP reply', {}
    host = GeneralPiHost(root=tmp_path / 'host', identity=fixture.identity, run_task=native_process_boundary)
    host.capability = fixture.capability
    server = make_server(host, control_token='test-only-control', address=('127.0.0.1', 0))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        executor = HttpGeneralPiExecutor(f'http://127.0.0.1:{server.server_port}',
            identity=host.identity, capability=host.capability, control_token='test-only-control')
        store, thread_id = chat_store
        store.set_native_executor(executor)
        request = command(store, thread_id, 'send_message', 'http', payload={'text': 'Hello over HTTP'})
        receipt = store.submit_command(request)
        assert receipt.status == 'accepted'
        result = run_pending_attempt(store, native_runtime_factory(executor, research_root=tmp_path / 'research',
                                     environment=environment),
            worker_id='native', implementation_family='native')
        assert result.status == 'completed'
        assert result.answer == 'Offline HTTP reply'
        assert store.submit_command(request) == receipt
        assert len(received) == 1
        assert received[0].timeout_seconds == expected_timeout
        deltas, after = [], 0
        while True:
            page = store.read_events(thread_id, after)
            deltas.extend(event.payload['text'] for event in page.events
                          if event.event_type == 'assistant_process_delta')
            if not page.has_more:
                break
            after = page.next_event_seq
        # Transport may coalesce adjacent deltas before persistence. The text
        # order and full content, rather than token-event boundaries, are public.
        assert ''.join(deltas) == ''.join(f'progress {index}\n' for index in range(300))
        assert list((tmp_path / 'host/receipts/records').glob('*.json'))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_native_postgres_restart_retains_accepted_configuration_and_old_lease_cannot_write(postgres_thread_service):
    import psycopg
    from capstone_agent.thread_service import PostgresThreadService, ThreadExecutionError
    store, thread_id = postgres_thread_service
    store.create_thread(replace(_snapshot(thread_id), active_model_context=None, active_grid_page_id=None,
                                minimum_protocol_version=2))
    executor = native_executor()
    store.set_native_executor(executor)
    request = command(store, thread_id, 'send_message', 'restart', payload={'text': 'Keep this input'})
    receipt = store.submit_command(request)
    restored = PostgresThreadService(store.dsn)
    restored.set_native_executor(executor)
    assert restored.submit_command(request) == receipt
    claim = restored.claim_attempt('native', 30, 'native')
    assert claim.model_context is None
    assert claim.task_context.model_contexts == ()
    frozen = claim.submission['_native_execution']
    executor.identity = {**executor.identity, 'config_revision': 'different-config'}
    assert claim.submission['_native_execution'] == frozen
    with psycopg.connect(store.dsn) as connection:
        connection.execute("UPDATE capstone_thread_attempts SET lease_deadline=clock_timestamp()-interval '1 second' WHERE attempt_id=%s",
                           (claim.attempt.attempt_id,))
    assert restored.interrupt_expired_attempts() == 1
    assert restored.snapshot(thread_id).works[0]['status'] == 'interrupted'
    assert restored.snapshot(thread_id).works[0]['messages'] == ['Keep this input']
    with pytest.raises(ThreadExecutionError, match='lease'):
        restored.finish_attempt(claim, phase='completed', payload={'answer': 'late'})
    work = restored.snapshot(thread_id).works[0]
    executor.identity = frozen['identity']
    restored.set_native_executor(executor)
    next_request = command(restored, thread_id, 'send_message', 'after_expiry', work_id=work['work_id'],
        revision=work['revision'], payload={'text': 'Continue'})
    assert restored.submit_command(next_request).status == 'accepted'
    current = restored.claim_attempt('replacement', 30, 'native')
    assert current.instruction == 'Continue'
    assert any(message['content'] == 'Keep this input' and message['status'] == 'interrupted'
               for message in current.conversation_context.to_document()['messages'])
    with pytest.raises(ThreadExecutionError, match='lease'):
        restored.finish_attempt(claim, phase='completed', payload={'answer': 'late again'})
    restored.finish_attempt(current, phase='failed', payload={'error_code': 'fixture_end'})


def test_native_configuration_drift_fails_without_calling_executor(chat_store):
    store, thread_id = chat_store
    executor = native_executor()
    store.set_native_executor(executor)
    store.submit_command(command(store, thread_id, 'send_message', 'drift', payload={'text': 'Hello'}))
    executor.identity = {**executor.identity, 'config_revision': 'changed-after-acceptance'}
    result = run_pending_attempt(store, IntentRuntimeFactory(None, None, None, general_executor=executor),
        worker_id='native', implementation_family='native')
    assert result.status == 'failed'
    assert executor.requests == []
    assert store.snapshot(thread_id).works[0]['messages'] == ['Hello']


def test_native_malformed_or_stale_typed_input_does_not_advance_work(chat_store):
    store, thread_id = chat_store
    executor = native_executor()
    store.set_native_executor(executor)
    for name, payload in [('mismatch', {'text': 'Hello', 'input': {'kind': 'text', 'text': 'Other'}}),
                          ('unknown_context', {'text': 'Hello', 'context_selection': {'include_refs': ['unknown'], 'exclude_refs': []}}),
                          ('professional', {'text': 'Hello', 'enabled_profiles': [{'profile_id': 'unknown', 'profile_version': '1'}]})]:
        receipt = store.submit_command(command(store, thread_id, 'send_message', name, payload=payload))
        assert receipt.status == 'rejected'
        assert store.snapshot(thread_id).works == ()
        assert store.snapshot(thread_id).current_attempt is None


def test_long_native_request_preserves_original_and_completes(chat_store, tmp_path):
    from capstone_agent.native_hosted_worker import native_runtime_factory

    store, thread_id = chat_store
    executor = native_executor()
    store.set_native_executor(executor)
    question = 'Long request: ' + 'context ' * 600 + 'ORIGINAL_SUFFIX'
    receipt = store.submit_command(command(store, thread_id, 'send_message',
        'long_request', payload={'text': question}))
    assert receipt.status == 'accepted'
    result = run_pending_attempt(store, native_runtime_factory(executor, research_root=tmp_path),
                                 worker_id='native', implementation_family='native')
    assert result.status == 'completed'
    assert executor.requests[0].instruction == question
    research = [event for event in store.read_events(thread_id, 0).events
                if event.event_type == 'research_state_updated']
    assert research[-1].payload['goal'] == question
    from capstone_agent.application_capacity import limits
    assert len(research[-1].payload['goal']) <= limits.research_goal_chars


def test_native_task_runner_rpc_process_reads_original_source_beyond_excerpt(chat_store, tmp_path, monkeypatch):
    import json
    import shutil
    import sys
    import threading
    from pathlib import Path
    import capstone_agent.general_pi_server as module
    from capstone_agent.general_pi_executor import GeneralPiProcess
    from capstone_agent.pi_delegation import HttpGeneralPiExecutor
    from capstone_agent.native_hosted_worker import native_runtime_factory
    from capstone_agent.enterprise_application import ConversationPolicy

    # macOS fixtures cannot switch UIDs. Only the OS privilege boundary is
    # adapted; NativeTaskRunner, launch materialization, RPC process, transport,
    # real shared record tool, leases, and terminal persistence remain real.
    monkeypatch.setattr(module.os, 'geteuid', lambda: 0)
    monkeypatch.setattr(module.os, 'chown', lambda *args: None)
    class LocalPiProcess(GeneralPiProcess):
        def __init__(self, command, environment, workspace, *, uid=None):
            super().__init__(command, environment, workspace)
    monkeypatch.setattr(module, 'GeneralPiProcess', LocalPiProcess)
    node = shutil.which('node')
    assert node is not None
    rpc = tmp_path / 'offline-rpc.py'
    rpc.write_text('''import json, os, subprocess, sys, traceback
from pathlib import Path
def fixture_failure(kind, error, tb):
    Path(__file__).with_suffix('.failure.txt').write_text(''.join(traceback.format_exception(kind, error, tb)) + str(getattr(error, 'output', '')))
sys.excepthook = fixture_failure
config = json.load(open(sys.argv[1]))
policy = config['applicationPolicy']['system_policy']
assert 'verified original saved bytes' in policy
assert 'do not expose private host or task workspace paths' in policy
materials = [item for item in config.get('contextFiles', []) if '/materials/' in item['path']]
facts = next(item for item in materials if item['path'].endswith('/facts.csv'))
assert Path(facts['path']).read_bytes() == b'item,value\\nA,42\\n'
document = next(item for item in materials if item['path'].endswith('/report.html'))
assert Path(document['path']).read_bytes() == b'<html>Original saved report</html>'
assert all(Path(item['path']).stat().st_mode & 0o222 == 0 for item in materials)
excerpt = next((item for item in materials if item['path'].endswith('/generated.md')), None)
explicit_excerpt = excerpt is not None and 'Leading excerpt only' in excerpt['content']
if explicit_excerpt:
    assert Path(excerpt['path']).read_bytes() == b'Recovered'
    assert 'excerpt' in excerpt['content'].lower()
previous_csv = next((item for item in materials if item['path'].endswith('/table.csv')), None)
if previous_csv:
    previous_bytes = Path(previous_csv['path']).read_bytes()
    assert previous_bytes == b'item,value\\nA,84\\n'
    number = int(previous_bytes.decode().splitlines()[1].split(',')[1]) + 1
else:
    number = int(Path(facts['path']).read_text().splitlines()[1].split(',')[1]) * 2
Path('table.csv').write_text('item,value\\nA,' + str(number) + '\\n')
frame = json.loads(sys.stdin.readline())
assert frame['type'] == 'prompt'
if 'CAPSTONE_SELECTED_TASK_RECORDS' in os.environ:
    extension = next(path for path in config['extensions'] if path.endswith('/task-record-tools.mjs'))
    code = """import {pathToFileURL} from 'node:url';
const {configureTaskRecordTool}=await import(pathToFileURL(process.argv[1]).href);
let tool; configureTaskRecordTool({registerTool(value){tool=value}},process.argv[2]);
let after=0, answer='';
while(true){const result=await tool.execute('read',{after}); if(result.isError)throw Error('read failed');
const page=JSON.parse(result.content[0].text); for(const event of page.events){
if(event.event_type==='attempt_completed')answer=event.payload.answer;}
if(!page.has_more)break; after=page.next_after;}
if(!answer.endsWith('SOURCE_SUFFIX') || (process.argv[3]==='long' && answer.length<=2048))throw Error('original source was lost');
console.log('Recovered SOURCE_SUFFIX');"""
    answer = subprocess.check_output([NODE, '--input-type=module', '-e', code, extension,
        os.environ['CAPSTONE_SELECTED_TASK_RECORDS'], 'excerpt' if explicit_excerpt else 'long'], text=True, stderr=subprocess.STDOUT).strip()
else:
    answer = 'A' * 3000 + 'SOURCE_SUFFIX'
Path('generated.md').write_text(answer)
print(json.dumps({'type':'message_update','assistantMessageEvent':{'type':'text_delta','delta':answer}}),flush=True)
print(json.dumps({'type':'agent_end','messages':[{'role':'assistant','content':[{'type':'text','text':answer}],
    'stopReason':'stop','usage':{}}]}),flush=True)
'''.replace('NODE', repr(node)))
    launch = module.native_pi_launch
    configs = []
    def fixture_launch(**kwargs):
        argv, environment = launch(**kwargs)
        configs.append(json.loads(Path(argv[-1]).read_text()))
        return (sys.executable, str(rpc), argv[-1]), environment
    monkeypatch.setattr(module, 'native_pi_launch', fixture_launch)
    config_root = tmp_path / 'config'
    config_root.mkdir()
    published = native_executor()
    runner_errors = []
    class CheckedTaskRunner(module.NativeTaskRunner):
        def __call__(self, *args, **kwargs):
            try:
                return super().__call__(*args, **kwargs)
            except Exception as error:
                import traceback
                runner_errors.append(traceback.format_exc())
                raise
    runner = CheckedTaskRunner(root=tmp_path / 'host', config_root=config_root,
        command=(sys.executable, str(rpc)), model='offline-fixture', relay_origin='http://127.0.0.1:1')
    host = module.GeneralPiHost(root=tmp_path / 'host', identity=published.identity, run_task=runner)
    host.capability = published.capability
    server = module.make_server(host, control_token='test-only-control', address=('127.0.0.1', 0))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        executor = HttpGeneralPiExecutor(f'http://127.0.0.1:{server.server_port}',
            identity=host.identity, capability=host.capability, control_token='test-only-control')
        store, thread_id = chat_store
        store.set_native_executor(executor)
        from capstone_agent.artifacts import MemoryObjectStore
        from capstone_agent.thread_materials import upload_material
        material_objects = MemoryObjectStore()
        store.set_material_store(material_objects)
        upload_material(store, material_objects, thread_id, 'facts.csv', b'item,value\nA,42\n')
        upload_material(store, material_objects, thread_id, 'report.html', b'<html>Original saved report</html>')
        factory = native_runtime_factory(executor, research_root=tmp_path / 'research')
        assert store.submit_command(command(store, thread_id, 'send_message', 'rpc_first', payload={'text': 'Remember the source'})).status == 'accepted'
        first = run_pending_attempt(store, factory, worker_id='native', implementation_family='native')
        assert first.status == 'completed', (runner_errors, [x['status'] for x in host._tasks.values()])
        work = store.snapshot(thread_id).works[0]
        assert store.submit_command(command(store, thread_id, 'send_message', 'rpc_second', work_id=work['work_id'],
            revision=work['revision'], payload={'text': 'Read the original suffix'})).status == 'accepted'
        second = run_pending_attempt(store, factory, worker_id='native', implementation_family='native')
        assert second.status == 'completed', (second, runner_errors,
            rpc.with_suffix('.failure.txt').read_text() if rpc.with_suffix('.failure.txt').exists() else '',
            [event.payload for event in store.read_events(thread_id, 0).events
             if event.event_type == 'attempt_failed'])
        assert second.answer == 'Recovered SOURCE_SUFFIX'
        from capstone_agent.native_artifact_projection import read_native_artifact
        artifacts = [event for event in store.read_events(thread_id, 0).events if event.event_type == 'native_artifact_published']
        assert len(artifacts) == 4
        assert all(event.visibility == 'public' for event in artifacts)
        descriptor = next(event.payload['artifact'] for event in reversed(artifacts) if event.payload['artifact']['file_name'] == 'generated.md')
        assert descriptor['work_id'] == work['work_id']
        assert descriptor['attempt_id'] == artifacts[-1].attempt_id
        published, content = read_native_artifact(store, executor, thread_id, descriptor['attempt_id'], descriptor['artifact_id'])
        assert content == b'Recovered SOURCE_SUFFIX'
        assert published['scope'] == 'instruction'
        versions = [event.payload['artifact'] for event in artifacts if event.payload['artifact']['file_name'] == 'table.csv']
        assert versions[0]['sha256'] != versions[1]['sha256']
        _, revised = read_native_artifact(store, executor, thread_id, versions[1]['attempt_id'], versions[1]['artifact_id'])
        assert revised == b'item,value\nA,85\n'
        assert configs[1]['applicationPolicy']['system_policy'] == ConversationPolicy().load()
        assert configs[1]['appendSystemPrompt'][-1] == ConversationPolicy().load()
        assert configs[1]['applicationPolicy']['external_lookup_enabled'] is False
        assert 'agent_task_records_read' in configs[1]['applicationPolicy']['allowed_tools']
        # An explicit excerpt keeps the full immutable source ref, but stages
        # only its declared bytes and cannot masquerade as the complete file.
        from capstone_agent.thread_products import product_index
        entry = next(item for item in product_index(store, thread_id)['products']
                     if item['ref']['origin'] == 'native_file' and item['source']['artifact_id'] == descriptor['artifact_id'])
        work = store.snapshot(thread_id).works[0]
        assert store.submit_command(command(store, thread_id, 'send_message', 'rpc_excerpt', work_id=work['work_id'],
            revision=work['revision'], payload={'text': 'Read the explicit leading excerpt', 'context_product_refs': [
                {'ref': entry['ref'], 'purpose': 'historical-context', 'excerpt': {'max_bytes': 9}}]})).status == 'accepted'
        third = run_pending_attempt(store, factory, worker_id='native', implementation_family='native')
        assert third.status == 'completed', runner_errors
        staged = next(item for item in configs[2]['contextFiles'] if item['path'].endswith('/generated.md'))
        assert 'excerpt' in staged['content'].lower()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
