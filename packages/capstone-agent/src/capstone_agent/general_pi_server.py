"""Private general Pi control service, separate from professional workers."""
from __future__ import annotations

from collections.abc import Callable
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import http.client
import json
import os
from pathlib import Path
import secrets
import shutil
import threading
import time
from urllib.parse import urlsplit

from .general_pi_executor import GeneralPiProcess, native_pi_launch, task_workspace, collect_artifacts
from .pi_delegation import PiTaskRequest, PiTaskResult, MAX_DOCUMENT_BYTES
from .general_pi_storage import GeneralPiStorage, request_hash


class GeneralPiHost:
    def __init__(self, *, root: Path, identity: dict, run_task: Callable,
                 max_tasks: int = 8, max_records: int = 256, retention_seconds: float = 86400,
                 max_storage_bytes: int = 64 * 1024 * 1024, max_saved_receipts: int = 4096) -> None:
        self.root, self.identity, self._run = root, dict(identity), run_task
        self.capability = {'capability_id': 'general-pi', 'display_name': 'General Pi agent',
            'enabled': True, 'available': True, 'operations': ['answer', 'rewrite', 'external_lookup'],
            'executor_identity': self.identity}
        self._max_tasks, self._max_records = max_tasks, max_records
        self._lock = threading.RLock()
        self._tasks: dict[str, dict] = {}
        root.mkdir(parents=True, exist_ok=True, mode=0o711)
        (root / 'receipts').mkdir(exist_ok=True, mode=0o700)
        (root / 'receipts').chmod(0o700)
        self.storage = GeneralPiStorage(root / 'receipts', retention_seconds=retention_seconds,
            max_receipts=max_saved_receipts, max_bytes=max_storage_bytes)
        self.storage.sweep(set())

    def submit(self, request: PiTaskRequest) -> None:
        if request.to_document()['executor_identity'] != self.identity:
            raise ValueError('General Pi configuration changed')
        with self._lock:
            self.sweep()
            old = self._tasks.get(request.task_id)
            if old is not None:
                if old['request'].to_document() != request.to_document():
                    raise ValueError('General Pi task identity conflict')
                return
            self._make_room()
            saved = self.storage.load(request.task_id)
            if saved is not None:
                if saved['request_hash'] != request_hash(request.to_document()):
                    raise ValueError('General Pi task identity conflict')
                if saved['result'] is None:
                    saved['result'] = {'schema': 'capstone-pi-task-result/1',
                        'task_id': request.task_id, 'parent_attempt_id': request.parent_attempt_id,
                        'executor_identity': self.identity, 'status': 'failed',
                        'answer': ('Result retention expired; task was not repeated.' if saved.get('expired')
                                   else 'Previous execution outcome is unknown; the task was not repeated.'),
                        'sources': [], 'artifacts': [], 'usage': {}}
                result = PiTaskResult.from_document(saved['result'], request)
                self._tasks[request.task_id] = {'request': request, 'status': result.status,
                    'events': [], 'result': result.to_document(), 'cancel': threading.Event()}
                return
            if sum(item['status'] in {'queued', 'running'} for item in self._tasks.values()) >= self._max_tasks:
                raise RuntimeError('General Pi executor capacity reached')
            record = {'request': request, 'status': 'running', 'events': [], 'result': None,
                      'cancel': threading.Event()}
            # An accepted receipt prevents replaying an unknown side effect after restart.
            self._save(request, None)
            self._tasks[request.task_id] = record
            threading.Thread(target=self._execute, args=(request, record), daemon=True).start()

    def _save(self, request: PiTaskRequest, result: dict | None) -> None:
        self.storage.save(request.to_document(), result)

    def _make_room(self):
        if len(self._tasks) >= self._max_records:
            completed = next((key for key, item in self._tasks.items()
                              if item['status'] not in {'queued', 'running'}), None)
            if completed is None:
                raise RuntimeError('General Pi record capacity reached')
            del self._tasks[completed]

    def sweep(self):
        with self._lock:
            active = {key for key, item in self._tasks.items() if item['status'] in {'queued', 'running'}}
            for task_id in self.storage.sweep(active):
                self._tasks.pop(task_id, None)

    def read_artifact(self, task_id, artifact_id):
        task_workspace(self.root, task_id)
        task_workspace(self.root, artifact_id)
        self.sweep()
        return self.storage.read_artifact(task_id, artifact_id)

    def _execute(self, request: PiTaskRequest, record: dict) -> None:
        started = time.monotonic()
        sources = []
        def cancelled():
            return record['cancel'].is_set() or time.monotonic() - started >= request.timeout_seconds
        def emit(event):
            # Public transport uses bounded receipts, never raw native frames.
            kind = event.get('type')
            payload = None
            if kind in {'tool_execution_start', 'tool_execution_end'}:
                payload = {'type': kind, 'tool_name': str(event.get('toolName', ''))[:128],
                           'tool_call_id': str(event.get('toolCallId', ''))[:128]}
                if kind == 'tool_execution_end' and len(sources) < 64:
                    body = json.dumps(event.get('result', {}), ensure_ascii=False).encode()
                    digest = sha256(body).hexdigest()
                    observation_id = 'observation-' + str(len(sources)) + '-' + digest
                    self.storage.observation(request.task_id, observation_id, body)
                    sources.append({'source_id': observation_id, 'task_id': request.task_id,
                        'parent_attempt_id': request.parent_attempt_id, 'kind': 'native_tool_observation',
                        'metadata': {'tool_name': payload['tool_name'], 'tool_call_id': payload['tool_call_id'],
                                     'output_sha256': digest}})
            elif kind == 'message_update':
                change = event.get('assistantMessageEvent', {})
                if change.get('type') == 'text_delta':
                    payload = {'type': 'assistant_delta', 'text': str(change.get('delta', ''))[:2048]}
            if payload is not None:
                with self._lock:
                    if len(record['events']) < 128 and len(json.dumps(record['events']).encode()) < 64 * 1024:
                        record['events'].append({'event_id': 'event-' + str(len(record['events']) + 1), **payload})
        status, answer, usage = 'completed', '', {}
        try:
            answer, usage = self._run(request, cancelled, emit)
        except InterruptedError:
            status = 'cancelled' if record['cancel'].is_set() else 'failed'
        except Exception:
            status = 'failed'
        if cancelled():
            status = 'cancelled' if record['cancel'].is_set() else 'failed'
            answer = ''
        workspace = self.root / 'tasks' / request.task_id
        try:
            artifacts = collect_artifacts(workspace, request.task_id, request.parent_attempt_id) if status == 'completed' else []
            self.storage.artifacts(request.task_id, workspace, artifacts)
            result = PiTaskResult.from_document({'schema': 'capstone-pi-task-result/1',
                'task_id': request.task_id, 'parent_attempt_id': request.parent_attempt_id,
                'executor_identity': self.identity, 'status': status, 'answer': answer,
                'sources': sources, 'artifacts': artifacts, 'usage': usage}, request).to_document()
            self._save(request, result)
        except (OSError, ValueError, TypeError):
            result = {'schema': 'capstone-pi-task-result/1', 'task_id': request.task_id,
                'parent_attempt_id': request.parent_attempt_id, 'executor_identity': self.identity,
                'status': 'failed', 'answer': '', 'sources': [], 'artifacts': [], 'usage': {}}
            try:
                self._save(request, result)
            except OSError:
                pass  # Initial accepted receipt remains an unknown-outcome replay guard.
        finally:
            shutil.rmtree(workspace, ignore_errors=True)
        with self._lock:
            record['status'], record['result'] = result['status'], result

    def read(self, task_id: str) -> dict:
        with self._lock:
            item = self._tasks[task_id]
            return json.loads(json.dumps({key: item[key] for key in ('status', 'events', 'result')}))

    def cancel(self, task_id: str) -> None:
        with self._lock:
            self._tasks[task_id]['cancel'].set()


