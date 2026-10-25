from pathlib import Path
import json
import sys
import time

import pytest


@pytest.fixture(autouse=True)
def single_child_cleanup(monkeypatch):
    # This module's RPC fixtures create one child and no descendants. The macOS test
    # host can deny group signals; Linux retains the real group cleanup path.
    if sys.platform != 'darwin':
        return
    from capstone_agent.general_pi_executor import GeneralPiProcess
    def stop_fixture(process):
        assert process.uid is None, 'UID isolation needs the Linux integration fixture'
        child, process.process = process.process, None
        if child is not None:
            child.terminate()
            child.wait(timeout=1)
            for stream in (child.stdin, child.stdout, child.stderr):
                if stream is not None:
                    stream.close()
    monkeypatch.setattr(GeneralPiProcess, 'stop', stop_fixture)


@pytest.mark.parametrize('mode', ['normal', 'debug'])
@pytest.mark.parametrize('outcome', ['complete', 'cancelled', 'deadline'])
def test_native_frame_backpressure_keeps_the_queue_bounded_without_aborting_research(tmp_path, monkeypatch, single_child_cleanup, mode, outcome):
    from queue import Queue, Full
    from capstone_agent import general_pi_executor as module
    from capstone_agent.application_capacity import current_capacity, initialize_capacity
    previous = current_capacity()
    initialize_capacity({'native_rpc_queue_frames': 2}, mode=mode)
    class TrackedQueue(Queue):
        blocked = 0
        def put(self, *args, **kwargs):
            try:
                return super().put(*args, **kwargs)
            except Full:
                self.blocked += 1
                raise
    frames = TrackedQueue(maxsize=2)
    monkeypatch.setattr(module, 'Queue', lambda maxsize: frames)
    terminal = {'type': 'agent_end', 'messages': [{'role': 'assistant', 'stopReason': 'stop',
        'content': [{'type': 'text', 'text': 'Useful research answer'}]}]}
    script = tmp_path / 'burst.py'
    script.write_text('import sys,json\nsys.stdin.readline()\n'
        'for index in range(40): print(json.dumps({"type":"turn_start","index":index}),flush=True)\n'
        'print(' + repr(json.dumps(terminal)) + ',flush=True)\n')
    process = module.GeneralPiProcess((sys.executable, str(script)), {'PATH': '/usr/bin'}, tmp_path)
    observed = []
    def consume(event):
        observed.append(event['index'])
        if len(observed) == 1:
            time.sleep(0.2)  # The producer must wait, not exceed its two-frame buffer.
    try:
        run = lambda: process.run('task', timeout=0.1 if outcome == 'deadline' else 5,
            cancelled=lambda: outcome == 'cancelled' and bool(observed), on_event=consume)
        if outcome == 'complete':
            assert run() == 'Useful research answer'
            assert observed == list(range(40))
        else:
            with pytest.raises(InterruptedError if outcome == 'cancelled' else TimeoutError):
                run()
        assert frames.maxsize == 2 and frames.blocked > 0
        assert process.process is None
    finally:
        process.stop()
        initialize_capacity(previous)


@pytest.mark.parametrize('extra,missing,accepted', [([], False, True), (['bash'], False, False), ([], True, False)])
def test_process_inventory_matches_the_explicit_organization_role(tmp_path, extra, missing, accepted):
    from capstone_agent.general_pi_executor import GeneralPiProcess
    required = ('agent_research_plan', 'agent_research_record', 'agent_research_assess', 'agent_research_revise', 'agent_research_finish')
    tools = list(required[:-1] if missing else required) + extra
    script = tmp_path / 'role_inventory.py'
    event = {'type': 'general_pi_inventory', 'tools': tools}
    script.write_text('print(' + repr(json.dumps(event)) + ',flush=True)\n')
    process = GeneralPiProcess((sys.executable, str(script)), {'PATH': '/usr/bin'}, tmp_path,
        required_tools=required, forbidden_tools=('read', 'bash', 'write', 'edit', 'agent_delegate'))
    try:
        if accepted:
            process.run('inventory', timeout=5, cancelled=lambda: False, on_event=lambda _: None, inventory_only=True)
            assert set(process.tools) == set(required)
        else:
            with pytest.raises(ValueError, match='tool inventory'):
                process.run('inventory', timeout=5, cancelled=lambda: False, on_event=lambda _: None, inventory_only=True)
    finally:
        process.stop()


