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
