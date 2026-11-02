from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from capstone_agent.managed_resource_http import register_managed_resource_routes
from capstone_agent.resource_permissions import ResourcePermissionDenied


def client(backend, allowed=True):
    app=FastAPI()
    @app.middleware('http')
    async def context(request,call_next):
        request.state.workspace_name='trusted-workspace'
        return await call_next(request)
    def authorize(request):
        if not allowed:raise HTTPException(403)
    register_managed_resource_routes(app,executor_provider=lambda:SimpleNamespace(managed_resources=backend),authorize=authorize)
    return TestClient(app)


def test_list_and_install_forward_only_workspace_context():
    backend=Mock(return_value={'status':'succeeded'})
    api=client(backend)
    assert api.get('/api/v1/managed-resources').status_code==200
    backend.assert_called_once_with('trusted-workspace','list',{})
    body={'request_id':'req','resource_id':'one','request':{'kind':'skill'}}
    assert api.post('/api/v1/managed-resources/operations/install',json=body).status_code==200
    backend.assert_called_with('trusted-workspace','install',body)


def test_authorization_denies_before_backend():
    backend=Mock()
    assert client(backend,False).post('/api/v1/managed-resources/operations/install',json={}).status_code==403
    backend.assert_not_called()


@pytest.mark.parametrize('error,status',[(ResourcePermissionDenied(),403),(KeyError('secret'),404),(ValueError('secret token'),422)])
def test_errors_are_classified_without_private_messages(error,status):
    backend=Mock(side_effect=error)
    response=client(backend).get('/api/v1/managed-resources')
    assert response.status_code==status
    assert 'secret' not in response.text


def test_operation_status_uses_receipt_not_repeated_install():
    backend=Mock(return_value={'status':'pending'})
    assert client(backend).get('/api/v1/managed-resources/operations/req').status_code==200
    backend.assert_called_once_with('trusted-workspace','operation',{'request_id':'req'})
