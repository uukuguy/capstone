import asyncio
import json
from pathlib import Path

import httpx
import pytest

from capstone_agent.data_gateway_mcp import GatewayError
from capstone_agent.gateway_investigation import BASE, VERSION, GatewayInvestigation


FIXTURES = Path(__file__).parent / 'fixtures/gateway-investigation-v1'
CONTRACT = json.loads((FIXTURES / 'contract.json').read_text())
EXCHANGE = json.loads((FIXTURES / 'synthetic-exchange.json').read_text())
DECLARATION = {'version': VERSION, 'contract_path': BASE + 'contract'}


@pytest.mark.parametrize('case', json.loads((FIXTURES / 'synthetic-logs.json').read_text())['cases'],
                         ids=lambda case: case['case'])
def test_logs_follow_published_examples(case):
    declaration = {'version':'gateway-investigation-logs/1','contract_path':BASE+'log-contract'}
    scope = {key:case['request'][key] for key in ('binding_handle','workspace_id','investigation_id')}
    query = {key:value for key,value in case['request'].items() if key not in scope}

    def respond(request):
        if request.method == 'GET':
            if request.url.path == BASE+'contract':
                return httpx.Response(200,json=CONTRACT)
            assert request.url.path == declaration['contract_path']
            return httpx.Response(200,json=json.loads((FIXTURES/'log-contract.json').read_text()))
        assert request.url.path == BASE+'logs' and json.loads(request.content) == case['request']
        return httpx.Response(case['expected_http_status'],json=case['response'])

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            access = await GatewayInvestigation.discover(client,'https://fixture.test/mcp',DECLARATION,declaration)
            if case['expected_http_status'] == 200:
                assert await access.read_logs(scope,query) == case['response']
            else:
                with pytest.raises(GatewayError,match=case['response']['error']['code']):
                    await access.read_logs(scope,query)
    asyncio.run(run())


def test_declared_contract_and_scoped_operations():
    paths = []
    def respond(request):
        paths.append(request.url.path)
        operation = request.url.path.split('/')[-1]
        if operation == 'contract':
            return httpx.Response(200, json=CONTRACT)
        body = json.loads(request.content)
        if body.get('workspace_id') != EXCHANGE['bind']['workspace_id']:
            return httpx.Response(404, json=EXCHANGE['not_visible'])
        values = {'bind': EXCHANGE['binding'], 'read': EXCHANGE['unknown'],
                  'list': {'receipts': [EXCHANGE['unknown']], 'next_cursor': None},
                  'close': {'state': 'closed'}}
        return httpx.Response(200, json=values[operation])

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            access = await GatewayInvestigation.discover(client, 'https://fixture.test/mcp', DECLARATION)
            binding = await access.invoke('bind', EXCHANGE['bind'])
            read = {**EXCHANGE['read_after_response_loss'], 'client_call_id': EXCHANGE['unknown']['client_call_id']}
            assert binding['binding_handle'] == read['binding_handle']
            receipt = await access.invoke('read', read)
            assert receipt['state'] == 'unknown' and receipt['automatic_retry'] is False
            with pytest.raises(GatewayError, match='receipt_not_visible'):
                await access.invoke('read', {**read, 'workspace_id': 'workspace-b'})
            scope = {k: v for k, v in read.items() if k != 'client_call_id'}
            assert (await access.invoke('list', scope))['receipts'] == [receipt]
            assert (await access.invoke('close', scope))['state'] == 'closed'
    asyncio.run(run())
    assert paths == [BASE + name for name in ('contract', 'bind', 'read', 'read', 'list', 'close')]


def test_missing_extension_and_untrusted_path_make_no_request():
    assert asyncio.run(GatewayInvestigation.discover(None, '', None)) is None
    with pytest.raises(GatewayError, match='contract_invalid'):
        asyncio.run(GatewayInvestigation.discover(None, '', {**DECLARATION, 'contract_path': '//other/contract'}))


