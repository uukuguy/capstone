"""Execution authority expires independently from task observation."""
import pytest

from capstone_agent.native_execution_authority import ExecutionAuthority


def test_expiry_is_terminal_even_when_renewal_arrives_late():
    now = [10.0]
    authority = ExecutionAuthority('generation-a', 'private-capability', 5, clock=lambda: now[0])
    now[0] = 15.0
    assert not authority.active()
    with pytest.raises(PermissionError):
        authority.renew('generation-a', 'private-capability', 1)
    now[0] = 11.0
    assert not authority.active()


def test_duplicate_renewal_does_not_extend_deadline():
    now = [0.0]
    authority = ExecutionAuthority('a', 'secret', 5, clock=lambda: now[0])
    now[0] = 2
    authority.renew('a', 'secret', 1)
    now[0] = 6
    authority.renew('a', 'secret', 1)
    now[0] = 7
    assert not authority.active()


@pytest.mark.parametrize('generation,capability,sequence', [('b','secret',1), ('a','wrong',1), ('a','secret',2)])
def test_rejected_renewal_does_not_change_authority(generation, capability, sequence):
    now = [0.0]
    authority = ExecutionAuthority('a', 'secret', 5, clock=lambda: now[0])
    with pytest.raises((PermissionError, ValueError)):
        authority.renew(generation, capability, sequence)
    now[0] = 5
    assert not authority.active()


def test_valid_renewal_survives_short_gap_but_revoke_is_terminal():
    now = [0.0]
    authority = ExecutionAuthority('a', 'secret', 5, clock=lambda: now[0])
    now[0] = 4
    authority.renew('a', 'secret', 1)
    now[0] = 6
    assert authority.active()
    authority.revoke()
    with pytest.raises(PermissionError):
        authority.renew('a', 'secret', 2)
    assert 'secret' not in repr(authority)


@pytest.mark.parametrize('duration', [0, -1, True, float('inf'), float('nan')])
def test_invalid_duration_is_rejected(duration):
    with pytest.raises(ValueError):
        ExecutionAuthority('a', 'secret', duration)
