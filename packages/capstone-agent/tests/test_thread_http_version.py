"""Version negotiation applies before a typed Thread response is parsed."""

import httpx
import pytest

from capstone_agent.thread_http import HttpThreadSession, ThreadHttpError


def test_python_client_declares_version_and_accepts_legacy_response():
    def respond(request):
        assert request.headers['Capstone-Thread-Version'] == '1'
        return httpx.Response(200, json={'legacy': True})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        session = HttpThreadSession('https://example.test', 'test-token', client)
        assert session._request('GET', '/api/v1/threads') == {'legacy': True}


def test_python_client_rejects_mismatched_response_version():
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(
        200, headers={'Capstone-Thread-Version': '2'}, content=b'not-v1-json',
    ))) as client:
        session = HttpThreadSession('https://example.test', 'test-token', client)
        with pytest.raises(ThreadHttpError, match='version') as failure:
            session._request('GET', '/api/v1/threads')
        assert failure.value.body == {'error': 'thread_version_mismatch'}


@pytest.mark.parametrize('error', ['unsupported_thread_version', 'protocol_upgrade_required'])
def test_python_client_preserves_protocol_error_details(error):
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(
        409, json={'error': error},
    ))) as client:
        session = HttpThreadSession('https://example.test', 'test-token', client)
        with pytest.raises(ThreadHttpError, match='version') as failure:
            session._request('GET', '/api/v1/threads')
        assert failure.value.body == {'error': error}


def test_python_v2_command_uses_explicit_object_target_without_snapshot_read():
    import json
    def respond(request):
        assert request.method == 'POST'
        assert request.headers['Capstone-Thread-Version'] == '2'
        command = json.loads(request.content)
        assert command['schema'] == 'capstone-command/2'
        assert 'expected_event_seq' not in command
        assert command['target'] == {'kind': 'work', 'id': 'new', 'expected_revision': 0}
        return httpx.Response(202, headers={'Capstone-Thread-Version': '2'}, json={
            'schema': 'capstone-command-receipt/1', 'command_id': command['command_id'],
            'idempotency_key': command['idempotency_key'], 'thread_id': 'thr_work',
            'run_id': 'run_work', 'status': 'accepted', 'accepted_event_seq': 1})
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        session = HttpThreadSession('https://example.test', 'test-token', client,
                                    thread_id='thr_work', run_id='run_work', protocol_version=2)
        assert session.command('work_message', {'text': 'Review'},
            target={'kind': 'work', 'id': 'new', 'expected_revision': 0}).status == 'accepted'


def test_python_v2_requires_response_echo_and_does_not_retry_write():
    requests = []
    def respond(request):
        requests.append(request)
        return httpx.Response(201, json={'legacy': True})
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        session = HttpThreadSession('https://example.test', 'test-token', client, protocol_version=2)
        with pytest.raises(ThreadHttpError, match='version'):
            session.create()
    assert len(requests) == 1
