from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from capstone_agent.product_series_http import register_product_series_routes


def test_authorization_bounded_bodies_and_trusted_actor():
    app = FastAPI()
    class Service:
        calls = []
        def command(self, thread, body, *, actor):
            self.calls.append((thread, body, actor))
            return {'revision': 1}
        def compare(self, thread, original, revised):
            raise ValueError('budget exceeded')
    service = Service()
    def authorize(request):
        if request.headers.get('authorization') != 'Bearer test':
            raise HTTPException(401)
    register_product_series_routes(app, service=service, authorize=authorize,
        actor_provider=lambda request: 'operator:private')
    with TestClient(app) as client:
        path = '/api/v1/threads/thr_one/product-series/commands'
        assert client.post(path, content=b'x'*20000).status_code == 401
        headers = {'Authorization': 'Bearer test'}
        assert client.post(path, headers=headers, content=b'x'*20000).status_code == 413
        assert client.post(path, headers=headers, content='{"schema":1,"schema":2}').status_code == 422
        assert not service.calls
        assert client.post(path, headers=headers, json={'operation':'clear'}).status_code == 200
        assert service.calls[-1][2] == 'operator:private'
        response = client.post('/api/v1/threads/thr_one/product-comparisons', headers=headers,
            json={'original_ref': {}, 'revised_ref': {}})
        assert response.status_code == 422


def test_safe_comparison_failure_is_specific():
    from capstone_agent.product_series_source import ProductSourceError
    class Service:
        def compare(self,*args): raise ProductSourceError('invalid_utf8')
    app=FastAPI()
    register_product_series_routes(app,service=Service(),authorize=lambda request:None,
        actor_provider=lambda request:'operator:test')
    with TestClient(app) as client:
        response=client.post('/api/v1/threads/thread/product-comparisons',
            json={'original_ref':{},'revised_ref':{}})
        assert response.status_code==422
        assert response.json()=={'detail':'invalid_utf8'}
