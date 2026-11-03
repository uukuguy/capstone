"""Small dependency adapter. Every command uses the trusted isolated runner.

The runner must copy successful isolated output back with trusted ownership when
``sync_output=True``. The installer verifies and freezes that output afterward.
Python transitive dependencies must be supplied as exact pins; source builds and
package scripts are never run. Unsupported declaration formats fail explicitly.
"""
import json
from pathlib import Path
import re
import sys
import platform
from urllib.parse import urlsplit

from .application_capacity import limits
from .managed_resource_installation import InstallationError


RECEIPT = '.managed-dependencies.json'
PYTHON_TARGET = '.managed-python'
PYTHON_REQUIREMENTS = '.managed-python-requirements.txt'
_DECLARATIONS = {'requirements.txt', 'package.json', 'package-lock.json', 'npm-shrinkwrap.json',
                 'pyproject.toml', 'uv.lock', 'poetry.lock', 'Pipfile', 'Pipfile.lock',
                 'environment.yml', 'environment.yaml', 'setup.py', 'setup.cfg'}
_SUPPORTED = {'requirements.txt', 'package.json', 'package-lock.json', 'npm-shrinkwrap.json'}


def runtime_compatibility():
    return {'python': platform.python_version(), 'platform': sys.platform, 'machine': platform.machine()}
_PIN = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]*(?:\[[A-Za-z0-9_,.-]+\])?'
                  r'==[A-Za-z0-9][A-Za-z0-9_.+!-]*(?:\s+--hash=sha256:[a-f0-9]{64})*')


def _read(path):
    with path.open('rb') as reader:
        data = reader.read(limits.control_document_bytes + 1)
    if len(data) > limits.control_document_bytes:
        raise InstallationError('resource_declaration_limit')
    return data.decode('utf-8')


def dependency_environment(package: Path, compatibility=None) -> dict[str, str]:
    """Use in the isolated local runtime; merge with its protected environment.

    Node resolves package-local node_modules from its entrypoint automatically.
    This does not install packages into a task's system Python environment.
    """
    package = Path(package)
    if not (package / RECEIPT).is_file():
        return {}
    receipt = json.loads(_read(package / RECEIPT))
    if receipt.get('schema') != 'capstone-managed-dependencies/1':
        raise InstallationError('resource_dependency_receipt_invalid')
    if compatibility is not None and receipt.get('compatibility') != compatibility:
        raise InstallationError('resource_dependency_runtime_incompatible')
    return {'PYTHONPATH': str(package / PYTHON_TARGET)} if receipt.get('python') else {}


class IsolatedDependencyInstaller:
    def __init__(self, runner, *, check_network, compatibility):
        if (not isinstance(compatibility, dict) or not {'python', 'platform', 'machine'} <= set(compatibility)
                or set(compatibility) - {'python', 'platform', 'machine', 'node'}
                or any(not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_.+-]{1,128}', value)
                       for value in compatibility.values())):
            raise ValueError('resource_dependency_compatibility_invalid')
        self.runner, self.check_network = runner, check_network
        self.compatibility = dict(compatibility)

    def __call__(self, package, explicit_pins=()):
        package = Path(package)
        reserved = {RECEIPT, PYTHON_TARGET, PYTHON_REQUIREMENTS, 'node_modules'}
        for path in package.rglob('*'):
            if path.name in reserved:
                raise InstallationError('resource_dependency_path_reserved')
            if path.name in _DECLARATIONS and (path.parent != package or path.name not in _SUPPORTED):
                raise InstallationError('resource_dependency_format_unsupported')
        if not isinstance(explicit_pins, (tuple, list)):
            raise InstallationError('resource_dependencies_unpinned')
        requirements = package / 'requirements.txt'
        pins = ([line.strip() for line in _read(requirements).splitlines()
                 if line.strip() and not line.lstrip().startswith('#')]
                if requirements.is_file() else []) + list(explicit_pins)
        if any(not isinstance(pin, str) or not _PIN.fullmatch(pin) for pin in pins):
            raise InstallationError('resource_dependencies_unpinned')
        pins = list(dict.fromkeys(pins))
        npm = self._npm(package)
        receipt = {'schema': 'capstone-managed-dependencies/1', 'compatibility': dict(self.compatibility)}
        if pins:
            self.check_network()
            (package / PYTHON_REQUIREMENTS).write_text('\n'.join(pins) + '\n', encoding='utf-8')
            self._run(('python3', '-m', 'pip', 'install', '--disable-pip-version-check',
                       '--no-input', '--no-compile', '--only-binary=:all:', '--no-deps',
                       '--target', PYTHON_TARGET, '--requirement', PYTHON_REQUIREMENTS), package)
            receipt['python'] = {'target': PYTHON_TARGET, 'requirements': PYTHON_REQUIREMENTS, 'pins': pins}
        if npm:
            self.check_network()
            self._run(('npm', 'ci', '--ignore-scripts', '--no-audit', '--no-fund'), package)
            receipt['npm'] = {'lockfile': npm, 'target': 'node_modules', 'scripts': False}
        # Only this final receipt signals completed dependency installation.
        (package / RECEIPT).write_text(json.dumps(receipt, sort_keys=True, indent=2) + '\n', encoding='utf-8')
        return receipt

    def _run(self, argv, package):
        try:
            self.runner(argv, package, (), sync_output=True)
        except InstallationError:
            raise
        except Exception:
            raise InstallationError('resource_dependency_install_failed') from None

    @staticmethod
    def _npm(package):
        manifest = package / 'package.json'
        locks = [name for name in ('npm-shrinkwrap.json', 'package-lock.json') if (package / name).is_file()]
        if not manifest.is_file():
            if locks:
                raise InstallationError('resource_dependency_manifest_missing')
            return None
        body = json.loads(_read(manifest))
        if not isinstance(body, dict) or body.get('workspaces'):
            raise InstallationError('resource_dependency_format_unsupported')
        declared = any(body.get(name) for name in ('dependencies', 'devDependencies', 'optionalDependencies', 'peerDependencies'))
        if not declared:
            return None
        if not locks:
            raise InstallationError('resource_dependencies_unpinned')
        lock = json.loads(_read(package / locks[0]))
        if not isinstance(lock, dict) or lock.get('lockfileVersion') not in (2, 3) or not isinstance(lock.get('packages'), dict):
            raise InstallationError('resource_dependency_lock_invalid')
        for item in lock['packages'].values():
            if not isinstance(item, dict) or item.get('link'):
                raise InstallationError('resource_dependency_format_unsupported')
            if 'resolved' in item:
                url = urlsplit(item['resolved'])
                if (url.scheme not in {'http', 'https'} or not url.hostname or url.username or url.password
                        or url.query or url.fragment or any(ord(c) < 33 for c in item['resolved'])):
                    raise InstallationError('resource_dependency_lock_invalid')
        return locks[0]
