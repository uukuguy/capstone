from fastapi.testclient import TestClient

from test_thread_http_api import _app, _auth, _service
from test_thread_management import _message


def test_process_catalog_includes_failure_without_exposing_diagnostics():
    service = _service()
    _message(service, 1)
    claim = service.claim_attempt('worker', 30)
    service.finish_attempt(claim, phase='failed', payload={'error_code': 'solver_unavailable', 'debug': 'private-trace'})
    with TestClient(_app(service), base_url='http://localhost') as client:
        response = client.get('/api/v1/threads/thr_demo_39/products', headers=_auth())
        assert response.status_code == 200
        page = response.json()
        item = page['products'][0]
        assert item['scope'] == 'instruction'
        assert item['status'] == 'failed'
        assert item['attempt_id'] == claim.attempt.attempt_id
        assert item['instruction'] == 'question 1'
        assert item['work_id'] is None
        assert item['failure_code'] == 'solver_unavailable'
        assert 'private-trace' not in response.text
        assert 'answer' not in item
        assert client.get('/api/v1/threads/thr_other/products', headers=_auth()).status_code == 404
        assert client.get('/api/v1/threads/thr_demo_39/products').status_code == 401


def test_process_catalog_pages_keep_success_failure_and_cancelled_distinct():
    service = _service()
    for i, phase in enumerate(('completed', 'failed', 'cancelled'), 1):
        _message(service, i)
        claim = service.claim_attempt('worker', 30)
        service.finish_attempt(claim, phase=phase, payload={'answer': 'done'} if phase == 'completed' else {})
    with TestClient(_app(service), base_url='http://localhost') as client:
        before = None
        products = []
        for _ in range(12):
            page = client.get('/api/v1/threads/thr_demo_39/products', headers=_auth(),
                              params={'limit': 2, **({} if before is None else {'before': before})}).json()
            products.extend(page['products'])
            if not page['has_more']:
                break
            assert before is None or page['next_before_event_seq'] < before
            before = page['next_before_event_seq']
        assert [item['status'] for item in products] == ['cancelled', 'failed', 'completed']
        assert len({item['product_id'] for item in products}) == 3
