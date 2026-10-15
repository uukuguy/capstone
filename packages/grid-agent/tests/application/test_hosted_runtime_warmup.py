from types import SimpleNamespace

import pytest

from capability_agent.application.profile import CredentialScope
from grid_agent import hosted


@pytest.mark.parametrize('failed', [False, True])
def test_runtime_warmup_reads_only_catalog_and_closes_private_endpoint(monkeypatch, failed):
    calls = []
    def invoke(capability, arguments):
        calls.append((capability, arguments))
        if failed:
            raise RuntimeError('catalog unavailable')
        return {'protocol': 'grid-capability'}
    endpoint = SimpleNamespace(executor=SimpleNamespace(invoke=invoke), close=lambda: calls.append('closed'))
    manifest = SimpleNamespace(assert_environment_compatible=lambda value: calls.append('validated'))
    binding = SimpleNamespace(binding_id='grid', credential_scope=CredentialScope(scope_id='empty'),
        profile=SimpleNamespace(manifest=manifest,
            provisioner=SimpleNamespace(prepare=lambda **kwargs: endpoint)))
    monkeypatch.setattr(hosted, 'build_pandapower_application_profile', lambda: SimpleNamespace(domains=[binding]))
    if failed:
        with pytest.raises(RuntimeError, match='catalog unavailable'):
            hosted._warm_runtime_catalog()
    else:
        hosted._warm_runtime_catalog()
        assert 'validated' in calls
    assert calls[0] == ('environment.describe', {})
    assert calls[-1] == 'closed'
