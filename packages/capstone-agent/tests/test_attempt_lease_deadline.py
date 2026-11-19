from types import SimpleNamespace

import pytest

from capstone_agent import attempt_lease


def test_transient_heartbeat_failure_does_not_revoke_ownership(caplog):
    outcomes = iter([OSError, True, False])

    def renew(*_):
        outcome = next(outcomes)
        if outcome is OSError:
            raise OSError('Private connection details')
        return outcome

    claim = SimpleNamespace(attempt=SimpleNamespace(attempt_id='lease-test'))
    lease = attempt_lease.AttemptLeaseRenewal(SimpleNamespace(renew_attempt=renew), claim, 30)
    lease._refresh()
    lease.check()
    assert 'Attempt heartbeat unavailable' in caplog.text
    assert 'Private connection details' not in caplog.text
    lease._refresh()
    lease.check()
    lease._refresh()
    with pytest.raises(RuntimeError, match='owner is unavailable'):
        lease.check()


def test_ledger_owner_rejection_prevents_runtime_entry():
    claim = SimpleNamespace(attempt=SimpleNamespace(attempt_id='lease-test'))
    service = SimpleNamespace(renew_attempt=lambda *_: False)
    with pytest.raises(RuntimeError, match='owner is unavailable'):
        with attempt_lease.AttemptLeaseRenewal(service, claim, 30):
            pytest.fail('invalid owner started')
