"""Exercise the locked native Pi against loopback SSE, without a real Provider."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import queue
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from capstone_agent.runtime import resolve_harness_llm
from capability_agent.runtime.environment import RuntimePaths, build_pi_launch
from capability_agent.runtime.locator import PiRuntimeLocator
from capability_agent.runtime.lock import PiRuntimeLock

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('protocol_host_runtime', ROOT / 'deploy/launch_host_runtime.py')
assert SPEC and SPEC.loader
RUNTIME = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNTIME)
KEY = 'protocol-test-secret-canary-not-a-real-key'
MODEL = 'deepseek-flash'
FINAL = 'Local protocol response complete.'


@pytest.mark.parametrize('family', ['pandapower', 'pypsa'])
@pytest.mark.parametrize('use_tool', [False, True], ids=['text', 'tool-roundtrip'])
def test_native_pi_chat_completions_protocol(tmp_path, family, use_tool):
    requests = []
    errors = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            stage = 'route'
            try:
                assert self.path == '/v1/chat/completions', 'Expected the Chat Completions route'
                stage = 'authorization'
                assert self.headers.get('Authorization') == 'Bearer ' + KEY
                stage = 'request-body'
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                requests.append(body)
                assert body['model'] == MODEL
                assert body['stream'] is True
                assert isinstance(body['messages'], list)
                assert any(m['role'] == 'user' for m in body['messages'])
                if use_tool:
                    assert any(t['function']['name'] == 'protocol_echo' for t in body['tools'])
                if use_tool and len(requests) == 1:
                    chunks = [
                        ({'role': 'assistant', 'tool_calls': [{'index': 0, 'id': 'call_echo_1',
                          'type': 'function', 'function': {'name': 'protocol_echo', 'arguments': '{"text":'}}]}, None),
                        ({'tool_calls': [{'index': 0, 'function': {'arguments': '"echo-check"}'}}]}, None),
                        ({}, 'tool_calls'),
                    ]
                else:
                    assert len(requests) == (2 if use_tool else 1)
                    if use_tool:
                        calls = [c for m in body['messages'] if m['role'] == 'assistant'
                                 for c in m.get('tool_calls', [])]
                        assert any(c['id'] == 'call_echo_1' and c['function']['name'] == 'protocol_echo'
                                   and json.loads(c['function']['arguments']) == {'text': 'echo-check'} for c in calls)
                        assert any(m['role'] == 'tool' and m['tool_call_id'] == 'call_echo_1'
                                   and 'echo-check' in str(m['content']) for m in body['messages'])
                    chunks = [({'role': 'assistant', 'content': 'Local protocol '}, None),
                              ({'content': 'response complete.'}, None), ({}, 'stop')]
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream')
                self.send_header('Connection', 'close')
                self.end_headers()
                for delta, finish in chunks:
                    chunk = {'id': 'chatcmpl-local', 'object': 'chat.completion.chunk',
                             'created': 1, 'model': MODEL,
                             'choices': [{'index': 0, 'delta': delta, 'finish_reason': finish}]}
                    self.wfile.write(('data: ' + json.dumps(chunk) + '\n\n').encode())
                    self.wfile.flush()
                self.wfile.write(b'data: [DONE]\n\n')
                self.wfile.flush()
                self.close_connection = True
            except Exception as error:
                errors.append(stage + ':' + type(error).__name__)
                self.send_error(400, 'Local protocol contract failed')

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    process = None
    reader = None
    error_reader = None
    events = []
    stderr_chunks = []
    try:
        settings = {'CAPSTONE_RUNTIME_PROFILE': 'capstone-dev-trial-v1',
                    'CAPSTONE_DEPLOYMENT_STAGE': 'local', 'CAPSTONE_HOSTED_APPLICATION': family,
                    'PROVIDER': 'openai', 'OPENAI_MODEL': MODEL, 'OPENAI_API_KEY': KEY,
                    'OPENAI_BASE_URL': f'http://127.0.0.1:{server.server_port}/v1'}
        resolved = resolve_harness_llm(ROOT, RUNTIME.select_runtime(ROOT, settings, 'worker')[3])
        command = PiRuntimeLocator(ROOT / '.grid-agent/runtime/pi', {},
            runtime_lock=PiRuntimeLock.load(ROOT / 'configs/runtime/pi-runtime.lock.json')).resolve()
        extension = None
        if use_tool:
            extension = tmp_path / 'protocol-echo.mjs'
            extension.write_text('''export default function (pi) {
  pi.registerTool({name: "protocol_echo", label: "Protocol echo",
    description: "Return the test text without side effects.",
    parameters: {type: "object", properties: {text: {type: "string"}}, required: ["text"], additionalProperties: false},
    async execute(_id, args) {
      return {content: [{type: "text", text: args.text}], details: {testOnly: true}};
    }
  });
}
''')
        paths = RuntimePaths(command=command, project_pi_dir=tmp_path / 'agent',
                             session_dir=tmp_path / 'session', workspace=tmp_path, extension_path=extension)
        launch = build_pi_launch(resolved, paths, base_environment={
            'PATH': os.environ['PATH'], 'HOME': str(tmp_path), 'CAPABILITY_AGENT_PI_OFFLINE': '1'})
        # Refuse to send a prompt if runtime selection escapes the loopback fixture.
        assert resolved.config.base_url == settings['OPENAI_BASE_URL']
        model_config = json.loads((Path(launch.environment['PI_CODING_AGENT_DIR']) / 'models.json').read_text())
        assert model_config['providers']['openai']['baseUrl'] == settings['OPENAI_BASE_URL']
        process = subprocess.Popen(launch.argv, env=launch.environment, cwd=tmp_path,
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output = queue.Queue()
        def read_output():
            for line in process.stdout:
                output.put(line)
            output.put(None)
        reader = threading.Thread(target=read_output, daemon=True)
        reader.start()
        def read_errors():
            for line in process.stderr:
                stderr_chunks.append(line)
        error_reader = threading.Thread(target=read_errors, daemon=True)
        error_reader.start()
        process.stdin.write(json.dumps({'id': 'protocol-prompt', 'type': 'prompt',
                                        'message': 'Perform the local protocol test.'}).encode() + b'\n')
        process.stdin.flush()
        deadline = time.monotonic() + 30
        while True:
            remaining = deadline - time.monotonic()
            assert remaining > 0, 'Native Pi did not complete the loopback request'
            try:
                line = output.get(timeout=remaining)
            except queue.Empty:
                pytest.fail('Native Pi did not complete the loopback request')
            assert line is not None, 'Native Pi exited before completing the prompt'
            event = json.loads(line)
            events.append(event)
            if event.get('type') == 'response':
                assert event.get('success'), 'Native Pi rejected the prompt'
            if event.get('type') == 'agent_end':
                break
        assert not errors, f'The HTTP request did not match the protocol contract: {errors}'
        assert len(requests) == (2 if use_tool else 1)
        messages = events[-1]['messages']
        final = messages[-1]
        assert final['role'] == 'assistant'
        assert final['stopReason'] == 'stop'
        assert ''.join(c['text'] for c in final['content'] if c['type'] == 'text') == FINAL
        if use_tool:
            assert any(e.get('type') == 'tool_execution_end' and e.get('toolName') == 'protocol_echo'
                       and not e.get('isError') for e in events)
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            for thread in (reader, error_reader):
                if thread is not None:
                    thread.join(timeout=5)
            for pipe in (process.stdin, process.stdout, process.stderr):
                pipe.close()
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=5)
    assert KEY not in json.dumps(events)
    assert KEY.encode() not in b''.join(stderr_chunks)
    for path in tmp_path.rglob('*'):
        if path.is_file():
            assert KEY.encode() not in path.read_bytes(), 'A runtime file contains the test secret'