def test_native_no_progress_response_keeps_safe_reason_without_raw_message(tmp_path):
    from capstone_agent.general_pi_executor import GeneralPiProcess
    script = tmp_path / 'no_progress.py'
    event = {'type': 'response', 'success': False, 'code': 'continuation_no_progress',
             'phase': 'continuation', 'message': 'PRIVATE model instruction and diagnostics'}
    script.write_text('import sys\nsys.stdin.readline()\nprint(' + repr(json.dumps(event)) + ',flush=True)\n')
    process = GeneralPiProcess((sys.executable, str(script)), {'PATH': '/usr/bin'}, tmp_path)
    with pytest.raises(RuntimeError) as raised:
        process.run('task', timeout=5, cancelled=lambda: False, on_event=lambda _: None)
    assert str(raised.value) == 'continuation_no_progress'
    assert 'PRIVATE' not in str(raised.value)
    assert process.process is None


def test_failed_continuation_terminal_preserves_real_usage_and_never_succeeds(tmp_path):
    from capstone_agent.general_pi_executor import GeneralPiProcess
    assistants = [{'role': 'assistant', 'stopReason': 'stop', 'content': [], 'usage': {
        'input': 4, 'output': 2, 'cacheRead': 0, 'cacheWrite': 0, 'totalTokens': 6}} for _ in range(2)]
    event = {'type': 'agent_end', 'success': False, 'code': 'continuation_no_progress',
             'phase': 'continuation', 'messages': assistants}
    script = tmp_path / 'no_progress_usage.py'
    script.write_text('import sys\nsys.stdin.readline()\nprint(' + repr(json.dumps(event)) + ',flush=True)\n')
    process = GeneralPiProcess((sys.executable, str(script)), {'PATH': '/usr/bin'}, tmp_path)
    with pytest.raises(RuntimeError, match='^continuation_no_progress$') as raised:
        process.run('task', timeout=5, cancelled=lambda: False, on_event=lambda _: None)
    usage = raised.value.saved_usage
    assert usage['parent_model_responses'] == 2 and usage['parent_input'] == 8
    assert usage['total_model_responses'] == 2 and usage['total_input'] == 8
    assert usage['usage_complete'] is True


@pytest.mark.parametrize('kind', ['enterprise_cycle_progress', 'delegation_child_started', 'delegation_child_tool', 'delegation_child_finished', 'enterprise_graph_tool_failure'])
def test_cycle_progress_is_forwarded_without_counting_an_extra_model_response(tmp_path, single_child_cleanup, kind):
    from capstone_agent.general_pi_executor import GeneralPiProcess
    progress = {'type': kind, 'owner': {'thread_id': 'thread', 'work_id': 'work',
        'research_id': 'research', 'goal_revision': 1}, 'attempt_id': 'attempt', 'action_id': 'cycle-' + 'a' * 64,
        'checkpoint': {'ref': 'runtime.checkpoint.example', 'revision': 1},
        'progress': {'step_id': 'read', 'phase': 'started', 'text': 'Read sources'}}
    complete = {'type': 'agent_end', 'messages': [{'role': 'assistant', 'stopReason': 'stop',
        'content': [{'type': 'text', 'text': 'Answer'}], 'usage': {'input': 4, 'output': 2}}]}
    script = tmp_path / 'cycle_progress.py'
    script.write_text('import sys\nsys.stdin.readline()\n' + '\n'.join(
        'print(' + repr(json.dumps(event)) + ',flush=True)' for event in [progress, complete]))
    process = GeneralPiProcess((sys.executable, str(script)), {'PATH': '/usr/bin'}, tmp_path)
    events = []
    process.run('task', timeout=5, cancelled=lambda: False, on_event=events.append)
    assert events == [progress]
    assert process.usage['parent_model_responses'] == 1 and process.usage['parent_input'] == 4