@pytest.mark.parametrize('policy', ['undeclared', 'allow_sanitized'])
def test_export_is_scoped_to_explicit_policy_and_safe_fields(policy, monkeypatch, tmp_path):
    from types import SimpleNamespace
    from capstone_agent.gateway_investigation import investigation_workspace_id, read_bound_observation

    paths = []
    deployment_policy = policy
    receipt = EXCHANGE['unknown']

    def respond(request, owner, scope):
        paths.append(request.url.path)
        if request.url.path == BASE + 'contract':
            return httpx.Response(200, json={**CONTRACT, 'export': {
                'deployment_policy': deployment_policy, 'allowed': ['state', 'client_call_id', 'request_id'],
            }})
        if request.url.path == BASE + 'bind':
            assert json.loads(request.content) == {
                **owner, 'instance_id': 'fixture', 'idempotency_key': owner['investigation_id']}
            return httpx.Response(200, json=EXCHANGE['binding'])
        assert request.url.path == BASE + 'list'
        assert json.loads(request.content) == {**scope, 'limit': 32}
        return httpx.Response(200, json={'receipts': [receipt], 'next_cursor': None})

    async def run(workspace='local', investigation_id='inv_one'):
        owner = {'workspace_id': investigation_workspace_id(workspace), 'investigation_id': investigation_id}
        scope = {**owner, 'binding_handle': EXCHANGE['binding']['binding_handle']}
        transport = httpx.MockTransport(lambda request: respond(request, owner, scope))
        async with httpx.AsyncClient(transport=transport) as client:
            session = SimpleNamespace(instance_identity={'instance_id': 'fixture'}, http_client=client,
                                      investigation=DECLARATION, investigation_logs=None)
            return await read_bound_observation(session, 'https://fixture.test/mcp', instance_id='fixture',
                                                workspace=workspace, investigation_id=investigation_id,
                                                operation='export', query={})

    exported = asyncio.run(run())
    if policy == 'allow_sanitized':
        assert exported == {'status': 'available', 'truncated': False, 'events': [{'state': 'unknown'}]}
        assert paths == [BASE + 'contract', BASE + 'bind', BASE + 'list']
        from fastapi.testclient import TestClient
        import subprocess
        import sys
        from capstone_agent import debug_investigations
        from capstone_agent.host_api import create_host_app
        from test_attempt_records import completed_task
        from test_thread_http_api import _Ledger, WorkerRegistry

        monkeypatch.setenv('CAPSTONE_DEPLOYMENT_STAGE', 'local')
        monkeypatch.setenv('CAPSTONE_DEBUG_COMMANDS', '1')
        monkeypatch.setenv('CAPSTONE_DEBUG_TIMELINE_EXPORT', '1')
        service, claim = completed_task()
        register = debug_investigations.InvestigationRegister(service)
        monkeypatch.setattr(debug_investigations, 'InvestigationRegister', lambda service: register)
        monkeypatch.setattr(register, 'historical_gateway', lambda *scope: {'instance_id': 'fixture'})
        investigation = register.start(claim.workspace_name, claim.thread_id, 'fixture-export', '复验失败',
                                       claim.attempt.attempt_id)

        def read(binding, workspace, investigation_id, operation, query):
            assert (binding, workspace, investigation_id, operation, query) == (
                {'instance_id': 'fixture'}, claim.workspace_name, investigation['investigation_id'], 'export', {})
            return asyncio.run(run(workspace, investigation_id))

        app = create_host_app(_Ledger(), WorkerRegistry(()), operator_token='hosted-secret',
                             allowed_hosts={'localhost'}, allowed_origins={'http://localhost:5173'},
                             thread_open_access=True, thread_service=service,
                             native_artifact_executor=SimpleNamespace(debug_observation=read))
        url = f"/api/v1/threads/{claim.thread_id}/debug/investigations/{investigation['investigation_id']}/evidence"
        tools = Path(__file__).resolve().parents[3] / 'tools'
        with TestClient(app, base_url='http://localhost') as client:
            response = client.get(url)
            assert response.status_code == 200
            before = tmp_path / 'before.json'
            before.write_bytes(response.content)
            replay = subprocess.run([sys.executable, str(tools / 'check_debug_evidence.py'), str(before),
                                     '--import-to', str(tmp_path)], check=True, capture_output=True)
            imported = Path(json.loads(replay.stdout)['import_directory'])
            assert json.loads((imported / 'gateway-events.jsonl').read_text()) == {'state': 'unknown'}
            assert (imported / 'capstone-events.jsonl').stat().st_size > 0
            metadata = json.loads((imported / 'correlation.json').read_text())
            assert metadata['attempt_id'] == claim.attempt.attempt_id
            assert metadata['request_correlation'] == {'status': 'unverified', 'links': []}
            assert '首条公开异常' in (imported / 'diagnosis.md').read_text()
            snapshot = response.json()['snapshot_id']
            receipt = {**receipt, 'state': 'observed', 'observed_status': 'ok'}
            candidate = tmp_path / 'candidate.json'
            candidate.write_bytes(client.get(url, params={'snapshot_id': snapshot}).content)
            comparison = subprocess.run([sys.executable, str(tools / 'compare_debug_timelines.py'),
                                         str(before), str(candidate)], capture_output=True)
            assert comparison.returncode == 1, comparison.stderr
            result = json.loads(comparison.stdout)
            assert result['first_difference'] is None
            assert result['gateway_receipt_comparison']['first_difference']['candidate'] == {'state': 'observed'}
            deployment_policy = 'undeclared'
            denied = client.get(url, params={'snapshot_id': snapshot}).json()
            assert denied['snapshot_id'] == snapshot
            assert denied['data_gateway']['status'] == 'export_not_authorized'
            assert denied['data_gateway']['events'] == []
    else:
        assert exported == {'status': 'export_not_authorized', 'events': []}
        assert paths == [BASE + 'contract', BASE + 'bind']


