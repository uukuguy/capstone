from pathlib import Path
import json
import sys
import time

import pytest


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


def test_general_rpc_returns_answer_and_actual_tool_receipts(tmp_path):
    from capstone_agent.general_pi_executor import GeneralPiProcess
    script = tmp_path / 'fake.py'
    script.write_text('''import json,sys
for line in sys.stdin:
    request=json.loads(line)
    if request['type']=='prompt':
        print(json.dumps({'type':'tool_execution_start','toolName':'bash','toolCallId':'t1','args':{'command':'date'}}),flush=True)
        print(json.dumps({'type':'tool_execution_end','toolName':'bash','toolCallId':'t1','isError':False,'result':{'content':[{'type':'text','text':'2026'}]}}),flush=True)
        print(json.dumps({'type':'agent_end','messages':[{'role':'assistant','content':[{'type':'text','text':'Done'}],'stopReason':'stop','usage':{'input':3,'output':2}}]}),flush=True)
''')
    process = GeneralPiProcess((sys.executable, str(script)), {'PATH': '/usr/bin'}, tmp_path)
    events = []
    assert process.run('task', timeout=5, cancelled=lambda: False, on_event=events.append) == 'Done'
    assert any(event['type'] == 'tool_execution_end' for event in events)
    assert process.usage['input'] == 3 and process.usage['output'] == 2
    assert process.usage['cost_status'] == 'unknown'
    assert process.usage['reported_usage'] == [{'input': 3, 'output': 2}]
    assert process.process is None


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
