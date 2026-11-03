import copy
import json

import pytest

from capstone_agent.application_capacity import _profile
from capstone_agent.capacity_contract import (
    capacity_contract, capacity_model_guidance, load_capacity_policy,
)


def test_contract_covers_profile_once_without_numeric_defaults():
    profile = _profile()
    policy = load_capacity_policy()
    members = [member for group in policy['groups'] for member in group['members']]
    assert len(members) == len(set(members))
    assert set(members) == set(profile.values) == set(policy['units'])
    assert not any(type(value) is int for group in policy['groups'] for value in group.values())
    contract = capacity_contract(profile)
    assert contract['profile_fingerprint'] == profile.fingerprint
    for name, detail in contract['dimensions'].items():
        assert detail['effective'] == profile.values[name]
        for key in ('unit', 'description', 'category', 'scope', 'protected_resource',
                    'anomaly', 'recovery', 'enforcement'):
            assert detail[key]
        assert detail['basis'] == 'default_design_bound'
        assert detail['review_needed'] is True


def test_override_changes_effective_contract_and_guidance():
    baseline = _profile()
    override = _profile({'tool_search_page_items': 17, 'execution_seconds': 1901})
    contract = capacity_contract(override)
    assert contract['profile_fingerprint'] != baseline.fingerprint
    assert contract['dimensions']['tool_search_page_items']['effective'] == 17
    assert 'tool_search_page_items=17 items' in capacity_model_guidance(override)
    assert 'execution_seconds=1901 seconds' in capacity_model_guidance(override)


def test_current_profile_is_resolved_each_time(monkeypatch):
    from capstone_agent import capacity_contract as module
    first = _profile({'execution_seconds': 1902})
    second = _profile({'execution_seconds': 1903})
    monkeypatch.setattr(module, 'current_capacity', lambda: first)
    assert module.capacity_contract()['dimensions']['execution_seconds']['effective'] == 1902
    monkeypatch.setattr(module, 'current_capacity', lambda: second)
    assert module.capacity_contract()['dimensions']['execution_seconds']['effective'] == 1903
    assert 'execution_seconds=1903 seconds' in module.capacity_model_guidance()


@pytest.mark.parametrize('damage', ['duplicate', 'missing', 'unknown', 'schema', 'metadata', 'unit'])
def test_invalid_metadata_fails_closed(damage):
    policy = copy.deepcopy(load_capacity_policy())
    if damage == 'duplicate':
        policy['groups'][0]['members'].append(policy['groups'][0]['members'][0])
    elif damage == 'missing':
        policy['groups'][0]['members'].pop()
    elif damage == 'unknown':
        policy['groups'][0]['members'].append('unregistered_capacity')
    elif damage == 'schema':
        policy['schema'] = 'unsupported'
    elif damage == 'metadata':
        del policy['groups'][0]['anomaly']
    else:
        policy['units'].pop(next(iter(policy['units'])))
    with pytest.raises(ValueError):
        capacity_contract(_profile(), policy=policy)


def test_guidance_has_actionable_limits_without_housekeeping():
    guidance = capacity_model_guidance(_profile())
    assert 'Independent requests queue' in guidance
    assert 'not a total-call or total-round ceiling' in guidance
    assert 'page cursors' in guidance
    assert 'storage quotas are separate' in guidance
    assert 'upload_file_bytes=' in guidance
    assert 'model_context_tokens=' in guidance
    assert 'research_round_count=' in guidance
    for name, detail in capacity_contract(_profile())['dimensions'].items():
        if detail['model_visible']:
            assert f'{name}={detail["effective"]} {detail["unit"]}' in guidance
    for name in ('thread_stream_count', 'http_dns_workers', 'native_server_connections',
                 'ui_reconnect_base_ms', 'native_http_wait_ms'):
        assert name not in guidance
    assert len(guidance) < 6500


def test_selected_context_overrides_application_fallback():
    context = {'context_window_tokens': 262144, 'max_output_tokens': 32768,
               'compaction_reserve_tokens': 65536, 'compaction_keep_recent_tokens': 16384}
    contract = capacity_contract(_profile(), context_policy=context)
    assert contract['dimensions']['model_context_tokens']['effective'] == 262144
    assert contract['dimensions']['model_output_tokens']['effective'] == 32768
    assert contract['dimensions']['model_context_tokens']['source'] == 'selected_model_context_policy'
    assert contract['model_context']['compression_threshold_tokens'] == 196608
    guidance = capacity_model_guidance(_profile(), context_policy=context)
    assert 'model_context_tokens=262144 tokens' in guidance
    assert 'model_context_tokens=131072' not in guidance
    assert '196608 tokens' in guidance
    with pytest.raises(ValueError):
        capacity_contract(_profile(), context_policy={**context, 'max_output_tokens': 999999})


def test_explicit_policy_path_and_schema(tmp_path):
    path = tmp_path / 'policy.json'
    path.write_text(json.dumps(load_capacity_policy()))
    assert load_capacity_policy(path)['schema'] == 'capstone-capacity-policy/1'
    path.write_text('{"schema":"unknown"}')
    with pytest.raises(ValueError, match='schema'):
        load_capacity_policy(path)
