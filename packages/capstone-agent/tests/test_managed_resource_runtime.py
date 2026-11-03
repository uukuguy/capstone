from pathlib import Path
from types import SimpleNamespace
import pytest
from capstone_agent.managed_resource_runtime import create_managed_resource_service
from capstone_agent.resource_permissions import ResourcePrincipal, ResourcePermissionDenied

P=ResourcePrincipal('operator',())
POLICY=Path(__file__).parents[3]/'configs/runtime/resource-permissions.json'


def service(tmp_path,profile):
    return create_managed_resource_service(tmp_path/'managed',network_policy=SimpleNamespace(
        state=lambda:{'enforced':True,'external_access':False}),environment={
        'CAPSTONE_RESOURCE_POLICY_FILE':str(POLICY),'CAPSTONE_RESOURCE_PERMISSION_PROFILE':profile})


def test_network_disabled_install_is_persisted_failure_without_publication(tmp_path):
    app=service(tmp_path,'local')
    result=app.invoke(P,'w','install',{'request_id':'request','resource_id':'server','request':{
        'kind':'mcp_remote','source':{'locator':'https://example.org/mcp','revision':'discover'}}})
    assert result['status']=='failed'
    assert result['diagnostic']=='resource_network_disabled'
    assert app.invoke(P,'w','list',{})['resources']==[]
    assert service(tmp_path,'local').invoke(P,'w','operation',{'request_id':'request'})==result


def test_intranet_management_is_denied_before_receipt_is_created(tmp_path):
    app=service(tmp_path,'intranet')
    with pytest.raises(ResourcePermissionDenied):
        app.invoke(P,'w','install',{'request_id':'request','resource_id':'server','request':{
            'kind':'mcp_remote','source':{'locator':'https://example.org/mcp','revision':'discover'}}})
    with pytest.raises(KeyError):app.invoke(P,'w','operation',{'request_id':'request'})


def test_missing_profile_is_closed(tmp_path):
    app=service(tmp_path,'')
    with pytest.raises(ResourcePermissionDenied):app.invoke(P,'w','list',{})


def test_closed_task_cannot_create_late_mcp_session(tmp_path):
    from capstone_agent.managed_resource_mcp import ManagedMcpError
    app=service(tmp_path,'local')
    item={'resource_id':'remote','version':'v1','kind':'mcp_remote','package_ref':'',
          'source':{'locator':'https://example.org/mcp'},'runtime':{'secret_refs':[]}}
    app.open_task('task')
    assert app.task_is_open('task')
    app.close_task('task')
    assert not app.task_is_open('task')
    with pytest.raises(ManagedMcpError,match='resource_task_closed') as caught:
        app.invoke_mcp(item,None,session_key='task')
    assert caught.value.executed is False
