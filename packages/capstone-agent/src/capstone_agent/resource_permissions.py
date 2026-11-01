"""Deployment-selected resource policy. Callers must supply backend-authenticated roles.

This module does not authenticate requests. Never build ResourcePrincipal from
model output or from role fields in a public request. Each decision reads one
current policy snapshot; callers must recheck before publishing a change.
"""

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path


RESOURCE_ACTIONS = frozenset({
    'resources.install', 'resources.enable', 'resources.disable',
    'resources.update', 'resources.uninstall', 'resources.use',
    'resources.preinstall.manage',
})


@dataclass(frozen=True)
class ResourcePrincipal:
    subject: str
    roles: tuple[str, ...]


class ResourcePermissionDenied(PermissionError):
    """Safe error code suitable for HTTP and tool adapters; no policy data."""

    def __init__(self, code: str = 'resource_permission_denied') -> None:
        self.code = code
        super().__init__(code)


def _strings(value: object) -> bool:
    return (isinstance(value, list) and bool(value)
            and all(isinstance(item, str) and bool(item.strip()) for item in value))


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate policy key')
        result[key] = value
    return result


class ResourcePermissions:
    def __init__(self, path: Path, profile: str) -> None:
        self.path = Path(path)
        self.profile = profile

    def _load(self) -> tuple[list[dict], str]:
        try:
            policy = json.loads(self.path.read_text(encoding='utf-8'),
                                object_pairs_hook=_unique_object)
            if (not isinstance(policy, dict) or set(policy) != {'version', 'profiles'}
                    or type(policy['version']) is not int or policy['version'] != 1):
                raise ValueError('invalid policy')
            profiles = policy['profiles']
            if not isinstance(profiles, dict) or not profiles:
                raise ValueError('invalid profiles')
            for name, profile in profiles.items():
                if (not name.strip() or not isinstance(profile, dict)
                        or set(profile) != {'rules'} or not isinstance(profile['rules'], list)):
                    raise ValueError('invalid profile')
                for rule in profile['rules']:
                    if (not isinstance(rule, dict)
                            or not {'effect', 'actions'} <= set(rule)
                            or set(rule) - {'effect', 'actions', 'roles', 'workspaces'}
                            or rule['effect'] not in ('allow', 'deny')
                            or not _strings(rule['actions'])
                            or not set(rule['actions']) <= RESOURCE_ACTIONS):
                        raise ValueError('invalid rule')
                    for field in ('roles', 'workspaces'):
                        if field in rule and not _strings(rule[field]):
                            raise ValueError('invalid constraint')
            if not isinstance(self.profile, str) or self.profile not in profiles:
                raise ValueError('unknown profile')
            canonical = json.dumps(policy, sort_keys=True, separators=(',', ':'),
                                   ensure_ascii=True).encode('utf-8')
            return profiles[self.profile]['rules'], 'sha256:' + hashlib.sha256(canonical).hexdigest()
        except (OSError, UnicodeError, ValueError, TypeError, RecursionError):
            raise ResourcePermissionDenied('resource_policy_invalid') from None

    @staticmethod
    def _valid_context(principal: ResourcePrincipal, workspace: str) -> bool:
        return (isinstance(principal, ResourcePrincipal)
                and isinstance(principal.subject, str) and bool(principal.subject.strip())
                and isinstance(principal.roles, tuple)
                and all(isinstance(role, str) and bool(role.strip()) for role in principal.roles)
                and isinstance(workspace, str) and bool(workspace.strip()))

    @staticmethod
    def _allowed(rules: list[dict], principal: ResourcePrincipal,
                 workspace: str, action: str) -> bool:
        allowed = False
        for rule in rules:
            if action not in rule['actions']:
                continue
            if 'roles' in rule and not set(principal.roles).intersection(rule['roles']):
                continue
            if 'workspaces' in rule and workspace not in rule['workspaces']:
                continue
            if rule['effect'] == 'deny':
                return False
            allowed = True
        return allowed

    def require(self, principal: ResourcePrincipal, workspace: str, action: str) -> str:
        if not isinstance(action, str) or action not in RESOURCE_ACTIONS:
            raise ResourcePermissionDenied('resource_action_unknown')
        rules, revision = self._load()
        if (not self._valid_context(principal, workspace)
                or not self._allowed(rules, principal, workspace, action)):
            raise ResourcePermissionDenied()
        return revision

    def allowed_actions(self, principal: ResourcePrincipal, workspace: str) -> list[str]:
        try:
            rules, _ = self._load()
        except ResourcePermissionDenied:
            return []
        if not self._valid_context(principal, workspace):
            return []
        return [action for action in sorted(RESOURCE_ACTIONS)
                if self._allowed(rules, principal, workspace, action)]
