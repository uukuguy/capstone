from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('railway_control_plane', ROOT / 'deploy/railway/control_plane.py')
assert SPEC and SPEC.loader
CONTROL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONTROL)

QUERY = ['api', 'query($id:String!){project(id:$id){name}}', '--variables', '@-', '--compact']


def sequence(results):
    calls = []

    def run(args, **kwargs):
        calls.append((args, kwargs))
        result = results[len(calls) - 1]
        if isinstance(result, Exception):
            raise result
        return subprocess.CompletedProcess(args, *result)

    return run, calls


def test_transient_tls_read_recovers_without_changing_credentials():
    run, calls = sequence([(1, '', 'tls handshake eof'), (1, '', 'connection reset by peer'),
                           (0, '{"data":{"project":{"name":"capstone-cloud-dev"}}}', '')])
    pauses = []
    result = CONTROL.run_read(QUERY, runner=run, sleep=pauses.append, input='{"id":"project-id"}')
    assert 'capstone-cloud-dev' in result
    assert len(calls) == 3 and pauses == [1, 2]
    assert all(args == ['railway', *QUERY] for args, _ in calls)
    assert all('env' not in kwargs and kwargs['input'] == '{"id":"project-id"}' for _, kwargs in calls)


def test_auth_failure_does_not_retry_or_expose_secret():
    run, calls = sequence([(1, '', 'HTTP 401 Unauthorized Bearer test-private-value')])
    with pytest.raises(CONTROL.ControlPlaneError) as error:
        CONTROL.run_read(QUERY, runner=run, sleep=lambda _: None)
    assert error.value.code == 'authentication_failed'
    assert len(calls) == 1
    assert 'test-private-value' not in str(error.value)


def test_lost_upload_response_does_not_create_a_second_deployment():
    run, calls = sequence([(1, '', 'tls handshake eof')])
    with pytest.raises(CONTROL.ControlPlaneError) as error:
        CONTROL.run_write(['up', '.', '--detach'], runner=run)
    assert error.value.code == 'write_outcome_unknown'
    assert len(calls) == 1


def test_mutation_cannot_use_read_retry_path():
    run, calls = sequence([])
    with pytest.raises(ValueError):
        CONTROL.run_read(['api', 'mutation { deploymentRestart(id:"example") }'], runner=run)
    assert not calls


def test_network_retry_is_bounded_and_reports_transport_not_auth():
    run, calls = sequence([(1, '', 'client error (Connect): tls handshake eof')] * 3)
    with pytest.raises(CONTROL.ControlPlaneError) as error:
        CONTROL.run_read(QUERY, runner=run, sleep=lambda _: None)
    assert error.value.code == 'network_unavailable'
    assert error.value.attempts == 3 and len(calls) == 3


def test_permission_error_is_not_retried_as_network_failure():
    run, calls = sequence([(1, '', 'GraphQL error: Not Authorized to access project')])
    with pytest.raises(CONTROL.ControlPlaneError) as error:
        CONTROL.run_read(QUERY, runner=run, sleep=lambda _: None)
    assert error.value.code == 'permission_denied'
    assert len(calls) == 1


def test_read_timeout_retries_but_write_timeout_requires_reconciliation():
    timeout = subprocess.TimeoutExpired('railway', 20)
    run, calls = sequence([timeout, (0, '{"data":{}}', '')])
    assert CONTROL.run_read(QUERY, runner=run, sleep=lambda _: None) == '{"data":{}}'
    assert len(calls) == 2
    run, calls = sequence([timeout])
    with pytest.raises(CONTROL.ControlPlaneError) as error:
        CONTROL.run_write(['up', '.', '--detach'], runner=run)
    assert error.value.code == 'write_outcome_unknown' and len(calls) == 1


def test_missing_cli_reports_setup_without_requesting_a_new_token():
    run, calls = sequence([FileNotFoundError('railway')])
    with pytest.raises(CONTROL.ControlPlaneError) as error:
        CONTROL.run_read(QUERY, runner=run)
    assert error.value.code == 'cli_unavailable' and len(calls) == 1


def test_certificate_error_is_reported_and_does_not_disable_tls():
    run, calls = sequence([(1, '', 'certificate verify failed')])
    with pytest.raises(CONTROL.ControlPlaneError) as error:
        CONTROL.run_read(QUERY, runner=run)
    assert error.value.code == 'certificate_rejected' and len(calls) == 1


def test_http_401_takes_priority_over_ambiguous_not_authorized_text():
    run, calls = sequence([(1, '', 'HTTP 401: NotAuthorized')])
    with pytest.raises(CONTROL.ControlPlaneError) as error:
        CONTROL.run_read(QUERY, runner=run)
    assert error.value.code == 'authentication_failed' and len(calls) == 1