def test_native_parent_child_usage_is_separate_complete_and_not_double_counted(tmp_path):
    from capstone_agent.general_pi_executor import GeneralPiProcess
    from capstone_agent.delegated_runtime import bounded_metadata
    children = [{'source': {'id': 'a'}, 'status': 'completed', 'answer': 'PRIVATE CHILD ANSWER',
                 'model_responses': 2, 'turns': 2,
                 'usage': [{'input': 3, 'output': 4, 'cacheRead': 0, 'cacheWrite': 0, 'totalTokens': 7},
                           {'input': 5, 'output': 6, 'cacheRead': 0, 'cacheWrite': 0, 'totalTokens': 11}]}]
    child_event = {'type': 'tool_execution_end', 'toolName': 'agent_delegate', 'toolCallId': 'delegate-1',
                   'result': {'details': {'schema': 'capstone-delegation-result/1', 'children': children}}}
    parent = {'role': 'assistant', 'stopReason': 'stop', 'content': [{'type': 'text', 'text': 'Answer'}],
              'usage': {'input': 10, 'output': 11, 'cacheRead': 0, 'cacheWrite': 0, 'totalTokens': 21}}
    frames = [{'type': 'tool_execution_start', 'toolName': 'agent_delegate', 'toolCallId': 'delegate-1'},
              child_event, child_event, {'type': 'message_end', 'message': parent}, {'type': 'turn_end'},
              {'type': 'agent_end', 'messages': [parent]}]
    script = tmp_path / 'usage.py'
    script.write_text('import sys\nsys.stdin.readline()\n' + '\n'.join('print(' + repr(json.dumps(e)) + ',flush=True)' for e in frames))
    process = GeneralPiProcess((sys.executable, str(script)), {'PATH': '/usr/bin'}, tmp_path)
    assert process.run('task', timeout=5, cancelled=lambda: False, on_event=lambda _: None) == 'Answer'
    assert process.usage['parent_input'] == 10 and process.usage['child_input'] == 8
    assert process.usage['total_input'] == 18 and process.usage['input'] == 18
    assert process.usage['parent_model_responses'] == 1
    assert process.usage['child_model_responses'] == 2 and process.usage['total_model_responses'] == 3
    assert process.usage['child_turns'] == 2
    receipt = bounded_metadata(process.usage)
    for key in ('parent_input', 'child_input', 'total_input', 'total_model_responses', 'child_turns'):
        assert receipt[key] == process.usage[key]
    first_thirty = dict(list(process.usage.items())[:30])
    assert all(value is None or type(value) in {bool, int, str} for value in first_thirty.values())
    assert {'parent_model_responses', 'child_model_responses', 'total_model_responses',
            'child_failed', 'child_cancelled', 'usage_complete', 'cost_status', 'totalTokens'} <= first_thirty.keys()
    assert bounded_metadata(first_thirty) == first_thirty
    assert 'PRIVATE CHILD ANSWER' not in str(process.usage)


def test_native_missing_child_receipt_is_unknown_even_when_parent_completes(tmp_path):
    from capstone_agent.general_pi_executor import GeneralPiProcess
    frames = [{'type': 'tool_execution_start', 'toolName': 'agent_delegate', 'toolCallId': 'missing'},
              {'type': 'agent_end', 'messages': [{'role': 'assistant', 'stopReason': 'stop',
                'content': [{'type': 'text', 'text': 'Answer'}], 'usage': {'input': 4, 'output': 2}}]}]
    script = tmp_path / 'unknown.py'
    script.write_text('import sys\nsys.stdin.readline()\n' + '\n'.join('print(' + repr(json.dumps(e)) + ',flush=True)' for e in frames))
    process = GeneralPiProcess((sys.executable, str(script)), {'PATH': '/usr/bin'}, tmp_path)
    process.run('task', timeout=5, cancelled=lambda: False, on_event=lambda _: None)
    assert process.usage['parent_input'] == 4
    assert process.usage['child_input'] is None and process.usage['total_input'] is None
    assert process.usage['child_model_responses'] is None
    assert process.usage['usage_complete'] is False


