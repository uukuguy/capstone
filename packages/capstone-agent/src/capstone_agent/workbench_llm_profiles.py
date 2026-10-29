"""Application-owned model profiles; only public frozen identities cross tasks."""
import hashlib
import json
import os
from pathlib import Path


def _config_path():
    configured = os.environ.get('CAPSTONE_WORKBENCH_LLM_PROFILES')
    if configured:
        return Path(configured)
    for root in (Path('/opt/general'), *Path(__file__).resolve().parents):
        candidate = root / 'configs/runtime/workbench-llm-profiles.json'
        if candidate.is_file():
            return candidate
    raise ValueError('Workbench LLM profiles are not installed')


class ProfileRegistry:
    def __init__(self, path=None, *, environment=None):
        self.environment = dict(os.environ if environment is None else environment)
        self.document = json.loads((Path(path) if path else _config_path()).read_text())
        if self.document['schema'] != 'capstone-workbench-llm-profiles/1':
            raise ValueError('Invalid workbench LLM profile schema')
        preset = self.environment.get('CAPSTONE_WORKBENCH_PRESET', 'local')
        if preset not in self.document['defaults']:
            raise ValueError('Unknown workbench deployment preset')
        self.default = self.document['defaults'][preset]
        self.profiles = {p['id']: p for p in self.document['profiles']}

    def _resolved(self, profile_id):
        if profile_id not in self.profiles:
            raise ValueError('Unknown workbench LLM profile')
        p = self.profiles[profile_id]
        options = p.get('title_request_options', {})
        model = p.get('model') or self.environment.get(p.get('model_env', ''), '')
        url = p.get('base_url') or self.environment.get(p.get('base_url_env', ''), '')
        if p['provider'] == 'deepseek':
            url = 'https://api.deepseek.com/v1'
        key = self.environment.get(p.get('credential_env', ''), '')
        available = bool(model and url and (not p.get('credential_env') or key))
        execution = {key: value for key, value in p.items() if key not in {'label', 'icon', 'title_request_options'}}
        revision = hashlib.sha256(json.dumps({'profile': execution, 'model': model, 'base_url': url}, sort_keys=True).encode()).hexdigest()
        title_revision = hashlib.sha256(json.dumps(options, sort_keys=True).encode()).hexdigest()
        return {**p, 'model': model, 'base_url': url, 'key': key or 'internal', 'available': available, 'profile_revision': revision, 'title_request_revision': title_revision}

    def catalog(self):
        return {'default_profile_id': self.default, 'profiles': [{**{k: p[k] for k in ('id', 'label', 'model', 'available')}, 'icon': p.get('icon', 'server')}
                for p in (self._resolved(i) for i in self.profiles)]}

    def freeze(self, profile_id=None):
        p = self._resolved(profile_id or self.default)
        if not p['available']:
            raise ValueError('Workbench LLM profile is unavailable')
        return {'profile_id': p['id'], **{k: p[k] for k in ('provider', 'model', 'profile_revision')}}

    def resolve(self, selection):
        expected = self.freeze(selection.get('profile_id'))
        if selection != expected:
            # Accept previously issued whole-profile hashes only when they can
            # still be proven against this exact registered execution target.
            p = self.profiles[expected['profile_id']]
            resolved = self._resolved(expected['profile_id'])
            legacy = {hashlib.sha256(json.dumps({'profile': candidate, 'model': resolved['model'],
                'base_url': resolved['base_url']}, sort_keys=True).encode()).hexdigest()
                for candidate in (p, {k: v for k, v in p.items() if k != 'title_request_options'})}
            if ({**selection, 'profile_revision': expected['profile_revision']} != expected
                    or selection.get('profile_revision') not in legacy):
                raise ValueError('Frozen workbench LLM profile changed; resubmit the instruction')
        return self._resolved(expected['profile_id'])
