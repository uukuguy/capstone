"""Trusted installation adapters with private storage and per-process identities."""
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import threading

from .application_capacity import limits
from .managed_resource_installation import ManagedResourceInstaller, PinnedGitFetcher, InstallationError
from .managed_resource_service import ManagedResourceService
from .managed_resources import ManagedResourceStore
from .managed_resource_mcp import ManagedMcpError
from .resource_permissions import ResourcePermissions


def create_managed_resource_service(root, *, network_policy, environment):
    policy = ResourcePermissions(Path(environment.get('CAPSTONE_RESOURCE_POLICY_FILE', '/opt/general/configs/runtime/resource-permissions.json')),
                                 environment.get('CAPSTONE_RESOURCE_PERMISSION_PROFILE', ''))
    store = ManagedResourceStore(Path(root), policy)
    store.root.chmod(0o700)
    work_root = store.root.parent / 'inputs' / '.managed-installers'
    work_root.mkdir(mode=0o711, parents=True, exist_ok=True)
    work_root.chmod(0o711)

    def allocate_uid():
        with (store.root / 'next-installer-uid').open('a+') as counter:
            fcntl.flock(counter, fcntl.LOCK_EX)
            counter.seek(0)
            value = counter.read().strip()
            uid = int(value) if value else 2**31
            if uid >= 2**32-2:
                raise InstallationError('resource_installer_identity_exhausted')
            counter.seek(0)
            counter.truncate()
            counter.write(str(uid+1))
            counter.flush()
            os.fsync(counter.fileno())
            return uid

    def network(source):
        state = network_policy.state()
        if state.get('enforced') is not True or state.get('external_access') is not True:
            raise InstallationError('resource_network_disabled')

    def cleanup_execution(temporary,uid):
        # A dedicated UID is never reused, including descendants that detach.
        import signal
        deadline=time.monotonic()+2
        while True:
            owned=[]
            for entry in Path('/proc').glob('[0-9]*'):
                try:
                    status=(entry/'status').read_text()
                    if any(line.startswith('Uid:') and int(line.split()[1])==uid for line in status.splitlines()):
                        owned.append(int(entry.name))
                except (FileNotFoundError,ProcessLookupError):
                    continue
            if not owned:break
            for pid in owned:
                try:os.kill(pid,signal.SIGKILL)
                except ProcessLookupError:pass
            if time.monotonic()>=deadline:
                raise InstallationError('resource_cleanup_incomplete')
            time.sleep(.01)
        temporary.cleanup()

    def prepare_execution(argv, cwd, secret_refs, *, input_document=None, package=None):
        if secret_refs:
            raise InstallationError('resource_secret_binding_unavailable')
        if os.geteuid() != 0:
            raise InstallationError('resource_installer_isolation_required')
        cwd = Path(cwd)
        if not cwd.resolve().is_relative_to((store.root / 'staging').resolve()):
            raise InstallationError('resource_installer_path_invalid')
        command = shutil.which(argv[0])
        if command is None:
            raise InstallationError('resource_installer_dependency_missing')
        uid = allocate_uid()
        temporary = tempfile.TemporaryDirectory(prefix='operation-', dir=work_root)
        try:
            private = Path(temporary.name)
            execution = private / 'cwd'
            shutil.copytree(cwd, execution, symlinks=True)
            home = private / 'home'
            home.mkdir()
            document = None if input_document is None else dict(input_document)
            if package is not None:
                shutil.copytree(package, private / 'package', symlinks=True)
                document['package'] = str(private / 'package')
            for path in [private, *private.rglob('*')]:
                os.chown(path, uid, uid, follow_symlinks=False)
                if not path.is_symlink():
                    path.chmod(0o700 if path.is_dir() or path.stat().st_mode & 0o111 else 0o600)
            arguments = ['/usr/bin/setpriv', f'--reuid={uid}', f'--regid={uid}', '--clear-groups', '--no-new-privs', command, *argv[1:]]
            child_environment = {'PATH': '/usr/local/bin:/usr/bin:/bin', 'HOME': str(home), 'TMPDIR': str(home),
                'LANG': 'C.UTF-8', 'PYTHONPATH': '/opt/general', 'GIT_TERMINAL_PROMPT': '0', 'PYTHONDONTWRITEBYTECODE': '1'}
            return temporary, execution, arguments, child_environment, document, uid
        except BaseException:
            temporary.cleanup()
            raise

    def runner(argv, cwd, secret_refs, *, input_document=None, timeout=None, package=None):
        temporary, execution, arguments, child_environment, document, uid = prepare_execution(
            argv,cwd,secret_refs,input_document=input_document,package=package)
        try:
            try:
                result = subprocess.run(arguments,cwd=execution,env=child_environment,
                    input=json.dumps(document) if document is not None else '',capture_output=True,text=True,
                    timeout=max(.001,timeout if timeout is not None else limits.mcp_initialize_seconds))
            except subprocess.TimeoutExpired as error:
                if document is not None and document.get('call') is not None:
                    raise ManagedMcpError('resource_call_outcome_unknown',stage='execution',executed=None) from error
                raise InstallationError('resource_installation_timeout') from error
            if result.returncode:
                if document is not None and document.get('call') is not None:
                    raise ManagedMcpError('resource_call_outcome_unknown',stage='execution',executed=None)
                raise InstallationError('resource_installer_command_failed')
            if argv[0]=='git':
                shutil.rmtree(cwd)
                shutil.copytree(execution,cwd,symlinks=True)
            return result.stdout
        finally:
            from .runtime_cleanup import run_runtime_cleanup
            run_runtime_cleanup(lambda:cleanup_execution(temporary,uid),operation='resource_process_cleanup')

    def decode(raw):
        receipt = json.loads(raw)
        if receipt.get('ok') is True:
            return receipt['result']
        error = receipt['error']
        raise ManagedMcpError(error['code'], stage=error['stage'], executed=error['executed'])

    def skill(package, runtime):
        if sum(path.stat().st_size for path in package.rglob('SKILL.md') if path.is_file()) > limits.native_context_bytes:
            raise InstallationError('resource_skill_metadata_too_large')
        program = '''import {loadSkillsFromDir} from "/opt/pi/packages/coding-agent/dist/index.js";
import path from "node:path";
const root=process.cwd();const result=loadSkillsFromDir({dir:root,source:"managed"});
console.log(JSON.stringify({skills:result.skills.map(s=>({name:s.name,description:s.description,path:path.relative(root,s.filePath)}))}));'''
        return json.loads(runner(('node', '--input-type=module', '-e', program), package, runtime.secret_refs))

    def probe(document, secret_refs=(), *, package=None, timeout=None):
        staging = store.root / 'staging'
        staging.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='probe-', dir=staging) as temporary:
            return decode(runner((sys.executable, '-m', 'capstone_agent.managed_resource_probe', '--invoke'),
                Path(temporary), secret_refs, input_document=document, package=package,
                timeout=timeout if timeout is not None else limits.mcp_initialize_seconds+limits.mcp_catalog_seconds))

    def remote(source, runtime):
        return probe({'kind': 'mcp_remote', 'source': {'locator': source.locator}, 'runtime': {}, 'call': None}, runtime.secret_refs)

    def local(package, runtime):
        from dataclasses import asdict
        return probe({'kind': 'mcp_local', 'source': {}, 'runtime': asdict(runtime), 'call': None},
                     runtime.secret_refs, package=package)

    installer = ManagedResourceInstaller(store, fetch_git=PinnedGitFetcher(runner), verify_skill=skill,
        probe_local=local, probe_remote=remote, check_network=network)
    service = ManagedResourceService(store, installer)

    sessions={}
    active_tasks=set()
    session_lock=threading.RLock()

    def open_task(task_id):
        with session_lock:active_tasks.add(task_id)

    def task_is_open(task_id):
        with session_lock:return task_id in active_tasks

    def invoke_mcp(item, arguments, *, deadline=None, session_key=None):
        package = store.root / item['package_ref'] if item['package_ref'] else None
        timeout = limits.mcp_initialize_seconds+limits.mcp_catalog_seconds+(limits.mcp_tool_seconds if arguments is not None else 0)
        if deadline is not None:
            timeout = min(timeout, max(0, deadline-time.monotonic()))
            if timeout <= 0:
                raise ManagedMcpError('resource_task_deadline', stage='admission', executed=False)
        document={'kind':item['kind'],'source':item['source'],'runtime':item['runtime'],'call':arguments}
        if session_key is None:
            if package is not None and installer._digest(package)!='sha256:'+package.name:
                raise InstallationError('resource_package_corrupt')
            return probe(document,item['runtime']['secret_refs'],package=package,timeout=timeout)
        key=(session_key,item['resource_id'],item['version'])
        from .managed_resource_session import ManagedResourceSession
        stale=None
        with session_lock:
            if session_key not in active_tasks:
                raise ManagedMcpError('resource_task_closed',stage='admission',executed=False)
            connection=sessions.get(key)
            if arguments is None and connection is not None and (connection.closed or connection.process.poll() is not None):
                stale=sessions.pop(key)
                connection=None
        if stale is not None:stale.close()
        if connection is None:
            if package is not None and installer._digest(package)!='sha256:'+package.name:
                raise InstallationError('resource_package_corrupt')
            staging=store.root/'staging';staging.mkdir(exist_ok=True)
            with tempfile.TemporaryDirectory(prefix='session-',dir=staging) as temporary:
                private,cwd,argv,env,initial,uid=prepare_execution(
                    (sys.executable,'-m','capstone_agent.managed_resource_probe','--serve'),Path(temporary),
                    item['runtime']['secret_refs'],input_document=document,package=package)
            try:
                candidate=ManagedResourceSession(argv,cwd=cwd,environment=env,initial=initial,cleanup=lambda:cleanup_execution(private,uid))
            except BaseException:
                cleanup_execution(private,uid)
                raise
            # No connection or tool call is started until the first exchange.
            # Slow package preparation must not hold the task-lifecycle lock.
            with session_lock:
                active=session_key in active_tasks
                connection=sessions.get(key) if active else None
                if active and connection is None:
                    sessions[key]=candidate
                    connection=candidate
            if connection is not candidate:candidate.close()
            if not active:
                raise ManagedMcpError('resource_task_closed',stage='admission',executed=False)
        return connection.exchange(arguments,deadline=min(deadline,time.monotonic()+timeout) if deadline is not None else time.monotonic()+timeout)

    def close_task(task_id):
        with session_lock:
            active_tasks.discard(task_id)
            closing=[sessions.pop(key) for key in list(sessions) if key[0]==task_id]
        errors=[]
        for connection in closing:
            try:connection.close()
            except Exception as error:errors.append(error)
        if errors:raise ExceptionGroup('managed resource session cleanup failed',errors)

    service.open_task=open_task
    service.task_is_open=task_is_open
    service.close_task=close_task

    service.invoke_mcp = invoke_mcp
    return service
