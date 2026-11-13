from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest

from capstone_agent.presentation_template_http import register_presentation_template_routes
from capstone_agent.presentation_templates import PresentationTemplates
from capstone_agent.artifacts import MemoryObjectStore
from test_enterprise_normal_chat import chat_store
from test_thread_postgres import postgres_thread_service


@pytest.fixture
def template_api(chat_store):
    service, thread = chat_store
    objects = MemoryObjectStore()
    builtin = Path(__file__).resolve().parents[3] / 'tools/presentation-templates/state-grid.pptx'
    app = FastAPI()
    def authorize(request):
        if request.headers.get('Authorization') != 'Bearer test':
            raise HTTPException(401, 'unauthorized')
    library = PresentationTemplates(service, objects, builtin=builtin)
    register_presentation_template_routes(app, service=service, objects=objects, authorize=authorize, library=library)
    with TestClient(app, headers={'Authorization': 'Bearer test'}) as client:
        yield client, thread


def test_catalog_select_default_and_download_are_authenticated(template_api):
    client, thread = template_api
    base = f'/api/v1/threads/{thread}/presentation-templates'
    catalog = client.get(base).json()
    assert catalog['selection']['revision'] == 0
    default = {k: catalog['builtin'][k] for k in ('template_id', 'version', 'sha256')}
    response = client.post(base + '/commands', json={'operation': 'select', 'request_id': 'select',
                           'reference': default, 'expected_revision': 0})
    assert response.status_code == 200
    assert response.json()['result']['revision'] == 1
    download = client.get(base + '/' + default['template_id'] + '/versions/' + default['version'] + '/content')
    assert download.status_code == 200
    from hashlib import sha256
    assert sha256(download.content).hexdigest() == default['sha256']
    assert client.get(base, headers={'Authorization': 'invalid'}).status_code == 401


def test_unknown_operations_scope_fields_and_stale_selection_are_rejected(template_api):
    client, thread = template_api
    base = f'/api/v1/threads/{thread}/presentation-templates'
    catalog = client.get(base).json()
    default = {k: catalog['builtin'][k] for k in ('template_id', 'version', 'sha256')}
    for body in ({'operation': 'shell', 'command': 'anything'},
                 {'operation': 'select', 'request_id': 'select', 'reference': default,
                  'expected_revision': 0, 'workspace': 'other'}):
        assert client.post(base + '/commands', json=body).status_code == 422
    response = client.post(base + '/commands', json={'operation': 'select', 'request_id': 'stale',
                           'reference': default, 'expected_revision': 4})
    assert response.status_code == 409
    assert client.get(base, headers={'Capstone-Workspace': 'other'}).status_code == 404
