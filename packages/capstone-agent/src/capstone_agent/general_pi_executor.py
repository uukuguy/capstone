"""Native general Pi process. The host selects configuration and isolation."""
from __future__ import annotations

import json
from hashlib import sha256
import os
from pathlib import Path
from queue import Empty, Full, Queue
import re
import shutil
import signal
import stat
import subprocess
from threading import Event, Thread
import time
from collections.abc import Callable, Mapping


_TASK_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z')
_MAX_FRAME = 262_144


def collect_artifacts(workspace: Path, task_id: str, parent_attempt_id: str) -> list[dict]:
    """Snapshot finite regular task files. Private runtime input is excluded."""
    artifacts = []
    for path in sorted(workspace.rglob('*')):
        relative = path.relative_to(workspace)
        if (relative.parts[0].startswith('.') or relative.parts[0] == 'context.json'
                or any(part.is_symlink() for part in [path, *path.parents] if part != workspace.parent)
                or not path.resolve().is_relative_to(workspace.resolve())):
            continue
        mode = path.lstat()
        if not stat.S_ISREG(mode.st_mode) or mode.st_size > 4 * 1024 * 1024:
            continue
        digest = sha256(path.read_bytes()).hexdigest()
        artifacts.append({'artifact_id': 'file-' + sha256(str(relative).encode()).hexdigest()[:16] + '-' + digest, 'task_id': task_id,
            'parent_attempt_id': parent_attempt_id, 'kind': 'workspace_file',
            'metadata': {'path': str(relative), 'sha256': digest, 'size_bytes': mode.st_size}})
        if len(artifacts) == 64:
            break
    return artifacts


def task_workspace(root: Path, task_id: str) -> Path:
    if not isinstance(task_id, str) or not _TASK_ID.fullmatch(task_id) or task_id in {'.', '..'}:
        raise ValueError('General Pi task identity is invalid')
    root = root.resolve()
    path = root / task_id
    if path.is_symlink() or path.resolve().parent != root:
        raise ValueError('General Pi workspace is invalid')
    return path


def native_pi_launch(*, command: tuple[str, ...], workspace: Path, config_root: Path,
                     model: str, relay_url: str, relay_token: str,
                     context_extension: Path) -> tuple[tuple[str, ...], dict[str, str]]:
    """Load native managed config; no business launcher or developer HOME."""
    if not command or any(not isinstance(part, str) or not part for part in command):
        raise ValueError('General Pi command is invalid')
    workspace.mkdir(mode=0o700, parents=True, exist_ok=False)
    agent = workspace / '.agent'
    agent.mkdir(mode=0o700)
    for path in config_root.iterdir():
        if path.name in {'auth.json', 'models.json'} or path.is_symlink():
            raise ValueError('General Pi config contains protected transport or symbolic links')
        target = workspace / path.name if path.name in {'AGENTS.md', 'CLAUDE.md'} else agent / path.name
        if path.is_dir():
            if any(item.is_symlink() for item in path.rglob('*')):
                raise ValueError('General Pi config contains symbolic links')
            shutil.copytree(path, target)
        else:
            shutil.copyfile(path, target)
    models = {'providers': {'capstone-general': {
        'baseUrl': relay_url, 'api': 'openai-completions', 'apiKey': relay_token,
        'models': [{'id': model, 'name': model, 'reasoning': False, 'input': ['text'],
                    'contextWindow': 128000, 'maxTokens': 8192,
                    'cost': {'input': 0, 'output': 0, 'cacheRead': 0, 'cacheWrite': 0}}],
    }}}
    (agent / 'models.json').write_text(json.dumps(models))
    (agent / 'models.json').chmod(0o600)
    environment = {'PATH': '/usr/local/bin:/usr/bin:/bin', 'HOME': str(workspace),
                   'LANG': 'C.UTF-8', 'PI_CODING_AGENT_DIR': str(agent), 'PI_OFFLINE': '1'}
    argv = (*command, '--mode', 'rpc', '--provider', 'capstone-general', '--model', model,
            '--approve', '--offline', '--session-dir', str(agent / 'sessions'),
            '--extension', str(context_extension))
    return argv, environment


