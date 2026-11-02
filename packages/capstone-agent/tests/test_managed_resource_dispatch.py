from unittest.mock import Mock
import pytest
from capstone_agent.managed_resource_dispatch import dispatch_resource_request
from capstone_agent.resource_permissions import ResourcePermissionDenied
from capstone_agent.pi_delegation import HttpGeneralPiExecutor


def test_dispatch_owns_principal_and_rejects_role_injection():
    service=Mock();service.invoke.return_value={'resources':[]}
    body={'workspace':'enterprise','operation':'list','document':{}}
    assert dispatch_resource_request(service,body)['ok']
    principal,workspace,_,_=service.invoke.call_args.args
    assert principal.subject=='workspace:enterprise' and principal.roles==()
    service.reset_mock()
    assert not dispatch_resource_request(service,{**body,'principal':{'roles':['admin']}})['ok']
    service.invoke.assert_not_called()


def test_denial_has_typed_transport_receipt():
    service=Mock();service.invoke.side_effect=ResourcePermissionDenied()
    result=dispatch_resource_request(service,{'workspace':'enterprise','operation':'install','document':{}})
    assert result=={'ok':False,'kind':'permission','code':'resource_permission_denied'}


def test_executor_uses_existing_protected_transport_with_keyword_body():
    executor=object.__new__(HttpGeneralPiExecutor)
    def call(method,path,*,document,timeout,total_timeout):
        assert method=='POST' and path=='/managed-resources'
        assert document=={'workspace':'enterprise','operation':'list','document':{}}
        return {'ok':True,'result':{'resources':[]}}
    executor._call=call
    assert executor.managed_resources('enterprise','list',{})=={'resources':[]}
