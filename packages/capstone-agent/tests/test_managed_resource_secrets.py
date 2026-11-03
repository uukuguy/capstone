import json
import os

import pytest

from capstone_agent.managed_resource_secrets import ProtectedResourceBindings, ResourceBindingError


SCOPE = dict(workspace='workspace', resource_id='server', source_locator='https://example.org/mcp', kind='mcp_remote')


def protected(path, content):
    path.write_text(content)
    path.chmod(0o600)
    return path


def configuration(tmp_path, *, kind='mcp_remote', headers=None, environment=None):
    secret = protected(tmp_path / 'secret', 'private-value')
    binding = {**SCOPE, 'kind': kind, 'headers': {'Authorization': str(secret)} if headers is None and kind == 'mcp_remote' else headers or {},
               'environment': environment or {}}
    path = protected(tmp_path / 'bindings.json', json.dumps({'schema': 'capstone-managed-resource-bindings/1',
                     'bindings': {'secret:credential': binding}}))
    return path, secret, binding


def resolve(path, **scope):
    return ProtectedResourceBindings(path).resolve(('secret:credential',), **{**SCOPE, **scope})


def test_empty_refs_need_no_configuration():
    assert ProtectedResourceBindings().resolve((), **SCOPE) == {'headers': {}, 'environment': {}}


def test_remote_binding_resolves_only_exact_scope_and_current_value(tmp_path):
    path, secret, _ = configuration(tmp_path)
    assert resolve(path) == {'headers': {'Authorization': 'private-value'}, 'environment': {}}
    secret.write_text('rotated-value')
    assert resolve(path)['headers']['Authorization'] == 'rotated-value'


@pytest.mark.parametrize('scope', [dict(workspace='other'), dict(resource_id='other'),
                                  dict(source_locator='https://other.org/mcp'), dict(kind='mcp_local')])
def test_scope_mismatch_denies(tmp_path, scope):
    path, _, _ = configuration(tmp_path)
    with pytest.raises(ResourceBindingError, match='scope'):
        resolve(path, **scope)


def test_missing_configuration_and_reference_deny(tmp_path):
    with pytest.raises(ResourceBindingError):
        resolve(None)
    path, _, _ = configuration(tmp_path)
    with pytest.raises(ResourceBindingError):
        ProtectedResourceBindings(path).resolve(('secret:unknown',), **SCOPE)


@pytest.mark.parametrize('target', ['bindings.json', 'secret'])
def test_permissions_are_protected_for_both_files(tmp_path, target):
    path, _, _ = configuration(tmp_path)
    (tmp_path / target).chmod(0o640)
    with pytest.raises(ResourceBindingError, match='file'):
        resolve(path)


@pytest.mark.parametrize('target', ['bindings.json', 'secret'])
def test_symlink_files_deny(tmp_path, target):
    path, _, _ = configuration(tmp_path)
    original = tmp_path / target
    moved = tmp_path / (target + '.actual')
    original.rename(moved)
    original.symlink_to(moved)
    with pytest.raises(ResourceBindingError):
        resolve(path)


def test_symlink_parent_denies(tmp_path):
    real = tmp_path / 'real'
    real.mkdir()
    path, _, _ = configuration(real)
    link = tmp_path / 'linked'
    link.symlink_to(real, target_is_directory=True)
    with pytest.raises(ResourceBindingError):
        resolve(link / path.name)


@pytest.mark.parametrize('value', ['private-value\nInjected: yes', 'private-value\r', '\x00private-value'])
def test_header_formatting_error_never_exposes_value(tmp_path, value):
    path, secret, _ = configuration(tmp_path)
    secret.write_text(value)
    with pytest.raises(ResourceBindingError) as caught:
        resolve(path)
    assert 'private-value' not in str(caught.value)
    assert str(secret) not in str(caught.value)


@pytest.mark.parametrize('name', ['PATH', 'PYTHONPATH', 'HOME', 'TMPDIR', 'NODE_OPTIONS',
                                 'LD_PRELOAD', 'PYTHONINSPECT', 'lowercase', 'BAD=NAME'])
def test_local_environment_control_variables_deny(tmp_path, name):
    path, _, _ = configuration(tmp_path, kind='mcp_local', environment={name: str(tmp_path / 'secret')})
    with pytest.raises(ResourceBindingError):
        resolve(path, kind='mcp_local')


def test_local_environment_and_remote_headers_are_separate(tmp_path):
    path, _, _ = configuration(tmp_path, kind='mcp_local', environment={'SERVICE_TOKEN': str(tmp_path / 'secret')})
    assert resolve(path, kind='mcp_local') == {'environment': {'SERVICE_TOKEN': 'private-value'}, 'headers': {}}
    path, _, _ = configuration(tmp_path, environment={'SERVICE_TOKEN': str(tmp_path / 'secret')})
    with pytest.raises(ResourceBindingError):
        resolve(path)


def test_size_limits_and_non_absolute_file_values_deny(tmp_path):
    path, secret, binding = configuration(tmp_path)
    secret.write_bytes(b'x' * (65536 + 1))
    with pytest.raises(ResourceBindingError):
        resolve(path)
    binding['headers']['Authorization'] = 'secret'
    path.write_text(json.dumps({'schema': 'capstone-managed-resource-bindings/1', 'bindings': {'secret:credential': binding}}))
    with pytest.raises(ResourceBindingError):
        resolve(path)


def test_owner_must_match_current_effective_uid(tmp_path, monkeypatch):
    path, _, _ = configuration(tmp_path)
    monkeypatch.setattr(os, 'geteuid', lambda: path.stat().st_uid + 1)
    with pytest.raises(ResourceBindingError):
        resolve(path)


def test_duplicate_and_unknown_schema_fields_deny(tmp_path):
    path, _, _ = configuration(tmp_path)
    path.write_text('{"schema":"capstone-managed-resource-bindings/1","bindings":{},"bindings":{}}')
    with pytest.raises(ResourceBindingError):
        resolve(path)
    path.write_text('{"schema":"unknown","bindings":{}}')
    with pytest.raises(ResourceBindingError):
        resolve(path)


def test_conflicting_header_names_are_case_insensitive(tmp_path):
    path, secret, binding = configuration(tmp_path)
    binding['headers']['authorization'] = str(secret)
    path.write_text(json.dumps({'schema': 'capstone-managed-resource-bindings/1',
                               'bindings': {'secret:credential': binding}}))
    with pytest.raises(ResourceBindingError, match='conflict'):
        resolve(path)


def test_oversized_configuration_is_not_parsed(tmp_path):
    path = protected(tmp_path / 'bindings.json', ' ' * 65537)
    with pytest.raises(ResourceBindingError, match='file_unavailable'):
        resolve(path)
