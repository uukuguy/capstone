"""Opt-in offline Docker verification of real native Pi tools and isolation."""
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import subprocess
import threading
import time
from uuid import uuid4

import httpx
import pytest

from capstone_agent.pi_delegation import HttpGeneralPiExecutor, PiTaskRequest
from capstone_agent.request_intent import NodeControl


@pytest.mark.skipif(os.environ.get('CAPSTONE_GENERAL_NATIVE_TESTS') != '1', reason='requires local general Pi Docker image')
def test_real_general_pi_builtin_bash_isolated_and_same_for_both_entrypoints():
    calls = []
    class Provider(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_POST(self):
            document = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            calls.append(document)
            assert self.headers['Authorization'] == 'Bearer fixture-provider-credential'
            previous = [message for message in document['messages'] if message['role'] == 'tool']
            if 'Cancel inherited pipes' in str(document['messages']):
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
                        'test ! -e /app/.grid-agent && echo NO_BUSINESS_ASSETS'})}}]}
                reason = 'tool_calls'
            else:
                assert 'DENIED' in previous[-1]['content']
                assert 'NO_BUSINESS_ASSETS' in previous[-1]['content']
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
    name = 'capstone-general-test-' + uuid4().hex[:12]
    script = f'''
from pathlib import Path
from capstone_agent.general_pi_server import GeneralPiHost,NativeTaskRunner,make_server
import traceback
class FixtureRunner(NativeTaskRunner):
    def __call__(self,*args,**kwargs):
        try:
            return super().__call__(*args,**kwargs)
        except Exception:
            traceback.print_exc()
            raise
root=Path('/var/lib/general-pi')
runner=FixtureRunner(root=root,config_root=Path('/opt/general/config'),command=('node','/opt/pi/packages/coding-agent/dist/cli.js'),model='fixture-model',relay_origin='http://127.0.0.1:8790')
host=GeneralPiHost(root=root,identity={{'engine':'pi','config_revision':'fixture','model':'fixture-model'}},run_task=runner)
host.capability['native_tools']=runner.verify_tools(host.identity)
make_server(host,control_token='fixture-control',address=('0.0.0.0',8790),runner=runner,upstream='http://host.docker.internal:{provider.server_port}',provider_key='fixture-provider-credential').serve_forever()
'''
    try:
        subprocess.run(['docker', 'run', '-d', '--init', '--name', name, '--cap-drop=ALL',
            '--cap-add=SETUID', '--cap-add=SETGID', '--cap-add=CHOWN', '--cap-add=DAC_OVERRIDE', '--cap-add=KILL',
            '--security-opt=no-new-privileges', '--memory=512m', '--pids-limit=128',
            '--read-only', '--tmpfs', '/var/lib/general-pi/tasks:rw,nosuid,size=256m,mode=0711',
            '--tmpfs', '/tmp:rw,nosuid,noexec,size=64m', '--tmpfs', '/var/lib/general-pi/receipts:rw,nosuid,size=64m,mode=0700',
            '-p', '127.0.0.1::8790', 'capstone-general-pi:local', 'python', '-c', script],
            check=True, capture_output=True)
        binding = subprocess.run(['docker', 'port', name, '8790'], check=True,
                                  capture_output=True, text=True).stdout.strip()
        origin = 'http://' + binding
        deadline = time.monotonic()+30
        while True:
            try:
                health = httpx.get(origin+'/health/ready', timeout=1).json()
                break
            except (httpx.HTTPError, ValueError):
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
            check = 'from pathlib import Path; print(sum(p.stat().st_uid==' + str(10001+index) + ' for p in Path("/proc").glob("[0-9]*")))'
            alive = subprocess.run(['docker','exec',name,'python','-c',check], capture_output=True, text=True, check=True)
            assert alive.stdout.strip() == '0', 'A native tool descendant survived task completion'
        assert len(calls) == 4
        tools = {item['function']['name'] for item in calls[0]['tools']}
        assert {'bash', 'read', 'write', 'edit'} <= tools
        request = PiTaskRequest.from_document({'schema': 'capstone-pi-task/1', 'task_id': 'task-cancel',
            'parent_attempt_id': 'attempt-1', 'entrypoint': 'delegated', 'instruction': 'Cancel inherited pipes',
            'messages': [], 'dependency_results': [], 'executor_identity': health['identity'], 'timeout_seconds': 2})
        started = time.monotonic()
        with pytest.raises(TimeoutError):
            client.execute(request, NodeControl(lambda: None, time.monotonic()+5), lambda _: None)
        assert time.monotonic() - started < 3
        assert len(calls) >= 5
        receipt = httpx.get(origin + '/tasks/task-cancel', headers={'Authorization': 'Bearer fixture-control'}).json()
        assert receipt['status'] in {'failed', 'cancelled'}
        check = 'from pathlib import Path; print(sum(p.stat().st_uid==10003 for p in Path("/proc").glob("[0-9]*")))'
        alive = subprocess.run(['docker','exec',name,'python','-c',check], capture_output=True, text=True, check=True)
        assert alive.stdout.strip() == '0', 'Detached child with inherited pipes survived task timeout'
    finally:
        subprocess.run(['docker', 'rm', '-f', name], capture_output=True)
        provider.shutdown()
        provider.server_close()
        thread.join(timeout=2)
