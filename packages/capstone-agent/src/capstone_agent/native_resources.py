"""Host-owned role profiles and immutable accepted native input snapshots."""
from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

from .runtime_resources import ResolvedResourceProfile, content_hash, resolve_resource_profile, safe_path, _tree_identity, _read_settings
from .resource_installation import inspect_installation, verify_source_tree


def native_resource_root(path: Path, boundary: Path) -> Path:
    """A declared directory, or a declared file's finite sibling package."""
    root = path if path.is_dir() else path.parent
    if not root.resolve().is_relative_to(boundary.resolve()):
        raise ValueError('native resource escapes its declared root')
    files = list(root.rglob('*'))
    if root.is_symlink() or any(file.is_symlink() for file in files):
        raise ValueError('native resource contains a symbolic link')
    if any(file.name in {'auth.json', 'models.json', '.env'} for file in files):
        raise ValueError('native resource contains protected transport state')
    patterns = (r'''\b(?:import|export)\s+[^;]*?\bfrom\s*["']([^"']+)["']''',
                r'''\bimport\s*["']([^"']+)["']''',
                r'''\b(?:import|require)\s*\(\s*["']([^"']+)["']''',
                r'''\bnew\s+URL\s*\(\s*["']([^"']+)["']\s*,\s*import\.meta\.url''')
    for file in files:
        if file.is_file() and file.suffix in {'.js', '.mjs', '.cjs', '.ts', '.tsx'}:
            body = file.read_text()
            for reference in (item for pattern in patterns for item in re.findall(pattern, body)):
                if (reference.startswith(('/', 'file:', 'http:', 'https:')) or
                        reference.startswith('.') and not (file.parent / reference).resolve().is_relative_to(root.resolve())):
                    raise ValueError('native resource import escapes its declared root')
    return root


def _remove_unpublished(path: Path) -> None:
    """Remove only an unpublished task-owned stage, including read-only copies."""
    for item in [path, *path.rglob('*')]:
        if not item.is_symlink():
            item.chmod(0o700 if item.is_dir() else 0o600)
    shutil.rmtree(path)


def validate_native_input(task_input, profile: ResolvedResourceProfile):
    return _input_name(task_input, profile.to_document(), json.loads(profile.configuration_json))


def _input_name(task_input, profile, manifest):
    if task_input['kind'] == 'text':
        return None
    selected = next((item for item in profile['resources'] if item['id'] == task_input['skill_id']), None)
    if (selected is None or selected['kind'] != 'skill' or not selected['enabled'] or not selected['ready']
            or selected['version'] != task_input['skill_version']):
        raise ValueError('accepted native skill is unavailable or changed')
    declaration = next((item for item in manifest.get('resources', []) if item['id'] == selected['id']), None)
    if not declaration or not isinstance(declaration.get('native_name'), str):
        raise ValueError('accepted native skill declaration is missing')
    return declaration['native_name']


