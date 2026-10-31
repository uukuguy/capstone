from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from capstone_agent.gateway_connections_http import register_gateway_connection_routes
from test_thread_gateway import empty_service, message, publication


def test_session_selection_does_not_change_default_and_lock_cannot_be_bypassed():
    service, thread = empty_service()
    class Executor:
        default = 'one'
        calls = []
        def gateway_connections(self):
            return {'schema':'capstone-gateway-connections/1','revision':1,'checking':False,'selected_id':self.default,
                    'entries':[{'id':name,'label':name,'url':'http://'+name+'.example/mcp','status':'connected'} for name in ('one','two')]}
        def thread_gateway_publication(self, binding=None, *, refresh=False):
            name = (binding or {}).get('connection_id') or self.default
            self.calls.append((name,refresh))
            return publication(name, 'instance-'+name)
    executor = Executor()
    app = FastAPI()
    def authorize(request):
        if request.headers.get('Authorization') != 'Bearer operator':
            raise HTTPException(401)
    register_gateway_connection_routes(app, executor_provider=lambda:executor, authorize=authorize, thread_service=service)
    base = '/api/v1/threads/'+thread+'/gateways'
    with TestClient(app) as client:
        assert client.get(base).status_code == 401
        client.headers['Authorization']='Bearer operator'
        assert client.get(base).json()['selected_id'] == 'one'
        selected = client.post(base+'/select',json={'id':'two'})
        assert selected.status_code == 200
        assert selected.json()['selected_id'] == 'two'
        assert selected.json()['locked'] is False
        assert next(item for item in selected.json()['entries'] if item['id']=='two')['identity']['available'] is True
        assert executor.default == 'one'
        assert service.submit_gateway_command(message(thread), publication('two','instance-two')).status == 'accepted'
        locked = client.get(base).json()
        assert locked['locked'] is True and locked['selected_id'] == 'two'
        count = len(executor.calls)
        rejected = client.post(base+'/select',json={'id':'one'})
        assert rejected.status_code == 409
        assert rejected.json()['detail']['code'] == 'gateway_session_locked'
        assert len(executor.calls) == count
        assert client.post(base+'/reload',json={}).status_code == 200
        assert executor.calls[-1] == ('two',True)
