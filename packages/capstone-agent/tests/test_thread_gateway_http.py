from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from capstone_agent.gateway_connections_http import register_gateway_connection_routes
from test_thread_gateway import empty_service, message, publication


def test_session_selection_updates_the_default_used_by_new_sessions():
    service, thread = empty_service()
    class Executor:
        default = 'one'
        calls = []
        controls = []
        unavailable = None
        def gateway_connections(self):
            return {'schema':'capstone-gateway-connections/1','revision':1,'checking':False,'selected_id':self.default,
                    'entries':[{'id':name,'label':name,'url':'http://'+name+'.example/mcp','status':'connected'} for name in ('one','two')]}
        def thread_gateway_publication(self, binding=None, *, refresh=False):
            name = (binding or {}).get('connection_id') or self.default
            self.calls.append((name,refresh))
            if name == self.unavailable:
                from capstone_agent.pi_delegation import PiHTTPFailure
                raise PiHTTPFailure(503, 'gateway_transport_failed')
            return publication(name, 'instance-'+name)
        def control_gateway_connections(self, action, document):
            self.controls.append((action, dict(document)))
            if action == 'select':
                self.default = document['id']
            return self.gateway_connections()
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
        assert executor.calls == []
        selected = client.post(base+'/select',json={'id':'two'})
        assert selected.status_code == 200
        assert selected.json()['selected_id'] == 'two'
        assert selected.json()['locked'] is False
        assert next(item for item in selected.json()['entries'] if item['id']=='two')['identity']['available'] is True
        assert executor.default == 'two'
        assert executor.controls == [('select', {'id': 'two'})]
        assert service.submit_gateway_command(message(thread), publication('two','instance-two')).status == 'accepted'
        locked = client.get(base).json()
        assert locked['locked'] is False and locked['selected_id'] == 'two'
        count = len(executor.calls)
        switched = client.post(base+'/select',json={'id':'one'})
        assert switched.status_code == 200
        assert switched.json()['selected_id'] == 'one'
        assert executor.default == 'one'
        assert ('one', True) in executor.calls[count:]
        assert client.post(base+'/refresh',json={}).status_code == 200
        assert executor.calls[-1] == ('one',True)
        assert client.get(base).json()['selected_id'] == 'one'
        assert executor.calls[-1] == ('one', False)
        executor.unavailable = 'two'
        failed = client.post(base+'/select', json={'id':'two'})
        assert failed.status_code == 503
        assert failed.json()['detail']['code'] == 'gateway_transport_failed'
        assert service.read_thread_gateway(thread)['connection_id'] == 'one'
        assert executor.default == 'one'


def test_session_switch_is_what_a_later_unbound_session_reads():
    current, thread = empty_service()
    bound, bound_thread = empty_service()
    fresh, fresh_thread = empty_service()
    from capstone_agent.thread_gateway import publication_binding
    bound.select_thread_gateway(bound_thread, publication_binding(publication('remote', 'instance-remote')))
    class Executor:
        default = 'remote'
        controls = []
        def gateway_connections(self):
            return {'schema':'capstone-gateway-connections/1','revision':2,'checking':False,'selected_id':self.default,
                    'entries':[{'id':'remote','label':'三区研发','url':'http://remote.example/mcp','status':'disconnected','error':'gateway_timeout'},
                               {'id':'local','label':'本机联调','url':'http://local.example/mcp','status':'connected'}]}
        def thread_gateway_publication(self, binding=None, *, refresh=False):
            name = (binding or {}).get('connection_id') or self.default
            return publication(name, 'instance-'+name)
        def control_gateway_connections(self, action, document):
            self.controls.append((action, dict(document)))
            self.default = document['id']
            return self.gateway_connections()
    executor = Executor()
    def client_for(service):
        app = FastAPI()
        register_gateway_connection_routes(app, executor_provider=lambda: executor, authorize=lambda request: None, thread_service=service)
        return TestClient(app)
    with client_for(current) as client, client_for(bound) as kept, client_for(fresh) as later:
        assert client.get('/api/v1/threads/'+thread+'/gateways').json()['selected_id'] == 'remote'
        selected = client.post('/api/v1/threads/'+thread+'/gateways/select', json={'id':'local'})
        assert selected.status_code == 200
        assert selected.json()['selected_id'] == 'local'
        assert executor.controls == [('select', {'id':'local'})]
        opened = later.get('/api/v1/threads/'+fresh_thread+'/gateways').json()
        assert opened['selected_id'] == 'local'
        assert next(item for item in opened['entries'] if item['id']=='local')['label'] == '本机联调'
        preserved = kept.get('/api/v1/threads/'+bound_thread+'/gateways').json()
        assert preserved['selected_id'] == 'remote'
        assert bound.read_thread_gateway(bound_thread)['connection_id'] == 'remote'


