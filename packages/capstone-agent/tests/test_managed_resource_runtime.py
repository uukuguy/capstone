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