@pytest.mark.parametrize('missing_terminal', [False, True])
def test_graph_process_counts_exact_child_actions_and_preserves_unknown(tmp_path, missing_terminal):
    from capstone_agent.general_pi_executor import GeneralPiProcess
    token_usage = {'input': 1, 'output': 1, 'cacheRead': 0, 'cacheWrite': 0, 'totalTokens': 2}
    parent = {'role': 'assistant', 'stopReason': 'stop',
              'content': [{'type': 'text', 'text': 'Answer'}], 'usage': token_usage}
    frames = []
    for action, count in [('A', 6), ('B', 5), ('C', 7)]:
        started = {'type': 'enterprise_graph_child_started', 'action_id': 'action:' + action}
        frames.extend([started, started])
        frames.append({'type': 'enterprise_graph_child_response_started', 'action_id': 'action:' + action, 'response_number': 1})
        if missing_terminal and action == 'C':
            continue
        finished = {'type': 'enterprise_graph_child_finished', 'action_id': 'action:' + action,
                    'status': 'completed', 'model_responses': count, 'turns': count,
                    'usage': [token_usage] * count}
        frames.extend([finished, finished])
    for _ in range(24):
        frames.extend([{'type': 'message_end', 'message': parent}, {'type': 'turn_end'}])
    frames.append({'type': 'agent_end', 'messages': [parent] * 24})
    script = tmp_path / 'graph_usage.py'
    script.write_text('import sys\nsys.stdin.readline()\n' + '\n'.join(
        'print(' + repr(json.dumps(frame)) + ',flush=True)' for frame in frames)
        + '\nsys.stdin.readline()\n')
    process = GeneralPiProcess((sys.executable, str(script)), {'PATH': '/usr/bin'}, tmp_path)
    observed = []
    process.run('task', timeout=5, cancelled=lambda: False, on_event=observed.append)
    assert len([event for event in observed if event['type'] == 'enterprise_graph_child_response_started']) == 3
    usage = process.usage
    assert usage['parent_model_responses'] == 24
    assert usage['child_model_responses'] == (None if missing_terminal else 18)
    assert usage['child_turns'] == (None if missing_terminal else 18)
    assert usage['total_model_responses'] == (None if missing_terminal else 42)
    assert usage['child_input'] == (None if missing_terminal else 18)
    assert usage['total_input'] == (None if missing_terminal else 42)
    assert usage['usage_complete'] is (not missing_terminal)


def test_native_child_missing_token_field_does_not_claim_complete_usage():
    from capstone_agent.general_pi_executor import _NativeUsage
    observed = _NativeUsage()
    observed.observe({'type': 'tool_execution_end', 'toolName': 'agent_delegate', 'toolCallId': 'partial-usage',
                      'result': {'details': {'schema': 'capstone-delegation-result/1', 'children': [
                          {'status': 'completed', 'model_responses': 1, 'turns': 1,
                           'usage': [{'input': 3, 'output': 4, 'cacheWrite': 0, 'totalTokens': 7}]}]}}})
    observed.observe({'type': 'agent_end', 'messages': [{'role': 'assistant', 'usage': {
        'input': 10, 'output': 11, 'cacheRead': 0, 'cacheWrite': 0, 'totalTokens': 21}}]})
    summary = observed.summary()
    assert summary['total_input'] == 13 and summary['total_model_responses'] == 2
    assert summary['child_cacheRead'] is None and summary['total_cacheRead'] is None
    assert summary['usage_complete'] is False


def test_native_failure_retains_observed_usage_for_host_terminal_receipt(tmp_path):
    from capstone_agent.general_pi_executor import GeneralPiProcess
    frames = [{'type': 'message_end', 'message': {'role': 'assistant', 'usage': {'input': 4, 'output': 2}}},
              {'type': 'response', 'success': False}]
    script = tmp_path / 'failed_usage.py'
    script.write_text('import sys\nsys.stdin.readline()\n' + '\n'.join('print(' + repr(json.dumps(e)) + ',flush=True)' for e in frames))
    process = GeneralPiProcess((sys.executable, str(script)), {'PATH': '/usr/bin'}, tmp_path)
    with pytest.raises(RuntimeError) as raised:
        process.run('task', timeout=5, cancelled=lambda: False, on_event=lambda _: None)
    assert raised.value.saved_usage['parent_input'] == 4
    assert raised.value.saved_usage['parent_model_responses'] == 1
    assert raised.value.saved_usage['usage_complete'] is False


@pytest.mark.parametrize('answer_limit,succeeds', [(100_000, True), (89_999, False)])
def test_general_rpc_answer_uses_initialized_utf8_capacity(tmp_path, answer_limit, succeeds):
    from capstone_agent.application_capacity import CapacityExceeded, current_capacity, initialize_capacity
    from capstone_agent.general_pi_executor import GeneralPiProcess
    original = current_capacity()
    script = tmp_path / 'large_answer.py'
    script.write_text("import json,sys\nsys.stdin.readline()\nprint(json.dumps({'type':'agent_end','messages':["
                      "{'role':'assistant','stopReason':'stop','content':[{'type':'text','text':'字'*30000}]}]}),flush=True)\n")
    try:
        initialize_capacity({'answer_bytes': answer_limit, 'rpc_frame_bytes': 400_000})
        process = GeneralPiProcess((sys.executable, str(script)), {'PATH': '/usr/bin'}, tmp_path)
        if succeeds:
            assert process.run('task', timeout=5, cancelled=lambda: False, on_event=lambda _: None) == '字' * 30000
        else:
            with pytest.raises(CapacityExceeded) as raised:
                process.run('task', timeout=5, cancelled=lambda: False, on_event=lambda _: None)
            assert raised.value.dimension == 'answer_bytes'
            assert raised.value.actual == 90_000 and raised.value.limit == answer_limit
        assert process.process is None
    finally:
        initialize_capacity(original)


