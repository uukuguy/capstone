from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from capstone_agent.product_index_http import register_product_index_routes


def client_for(service):
    app = FastAPI()
    def authorize(request):
        if request.headers.get('authorization') != 'Bearer test':
            raise HTTPException(401, 'unauthorized')
    register_product_index_routes(app, service=service, authorize=authorize)
    return TestClient(app)


class Service:
    calls = 0
    def request(self, thread, ref):
        self.calls += 1
        return {'state': 'queued', 'parent_ref': ref}
    def status(self, thread, job):
        raise KeyError('private storage key')
    def blocks(self, thread, job, **page):
        return page


def test_auth_and_bounded_strict_request():
    service = Service()
    with client_for(service) as client:
        path = '/api/v1/threads/t/product-block-indexes'
        assert client.post(path, json={'ref': {}}).status_code == 401
        headers = {'authorization': 'Bearer test'}
        assert client.post(path, headers=headers, content=b'x'*16385).status_code == 413
        assert client.post(path, headers=headers, content='{"ref":{},"ref":{}}').status_code == 422
        assert client.post(path, headers=headers, json={'ref': {}, 'extra': 1}).status_code == 422
        result = client.post(path, headers=headers, json={'ref': {}})
        assert result.status_code == 202 and service.calls == 1


def test_scoped_status_and_page_errors_do_not_expose_private_details():
    with client_for(Service()) as client:
        path = '/api/v1/threads/t/product-block-indexes/j'
        headers = {'authorization': 'Bearer test'}
        result = client.get(path, headers=headers)
        assert result.status_code == 404 and 'private' not in result.text
        assert client.get(path+'/blocks', headers=headers, params={'offset': -1}).status_code == 422
        assert client.get(path+'/blocks', headers=headers, params={'offset': 2, 'limit': 1}).json() == {'offset': 2, 'limit': 1}
