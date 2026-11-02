from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from capstone_agent.network_policy_http import register_network_policy_routes


def test_application_switch_uses_executor_confirmed_state():
    class Executor:
        enabled = False
        def network_policy(self):
            return {'external_access': self.enabled, 'enforced': True}
        def set_network_policy(self, enabled):
            self.enabled = enabled
            return self.network_policy()
    app = FastAPI()
    executor = Executor()
    register_network_policy_routes(app, executor_provider=lambda: executor, authorize=lambda _: None)
    client = TestClient(app)
    path = '/api/v1/network-policy'
    assert client.get(path).json()['external_access'] is False
    assert client.post(path, json={'external_access': True}).json()['external_access'] is True
    assert client.post(path, json={'external_access': 'false'}).status_code == 400
    assert executor.enabled is True
    assert client.post(path, json={'external_access': False}).json()['external_access'] is False


def test_unavailable_is_not_reported_as_enforced_off():
    app = FastAPI()
    register_network_policy_routes(app, executor_provider=lambda: None, authorize=lambda _: None)
    assert TestClient(app).get('/api/v1/network-policy').status_code == 503


def test_scripted_demo_cannot_read_or_change_global_policy():
    def deny(_):
        raise HTTPException(403, 'not permitted')
    app = FastAPI()
    register_network_policy_routes(app, executor_provider=lambda: None, authorize=deny)
    client = TestClient(app)
    assert client.get('/api/v1/network-policy').status_code == 403
    assert client.post('/api/v1/network-policy', json={'external_access': True}).status_code == 403
