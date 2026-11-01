import json
from pathlib import Path

import pytest

from capstone_agent.resource_permissions import (
    RESOURCE_ACTIONS,
    ResourcePermissionDenied,
    ResourcePermissions,
    ResourcePrincipal,
)


PRINCIPAL = ResourcePrincipal('operator', ())
DEFAULT_POLICY = Path(__file__).resolve().parents[3] / 'configs/runtime/resource-permissions.json'


def write_policy(tmp_path, rules):
    path = tmp_path / 'policy.json'
    path.write_text(json.dumps({'version': 1, 'profiles': {'test': {'rules': rules}}}))
    return path


def test_local_all_actions_and_intranet_use_only():
    local = ResourcePermissions(DEFAULT_POLICY, 'local')
    intranet = ResourcePermissions(DEFAULT_POLICY, 'intranet')
    assert local.allowed_actions(PRINCIPAL, 'workspace') == sorted(RESOURCE_ACTIONS)
    assert intranet.allowed_actions(PRINCIPAL, 'workspace') == ['resources.use']
    assert local.require(PRINCIPAL, 'workspace', 'resources.use') != intranet.require(PRINCIPAL, 'workspace', 'resources.use')
    for action in RESOURCE_ACTIONS - {'resources.use'}:
        with pytest.raises(ResourcePermissionDenied, match='resource_permission_denied'):
            intranet.require(PRINCIPAL, 'workspace', action)


def test_role_override_workspace_constraint_and_deny_precedence(tmp_path):
    path = write_policy(tmp_path, [
        {'effect': 'allow', 'actions': ['resources.use']},
        {'effect': 'allow', 'actions': ['resources.install'],
         'roles': ['admin'], 'workspaces': ['trusted']},
        {'effect': 'deny', 'actions': ['resources.install'], 'roles': ['suspended']},
    ])
    policy = ResourcePermissions(path, 'test')
    admin = ResourcePrincipal('admin-user', ('admin',))
    assert policy.require(admin, 'trusted', 'resources.install').startswith('sha256:')
    assert policy.allowed_actions(admin, 'other') == ['resources.use']
    assert policy.allowed_actions(PRINCIPAL, 'trusted') == ['resources.use']
    assert policy.allowed_actions(ResourcePrincipal('admin-user', ('admin', 'suspended')),
                                  'trusted') == ['resources.use']


def test_live_revocation_and_canonical_revision(tmp_path):
    rule = {'effect': 'allow', 'actions': ['resources.use']}
    path = write_policy(tmp_path, [rule])
    policy = ResourcePermissions(path, 'test')
    revision = policy.require(PRINCIPAL, 'w', 'resources.use')
    path.write_text(json.dumps(json.loads(path.read_text()), indent=4, sort_keys=True))
    assert policy.require(PRINCIPAL, 'w', 'resources.use') == revision
    write_policy(tmp_path, [])
    assert policy.allowed_actions(PRINCIPAL, 'w') == []
    with pytest.raises(ResourcePermissionDenied):
        policy.require(PRINCIPAL, 'w', 'resources.use')


@pytest.mark.parametrize('content', [None, '{', '{}',
    '{"version":1,"version":1,"profiles":{}}',
    '{"version":true,"profiles":{"test":{"rules":[]}}}',
])
def test_missing_or_invalid_policy_fails_closed(tmp_path, content):
    path = tmp_path / 'policy.json'
    if content is not None:
        path.write_text(content)
    policy = ResourcePermissions(path, 'test')
    assert policy.allowed_actions(PRINCIPAL, 'w') == []
    with pytest.raises(ResourcePermissionDenied) as error:
        policy.require(PRINCIPAL, 'w', 'resources.use')
    assert error.value.code == 'resource_policy_invalid'
    assert str(path) not in str(error.value)


@pytest.mark.parametrize('rule', [
    {'effect': 'allow', 'actions': ['*']},
    {'effect': 'allow', 'actions': ['resources.use'], 'role': ['admin']},
    {'effect': 'allow', 'actions': ['resources.use'], 'roles': 'admin'},
    {'effect': 'allow', 'actions': ['resources.use'], 'workspaces': []},
])
def test_invalid_rules_fail_closed(tmp_path, rule):
    policy = ResourcePermissions(write_policy(tmp_path, [rule]), 'test')
    assert policy.allowed_actions(PRINCIPAL, 'w') == []


def test_unknown_profile_and_action_fail_closed():
    with pytest.raises(ResourcePermissionDenied) as error:
        ResourcePermissions(DEFAULT_POLICY, 'unknown').require(PRINCIPAL, 'w', 'resources.use')
    assert error.value.code == 'resource_policy_invalid'
    with pytest.raises(ResourcePermissionDenied) as error:
        ResourcePermissions(DEFAULT_POLICY, 'local').require(PRINCIPAL, 'w', 'resources.delete')
    assert error.value.code == 'resource_action_unknown'


def test_principal_requires_backend_type():
    policy = ResourcePermissions(DEFAULT_POLICY, 'local')
    assert policy.allowed_actions({'subject': 'attacker', 'roles': ['admin']}, 'w') == []
