import pytest

from capstone_agent.control_host import ControlHost, register_control_routes
from capstone_control.service import ControlService
from capstone_control.store import MemoryStore


def goal_request():
    return dict(schema='capstone-control-goal-create/1', operation_id='create-1',
        objective='Produce and verify original bytes', acceptance_criteria=['Review exact report'],
        max_delegations=2, deadline_at='2099-01-01T00:00:00Z', tasks=[
            dict(task_id='draft', objective='Save draft', delivery_requirements=['Save an original draft'],
                 required_products=['draft.txt'], depends_on=[], agent_id='capstone', mode='single', max_attempts=1),
            dict(task_id='review', objective='Read original and report', delivery_requirements=['Verify original hash'],
                 required_products=['report.md'], depends_on=['draft'], agent_id='capstone', mode='single', max_attempts=1)])


class Agent:
    def __init__(self):
        self.calls = []
    def delegate(self, workspace, request):
        self.calls.append(request)
        return {'thread_id': 'thread_' + request['task_id'], 'work_id': 'work_' + request['task_id']}
    def observe(self, workspace, request):
        name = 'draft.txt' if request['task_id'] == 'draft' else 'report.md'
        return {'sequence': 1, 'state': 'completed', 'summary': 'Saved', 'delivery': {
            'answer_ref': 'answer_' + request['task_id'], 'status': 'completed',
            'products': [{'file_name': name, 'sha256': 'a' * 64, 'size_bytes': 16}]}}


def test_background_tick_organizes_two_stages_and_waits_for_user_acceptance():
    service = ControlService(MemoryStore())
    agent = Agent()
    verified = []
    host = ControlHost(service, agent, verify_product=lambda workspace, p: verified.append(p))
    goal = service.create('enterprise', goal_request())
    for _ in range(6):
        host.tick()
    current = service.read('enterprise', goal['goal_id'])
    assert current['state'] == 'delivered'
    assert current['acceptance'] is None
    assert len(agent.calls) == 2
    assert agent.calls[1]['context_products'][0]['file_name'] == 'draft.txt'
    assert len(verified) == 2


def test_required_product_failure_never_releases_dependent_task():
    service = ControlService(MemoryStore())
    agent = Agent()
    def unavailable(workspace, product):
        raise OSError('saved product unavailable')
    host = ControlHost(service, agent, verify_product=unavailable)
    goal = service.create('enterprise', goal_request())
    for _ in range(5):
        host.tick()
    current = service.read('enterprise', goal['goal_id'])
    assert current['tasks'][0]['state'] == 'delivered'
    assert current['tasks'][1]['state'] == 'pending'
    assert len(agent.calls) == 1


def test_control_http_workspace_cas_and_exact_acceptance():
    from fastapi.testclient import TestClient
    from test_thread_http_api import _app, _auth, _service
    threads = _service()
    with TestClient(_app(threads), base_url='http://localhost') as client:
        created = client.post('/api/v1/control/goals', headers=_auth(), json=goal_request())
        assert created.status_code == 201
        goal = created.json()
        path = '/api/v1/control/goals/' + goal['goal_id']
        assert client.get(path, headers={**_auth(), 'Capstone-Workspace': 'other'}).status_code == 404
        assert client.get('/api/v1/control/goals', headers=_auth()).json()['goals'][0] == goal
        cmd = dict(schema='capstone-control-command/1', operation_id='pause-1', goal_id=goal['goal_id'],
                   expected_revision=goal['revision'], kind='pause', payload={})
        first = client.post(path + '/commands', headers=_auth(), json=cmd)
        assert first.status_code == 200
        assert client.post(path + '/commands', headers=_auth(), json=cmd).json() == first.json()
        assert client.post(path + '/commands', headers=_auth(), json={**cmd, 'operation_id': 'stale'}).status_code == 409
        bad = {**cmd, 'goal_id': 'forged'}
        assert client.post(path + '/commands', headers=_auth(), json=bad).status_code == 422
