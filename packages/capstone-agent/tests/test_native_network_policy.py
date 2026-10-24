import subprocess

import pytest

from capstone_agent.native_network_policy import NativeNetworkPolicy, InternalEndpoint


def test_effective_prompt_preserves_task_source_limits_and_removes_legacy_blanket_ban():
    from capstone_agent.native_network_policy import execution_policy
    old = {'system_policy': 'Do the task. External lookup is disabled. '
           'Do not use shell commands or MCP tools to bypass that application restriction. Keep source evidence.',
           'external_lookup_enabled': False}
    updated = execution_policy(old, external_access=True)
    assert updated['external_lookup_enabled'] is True
    assert 'External lookup is disabled' not in updated['system_policy']
    assert 'Keep source evidence.' in updated['system_policy']
    assert 'user' in updated['system_policy']
    assert old['external_lookup_enabled'] is False


def test_start_is_closed_and_covers_both_address_families():
    calls = []
    policy = NativeNetworkPolicy(apply_rules=calls.append)
    assert policy.state() == {'external_access': False, 'enforced': False}
    policy.start()
    assert policy.state() == {'external_access': False, 'enforced': True}
    assert 'table inet capstone_tasks' in calls[0]
    assert 'meta skuid < 10000 ct direction original ct mark set 0x43505354 return' in calls[0]
    assert 'ct mark 0x43505354 return' in calls[0]
    assert 'ip daddr 127.0.0.1 tcp dport 8790 accept' in calls[0]
    assert calls[0].endswith('reject\n}\n}\n')
    reply = 'tcp sport 8790 ct direction reply ct state established accept'
    assert reply in calls[0]
    assert calls[0].index(reply) < calls[0].index('meta skuid')
    assert '\nct state established accept' not in calls[0]


def test_switch_preserves_internal_endpoint_and_replaces_table_atomically():
    calls = []
    policy = NativeNetworkPolicy(internal_endpoints=(InternalEndpoint('10.20.0.2', 443),),
                                 apply_rules=calls.append)
    policy.start()
    policy.set_external_access(True)
    assert policy.state()['external_access'] is True
    policy.set_external_access(False)
    assert policy.state()['external_access'] is False
    for script in calls:
        assert 'ip daddr 10.20.0.2 tcp dport 443 accept' in script
        assert 'tcp sport 8790 ct direction reply ct state established accept' in script
        assert 'meta skuid < 10000 ct direction original ct mark set 0x43505354 return' in script
        assert script.index('ct mark 0x43505354 return') < script.index('meta skuid')
    assert calls[1].startswith('add table inet capstone_tasks\nflush table inet capstone_tasks\n')
    assert 'ip6 daddr 2000::/3 accept' in calls[1]
    assert 'ip6 daddr 2000::/3 accept' not in calls[2]
    assert '127.0.0.11' not in calls[2]


def test_failed_switch_does_not_report_success():
    def fail(_):
        raise subprocess.CalledProcessError(1, ['nft'])
    policy = NativeNetworkPolicy(apply_rules=fail)
    with pytest.raises(subprocess.CalledProcessError):
        policy.start()
    assert policy.state()['enforced'] is False
    with pytest.raises(RuntimeError):
        policy.set_external_access(True)


def test_failed_atomic_update_retains_previous_state():
    calls = []
    def apply(script):
        if calls:
            raise subprocess.CalledProcessError(1, ['nft'])
        calls.append(script)
    policy = NativeNetworkPolicy(apply_rules=apply)
    policy.start()
    with pytest.raises(subprocess.CalledProcessError):
        policy.set_external_access(True)
    assert policy.state() == {'external_access': False, 'enforced': True}


@pytest.mark.parametrize('address,port,protocol', [
    ('example.com', 443, 'tcp'), ('10.0.0.1; accept', 443, 'tcp'),
    ('10.0.0.1', 0, 'tcp'), ('10.0.0.1', 65536, 'tcp'), ('10.0.0.1', 80, 'any'),
])
def test_endpoints_are_typed_literals(address, port, protocol):
    with pytest.raises(ValueError):
        InternalEndpoint(address, port, protocol)