class NativeResourceStore:
    """Retain settings bytes and installation identity across new acceptance."""
    def __init__(self, config_root: Path, root: Path):
        self.config_root, self.root = config_root.resolve(), root
        self.managed = self.config_root.parent.parent / '.grid-agent/runtime/agent-resources'
        root.mkdir(parents=True, exist_ok=True)
        self.profiles = {}
        self._installations = {}
        for role in ('direct_pi', 'delegated_pi'):
            profile = resolve_resource_profile(config_root, role)
            roots = []
            for path in profile.native_settings_paths:
                boundary = self.config_root if path.is_relative_to(self.config_root) else safe_path(self.managed, profile.installation_id or '')
                native_resource_root(path.parent, boundary)
                values = json.loads(path.read_text())
                resources = {}
                for key in ('skills', 'extensions', 'packages', 'prompts', 'themes'):
                    entries = values.get(key, [])
                    if not isinstance(entries, list):
                        raise ValueError('native resource settings must be arrays')
                    if key != 'packages' and (path.parent / key).is_dir():
                        entries = [*entries, key]
                    resources[key] = []
                    for entry in entries:
                        selected = safe_path(boundary, entry if isinstance(entry, str) else entry['source'], base=path.parent)
                        resources[key].append(_tree_identity(native_resource_root(selected, boundary), boundary)
                                              if selected.exists() else None)
                roots.append({'source': _tree_identity(path.parent, boundary), 'resources': resources})
            profile = replace(profile, revision=content_hash({'resolved': profile.revision, 'native_roots': roots}))
            self._resolved = getattr(self, '_resolved', {})
            self._resolved[role] = profile
            if profile.prepared_descriptor_json:
                descriptor = json.loads(profile.prepared_descriptor_json)
                self._installations[content_hash(descriptor)] = descriptor
            profile = replace(profile, profile_id=role,
                resources=tuple(replace(item, ready=False,
                    reason=item.reason or 'native publication is not verified') for item in profile.resources))
            profile = replace(profile, revision=content_hash({'resolved': profile.revision, 'profile': profile.to_document()}))
            self.profiles[role] = self._retain(profile)

    def _retain(self, profile, load_receipt=None, source_state=None):
        destination = self.root / profile.revision
        if destination.is_symlink():
            raise ValueError('accepted native snapshot contains a symbolic link')
        if destination.exists():
            if (destination / 'accepted.json').is_file():
                self.accepted(profile.role, profile.revision)
                return profile
            if not destination.is_dir():
                raise ValueError('unpublished native snapshot is not a directory')
            _remove_unpublished(destination)
        staging = Path(tempfile.mkdtemp(prefix='.pending-' + profile.revision + '-', dir=self.root))
        try:
            settings = []
            for index, path in enumerate(profile.native_settings_paths):
                target = staging / f'native-{index}'
                if source_state is not None:
                    shutil.copytree(Path(source_state['settings'][index]).parent, target)
                    settings.append(str(destination / f'native-{index}' / 'settings.json'))
                    continue
                # Copy settings together with their native local resources. Managed
                # source references stay in the immutable retained install.
                boundary = self.config_root if path.is_relative_to(self.config_root) else safe_path(self.managed, profile.installation_id)
                target.mkdir()
                shutil.copytree(path.parent, target / 'source')
                values = json.loads(path.read_text())
                for key in ('skills', 'extensions', 'packages', 'prompts', 'themes'):
                    entries = values.get(key, [])
                    rebased = []
                    if key != 'packages' and (path.parent / key).is_dir():
                        entries = [*entries, key]
                    for number, entry in enumerate(entries):
                        source = entry if isinstance(entry, str) else entry['source']
                        resolved = safe_path(boundary, source, base=path.parent)
                        if not resolved.exists():
                            continue
                        # Settings-local resources are frozen. Managed external
                        # source bytes are checked by the retained descriptor.
                        chosen = target / f'{key}-{number}'
                        source_root = native_resource_root(resolved, boundary)
                        shutil.copytree(source_root, chosen)
                        selected = str(chosen.relative_to(target) / resolved.relative_to(source_root))
                        rebased.append(selected if isinstance(entry, str) else {**entry, 'source': selected})
                    values[key] = rebased
                (target / 'settings.json').write_text(json.dumps(values))
                settings.append(str(destination / f'native-{index}' / 'settings.json'))
            state = {'profile': profile.to_document(), 'configuration_json': profile.configuration_json,
                'installation_id': profile.installation_id, 'descriptor': json.loads(profile.prepared_descriptor_json) if profile.prepared_descriptor_json else None,
                'settings': settings, 'role': profile.role, 'load_receipt': load_receipt}
            state['tree_identity'] = _tree_identity(staging, staging)
            (staging / 'accepted.json').write_text(json.dumps(state))
            for path in staging.rglob('*'):
                path.chmod(0o555 if path.is_dir() else 0o444)
            os.replace(staging, destination)
            destination.chmod(0o555)
        except BaseException:
            if staging.exists():
                _remove_unpublished(staging)
            raise
        return profile

    def confirm_loaded(self, role, inventory):
        """Bind host-checked native publication to the accepted resource catalog."""
        original = self._resolved[role]
        state = self.accepted(role, self.profiles[role].revision)
        expected_skills = {}
        for name in state['settings']:
            _, _, paths = _read_settings(Path(name), self.root)
            expected_skills.update({key: hashlib.sha256((path / 'SKILL.md').read_bytes()).hexdigest()
                                    for key, path in paths.items()})
        declarations = json.loads(original.configuration_json)['resources']
        installed = {item.resource_id for item in original.resources if item.enabled and item.installed}
        allowed = {item['native_name'] for item in declarations if item['kind'] == 'skill'
                   and item['id'] in installed}
        expected_skills = {key: value for key, value in expected_skills.items() if key in allowed}
        actual_skills = {item['name']: item['sha256'] for item in inventory.get('skills', [])}
        if len(actual_skills) != len(inventory.get('skills', [])) or actual_skills != expected_skills:
            raise ValueError('native skill publication changed')
        descriptor = state['descriptor'] if any(item.kind == 'mcp' and item.enabled and item.installed
                                                for item in original.resources) else None
        if descriptor is not None and (inventory.get('tool_schema_hashes') != descriptor['tool_schema_hashes']
                or not set(descriptor['tool_schemas']) <= set(inventory['tools'])):
            raise ValueError('native MCP publication changed')
        tools = set(inventory['tools'])
        resources = []
        for item in original.resources:
            ready = item.enabled and item.installed and item.loaded_identity is not None and set(item.required_tools) <= tools
            # Only fixed managed adapters are supplied by this native executor.
            declaration = next(d for d in declarations if d['id'] == item.resource_id)
            if declaration.get('adapter') not in {None, 'powerskills-pandapower/1', 'powermcp-pandapower/1'}:
                ready = False
            resources.append(replace(item, ready=ready, reason=None if ready else item.reason or 'native publication is unavailable'))
        receipt = {'schema': 'capstone-resource-adapter-check/1', 'status': 'passed', 'role': role,
                   'adapter_id': 'native-pi-resources/1', 'source_sha256': inventory.get('adapter_sha256'),
                   'published_tool_ids': sorted(tools), 'skills': actual_skills,
                   'tool_schema_hashes': inventory.get('tool_schema_hashes', {}),
                   'descriptor_sha256': content_hash(descriptor) if descriptor else None}
        profile = replace(original, profile_id=role, resources=tuple(resources))
        profile = replace(profile, revision=content_hash({'resolved': original.revision, 'receipt': receipt,
                                                        'resources': profile.to_document()['resources']}))
        self.profiles[role] = self._retain(profile, receipt, state)
        return profile

    def accepted(self, role, revision):
        state = json.loads((safe_path(self.root, revision) / 'accepted.json').read_text())
        if state['role'] != role or state['profile']['revision'] != revision:
            raise ValueError('accepted role profile changed')
        current = json.loads((self.config_root / 'agent-resources.json').read_text())
        available = {item['id'] for item in current['resources'] if item['enabled'] and role in item['roles']}
        if any(item['enabled'] and item['id'] not in available for item in state['profile']['resources']):
            raise ValueError('accepted native resource was revoked')
        base = safe_path(self.root, revision)
        if any(path.is_symlink() for path in base.rglob('*')):
            raise ValueError('accepted native settings changed')
        actual = {str(path.relative_to(base)): hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in sorted(base.rglob('*')) if path.is_file() and path.name != 'accepted.json'}
        if content_hash(actual) != state['tree_identity']:
            raise ValueError('accepted native settings changed')
        if state['descriptor'] is not None:
            expected = content_hash(state['descriptor'])
            install = safe_path(self.managed, state['installation_id'])
            # Runtime imports were checked before publication. Installed inputs
            # are root-owned and read-only in the executor. Check pinned bytes on
            # every task; inspect an uncached historical runtime once.
            if expected not in self._installations:
                descriptor, reason = inspect_installation(self.managed, install_id=state['installation_id'],
                                                          expected_descriptor_sha256=expected)
                if descriptor is None:
                    raise ValueError(reason)
                self._installations[expected] = descriptor
            descriptor = self._installations[expected]
            if (content_hash(json.loads((install / 'prepared-mcp.json').read_text())) != expected
                    or hashlib.sha256((install / 'descriptor-schema.json').read_bytes()).hexdigest() != descriptor['descriptor_schema_sha256']
                    or content_hash(json.loads((install / 'installation-lock.json').read_text())) != descriptor['lock_sha256']
                    or hashlib.sha256((install / 'smoke.json').read_bytes()).hexdigest() != descriptor['smoke_sha256']
                    or json.loads((install / 'dependencies.json').read_text()) != descriptor['dependencies']
                    or hashlib.sha256((install / 'venv/bin/python').resolve().read_bytes()).hexdigest() != descriptor['runtime_identity']['base_interpreter_sha256']):
                raise ValueError('accepted managed resource identity changed')
            verify_source_tree(install, descriptor['source_files'])
        return state

    def task_config(self, role, revision, *, workspace, request, inventory_only=False):
        state = self.accepted(role, revision)
        settings = {}
        arrays = {key: [] for key in ('skills', 'extensions', 'packages', 'prompts', 'themes')}
        for name in state['settings']:
            path = Path(name)
            values = json.loads(path.read_text())
            settings.update({key: value for key, value in values.items() if key not in arrays})
            def paths(key):
                return [str(path.parent / entry) if isinstance(entry, str)
                        else {**entry, 'source': str(path.parent / entry['source'])}
                        for entry in values.get(key, [])]
            for key in arrays:
                arrays[key].extend(paths(key))
        settings.update(arrays)
        descriptor = state['descriptor']
        # Resources absent from this role cannot activate a prepared MCP server.
        if not any(item['kind'] == 'mcp' and item['enabled'] and item['installed'] and (inventory_only or item['ready'])
                   for item in state['profile']['resources']):
            descriptor = None
        active = {item['id'] for item in state['profile']['resources']
                  if item['enabled'] and item['installed'] and (inventory_only or item['ready'])}
        allowed = [item['native_name'] for item in json.loads(state['configuration_json'])['resources']
                   if item['kind'] == 'skill' and item['id'] in active]
        context_files = []
        system_prompt, append_system_prompt = None, []
        for name in state['settings']:
            base = Path(name).parent / 'source'
            for context_name in ('AGENTS.override.md', 'AGENTS.md', 'AGENTS.MD', 'CLAUDE.md', 'CLAUDE.MD'):
                path = base / context_name
                if path.is_file():
                    context_files.append({'path': str(path), 'content': path.read_text()})
                    break
            if system_prompt is None and (base / 'SYSTEM.md').is_file():
                system_prompt = (base / 'SYSTEM.md').read_text()
            if (base / 'APPEND_SYSTEM.md').is_file():
                append_system_prompt.append((base / 'APPEND_SYSTEM.md').read_text())
        return {'profile': state['profile'], 'configuration': json.loads(state['configuration_json']),
                'allowedSkills': allowed, 'contextFiles': context_files,
                'systemPrompt': system_prompt, 'appendSystemPrompt': append_system_prompt,
                'skillName': _input_name(request.to_document().get('input', {'kind': 'text', 'text': request.instruction}),
                                         state['profile'], json.loads(state['configuration_json'])),
                'settings': settings, 'inputBoundary': str(self.root / revision),
                'mcp': ({'install': str(safe_path(self.managed, state['installation_id'])),
                    'workspace': str(workspace), 'descriptor': descriptor,
                    'descriptor_sha256': content_hash(descriptor), 'task_id': request.task_id,
                    'parent_attempt_id': request.parent_attempt_id} if descriptor else None)}

    def input_name(self, role, revision, task_input):
        state = self.accepted(role, revision)
        return _input_name(task_input, state['profile'], json.loads(state['configuration_json']))
