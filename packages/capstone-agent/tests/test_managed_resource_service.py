import json
from unittest.mock import Mock
import pytest
from capstone_agent.managed_resource_service import ManagedResourceService
from capstone_agent.managed_resources import ManagedResourceStore
from capstone_agent.resource_permissions import ResourcePermissions, ResourcePrincipal, ResourcePermissionDenied

P = ResourcePrincipal('operator', ())


def service(tmp_path, profile='local'):
    from pathlib import Path
    policy=Path(__file__).parents[3]/'configs/runtime/resource-permissions.json'
    store=ManagedResourceStore(tmp_path/'resources', ResourcePermissions(policy,profile))
    return ManagedResourceService(store, Mock(max_files=10000,max_bytes=4294967296))


def test_list_is_workspace_scoped_and_declares_permissions(tmp_path):
    app=service(tmp_path)
    result=app.invoke(P,'workspace','list',{})
    assert result['resources']==[]
    assert 'resources.install' in result['allowed_actions']
    assert result['revision'].startswith('sha256:')


def test_published_install_contract_is_enforced_before_adapter(tmp_path):
    from jsonschema import Draft202012Validator
    app=service(tmp_path)
    contract=app.invoke(P,'workspace','list',{})['operation_contracts']['install']
    request={'request_id':'one','resource_id':'sample','request':{'kind':'mcp_local',
        'source':{'locator':'https://example.org/repo','revision':'a'*40},
        'runtime':{'entrypoint':'server.py','secret_refs':['secret:api']},
        'dependencies':['example==1.0']}}
    assert Draft202012Validator(contract).is_valid(request)
    request['request']['runtime']['entryPoint']=request['request']['runtime'].pop('entrypoint')
    assert not Draft202012Validator(contract).is_valid(request)
    with pytest.raises(ValueError,match='resource_request_fields_invalid'):
        app.invoke(P,'workspace','install',request)
    app.installer.install.assert_not_called()


@pytest.mark.parametrize('operation,body',[
    ('list',{'roles':['admin']}), ('state',{'resource_id':'one','enabled':True,'expected_version':'x','principal':'admin'}),
    ('install',{'request_id':'one','resource_id':'one','request':{},'workspace':'other'}),
    ('preinstall_import',{'manifest':{},'replace':'yes'}),
])
def test_rejects_untrusted_fields_before_installation(tmp_path,operation,body):
    app=service(tmp_path)
    with pytest.raises(ValueError):app.invoke(P,'workspace',operation,body)
    app.installer.install.assert_not_called()


def test_intranet_returns_use_only_actions(tmp_path):
    result=service(tmp_path,'intranet').invoke(P,'workspace','list',{})
    assert result['allowed_actions']==['resources.use']