def test_busy_registry_keeps_the_session_and_the_default():
    service, thread = empty_service()
    class Executor:
        default = 'remote'
        def gateway_connections(self):
            return {'schema':'capstone-gateway-connections/1','revision':2,'checking':False,'selected_id':self.default,
                    'entries':[{'id':'remote','label':'三区研发','url':'http://remote.example/mcp','status':'connected'},
                               {'id':'local','label':'本机联调','url':'http://local.example/mcp','status':'connected'}]}
        def thread_gateway_publication(self, binding=None, *, refresh=False):
            name = (binding or {}).get('connection_id') or self.default
            return publication(name, 'instance-'+name)
        def control_gateway_connections(self, action, document):
            from capstone_agent.pi_delegation import PiHTTPFailure
            raise PiHTTPFailure(409, 'gateway_connections_busy')
    executor = Executor()
    app = FastAPI()
    register_gateway_connection_routes(app, executor_provider=lambda: executor, authorize=lambda request: None, thread_service=service)
    base = '/api/v1/threads/'+thread+'/gateways'
    with TestClient(app) as client:
        failed = client.post(base+'/select', json={'id':'local'})
        assert failed.status_code == 409
        assert failed.json()['detail']['code'] == 'gateway_connections_busy'
        assert executor.default == 'remote'
        assert service.read_thread_gateway(thread) is None
        assert client.get(base).json()['selected_id'] == 'remote'


def test_new_session_read_returns_registered_gateway_without_live_reload():
    service, thread = empty_service()
    class Executor:
        calls = []
        def gateway_connections(self):
            return {'schema':'capstone-gateway-connections/1','revision':4,'checking':False,'selected_id':'remote',
                    'entries':[{'id':'remote','label':'三区研发','url':'http://remote.example/mcp','status':'disconnected','error':'gateway_timeout'},
                               {'id':'local','label':'本机联调','url':'http://local.example/mcp','status':'connected'}]}
        def thread_gateway_publication(self, binding=None, *, refresh=False):
            self.calls.append(refresh)
            from capstone_agent.pi_delegation import PiHTTPFailure
            raise PiHTTPFailure(503, 'gateway_timeout')
    executor = Executor()
    app = FastAPI()
    register_gateway_connection_routes(app, executor_provider=lambda: executor, authorize=lambda request: None, thread_service=service)
    base = '/api/v1/threads/' + thread + '/gateways'
    with TestClient(app) as client:
        body = client.get(base).json()
        assert body['selected_id'] == 'remote'
        assert body['locked'] is False
        remote = next(item for item in body['entries'] if item['id'] == 'remote')
        assert remote['label'] == '三区研发' and remote['status'] == 'disconnected' and remote['error'] == 'gateway_timeout'
        assert executor.calls == []
        failed = client.post(base + '/refresh', json={})
        assert failed.status_code == 503 and failed.json()['detail']['code'] == 'gateway_timeout'
        assert executor.calls == [True]