@pytest.mark.parametrize('lost', [True, False])
def test_registered_business_call_recovers_without_second_dispatch(lost):
    from unittest.mock import AsyncMock
    calls = []
    def respond(request):
        calls.append(request.method)
        return httpx.Response(200, json=CONTRACT if request.method == 'GET' else EXCHANGE['unknown'])

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            access = await GatewayInvestigation.discover(client, 'https://fixture.test/mcp', DECLARATION)
            gateway = AsyncMock()
            if lost:
                gateway.call.side_effect = GatewayError('gateway_timeout', result_unknown=True)
            else:
                gateway.call.return_value = {'isError': True, 'structuredContent': {'contract_version': VERSION,
                    'error': {'code': 'call_already_registered', 'automatic_retry': False}, 'receipt': EXCHANGE['unknown']}}
            meta = EXCHANGE['call']['_meta']
            scope = {k:v for k,v in meta['gateway/investigation'].items() if k != 'contract_version'}
            diagnostics = {**meta['gateway/diagnostics'], 'client_call_id': EXCHANGE['unknown']['client_call_id']}
            result = await access.call_registered(gateway, 'test', {}, {}, scope=scope, diagnostics=diagnostics)
            assert result == {'receipt': EXCHANGE['unknown']}
            gateway.call.assert_awaited_once()
    asyncio.run(run())
    assert calls == (['GET', 'POST'] if lost else ['GET'])


def test_bound_observation_rejects_override_before_binding_and_keeps_handle_private():
    from types import SimpleNamespace
    from capstone_agent.gateway_investigation import read_bound_observation
    calls = []
    def respond(request):
        calls.append(request.url.path)
        if request.method == 'GET':
            return httpx.Response(200, json=CONTRACT)
        body = json.loads(request.content)
        if request.url.path.endswith('/bind'):
            assert body['idempotency_key'] == body['investigation_id']
            return httpx.Response(200, json=EXCHANGE['binding'])
        assert body['binding_handle'] == EXCHANGE['binding']['binding_handle']
        return httpx.Response(200, json={'receipts': [], 'next_cursor': None})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            session = SimpleNamespace(instance_identity={'instance_id': 'fixture'}, http_client=client,
                                      investigation=DECLARATION, investigation_logs=None)
            args = dict(instance_id='fixture', workspace='local', investigation_id='inv_one', operation='list')
            with pytest.raises(GatewayError, match='investigation_request_invalid'):
                await read_bound_observation(session, 'https://fixture.test/mcp', **args, query={'workspace_id':'other'})
            assert calls == []
            result = await read_bound_observation(session, 'https://fixture.test/mcp', **args, query={'limit': 1})
            assert result == {'receipts': [], 'next_cursor': None}
    asyncio.run(run())
