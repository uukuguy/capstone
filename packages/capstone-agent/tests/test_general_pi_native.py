"""Opt-in offline Docker verification of real native Pi tools and isolation."""
import json
from dataclasses import replace
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import subprocess
import shutil
import threading
import time
from uuid import uuid4
from types import SimpleNamespace

import httpx
import pytest

from capstone_agent.pi_delegation import HttpGeneralPiExecutor, PiTaskRequest
from capstone_agent.request_intent import NodeControl


def test_native_context_extension_preserves_roles_and_separates_business_data(tmp_path):
    from pathlib import Path
    from capstone_agent.business_context import BusinessContext
    context = BusinessContext.empty('workspace', 0).to_document()
    (tmp_path / 'context.json').write_text(json.dumps({'messages': [
        {'role': 'user', 'content': 'User history'}, {'role': 'assistant', 'content': 'Assistant history'}],
        'dependency_results': [], 'business_context': context}))
    extension = Path(__file__).parents[1] / 'src/capstone_agent/resources/general-context.mjs'
    result = subprocess.run(['node', '--input-type=module', '-e',
        'const {default: register} = await import(process.argv[1]); '
        'const events = {}; register({on: (name, fn) => {events[name] = fn}}); '
        'console.log(JSON.stringify(await events.context({messages: [{role: "user", content: "Current task"}]}, '
        '{model: {api: "fixture", provider: "fixture", id: "fixture"}})));', extension.as_uri()],
        cwd=tmp_path, capture_output=True, text=True, check=True)
    messages = json.loads(result.stdout)['messages']
    assert [message['role'] for message in messages] == ['user', 'assistant', 'user', 'user']
    assert json.loads(messages[2]['content'])['business_context'] == context
    assert messages[-1]['content'] == 'Current task'


