"""Bounded installation and actual runtime verification of managed resources.

The host supplies trusted acquisition and real Pi/MCP verification adapters.
Adapters must run commands in the isolated, unprivileged installer environment;
this module never executes subprocesses. Public requests cannot select host paths.
Interrupted claims remain pending for operator recovery, never automatic replay.
"""

from dataclasses import asdict, dataclass
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile
import tomllib
from urllib.parse import urlsplit

from .managed_resource_manifest import (
    RuntimeSpec, SourceIdentity, VerifiedResource, canonical, content_digest,
    relative_path,
)
from .resource_permissions import ResourcePermissionDenied
from .managed_resource_mcp import ManagedMcpError


class InstallationError(ValueError):
    """A safe diagnostic code, with no captured adapter output."""


class PinnedGitFetcher:
    """Git acquisition through a host-owned isolated runner, never a host shell.

    Runner contract: (argv tuple, private cwd, secret reference tuple) -> stdout.
    The runner supplies a clean environment, non-root identity and bounded time.
    """

    def __init__(self, runner):
        self.runner = runner

    def __call__(self, source, destination, secret_refs):
        if urlsplit(source.locator).scheme not in {'http', 'https'} or not re.fullmatch(r'[a-fA-F0-9]{40}|[a-fA-F0-9]{64}', source.revision):
            raise InstallationError('resource_exact_git_revision_required')
        base = ('git', '-c', 'core.hooksPath=/dev/null', '-c', 'credential.helper=', '-c', 'protocol.file.allow=never', '-c', 'protocol.ext.allow=never', '-c', 'http.followRedirects=false')
        def run(*arguments):
            return self.runner(base + arguments, destination, secret_refs)
        run('init', '--quiet')
        run('remote', 'add', 'origin', source.locator)
        run('fetch', '--no-tags', '--depth', '1', 'origin', source.revision)
        if run('rev-parse', 'FETCH_HEAD').strip().lower() != source.revision.lower():
            raise InstallationError('resource_revision_mismatch')
        run('checkout', '--quiet', '--detach', source.revision)
        actual = run('rev-parse', 'HEAD').strip()
        metadata = destination / '.git'
        if metadata.is_dir():
            shutil.rmtree(metadata)
        return actual


@dataclass(frozen=True)
class InstallRequest:
    kind: str
    source: SourceIdentity
    runtime: RuntimeSpec = RuntimeSpec()
    subdirectory: str = ''
    dependencies: tuple[str, ...] = ()

    def __post_init__(self):
        if self.kind not in {'skill', 'mcp_local', 'mcp_remote'}:
            raise ValueError('invalid_resource_kind')
        if not isinstance(self.source, SourceIdentity) or not isinstance(self.runtime, RuntimeSpec):
            raise ValueError('invalid_resource_request')
        relative_path(self.subdirectory, empty=True)
        if not isinstance(self.dependencies, tuple) or any(not isinstance(pin, str) for pin in self.dependencies):
            raise ValueError('invalid_resource_dependencies')
        if self.kind == 'mcp_remote' and (not urlsplit(self.source.locator).scheme or self.subdirectory or self.dependencies):
            raise ValueError('invalid_remote_resource_request')

    def to_dict(self):
        return json.loads(canonical(asdict(self)))

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict) or not {'kind', 'source'} <= set(value) or set(value) - {'kind', 'source', 'runtime', 'subdirectory', 'dependencies'}:
            raise ValueError('invalid_resource_request')
        source = value['source']
        if not isinstance(source, dict) or set(source) != {'locator', 'revision'}:
            raise ValueError('invalid_resource_source')
        runtime = value.get('runtime', {})
        if not isinstance(runtime, dict) or set(runtime) - {'entrypoint', 'arguments', 'secret_refs', 'compatibility'}:
            raise ValueError('invalid_resource_runtime')
        if not isinstance(runtime.get('arguments', []), list) or not isinstance(runtime.get('secret_refs', []), list) or not isinstance(value.get('dependencies', []), list):
            raise ValueError('invalid_resource_request')
        return cls(value['kind'], SourceIdentity(**source), RuntimeSpec(runtime.get('entrypoint', ''), tuple(runtime.get('arguments', [])), tuple(runtime.get('secret_refs', [])), runtime.get('compatibility', '')), value.get('subdirectory', ''), tuple(value.get('dependencies', [])))