class NativeTaskRunner:
    """Pi uses a task UID; host secrets remain in a different root process."""
    def __init__(self, *, root: Path, config_root: Path, command: tuple[str, ...],
                 model: str, relay_origin: str) -> None:
        if os.geteuid() != 0 or os.name != 'posix':
            raise RuntimeError('General Pi requires its isolated Linux container')
        self.root, self.config_root, self.command = root, config_root, command
        self.model, self.relay_origin = model, relay_origin
        self._lock = threading.Lock()
        self.grants: dict[str, str] = {}
        root.mkdir(mode=0o711, parents=True, exist_ok=True)
        (root / 'tasks').mkdir(mode=0o711, exist_ok=True)

    def __call__(self, request, cancelled, emit, *, inventory_only=False):
        with self._lock:
            counter = self.root / 'receipts' / 'next-uid'
            uid = int(counter.read_text()) if counter.exists() else 10000
            if uid >= 2**31 - 1:
                raise RuntimeError('General Pi task identities exhausted')
            counter.write_text(str(uid + 1))
            counter.chmod(0o600)
            grant = secrets.token_urlsafe(32)
            self.grants[request.task_id] = grant
        workspace = task_workspace(self.root / 'tasks', request.task_id)
        process = None
        try:
            argv, environment = native_pi_launch(command=self.command, workspace=workspace,
                config_root=self.config_root, model=self.model,
                relay_url=self.relay_origin + '/provider/' + request.task_id, relay_token=grant,
                context_extension=Path(__file__).parent / 'resources' / 'general-context.mjs')
            context = {'messages': request.to_document()['messages'],
                       'dependency_results': request.to_document()['dependency_results']}
            (workspace / 'context.json').write_text(json.dumps(context))
            for path in [workspace, *workspace.rglob('*')]:
                os.chown(path, uid, uid)
            process = GeneralPiProcess(argv, environment, workspace, uid=uid)
            answer = process.run(request.instruction, timeout=request.timeout_seconds,
                                 cancelled=cancelled, on_event=emit, inventory_only=inventory_only)
            return answer, ({'native_tools': process.tools} if inventory_only else process.usage)
        finally:
            try:
                if process is not None:
                    process.stop()
            finally:
                with self._lock:
                    self.grants.pop(request.task_id, None)

    def verify_tools(self, identity):
        task_id = 'readiness-' + secrets.token_hex(8)
        request = PiTaskRequest.from_document({'schema': 'capstone-pi-task/1', 'task_id': task_id,
            'parent_attempt_id': task_id, 'entrypoint': 'direct', 'instruction': 'Readiness',
            'messages': [], 'dependency_results': [], 'executor_identity': identity, 'timeout_seconds': 15})
        try:
            return self(request, lambda: False, lambda _: None, inventory_only=True)[1]['native_tools']
        finally:
            shutil.rmtree(self.root / 'tasks' / task_id, ignore_errors=True)


