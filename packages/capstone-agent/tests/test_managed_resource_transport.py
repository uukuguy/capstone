from types import SimpleNamespace
import threading
import time
import httpx
from capstone_agent.general_pi_server import GeneralPiHost,make_server
from capstone_agent.general_pi_relay import ProviderRelay
from capstone_agent.managed_resource_service import ManagedResourceService
from test_managed_resource_installation import context,installer


def test_protected_control_and_task_scopes_share_the_same_service(context,tmp_path):
    engine=installer(context)
    host=GeneralPiHost(root=tmp_path/'host',identity={'engine':'test'},run_task=lambda *_:('ok',{}))
    relay=ProviderRelay()
    runner=SimpleNamespace(root=tmp_path/'host',managed_resource_service=ManagedResourceService(engine.store,engine),relay=relay)
    runner.managed_resource_service.task_is_open=lambda task:True
    runner.task_resource_inputs={'one':tmp_path/'inputs'}
    host._tasks['one']={'request':SimpleNamespace(managed_workspace='trusted')}
    relay.register('one','task-grant',time.monotonic()+10)
    server=make_server(host,control_token='control',address=('127.0.0.1',0),runner=runner)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        with httpx.Client(base_url=f'http://127.0.0.1:{server.server_address[1]}',trust_env=False) as client:
            body={'workspace':'trusted','operation':'list','document':{}}
            assert client.post('/managed-resources',json=body).status_code==401
            response=client.post('/managed-resources',json=body,headers={'Authorization':'Bearer control'})
            assert response.status_code==200
            assert response.json()['result']['allowed_actions']
            task={'operation':'list','document':{}}
            response=client.post('/managed-resource-tasks/one',json=task,headers={'Authorization':'Bearer task-grant'})
            assert response.status_code==200 and response.json()['ok'] is True
            response=client.post('/managed-resource-tasks/one',json={**task,'workspace':'other'},headers={'Authorization':'Bearer task-grant'})
            assert response.status_code==400
            assert client.post('/managed-resource-tasks/one',json=task,headers={'Authorization':'Bearer wrong'}).status_code==403
    finally:
        relay.revoke('one');server.shutdown();server.server_close();thread.join(2)