@pytest.mark.parametrize('dimension,phase', [('rpc_frame_bytes', 'native_prompt'), ('input_text_chars', 'native_input')])
@pytest.mark.parametrize('mode',['normal','debug'])
def test_native_prompt_capacity_receipt_preserves_structured_failure(tmp_path, dimension, phase, mode):
    from capstone_agent.application_capacity import CapacityExceeded
    from capstone_agent.general_pi_executor import GeneralPiProcess
    script = tmp_path / 'capacity_response.py'
    event = {'type': 'response', 'success': False, 'code': 'capacity_exceeded',
             'capacity': {'dimension': dimension, 'actual': 101, 'limit': 100, 'phase': phase}}
    if mode=='debug':event['capacity']['mode']='debug'
    script.write_text('import sys\nsys.stdin.readline()\nprint(' + repr(json.dumps(event)) + ',flush=True)\n')
    process = GeneralPiProcess((sys.executable, str(script)), {'PATH': '/usr/bin'}, tmp_path)
    with pytest.raises(CapacityExceeded) as raised:
        process.run('task', timeout=5, cancelled=lambda: False, on_event=lambda _: None)
    assert raised.value.dimension == dimension
    assert raised.value.actual == 101 and raised.value.limit == 100
    assert raised.value.phase == phase
    assert raised.value.mode == mode


def test_real_sdk_parallel_image_reads_fit_runtime_frames_without_losing_model_images(tmp_path):
    import os
    import random
    import shutil
    import struct
    import zlib
    from capstone_agent.general_pi_executor import GeneralPiProcess
    root = Path(__file__).resolve().parents[3]
    sdk = root / '.grid-agent/runtime/pi/source/packages/coding-agent/dist/index.js'
    assert sdk.is_file(), 'Run make install-pi before the pinned SDK acceptance'
    node = shutil.which('node')
    assert node is not None
    def chunk(kind, content):
        return struct.pack('!I', len(content)) + kind + content + struct.pack('!I', zlib.crc32(kind + content))
    pixels = random.Random(0).randbytes(1024 * 1024 * 3)
    scanlines = b''.join(b'\0' + pixels[row*3072:(row+1)*3072] for row in range(1024))
    png = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!IIBBBBB', 1024, 1024, 8, 2, 0, 0, 0))
           + chunk(b'IDAT', zlib.compress(scanlines)) + chunk(b'IEND', b''))
    (tmp_path / 'chart.png').write_bytes(png)
    agent = tmp_path / '.agent'
    agent.mkdir()
    config = tmp_path / 'sdk.json'
    config.write_text(json.dumps({'sdk': str(sdk), 'model': 'offline-image', 'settings': {},
        'extensions': [], 'contextFiles': [], 'allowedSkills': [], 'mcp': None,
        'input': {'kind': 'text', 'text': 'Read both images'},
        'applicationPolicy': {'allowed_tools': ['read', 'bash', 'write', 'edit']}}))
    fixture = Path(__file__).parent / 'fixtures/image-sdk-offline.mjs'
    entry = Path(__file__).parents[1] / 'src/capstone_agent/resources/general-sdk.mjs'
    process = GeneralPiProcess((node, str(fixture), str(config), str(entry)),
        {**os.environ, 'HOME': str(tmp_path), 'PI_CODING_AGENT_DIR': str(agent)}, tmp_path)
    events = []
    answer = process.run('Read both images', timeout=30, cancelled=lambda: False, on_event=events.append)
    assert answer == 'Both original images were available to the model.'
    reads = [event for event in events if event['type'] == 'tool_execution_end']
    assert len(reads) == 2
    assert max(len(json.dumps(event).encode()) for event in events) < 262144
    assert all('binary omitted' in str(event['result']) for event in reads)


