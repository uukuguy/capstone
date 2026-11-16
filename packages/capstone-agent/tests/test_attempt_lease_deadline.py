from types import SimpleNamespace

import pytest

from capstone_agent import attempt_lease


def test_local_lease_check_expires_even_if_renewal_thread_has_not_reported_loss(monkeypatch):
    now = [0.0]
    monkeypatch.setattr(attempt_lease, 'time', SimpleNamespace(monotonic=lambda: now[0]), raising=False)
    service = SimpleNamespace(renew_attempt=lambda *_: True)
    claim = SimpleNamespace(attempt=SimpleNamespace(attempt_id='lease-test'))
    with attempt_lease.AttemptLeaseRenewal(service, claim, 30) as lease:
        lease.check()
        now[0] = 30
        with pytest.raises(RuntimeError, match='lease is unavailable'):
            lease.check()
        now[0] = 1
        with pytest.raises(RuntimeError, match='lease is unavailable'):
            lease.check()


def test_slow_initial_renewal_cannot_grant_already_expired_local_authority(monkeypatch):
    now = [0.0]
    monkeypatch.setattr(attempt_lease, 'time', SimpleNamespace(monotonic=lambda: now[0]), raising=False)
    def slow(*_):
        now[0] = 31
        return True
    service = SimpleNamespace(renew_attempt=slow)
    claim = SimpleNamespace(attempt=SimpleNamespace(attempt_id='lease-test'))
    with pytest.raises(RuntimeError, match='lease is unavailable'):
        with attempt_lease.AttemptLeaseRenewal(service, claim, 30):
            pytest.fail('expired initial renewal admitted')
