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
    work_root = store.root.parent / 'tasks' / '.managed-installers'
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

    def runner(argv, cwd, secret_refs, *, input_document=None, timeout=None, package=None):
        if secret_refs:
            raise InstallationError('resource_secret_binding_unavailable')
        if os.geteuid() != 0:
            raise InstallationError('resource_installer_isolation_required')
        cwd = Path(cwd)
        if not cwd.resolve().is_relative_to((store.root / 'staging').resolve()):
            raise InstallationError('resource_installer_path_invalid')
        uid = allocate_uid()
        command = shutil.which(argv[0])
        if command is None:
            raise InstallationError('resource_installer_dependency_missing')
        # The persistent store never becomes traversable by an untrusted UID.
        with tempfile.TemporaryDirectory(prefix='operation-', dir=work_root) as temporary:
            private = Path(temporary)
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
                    path.chmod(0o700 if path.is_dir() else 0o700 if path.stat().st_mode & 0o111 else 0o600)
            try:
                result = subprocess.run(['/usr/bin/setpriv', f'--reuid={uid}', f'--regid={uid}', '--clear-groups', '--no-new-privs', command, *argv[1:]],
                    cwd=execution, env={'PATH': '/usr/local/bin:/usr/bin:/bin', 'HOME': str(home), 'TMPDIR': str(home),
                        'LANG': 'C.UTF-8', 'PYTHONPATH': '/opt/general', 'GIT_TERMINAL_PROMPT': '0', 'PYTHONDONTWRITEBYTECODE': '1'},
                    input=json.dumps(document) if document is not None else '', capture_output=True, text=True,
                    timeout=max(.001, timeout if timeout is not None else limits.mcp_initialize_seconds))
            except subprocess.TimeoutExpired as error:
                if document is not None and document.get('call') is not None:
                    raise ManagedMcpError('resource_call_outcome_unknown', stage='execution', executed=None) from error
                raise InstallationError('resource_installation_timeout') from error
            if result.returncode:
                if document is not None and document.get('call') is not None:
                    raise ManagedMcpError('resource_call_outcome_unknown', stage='execution', executed=None)
                raise InstallationError('resource_installer_command_failed')
            if argv[0] == 'git':
                # Copy bytes back into root-owned staging; never promote child ownership.
                shutil.rmtree(cwd)
                shutil.copytree(execution, cwd, symlinks=True)
            return result.stdout

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

    def invoke_mcp(item, arguments, *, deadline=None):
        package = store.root / item['package_ref'] if item['package_ref'] else None
        if package is not None and installer._digest(package) != 'sha256:'+package.name:
            raise InstallationError('resource_package_corrupt')
        timeout = limits.mcp_initialize_seconds+limits.mcp_catalog_seconds+(limits.mcp_tool_seconds if arguments is not None else 0)
        if deadline is not None:
            timeout = min(timeout, max(0, deadline-time.monotonic()))
            if timeout <= 0:
                raise ManagedMcpError('resource_task_deadline', stage='admission', executed=False)
        return probe({'kind': item['kind'], 'source': item['source'], 'runtime': item['runtime'], 'call': arguments},
                     item['runtime']['secret_refs'], package=package, timeout=timeout)

    service.invoke_mcp = invoke_mcp
    return service