class GeneralPiProcess:
    """Finite native RPC with a separate process group and optional Unix identity."""

    def __init__(self, command: tuple[str, ...], environment: Mapping[str, str], workspace: Path,
                 *, uid: int | None = None) -> None:
        self.command, self.environment, self.workspace = command, dict(environment), workspace
        if uid is not None and (type(uid) is not int or not 10000 <= uid < 2**31):
            raise ValueError('General Pi task privilege is invalid')
        self.uid = uid
        self.process: subprocess.Popen | None = None
        self.usage: dict = {}

    def run(self, instruction: str, *, timeout: float, cancelled: Callable[[], bool],
            on_event: Callable[[dict], None]) -> str:
        if timeout <= 0:
            raise ValueError('General Pi deadline is invalid')
        privilege = {} if self.uid is None else {'user': self.uid, 'group': self.uid, 'extra_groups': []}
        self.process = subprocess.Popen(self.command, cwd=self.workspace, env=self.environment,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            start_new_session=True, **privilege)
        process = self.process
        frames: Queue[bytes | None | Exception] = Queue(maxsize=64)
        stopped = Event()

        def enqueue(frame):
            while not stopped.is_set():
                try:
                    frames.put(frame, timeout=0.05)
                    return
                except Full:
                    pass

        def read() -> None:
            try:
                assert process.stdout is not None
                while line := process.stdout.readline(_MAX_FRAME + 1):
                    if len(line) > _MAX_FRAME:
                        enqueue(ValueError('General Pi frame exceeds bounds'))
                        return
                    enqueue(line)
            except (OSError, ValueError):
                pass
            finally:
                enqueue(None)

        def drain() -> None:
            assert process.stderr is not None
            try:
                while process.stderr.read(4096):
                    pass  # Private runtime diagnostics do not enter public output.
            except (OSError, ValueError):
                pass

        Thread(target=read, daemon=True).start()
        Thread(target=drain, daemon=True).start()
        deadline = time.monotonic() + timeout
        try:
            assert process.stdin is not None
            process.stdin.write((json.dumps({'type': 'prompt', 'message': instruction}) + '\n').encode())
            process.stdin.flush()
            while True:
                if cancelled():
                    raise InterruptedError('General Pi task cancelled')
                if time.monotonic() >= deadline:
                    raise TimeoutError('General Pi task deadline exceeded')
                try:
                    frame = frames.get(timeout=0.05)
                except Empty:
                    continue
                if frame is None:
                    raise RuntimeError('General Pi ended before completion')
                if isinstance(frame, Exception):
                    raise frame
                event = json.loads(frame)
                if not isinstance(event, dict):
                    raise ValueError('General Pi event is invalid')
                if event.get('type') == 'response' and event.get('success') is False:
                    raise RuntimeError('General Pi rejected request')
                if event.get('type') == 'agent_end':
                    messages = event.get('messages', [])
                    assistants = [item for item in messages if item.get('role') == 'assistant']
                    if not assistants or assistants[-1].get('stopReason') in {'error', 'aborted'}:
                        raise RuntimeError('General Pi did not complete')
                    self.usage = {key: sum(item.get('usage', {}).get(key, 0) for item in assistants)
                                  for key in ('input', 'output')}
                    answer = ''.join(part.get('text', '') for part in assistants[-1].get('content', [])
                                     if part.get('type') == 'text')
                    if not answer.strip() or len(answer) > 64_000:
                        raise ValueError('General Pi answer is invalid')
                    return answer
                if event.get('type') in {'tool_execution_start', 'tool_execution_end', 'message_update'}:
                    on_event(event)
        finally:
            stopped.set()
            self.stop()

    def stop(self) -> None:
        process, self.process = self.process, None
        if process is None:
            return
        # Native tools may have descendants after Pi exits. Kill the group too.
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            pass
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=1)
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream is not None:
                stream.close()
        if self.uid is not None:
            # A tool can create another process session. Each task has a unique UID.
            for _ in range(3):
                alive = False
                for path in Path('/proc').glob('[0-9]*'):
                    try:
                        if path.stat().st_uid == self.uid:
                            os.kill(int(path.name), signal.SIGKILL)
                            alive = True
                    except ProcessLookupError:
                        pass
                if not alive:
                    break
                time.sleep(0.01)