def _network_denied(source):
    raise InstallationError('resource_network_disabled')


class ManagedResourceInstaller:
    def __init__(self, store, *, staged_sources=None, fetch_git=None,
                 verify_skill=None, probe_local=None, probe_remote=None,
                 check_network=None, install_dependencies=None, max_files=10000, max_bytes=None):
        self.store = store
        self.staged_sources = {key: Path(value).resolve() for key, value in (staged_sources or {}).items()}
        self.fetch_git = fetch_git
        self.verify_skill = verify_skill
        self.probe_local = probe_local
        self.probe_remote = probe_remote
        self.check_network = check_network or _network_denied
        self.install_dependencies = install_dependencies
        self.max_files = max_files
        if max_bytes is None:
            from .application_capacity import current_capacity
            max_bytes = current_capacity().values['native_storage_bytes']
        self.max_bytes = max_bytes

    def install(self, principal, workspace, request_id, resource_id, request,
                expected_version=None, *, _prebuilt=None):
        if not isinstance(request, InstallRequest):
            raise TypeError('parsed_install_request_required')
        identity = request.to_dict()
        if _prebuilt is not None:
            identity = {**identity, 'prebuilt': content_digest(_prebuilt[1:])}
        operation = self.store.begin_install(principal, workspace, request_id,
                                             resource_id, identity, expected_version)
        if operation['status'] != 'pending':
            return operation
        # Persistent, exclusive claim across processes, without task scheduling.
        claims = self.store.root / 'installation-claims'
        claims.mkdir(exist_ok=True)
        claim = claims / content_digest([workspace, request_id]).split(':')[1]
        try:
            descriptor = os.open(claim, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            return operation
        os.close(descriptor)
        stage = None
        resource_lock = None
        try:
            self._authorize(principal, workspace, operation)
            locks = self.store.root / 'installation-locks'
            locks.mkdir(exist_ok=True)
            resource_lock = (locks / content_digest([workspace, resource_id]).split(':')[1]).open('a')
            try:
                fcntl.flock(resource_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise InstallationError('resource_installation_in_progress') from None
            if request.kind == 'mcp_remote':
                verified = self._remote(request)
            else:
                staging = self.store.root / 'staging'
                staging.mkdir(exist_ok=True)
                stage = Path(tempfile.mkdtemp(prefix='install-', dir=staging))
                verified = self._package(request, stage, prebuilt=_prebuilt[0] if _prebuilt else None)
            if _prebuilt is not None:
                if verified.to_dict() != _prebuilt[1] or self.publication(verified.digest) != _prebuilt[2]:
                    raise InstallationError('resource_preinstall_verification_mismatch')
            self._authorize(principal, workspace, operation)
            result = self.store.publish_verified(principal, workspace, request_id, verified, install_request=request)
        except ResourcePermissionDenied:
            return self.store.fail_operation(principal, workspace, request_id, 'resource_permission_revoked')
        except Exception as error:
            code = str(error) if isinstance(error, (InstallationError, ManagedMcpError)) and re.fullmatch(r'resource_[a-z_]{1,80}', str(error)) else 'resource_installation_failed'
            return self.store.fail_operation(principal, workspace, request_id, code)
        finally:
            try:
                if stage is not None:
                    shutil.rmtree(stage)
            finally:
                if resource_lock is not None:
                    resource_lock.close()
        return {**operation, 'status': 'succeeded', 'result': result}

    def install_prebuilt(self, principal, workspace, request_id, resource_id, request,
                         package_path, expected_resource, publication, expected_version=None):
        """Trusted deployment adapter. Frozen metadata is comparison, never authority."""
        from .managed_resource_manifest import parse_verified
        frozen = parse_verified(expected_resource)
        if frozen.source != request.source or frozen.runtime != request.runtime or frozen.kind != request.kind:
            raise InstallationError('resource_preinstall_verification_mismatch')
        if request.kind != 'mcp_remote' and package_path is None:
            raise InstallationError('resource_preinstall_package_missing')
        return self.install(principal, workspace, request_id, resource_id, request,
            expected_version, _prebuilt=(package_path, frozen.to_dict(), publication))

    def _authorize(self, principal, workspace, operation):
        self.store.permissions.require(principal, workspace, operation['action'])

    def _acquire(self, request, stage):
        locator = request.source.locator
        if (locator, request.source.revision) in self.staged_sources:
            acquired = self.staged_sources[(locator, request.source.revision)]
        elif locator in self.staged_sources:
            acquired = self.staged_sources[locator]
        else:
            if urlsplit(locator).scheme not in {'http', 'https'}:
                raise InstallationError('resource_source_not_registered')
            if not re.fullmatch(r'[a-fA-F0-9]{40}|[a-fA-F0-9]{64}', request.source.revision):
                raise InstallationError('resource_exact_git_revision_required')
            self.check_network(request.source)
            if self.fetch_git is None:
                raise InstallationError('resource_isolated_fetcher_required')
            acquired = stage / 'acquired'
            acquired.mkdir()
            actual = self.fetch_git(request.source, acquired, request.runtime.secret_refs)
            if actual.lower() != request.source.revision.lower():
                raise InstallationError('resource_revision_mismatch')
        selected = acquired / request.subdirectory if request.subdirectory else acquired
        # Check every parent before resolving, so no symlink can select host data.
        current = acquired
        for part in request.subdirectory.split('/') if request.subdirectory else []:
            current = current / part
            if current.is_symlink():
                raise InstallationError('resource_unsafe_path')
        if not selected.is_dir():
            raise InstallationError('resource_source_directory_missing')
        return selected

    def _snapshot(self, source, target):
        target.mkdir()
        count = total = 0
        for base, directories, files in os.walk(source, followlinks=False):
            directories.sort()
            files.sort()
            # Repository metadata is not executable package content.
            if Path(base) == source and '.git' in directories:
                directories.remove('.git')
            for name in directories + files:
                original = Path(base) / name
                relative = original.relative_to(source)
                relative_path(relative.as_posix())
                if self._protected(relative):
                    raise InstallationError('resource_protected_file')
                mode = original.lstat().st_mode
                if not (stat.S_ISLNK(mode) or stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
                    raise InstallationError('resource_unsafe_path')
                count += 1
                if count > self.max_files:
                    raise InstallationError('resource_package_limit')
                destination = target / relative
                if stat.S_ISLNK(mode):
                    destination.symlink_to(self._safe_link(original, source))
                    continue
                if stat.S_ISDIR(mode):
                    destination.mkdir()
                    continue
                # O_NOFOLLOW also closes a last-component replacement race.
                descriptor = os.open(original, os.O_RDONLY | os.O_NOFOLLOW)
                with os.fdopen(descriptor, 'rb') as reader, destination.open('xb') as writer:
                    if not stat.S_ISREG(os.fstat(reader.fileno()).st_mode):
                        raise InstallationError('resource_unsafe_path')
                    while chunk := reader.read(1024 * 1024):
                        total += len(chunk)
                        if total > self.max_bytes:
                            raise InstallationError('resource_package_limit')
                        writer.write(chunk)
                destination.chmod(0o755 if mode & 0o111 else 0o644)

    @staticmethod
    def _protected(relative):
        parts = [part.lower() for part in relative.parts]
        return any(part in {'.git', '.ssh', '.aws', '.azure', '.gnupg', '.grid-agent', '.capstone-agent', '.npmrc', '.pypirc', '.netrc', 'credentials.json', 'auth.json'} or part == '.env' or part.startswith('.env.') for part in parts)

    def _safe_link(self, path, root):
        target = os.readlink(path)
        try:
            resolved = path.resolve(strict=True)
            relative = resolved.relative_to(root.resolve())
        except (ValueError, OSError, RuntimeError):
            raise InstallationError('resource_unsafe_path') from None
        if Path(target).is_absolute() or self._protected(relative):
            raise InstallationError('resource_unsafe_path')
        return target

    def _digest(self, directory):
        digest = hashlib.sha256()
        count = total = 0
        for path in sorted(directory.rglob('*')):
            mode = path.lstat().st_mode
            count += 1
            if count > self.max_files:
                raise InstallationError('resource_package_limit')
            if stat.S_ISLNK(mode):
                digest.update(canonical([path.relative_to(directory).as_posix(), 'link', self._safe_link(path, directory)]).encode())
                digest.update(b'\0')
                continue
            if stat.S_ISDIR(mode):
                continue
            if not stat.S_ISREG(mode) or self._protected(path.relative_to(directory)):
                raise InstallationError('resource_unsafe_path')
            digest.update(canonical([path.relative_to(directory).as_posix(), bool(mode & 0o111), path.stat().st_size]).encode())
            digest.update(b'\0')
            with path.open('rb') as reader:
                while chunk := reader.read(1024 * 1024):
                    total += len(chunk)
                    if count > self.max_files or total > self.max_bytes:
                        raise InstallationError('resource_package_limit')
                    digest.update(chunk)
            digest.update(b'\0')
        return 'sha256:' + digest.hexdigest()

    def _dependencies(self, package, request):
        declared = bool(request.dependencies)
        pinned = True
        exact = r'[A-Za-z0-9_.\[\],-]+==[A-Za-z0-9_.+!-]+(?:\s+--hash=sha256:[a-f0-9]{64})*'
        pinned = all(re.fullmatch(exact, pin) for pin in request.dependencies)
        for path in package.rglob('*'):
            if path.name in {'requirements.txt', 'Pipfile', 'environment.yml', 'environment.yaml'} and path.is_file():
                lines = [line.strip() for line in self._declaration(path).splitlines() if line.strip() and not line.lstrip().startswith('#')]
                declared = declared or bool(lines)
                pinned = pinned and (not lines or path.name == 'requirements.txt' and all(re.fullmatch(exact, line) for line in lines))
            elif path.name == 'package.json' and path.is_file():
                body = json.loads(self._declaration(path))
                dependencies = any(body.get(key) for key in ('dependencies', 'devDependencies', 'optionalDependencies', 'peerDependencies'))
                declared = declared or dependencies
                pinned = pinned and (not dependencies or any((path.parent / name).is_file() for name in ('package-lock.json', 'npm-shrinkwrap.json')))
            elif path.name == 'pyproject.toml' and path.is_file():
                body = tomllib.loads(self._declaration(path))
                requirements = body.get('project', {}).get('dependencies', []) + body.get('build-system', {}).get('requires', [])
                dependencies = bool(requirements) or bool(body.get('tool', {}).get('poetry', {}).get('dependencies'))
                declared = declared or dependencies
                locked = any((path.parent / name).is_file() for name in ('uv.lock', 'poetry.lock'))
                pinned = pinned and (not dependencies or locked or bool(requirements) and all(re.fullmatch(exact, pin) for pin in requirements))
        if declared:
            if self.install_dependencies is None:
                raise InstallationError('resource_dependencies_unsupported')
            if not pinned:
                raise InstallationError('resource_dependencies_unpinned')
            self.check_network(request.source)
            self.install_dependencies(package, request.dependencies)

    @staticmethod
    def _declaration(path):
        from .application_capacity import current_capacity
        limit = current_capacity().values['control_document_bytes']
        with path.open('rb') as reader:
            data = reader.read(limit + 1)
        if len(data) > limit:
            raise InstallationError('resource_declaration_limit')
        return data.decode('utf-8')

    def _package(self, request, stage, *, prebuilt=None):
        acquired = Path(prebuilt) if prebuilt is not None else self._acquire(request, stage)
        package = stage / 'package'
        self._snapshot(acquired, package)
        if prebuilt is None:
            self._dependencies(package, request)
        else:
            from .managed_resource_dependencies import dependency_environment, runtime_compatibility, RECEIPT
            if not (package / RECEIPT).exists():
                # Validate declarations without granting a network installer.
                verifier = ManagedResourceInstaller(self.store, check_network=lambda source:None)
                verifier._dependencies(package, request)
            dependency_environment(package, runtime_compatibility())
        before = self._digest(package)
        if request.kind == 'skill':
            if self.verify_skill is None:
                raise InstallationError('resource_skill_verifier_required')
            publication = self._skills(self.verify_skill(package, request.runtime), package)
        else:
            if self.probe_local is None:
                raise InstallationError('resource_local_probe_required')
            if not request.runtime.entrypoint or not (package / request.runtime.entrypoint).is_file():
                raise InstallationError('resource_entrypoint_missing')
            publication = {'catalog': self._catalog(self.probe_local(package, request.runtime))}
        if self._digest(package) != before:
            raise InstallationError('resource_package_changed_during_verification')
        digest = content_digest({'package': before, 'runtime': asdict(request.runtime), **publication})
        destination = self.store.root / 'packages' / before.split(':')[1]
        if destination.exists():
            if self._digest(destination) != before:
                raise InstallationError('resource_package_corrupt')
        else:
            try:
                package.rename(destination)
            except OSError:
                if not destination.is_dir() or self._digest(destination) != before:
                    raise InstallationError('resource_package_publication_failed') from None
            for path in destination.rglob('*'):
                if not path.is_symlink():
                    path.chmod(0o555 if path.is_dir() or path.stat().st_mode & 0o111 else 0o444)
            destination.chmod(0o555)
        self._publish(digest, publication)
        return VerifiedResource(request.kind, request.source, digest, destination.relative_to(self.store.root).as_posix(), request.runtime)

    @staticmethod
    def _skills(receipt, package):
        if not isinstance(receipt, dict) or not isinstance(receipt.get('skills'), list) or not receipt['skills']:
            raise InstallationError('resource_skill_load_failed')
        skills = []
        for skill in receipt['skills']:
            if not isinstance(skill, dict):
                raise InstallationError('resource_skill_load_failed')
            path = skill.get('path', skill.get('filePath'))
            relative_path(path)
            if not (package / path).is_file() or not isinstance(skill.get('name'), str) or not skill['name']:
                raise InstallationError('resource_skill_load_failed')
            description = skill.get('description', '')
            if not isinstance(description, str):
                raise InstallationError('resource_skill_load_failed')
            skills.append({'path': path, 'name': skill['name'], 'description': description})
        return {'skills': skills}

    @staticmethod
    def _catalog(value):
        if not isinstance(value, dict) or not isinstance(value.get('tools'), list) or not isinstance(value.get('instructions'), str) or not isinstance(value.get('server_info'), dict) or not re.fullmatch(r'sha256:[a-f0-9]{64}', value.get('revision', '')):
            raise InstallationError('resource_mcp_discovery_failed')
        for tool in value['tools']:
            if not isinstance(tool, dict) or not isinstance(tool.get('name'), str) or not isinstance(tool.get('inputSchema'), dict):
                raise InstallationError('resource_mcp_discovery_failed')
        return json.loads(canonical(value))

    def _remote(self, request):
        self.check_network(request.source)
        if self.probe_remote is None:
            raise InstallationError('resource_remote_probe_required')
        catalog = self._catalog(self.probe_remote(request.source, request.runtime))
        if request.source.revision.startswith('sha256:') and request.source.revision != catalog['revision']:
            raise InstallationError('resource_revision_mismatch')
        source = SourceIdentity(request.source.locator, catalog['revision'])
        publication = {'catalog': catalog}
        digest = content_digest({'source': asdict(source), 'runtime': asdict(request.runtime), **publication})
        self._publish(digest, publication)
        return VerifiedResource('mcp_remote', source, digest, '', request.runtime)

    def _publish(self, digest, publication):
        directory = self.store.root / 'publications'
        directory.mkdir(exist_ok=True)
        target = directory / (digest.split(':')[1] + '.json')
        data = canonical(publication)
        descriptor, name = tempfile.mkstemp(dir=directory)
        temporary = Path(name)
        try:
            with os.fdopen(descriptor, 'w') as writer:
                writer.write(data)
                writer.flush()
                os.fsync(writer.fileno())
            temporary.chmod(0o444)
            try:
                os.link(temporary, target)
            except FileExistsError:
                if target.read_text() != data:
                    raise InstallationError('resource_publication_conflict')
        finally:
            temporary.unlink()

    def publication(self, digest):
        if not isinstance(digest, str) or not re.fullmatch(r'sha256:[a-f0-9]{64}', digest):
            raise ValueError('invalid_resource_digest')
        return json.loads((self.store.root / 'publications' / (digest.split(':')[1] + '.json')).read_text())