def test_native_launch_keeps_general_tools_and_native_discovery(tmp_path):
    from capstone_agent.general_pi_executor import native_pi_launch
    config = tmp_path / 'config'
    config.mkdir()
    (config / 'settings.json').write_text('{}')
    argv, env = native_pi_launch(command=('node', '/opt/pi/cli.js'), workspace=tmp_path / 'task',
        config_root=config, model='test', relay_url='http://127.0.0.1:8790/provider/task',
        relay_token='task-grant', context_extension=Path('/opt/context.mjs'))
    assert '--mode' in argv and 'rpc' in argv
    assert not {'--no-builtin-tools', '--no-skills', '--no-extensions', '--no-context-files'} & set(argv)
    assert '--system-prompt' not in argv
    assert set(env) <= {'PATH', 'HOME', 'LANG', 'PI_CODING_AGENT_DIR', 'PI_OFFLINE'}
    assert env['HOME'] == str(tmp_path / 'task')
    models = json.loads((tmp_path / 'task/.agent/models.json').read_text())
    assert models['providers']['capstone-general']['baseUrl'].endswith('/provider/task')
    assert models['providers']['capstone-general']['apiKey'] == 'task-grant'


def test_native_sdk_launch_uses_host_input_and_immutable_config(tmp_path):
    from capstone_agent.general_pi_executor import native_pi_launch
    config = tmp_path / 'config'
    config.mkdir()
    (config / 'settings.json').write_text('{}')
    sdk = {'sdk': '/opt/pi/packages/coding-agent/dist/index.js', 'input': {'kind': 'text', 'text': '/literal'}}
    (config / 'skills').mkdir()
    (config / 'skills/current-unaccepted.md').write_text('Current inputs must not replace acceptance.')
    workspace = tmp_path / 'task'
    argv, _ = native_pi_launch(command=('node', '/opt/pi/packages/coding-agent/dist/cli.js'),
        workspace=workspace, config_root=config, model='test', relay_url='http://127.0.0.1/relay',
        relay_token='grant', context_extension=Path('/opt/context.mjs'), sdk_config=sdk)
    assert argv[1].endswith('general-sdk.mjs') and '--mode' not in argv
    path = Path(argv[2])
    assert path.parent.name == '.inputs-task' and path.parent.parent == workspace.parent
    assert path.stat().st_mode & 0o222 == 0
    assert json.loads(path.read_text())['input'] == sdk['input']
    assert not (workspace / '.agent/skills').exists()