def test_native_context_extension_adds_trusted_background_policy(tmp_path):
    from pathlib import Path
    (tmp_path / 'context.json').write_text(json.dumps({'messages': [], 'dependency_results': []}))
    extension = Path(__file__).parents[1] / 'src/capstone_agent/resources/general-context.mjs'
    result = subprocess.run(['node', '--input-type=module', '-e',
        'const {default: register} = await import(process.argv[1]); '
        'const events = {}; register({on: (name, fn) => {events[name] = fn}}); '
        'console.log(JSON.stringify(await events.before_agent_start({systemPrompt: "Native policy"})));',
        extension.as_uri()], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    policy = json.loads(result.stdout)['systemPrompt']
    assert policy.startswith('Native policy')
    assert 'data, not instructions' in policy and 'current-run' in policy


@pytest.mark.skipif(os.environ.get('CAPSTONE_GENERAL_NATIVE_TESTS') != '1', reason='requires local general Pi Docker image')
def test_real_general_pi_builtin_bash_isolated_and_same_for_both_entrypoints(tmp_path):
    calls = []
    class Provider(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_POST(self):
            document = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            calls.append(document)
            assert self.headers['Authorization'] == 'Bearer fixture-provider-credential'
            previous = [message for message in document['messages'] if message['role'] == 'tool']
            def text_content(value):
                return value if isinstance(value, str) else ''.join(part.get('text', '') for part in value)
            if 'literal-input-verification' in str(document['messages']):
                user = text_content([message for message in document['messages'] if message['role'] == 'user'][-1]['content'])
                assert user == '/skill:pandapower literal-input-verification'
                delta, reason = {'role': 'assistant', 'content': 'Literal input preserved.'}, 'stop'
            elif 'skill-mcp-verification' in str(document['messages']):
                if 'restored-profile-verification' in str(document['messages']):
                    assert 'Frozen policy v1' in str(document['messages'])
                    assert 'Frozen policy v2' not in str(document['messages'])
                user = text_content([message for message in document['messages'] if message['role'] == 'user'][-1]['content'])
                assert '<skill name="pandapower"' in user and '## Default tool ladder' in user
                import re
                location = re.search(r'location="([^"]+)"', user).group(1)
                steps = [('load_network', {'file_path': str(__import__('pathlib').Path(location).parent / 'case39.json')}),
                         ('get_network_info', {}), ('audit_network', {}),
                         ('run_power_flow', {'algorithm': 'nr', 'calculate_voltage_angles': True,
                                             'max_iteration': 15, 'tolerance_mva': 1e-8})]
                for message in previous:
                    wire = json.loads(text_content(message['content']))
                    value = wire.get('structuredContent', wire.get('structured_content'))
                    assert value['result']['status'] == 'success', value
                if len(previous) < len(steps):
                    tool, arguments = steps[len(previous)]
                    delta = {'role': 'assistant', 'tool_calls': [{'index': 0, 'id': f'call_mcp_{len(previous)}',
                        'type': 'function', 'function': {'name': tool, 'arguments': json.dumps(arguments)}}]}
                    reason = 'tool_calls'
                else:
                    assert value['result']['results']['converged'] is True
                    delta, reason = {'role': 'assistant', 'content': 'Skill and external MCP task complete.'}, 'stop'
            elif 'state-isolation-verification' in str(document['messages']):
                if not previous:
                    delta = {'role': 'assistant', 'tool_calls': [{'index': 0, 'id': 'call_isolation',
                        'type': 'function', 'function': {'name': 'get_network_info', 'arguments': '{}'}}]}
                    reason = 'tool_calls'
                else:
                    assert 'No pandapower network' in previous[-1]['content']
                    delta, reason = {'role': 'assistant', 'content': 'Private MCP state is empty.'}, 'stop'
            elif 'Cancel inherited pipes' in str(document['messages']):
                command = "python -c 'import os,time; pid=os.fork(); os.setsid() if pid==0 else None; time.sleep(120) if pid==0 else None'"
                delta = {'role': 'assistant', 'tool_calls': [{'index': 0, 'id': 'call_block',
                    'type': 'function', 'function': {'name': 'bash', 'arguments': json.dumps({'command': command})}}]}
                reason = 'tool_calls'
            elif not previous:
                delta = {'role': 'assistant', 'tool_calls': [{'index': 0, 'id': 'call_tool',
                    'type': 'function', 'function': {'name': 'bash', 'arguments': json.dumps({'command':
                        'printf "native output" > result.txt; '
                        'python -c \'import os,time; os.setsid(); time.sleep(120)\' >/dev/null 2>&1 & sleep 0.2; '
                        'if cat /proc/1/environ >/dev/null 2>&1; then echo LEAK; else echo DENIED; fi; '
                        'test ! -e /app/.grid-agent && echo NO_BUSINESS_ASSETS; '
                        'input="../.inputs-$(basename "$PWD")"; '
                        'if printf changed > "$input/sdk.json"; then echo INPUT_WRITABLE; else echo INPUT_READ_ONLY; fi; '
                        'if mv "$input" "$input-replaced"; then echo INPUT_REPLACED; else echo INPUT_PATH_FIXED; fi'})}}]}
                reason = 'tool_calls'
            else:
                assert 'DENIED' in previous[-1]['content']
                assert 'NO_BUSINESS_ASSETS' in previous[-1]['content']
                assert 'INPUT_READ_ONLY' in previous[-1]['content'] and 'INPUT_PATH_FIXED' in previous[-1]['content']
                delta, reason = {'role': 'assistant', 'content': 'Native general task complete.'}, 'stop'
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.end_headers()
            for payload, finish in [(delta, None), ({}, reason)]:
                chunk = {'id': 'fixture', 'object': 'chat.completion.chunk', 'created': 0,
                    'model': 'fixture-model', 'choices': [{'index': 0, 'delta': payload, 'finish_reason': finish}]}
                self.wfile.write(('data: ' + json.dumps(chunk) + '\n\n').encode())
            self.wfile.write(b'data: [DONE]\n\n')
            self.wfile.flush()
    provider = ThreadingHTTPServer(('0.0.0.0', 0), Provider)
    thread = threading.Thread(target=provider.serve_forever, daemon=True)
    thread.start()
    from pathlib import Path
    configs = tmp_path / 'runtime'
    source = Path(__file__).parents[3] / 'configs/runtime'
    shutil.copytree(source, configs)
    settings_path = configs / 'general-pi/settings.json'
    settings = json.loads(settings_path.read_text())
    settings['extensions'] = ['sentinel.mjs']
    settings_path.write_text(json.dumps(settings))
    (configs / 'general-pi/AGENTS.md').write_text('Frozen policy v1')
    (configs / 'general-pi/sentinel.mjs').write_text('''import {readFileSync} from "node:fs";
export default function(pi){pi.on("session_start",async()=>{
if(process.getuid()<10000 || process.env.CAPSTONE_SENTINEL) throw new Error("readiness privilege leak");
let denied=false;try{readFileSync("/var/lib/general-pi/receipts/sentinel-secret")}catch{denied=true}
if(!denied) throw new Error("readiness private file leak");
});}''')
    name = 'capstone-general-test-' + uuid4().hex[:12]
    volumes = [name + '-profiles', name + '-resources']
    script = f'''
from pathlib import Path
from capstone_agent.general_pi_server import GeneralPiHost,NativeTaskRunner,make_server
from capstone_agent.general_pi_resource_seed import retain_seed
import traceback
retain_seed(Path('/opt/general/resource-seed'),Path('/opt/general/.grid-agent/runtime'))
class FixtureRunner(NativeTaskRunner):
    def __call__(self,*args,**kwargs):
        try:
            return super().__call__(*args,**kwargs)
        except Exception:
            traceback.print_exc()
            raise
root=Path('/var/lib/general-pi')
(root/'receipts/sentinel-secret').write_text('fixture-only-sentinel')
runner=FixtureRunner(root=root,config_root=Path('/opt/general/configs/runtime/general-pi'),command=('node','/opt/pi/packages/coding-agent/dist/cli.js'),model='fixture-model',relay_origin='http://127.0.0.1:8790')
host=GeneralPiHost(root=root,identity={{'engine':'pi','config_revision':'fixture','model':'fixture-model'}},run_task=runner)
host.capability['native_tools']=runner.verify_tools(host.identity)
host.capability['resource_profiles']=runner.verify_resources(host.identity)
make_server(host,control_token='fixture-control',address=('0.0.0.0',8790),runner=runner,upstream='http://host.docker.internal:{provider.server_port}',provider_key='fixture-provider-credential').serve_forever()
'''
    try:
        subprocess.run(['docker', 'run', '-d', '--init', '--name', name, '--cap-drop=ALL',
            '--cap-add=SETUID', '--cap-add=SETGID', '--cap-add=CHOWN', '--cap-add=DAC_OVERRIDE', '--cap-add=KILL',
            '--security-opt=no-new-privileges', '--memory=512m', '--pids-limit=128',
            '--read-only', '--tmpfs', '/var/lib/general-pi/tasks:rw,nosuid,size=256m,mode=0711',
            '--mount', 'type=volume,src=' + volumes[0] + ',dst=/var/lib/general-pi/profiles,volume-nocopy',
            '--mount', 'type=volume,src=' + volumes[1] + ',dst=/opt/general/.grid-agent/runtime,volume-nocopy',
            '--tmpfs', '/tmp:rw,nosuid,noexec,size=64m', '--tmpfs', '/var/lib/general-pi/receipts:rw,nosuid,size=64m,mode=0700',
            '-v', str(configs) + ':/opt/general/configs/runtime:ro', '-e', 'CAPSTONE_SENTINEL=fixture-only-sentinel',
            '-p', '127.0.0.1::8790', os.environ.get('CAPSTONE_GENERAL_NATIVE_IMAGE', 'capstone-general-pi:local'), 'python', '-c', script],
            check=True, capture_output=True)
        binding = subprocess.run(['docker', 'port', name, '8790'], check=True,
                                  capture_output=True, text=True).stdout.strip()
        origin = 'http://' + binding
        deadline = time.monotonic()+90
        while True:
            try:
                health = httpx.get(origin+'/health/ready', timeout=1).json()
                break
            except (httpx.HTTPError, ValueError):
                state = subprocess.run(['docker', 'inspect', '-f', '{{.State.Status}}', name], capture_output=True, text=True).stdout.strip()
                if state == 'exited':
                    pytest.fail(subprocess.run(['docker','logs',name], capture_output=True, text=True).stderr)
                if time.monotonic() >= deadline:
                    pytest.fail(subprocess.run(['docker','logs',name], capture_output=True, text=True).stderr)
                time.sleep(0.1)
        client = HttpGeneralPiExecutor(origin, identity=health['identity'], capability=health['capability'],
                                      control_token='fixture-control')
        assert {'bash', 'read', 'write', 'edit'} <= set(health['capability']['native_tools'])
        for index, entrypoint in enumerate(['delegated', 'direct']):
            events = []
            request = PiTaskRequest.from_document({'schema': 'capstone-pi-task/1', 'task_id': f'task-{index}',
                'parent_attempt_id': 'attempt-1', 'entrypoint': entrypoint, 'instruction': 'A general operation',
                'messages': [], 'dependency_results': [], 'executor_identity': health['identity'], 'timeout_seconds': 25})
            result = client.execute(request, NodeControl(lambda: None, time.monotonic()+25), events.append)
            assert result.status == 'completed', subprocess.run(['docker','logs',name], capture_output=True, text=True).stderr
            assert result.answer == 'Native general task complete.'
            assert any(event['type'] == 'tool_execution_end' and event['tool_name'] == 'bash' for event in events)
            assert result.artifacts[0]['metadata']['path'] == 'result.txt'
            product = httpx.get(origin + '/tasks/' + request.task_id + '/artifacts/' + result.artifacts[0]['artifact_id'],
                                headers={'Authorization': 'Bearer fixture-control'})
            assert product.content == b'native output'
            check = 'from pathlib import Path; print(sum(p.stat().st_uid==' + str(10003+index) + ' for p in Path("/proc").glob("[0-9]*")))'
            alive = subprocess.run(['docker','exec',name,'python','-c',check], capture_output=True, text=True, check=True)
            assert alive.stdout.strip() == '0', 'A native tool descendant survived task completion'
        assert len(calls) == 4
        tools = {item['function']['name'] for item in calls[0]['tools']}
        assert {'bash', 'read', 'write', 'edit'} <= tools
        from capstone_agent.business_context import BusinessContext
        profiles = health['capability']['resource_profiles']
        assert set(profiles) == {'direct_pi', 'delegated_pi'}
        assert '/opt/' not in json.dumps(profiles) and '/var/' not in json.dumps(profiles)
        for role, profile in profiles.items():
            assert all(item['ready'] for item in profile['resources'])
            assert profile['load_receipt']['role'] == role
            assert set(profile['load_receipt']['tool_schema_hashes']) <= tools
        for role in ('direct_pi', 'delegated_pi'):
            instruction = 'skill-mcp-verification'
            request = PiTaskRequest('skill-' + role, 'attempt-skill', 'direct' if role == 'direct_pi' else 'delegated',
                instruction, (), (), health['identity'], 60, business_context=BusinessContext.empty('workspace', 0),
                resource_profile={'profile_id': role, 'revision': profiles[role]['revision']},
                input={'kind': 'skill_invocation', 'text': instruction, 'skill_id': 'powerskills-pandapower',
                       'skill_version': profiles[role]['resources'][0]['version']})
            result = client.execute(request, NodeControl(lambda: None, time.monotonic()+60), lambda _: None)
            assert result.status == 'completed', subprocess.run(['docker','logs',name], capture_output=True, text=True).stderr
            assert result.answer == 'Skill and external MCP task complete.'
            assert len(result.sources) == 4 and all(item['kind'] == 'external_mcp_observation' for item in result.sources)
            assert result.artifacts == ()
        for marker in ('/skill:pandapower literal-input-verification', 'state-isolation-verification'):
            request = PiTaskRequest('text-' + str(len(calls)), 'attempt-text', 'direct', marker, (), (), health['identity'], 30,
                business_context=BusinessContext.empty('workspace', 0),
                resource_profile={'profile_id': 'direct_pi', 'revision': profiles['direct_pi']['revision']},
                input={'kind': 'text', 'text': marker})
            result = client.execute(request, NodeControl(lambda: None, time.monotonic()+30), lambda _: None)
            assert result.status == 'completed'
        for input_, profile_ in [({'kind': 'skill_invocation', 'text': 'changed-version',
            'skill_id': 'powerskills-pandapower', 'skill_version': 'wrong-version'}, profiles['direct_pi']),
            ({'kind': 'text', 'text': 'wrong-role'}, profiles['delegated_pi'])]:
            before = len(calls)
            request = PiTaskRequest('invalid-' + input_['text'], 'attempt-invalid', 'direct', input_['text'],
                (), (), health['identity'], 10, business_context=BusinessContext.empty('workspace', 0),
                resource_profile={'profile_id': profile_['profile_id'], 'revision': profile_['revision']}, input=input_)
            result = client.execute(request, NodeControl(lambda: None, time.monotonic()+10), lambda _: None)
            assert result.status == 'failed' and len(calls) == before
        request = PiTaskRequest.from_document({'schema': 'capstone-pi-task/1', 'task_id': 'task-cancel',
            'parent_attempt_id': 'attempt-1', 'entrypoint': 'delegated', 'instruction': 'Cancel inherited pipes',
            'messages': [], 'dependency_results': [], 'executor_identity': health['identity'], 'timeout_seconds': 6})
        started = time.monotonic()
        with pytest.raises(TimeoutError):
            client.execute(request, NodeControl(lambda: None, time.monotonic()+8), lambda _: None)
        assert time.monotonic() - started < 7
        assert len(calls) >= 5
        receipt = httpx.get(origin + '/tasks/task-cancel', headers={'Authorization': 'Bearer fixture-control'}).json()
        assert receipt['status'] in {'failed', 'cancelled'}
        check = 'from pathlib import Path; print(sum(p.stat().st_uid>=10000 for p in Path("/proc").glob("[0-9]*")))'
        alive = subprocess.run(['docker','exec',name,'python','-c',check], capture_output=True, text=True, check=True)
        assert alive.stdout.strip() == '0', 'Detached child with inherited pipes survived task timeout'
        # Verify the same real native engine behind both hosted worker entry points.
        from capstone_agent.conversation_context import ConversationContext
        from capstone_agent.intent_runtime import IntentRuntimeFactory
        from capstone_agent.request_intent import IntentDecision, IntentEngineIdentity
        from capstone_agent.thread_worker import _run_claimed_attempt
        from test_intent_runtime import claim
        from test_delegated_runtime import ContextSelector
        class Recognizer:
            identity = IntentEngineIdentity('fixture', 'model', 'config_1')
            calls = 0
            def recognize(self, request, control):
                self.calls += 1
                document = request.to_document()
                return IntentDecision.from_document({'schema': 'capstone-intent-decision/1',
                    'attempt_id': document['attempt_id'], 'history_cutoff': document['history_cutoff'],
                    'relationship': 'continuation', 'goals': [{'goal_id': 'lookup', 'description': 'General task',
                        'operation': 'external_lookup', 'message_refs': ['old:assistant'], 'object_refs': [],
                        'capability_refs': ['general-pi'], 'missing_requirements': [], 'depends_on': []}],
                    'clarification': None}, request)
        for mode in ('capstone', 'pi_reference'):
            service, current = claim()
            history = ConversationContext(messages=({'message_id': 'old:assistant', 'role': 'assistant',
                'content': 'Shared history marker', 'turn_id': 'old-turn', 'attempt_id': 'old',
                'model_context_id': 'ctx_test', 'status': 'completed'},))
            current = replace(current, attempt=replace(current.attempt, runtime_mode=mode), conversation_context=history)
            recognizer = Recognizer()
            def unavailable(*_):
                pytest.fail('Professional or legacy ordinary runtime was prepared')
            selector = ContextSelector(['ctx_test'], ['old:assistant'])
            factory = IntentRuntimeFactory(unavailable, lambda: recognizer, unavailable, general_executor=client,
                context_selector_factory=lambda: selector)
            before = len(calls)
            result = _run_claimed_attempt(service, factory, current, SimpleNamespace(check=lambda: None), 30, None)
            assert result.status == 'completed'
            assert result.answer == 'Native general task complete.'
            assert result.result_refs == result.evidence_refs == ()
            assert recognizer.calls == (1 if mode == 'capstone' else 0)
            assert len(calls) == before + 2
            assert 'Shared history marker' in str(calls[before]['messages'])
            if mode == 'pi_reference':
                assert 'ieee39' in str(calls[before]['messages'])
                assert 'capstone-business-context/1' in str(calls[before]['messages'])
                assert 'model_revision' not in str(calls[before]['messages'])
            public_events = service.read_events(current.thread_id, 0).events
            streamed_text = ''.join(event.payload['text'] for event in public_events
                                    if event.event_type == 'assistant_text_delta')
            assert streamed_text == 'Native general task complete.'
            receipts = [event.payload for event in public_events
                        if event.event_type == 'runtime_event']
            assert any(receipt.get('child_status') == 'completed' for receipt in receipts)
        updated_image = os.environ.get('CAPSTONE_GENERAL_NATIVE_UPDATED_IMAGE')
        if updated_image:
            old_profile = profiles['direct_pi']
            old_install = subprocess.run(['docker', 'exec', name, 'python', '-c',
                'import json;from pathlib import Path;print(json.loads(Path("/opt/general/.grid-agent/runtime/agent-resources/current.json").read_text())["install_id"])'],
                check=True, capture_output=True, text=True).stdout.strip()
            subprocess.run(['docker', 'rm', '-f', name], check=True, capture_output=True)
            (configs / 'general-pi/AGENTS.md').write_text('Frozen policy v2')
            args = ['docker', 'run', '-d', '--init', '--name', name, '--cap-drop=ALL',
                '--cap-add=SETUID', '--cap-add=SETGID', '--cap-add=CHOWN', '--cap-add=DAC_OVERRIDE', '--cap-add=KILL',
                '--security-opt=no-new-privileges', '--memory=512m', '--pids-limit=128', '--read-only',
                '--tmpfs', '/var/lib/general-pi/tasks:rw,nosuid,size=256m,mode=0711',
                '--tmpfs', '/var/lib/general-pi/receipts:rw,nosuid,size=64m,mode=0700',
                '--tmpfs', '/tmp:rw,nosuid,noexec,size=64m',
                '--mount', 'type=volume,src=' + volumes[0] + ',dst=/var/lib/general-pi/profiles,volume-nocopy',
                '--mount', 'type=volume,src=' + volumes[1] + ',dst=/opt/general/.grid-agent/runtime,volume-nocopy',
                '-v', str(configs) + ':/opt/general/configs/runtime:ro', '-p', '127.0.0.1::8790', updated_image,
                'python', '-c', script]
            subprocess.run(args, check=True, capture_output=True)
            origin = 'http://' + subprocess.run(['docker','port',name,'8790'],check=True,capture_output=True,text=True).stdout.strip()
            deadline = time.monotonic() + 90
            while True:
                try:
                    new_health = httpx.get(origin + '/health/ready', timeout=1).json()
                    break
                except (httpx.HTTPError, ValueError):
                    if time.monotonic() >= deadline or subprocess.run(['docker','inspect','-f','{{.State.Status}}',name],capture_output=True,text=True).stdout.strip() == 'exited':
                        pytest.fail(subprocess.run(['docker','logs',name],capture_output=True,text=True).stderr)
                    time.sleep(0.1)
            assert new_health['capability']['resource_profiles']['direct_pi']['revision'] != old_profile['revision']
            check = 'import json;from pathlib import Path;p=Path("/opt/general/.grid-agent/runtime/agent-resources");print(json.loads((p/"current.json").read_text())["install_id"]);assert (p/' + repr(old_install) + '/"prepared-mcp.json").is_file()'
            new_install = subprocess.run(['docker','exec',name,'python','-c',check],check=True,capture_output=True,text=True).stdout.strip()
            assert new_install != old_install
            restored = HttpGeneralPiExecutor(origin, identity=new_health['identity'], capability=new_health['capability'],control_token='fixture-control')
            text = 'skill-mcp-verification restored-profile-verification'
            skill = next(item for item in old_profile['resources'] if item['id'] == 'powerskills-pandapower')
            request = PiTaskRequest('restored-profile', 'attempt-restored', 'direct', text, (), (), new_health['identity'], 60,
                business_context=BusinessContext.empty('workspace',0), resource_profile={'profile_id':'direct_pi','revision':old_profile['revision']},
                input={'kind':'skill_invocation','text':text,'skill_id':skill['id'],'skill_version':skill['version']})
            result = restored.execute(request,NodeControl(lambda:None,time.monotonic()+60),lambda _:None)
            assert result.status == 'completed', subprocess.run(['docker','logs',name],capture_output=True,text=True).stderr
            assert len(result.sources) == 4
            assert all(item['metadata']['descriptor_sha256'] == old_profile['load_receipt']['descriptor_sha256']
                       for item in result.sources)
    finally:
        subprocess.run(['docker', 'rm', '-f', name], capture_output=True)
        for volume in volumes:
            subprocess.run(['docker', 'volume', 'rm', volume], capture_output=True)
        provider.shutdown()
        provider.server_close()
        thread.join(timeout=2)