def make_server(host: GeneralPiHost, *, control_token: str, address: tuple[str, int],
                runner: NativeTaskRunner | None = None, upstream: str | None = None,
                provider_key: str | None = None):
    if not control_token:
        raise ValueError('General Pi control authentication is required')
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def send_json(self, status, document):
            data = json.dumps(document).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def authorized(self):
            return secrets.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + control_token)

        def do_GET(self):
            if self.path == '/health/ready':
                return self.send_json(200, {'identity': host.identity, 'capability': host.capability})
            if not self.authorized():
                return self.send_json(401, {'error': 'unauthorized'})
            try:
                parts = self.path.split('/')
                if len(parts) == 5 and parts[1] == 'tasks' and parts[3] == 'artifacts':
                    data = host.read_artifact(parts[2], parts[4])
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/octet-stream')
                    self.send_header('Content-Length', str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    return
                if not self.path.startswith('/tasks/'):
                    raise KeyError()
                self.send_json(200, host.read(self.path.removeprefix('/tasks/')))
            except (KeyError, OSError, ValueError):
                self.send_json(404, {'error': 'task_not_found'})

        def do_DELETE(self):
            if not self.authorized():
                return self.send_json(401, {'error': 'unauthorized'})
            try:
                task_id = self.path.removeprefix('/tasks/')
                host.cancel(task_id)
                self.send_json(200, {'task_id': task_id, 'status': 'cancellation_requested'})
            except KeyError:
                self.send_json(404, {'error': 'task_not_found'})

        def do_POST(self):
            if self.path.startswith('/provider/'):
                return self.relay_provider()
            if not self.authorized():
                return self.send_json(401, {'error': 'unauthorized'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if self.path != '/tasks' or not 0 < length <= MAX_DOCUMENT_BYTES:
                    raise ValueError()
                request = PiTaskRequest.from_document(json.loads(self.rfile.read(length)))
                host.submit(request)
                self.send_json(202, {'task_id': request.task_id})
            except (ValueError, KeyError):
                self.send_json(400, {'error': 'invalid_task'})
            except (RuntimeError, OSError):
                self.send_json(503, {'error': 'executor_capacity'})

        def relay_provider(self):
            # A task gets a revocable relay grant, never the Provider credential.
            parts = self.path.split('/')
            if (runner is None or upstream is None or not provider_key or len(parts) != 5
                    or parts[3:] != ['chat', 'completions']):
                return self.send_json(404, {'error': 'relay_not_found'})
            grant = runner.grants.get(parts[2])
            if not grant or not secrets.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + grant):
                return self.send_json(401, {'error': 'unauthorized'})
            connection = None
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 2 * 1024 * 1024:
                    raise ValueError()
                body = self.rfile.read(length)
                document = json.loads(body)
                if document.get('model') != runner.model:
                    raise ValueError()
                target = urlsplit(upstream)
                if target.hostname is None or target.scheme not in {'http', 'https'}:
                    raise ValueError()
                connection_type = http.client.HTTPSConnection if target.scheme == 'https' else http.client.HTTPConnection
                connection = connection_type(target.hostname, target.port, timeout=60)
                connection.request('POST', target.path.rstrip('/') + '/chat/completions', body,
                    {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + provider_key})
                response = connection.getresponse()
                self.send_response(response.status)
                self.send_header('Content-Type', response.getheader('Content-Type', 'application/json'))
                self.send_header('Connection', 'close')
                self.end_headers()
                self.close_connection = True
                total = 0
                while chunk := response.read1(8192):
                    total += len(chunk)
                    if total > 4 * 1024 * 1024:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
            except (ValueError, OSError, http.client.HTTPException):
                if connection is None:
                    self.send_json(400, {'error': 'relay_request_invalid'})
                self.close_connection = True
            finally:
                if connection is not None:
                    connection.close()
    return ThreadingHTTPServer(address, Handler)


def main():
    if os.environ.get('CAPSTONE_GENERAL_SANDBOX') != 'container':
        raise RuntimeError('General Pi service must run in the isolated container')
    config = Path('/opt/general/config')
    root = Path('/var/lib/general-pi')
    providers = json.loads(Path('/opt/general/llm-providers.json').read_bytes())['providers']
    provider = providers[os.environ['CAPSTONE_PUBLIC_PROVIDER']]
    if (provider['auth']['kind'] != 'api_key_env'
            or provider['compatibility_profile'] == 'anthropic-messages'):
        raise ValueError('General Pi relay requires an API-key chat-completions transport')
    key = os.environ[provider['auth']['default_env']]
    port = int(os.environ.get('PORT', '8790'))
    revision = sha256()
    for path in sorted(config.rglob('*')):
        if path.is_file():
            revision.update(str(path.relative_to(config)).encode() + b'\0' + path.read_bytes())
    lock = json.loads(Path('/opt/general/pi-runtime.lock.json').read_bytes())
    identity = {'engine': 'pi', 'model': os.environ['CAPSTONE_PUBLIC_MODEL'],
                'provider': os.environ['CAPSTONE_PUBLIC_PROVIDER'],
                'pi_commit': lock['source']['commit'], 'config_revision': revision.hexdigest(),
                'runtime_lock_sha256': sha256(Path('/opt/general/pi-runtime.lock.json').read_bytes()).hexdigest(),
                'executor_revision': sha256(b''.join((Path(__file__).parent / name).read_bytes()
                    for name in ('general_pi_server.py', 'general_pi_executor.py', 'general_pi_storage.py', 'pi_delegation.py',
                                 'resources/general-context.mjs'))).hexdigest()}
    runner = NativeTaskRunner(root=root, config_root=config,
        command=('node', '/opt/pi/packages/coding-agent/dist/cli.js'), model=identity['model'],
        relay_origin=f'http://127.0.0.1:{port}')
    host = GeneralPiHost(root=root, identity=identity, run_task=runner)
    host.capability['native_tools'] = runner.verify_tools(identity)
    server = make_server(host, control_token=os.environ['CAPSTONE_GENERAL_CONTROL_TOKEN'],
        address=('0.0.0.0', port), runner=runner, upstream=provider['base_url'], provider_key=key)
    server.serve_forever()


if __name__ == '__main__':
    main()
