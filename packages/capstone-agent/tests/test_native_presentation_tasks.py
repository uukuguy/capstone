from hashlib import sha256
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from capstone_agent.native_presentation_tasks import PresentationTaskPort, TemplateBackendClient
from capstone_agent.presentation_template_http import register_presentation_template_routes
from test_enterprise_normal_chat import chat_store
from test_thread_postgres import postgres_thread_service
from test_presentation_templates import setup_library, upload, BUILTIN


def task_port(service, thread, tmp_path, *, admitted=()):
    library, uploads, objects = setup_library(service)
    app = FastAPI()
    register_presentation_template_routes(app, service=service, objects=objects,
        authorize=lambda _: None, library=library)
    client = TemplateBackendClient('http://testserver', 'test', 'enterprise', thread, client=TestClient(app))
    port = PresentationTaskPort(client, task_id='task-template', inputs=tmp_path/'inputs',
                                uid=os.getuid(), admitted_resources=admitted)
    return port, library, uploads, objects


@pytest.mark.parametrize('origin', ['https://user:secret@example.com', 'http://testserver/path', 'file:///tmp', 'http://testserver?next=other'])
def test_backend_origin_is_selected_by_host_without_credentials_or_paths(origin):
    with pytest.raises(ValueError, match='origin'):
        TemplateBackendClient(origin, 'test', 'enterprise', 'thread')


def test_materialization_returns_only_verified_task_private_bytes(chat_store, tmp_path):
    service, thread = chat_store
    port, library, _, _ = task_port(service, thread, tmp_path)
    catalog = port.invoke('catalog', {}, call_id='catalog')
    assert catalog['selection']['revision'] == 0
    result = port.invoke('materialize', {}, call_id='materialize')
    path = Path(result['path'])
    assert path.is_relative_to(tmp_path/'inputs')
    assert sha256(path.read_bytes()).hexdigest() == catalog['builtin']['sha256']
    assert result['template']['template_id'] == 'state-grid'
    assert path.stat().st_mode & 0o222 == 0
    with pytest.raises(ValueError):
        port.invoke('materialize', {'workspace': 'other'}, call_id='invalid')


def test_uploaded_source_must_be_in_current_task_grant(chat_store, tmp_path):
    service, thread = chat_store
    port, _, uploads, _ = task_port(service, thread, tmp_path)
    resource = upload(uploads, thread, BUILTIN.read_bytes())
    reference = {k: resource[k] for k in ('resource_id', 'version', 'sha256')}
    with pytest.raises(ValueError, match='not_admitted'):
        port.invoke('add', {'resource': reference, 'name': 'Uploaded'}, call_id='add')
    port.admitted_resources = (resource,)
    for version in (True, 1.0):
        with pytest.raises(ValueError, match='not_admitted'):
            port.invoke('add', {'resource': {**reference, 'version': version}, 'name': 'Uploaded'}, call_id='invalid-type')
    added = port.invoke('add', {'resource': reference, 'name': 'Uploaded'}, call_id='add')
    assert added['scope'] == 'session'
    assert port.invoke('add', {'resource': reference, 'name': 'Uploaded'}, call_id='add') == added


def test_unknown_operation_cannot_forward_caller_selected_endpoint(chat_store, tmp_path):
    service, thread = chat_store
    port, _, _, _ = task_port(service, thread, tmp_path)
    with pytest.raises(ValueError):
        port.invoke('fetch', {'url': 'https://example.com'}, call_id='fetch')


def test_lost_mutation_response_is_recovered_by_exact_receipt_without_replay(chat_store, tmp_path):
    import httpx
    from capstone_agent.native_presentation_tasks import TemplateOutcomeUnknown
    service, thread = chat_store
    port, _, _, _ = task_port(service, thread, tmp_path)
    catalog = port.invoke('catalog', {}, call_id='catalog')
    reference = {k: catalog['builtin'][k] for k in ('template_id', 'version', 'sha256')}
    original = port.client.client
    mutations = []
    def transport(request):
        response = original.request(request.method, str(request.url), headers=dict(request.headers), content=request.content)
        if request.method == 'POST':
            mutations.append(request.url.path)
            raise httpx.ReadTimeout('PRIVATE_SENSITIVE_TRANSPORT_DETAIL')
        return httpx.Response(response.status_code, headers=dict(response.headers), content=response.content)
    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        port.client.client = client
        with pytest.raises(TemplateOutcomeUnknown) as raised:
            port.invoke('select', {'reference': reference, 'expected_revision': 0}, call_id='select')
        assert 'PRIVATE_SENSITIVE' not in str(raised.value)
        receipt = port.invoke('operation', {'request_id': raised.value.request_id}, call_id='receipt')
        assert receipt['result']['revision'] == 1
        assert len(mutations) == 1