def test_sdk_task_preserves_extension_relative_imports_and_assets(tmp_path):
    from capstone_agent.general_pi_executor import native_pi_launch
    import subprocess
    config = tmp_path / 'config'
    config.mkdir()
    (config / 'extension.mjs').write_text('import {value} from "./helper.mjs"; export {value};')
    (config / 'helper.mjs').write_text('import {readFileSync} from "node:fs"; export const value=readFileSync(new URL("./asset.txt",import.meta.url),"utf8");')
    (config / 'asset.txt').write_text('Accepted asset')
    sdk = {'settings': {'extensions': [str(config / 'extension.mjs')]}, 'inputBoundary': str(config)}
    argv, _ = native_pi_launch(command=('node', '/opt/pi/cli.js'), workspace=tmp_path / 'task',
        config_root=config, model='test', relay_url='http://127.0.0.1/relay', relay_token='grant',
        context_extension=Path('/opt/context.mjs'), sdk_config=sdk)
    frozen = Path(json.loads(Path(argv[2]).read_text())['settings']['extensions'][0])
    result = subprocess.run(['node', '--input-type=module', '-e', 'console.log((await import(' + json.dumps(frozen.as_uri()) + ')).value)'],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == 'Accepted asset'


def test_native_launch_snapshots_managed_config_without_business_files(tmp_path):
    from capstone_agent.general_pi_executor import native_pi_launch
    config = tmp_path / 'config'
    (config / 'skills/example').mkdir(parents=True)
    (config / 'settings.json').write_text('{}')
    (config / 'skills/example/SKILL.md').write_text('A managed general skill.')
    (config / 'AGENTS.md').write_text('A general project convention.')
    workspace = tmp_path / 'task'
    native_pi_launch(command=('node', '/opt/pi/cli.js'), workspace=workspace, config_root=config,
        model='test', relay_url='http://127.0.0.1:8790/provider/task', relay_token='task-grant',
        context_extension=Path('/opt/context.mjs'))
    assert (workspace / '.agent/skills/example/SKILL.md').read_text().startswith('A managed')
    assert (workspace / 'AGENTS.md').read_text().startswith('A general')
    assert not (workspace / 'DOMAIN.md').exists()
    assert not (workspace / 'SYSTEM.md').exists()


@pytest.mark.parametrize('bad', ['../escape', '/escape', 'has space', ''])
def test_workspace_id_cannot_escape_root(tmp_path, bad):
    from capstone_agent.general_pi_executor import task_workspace
    with pytest.raises(ValueError):
        task_workspace(tmp_path, bad)


def test_native_rpc_command_is_not_selected_by_task(tmp_path):
    from capstone_agent.general_pi_executor import native_pi_launch
    config = tmp_path / 'config'
    config.mkdir()
    (config / 'settings.json').write_text('{}')
    with pytest.raises(ValueError):
        native_pi_launch(command=(), workspace=tmp_path / 'task', config_root=config,
            model='test', relay_url='http://127.0.0.1:8790/provider/task',
            relay_token='task-grant', context_extension=Path('/opt/context.mjs'))


@pytest.mark.parametrize('historical', [False, True])
def test_resource_input_uses_disk_directory_and_is_verified(tmp_path, historical):
    from hashlib import sha256
    from capstone_agent.general_pi_executor import native_pi_launch
    data = b'month,value\nAugust,10\n'
    source = tmp_path / 'source.csv'
    source.write_bytes(data)
    inputs = tmp_path / 'disk' / 'task'
    inputs.parent.mkdir()
    resource = {'resource_id': 'resource_' + 'a' * 32, 'file_name': 'data.csv',
                'size_bytes': len(data), 'sha256': sha256(data).hexdigest(),
                'version': 1, 'source_path': str(source)}
    if historical:
        resource['source_artifact'] = {'source_status': 'failed'}
    argv, _ = native_pi_launch(command=('node', '/opt/pi/cli.js'),
        workspace=tmp_path / 'memory' / 'task', config_root=tmp_path,
        model='test', relay_url='http://127.0.0.1/relay', relay_token='grant',
        context_extension=Path('/opt/context.mjs'),
        sdk_config={'selectedResourceFiles': [resource],
                    'deliveryReviewSources': [{'path': '/private/unadmitted'}]}, input_directory=inputs)
    snapshot = inputs / 'resources' / resource['resource_id'] / 'data.csv'
    assert snapshot.read_bytes() == data
    assert snapshot.stat().st_mode & 0o222 == 0
    assert Path(argv[2]).parent == inputs
    saved = json.loads(Path(argv[2]).read_text())
    assert saved['deliveryReviewSources'] == [{
        'path': str(snapshot), 'file_name': 'data.csv', 'size_bytes': len(data),
        'sha256': resource['sha256'],
        'source_ref': f"resource:{resource['resource_id']}:1:{resource['sha256']}", 'origin': 'previous_product' if historical else 'original_input',
    }]
    source.write_bytes(b'changed')
    assert snapshot.read_bytes() == data


def test_review_source_preserves_historical_material_excerpt(tmp_path):
    from base64 import b64encode
    from hashlib import sha256
    from capstone_agent.general_pi_executor import native_pi_launch
    data = b'Only the admitted excerpt.'
    material = {'material_id': 'material_example', 'file_name': 'notes.txt',
                'size_bytes': len(data), 'sha256': sha256(data).hexdigest(),
                'content_base64': b64encode(data).decode(),
                'source_product': {'excerpt': {'truncated': True}}}
    argv, _ = native_pi_launch(command=('node', '/opt/pi/cli.js'),
        workspace=tmp_path / 'task', config_root=tmp_path, model='test',
        relay_url='http://127.0.0.1/relay', relay_token='grant',
        context_extension=Path('/opt/context.mjs'), sdk_config={'selectedTaskMaterials': [material]})
    source = json.loads(Path(argv[2]).read_text())['deliveryReviewSources'][0]
    assert source['origin'] == 'selected_context'
    assert source['excerpt'] is True
    assert source['sha256'] == material['sha256']
    assert source['source_ref'] == f"material:material_example:{material['sha256']}"
    assert Path(source['path']).read_bytes() == data


def test_general_rpc_returns_answer_and_actual_tool_receipts(tmp_path):
    from capstone_agent.general_pi_executor import GeneralPiProcess
    script = tmp_path / 'fake.py'
    script.write_text('''import json,sys
for line in sys.stdin:
    request=json.loads(line)
    if request['type']=='prompt':
        print(json.dumps({'type':'turn_start'}),flush=True)
        print(json.dumps({'type':'tool_execution_start','toolName':'bash','toolCallId':'t1','args':{'command':'date'}}),flush=True)
        print(json.dumps({'type':'tool_execution_end','toolName':'bash','toolCallId':'t1','isError':False,'result':{'content':[{'type':'text','text':'2026'}]}}),flush=True)
        print(json.dumps({'type':'message_end','message':{'role':'assistant','content':[{'type':'text','text':'Done'}]}}),flush=True)
        print(json.dumps({'type':'turn_end'}),flush=True)
        print(json.dumps({'type':'agent_end','messages':[{'role':'assistant','content':[{'type':'text','text':'Done'}],'stopReason':'stop','usage':{'input':3,'output':2}}]}),flush=True)
''')
    process = GeneralPiProcess((sys.executable, str(script)), {'PATH': '/usr/bin'}, tmp_path)
    events = []
    assert process.run('task', timeout=5, cancelled=lambda: False, on_event=events.append) == 'Done'
    assert any(event['type'] == 'tool_execution_end' for event in events)
    assert [event['type'] for event in events if event['type'] in {'turn_start','message_end','turn_end'}] == ['turn_start','message_end','turn_end']
    assert process.usage['input'] == 3 and process.usage['output'] == 2
    assert process.usage['cost_status'] == 'unknown'
    assert process.usage['reported_usage'] == [{'input': 3, 'output': 2}]
    assert process.process is None


def test_real_rpc_completion_with_large_accumulated_sdk_history(tmp_path):
    from capstone_agent.general_pi_executor import GeneralPiProcess
    import shutil
    entry = Path(__file__).parents[1] / 'src/capstone_agent/resources/general-sdk.mjs'
    script = tmp_path / 'completion.mjs'
    script.write_text(f'''import {{rpcEvent}} from {json.dumps(entry.as_uri())};
import {{createInterface}} from 'node:readline';
for await (const line of createInterface({{input:process.stdin}})) {{
 const messages=Array.from({{length:60}},()=>({{role:'assistant',content:[{{type:'toolCall',arguments:{{script:'x'.repeat(10000)}}}}],usage:{{input:2,output:3}}}}));
 messages.push({{role:'assistant',stopReason:'stop',content:[{{type:'text',text:'Saved actual report.'}}],usage:{{input:5,output:7}}}});
 process.stdout.write(JSON.stringify(rpcEvent({{type:'agent_end',messages}}))+'\\n'); break;
}}
''')
    process = GeneralPiProcess((shutil.which('node'), str(script)), {'PATH': '/usr/bin'}, tmp_path)
    assert process.run('finish', timeout=5, cancelled=lambda: False, on_event=lambda _: None) == 'Saved actual report.'
    assert process.usage['input'] == 125 and process.usage['output'] == 187


def test_general_rpc_cancellation_terminates_process(tmp_path):
    from capstone_agent.general_pi_executor import GeneralPiProcess
    script = tmp_path / 'fake.py'
    script.write_text('import time; time.sleep(60)')
    process = GeneralPiProcess((sys.executable, str(script)), {'PATH': '/usr/bin'}, tmp_path)
    start = time.monotonic()
    with pytest.raises(InterruptedError):
        process.run('task', timeout=5, cancelled=lambda: time.monotonic() - start > 0.1,
                    on_event=lambda _: None)
    assert time.monotonic() - start < 3
    assert process.process is None


def test_model_failure_retains_safe_terminal_category(tmp_path):
    from capstone_agent.general_pi_executor import GeneralPiProcess
    script = tmp_path / 'failure.py'
    script.write_text("import json,sys\nfor line in sys.stdin:\n print(json.dumps({'type':'agent_end','messages':[{'role':'assistant','stopReason':'error','errorCode':'model_context_limit'}]}),flush=True)\n")
    process = GeneralPiProcess((sys.executable, str(script)), {'PATH': '/usr/bin'}, tmp_path)
    with pytest.raises(RuntimeError, match='^model_context_limit$'):
        process.run('task', timeout=5, cancelled=lambda: False, on_event=lambda _: None)


def test_artifacts_are_host_bound_and_exclude_private_config_and_symlinks(tmp_path):
    from capstone_agent.general_pi_executor import collect_artifacts
    (tmp_path / 'answer.txt').write_text('task output')
    (tmp_path / '.agent').mkdir()
    (tmp_path / '.agent/models.json').write_text('private grant')
    (tmp_path / 'context.json').write_text('shared history')
    (tmp_path / 'escape').symlink_to('/etc/passwd')
    artifacts = collect_artifacts(tmp_path, 't1', 'a1')
    assert len(artifacts) == 1
    assert artifacts[0]['task_id'] == 't1'
    assert artifacts[0]['parent_attempt_id'] == 'a1'
    assert artifacts[0]['metadata']['path'] == 'answer.txt'
    assert len(artifacts[0]['metadata']['sha256']) == 64
