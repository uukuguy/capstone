from pathlib import Path
import pytest
from capstone_agent.managed_resource_task import resource_task_action
from capstone_agent.managed_resource_service import ManagedResourceService
from test_managed_resource_installation import context, installer, request, P


def test_skill_load_is_versioned_readonly_and_revocation_blocks_next_call(context,tmp_path):
    engine=installer(context);store,_,_=context
    item=engine.install(P,'w','install','example',request())['result']
    service=ManagedResourceService(store,engine)
    document={'resource_id':'example','version':item['version']}
    result=resource_task_action(service,P,'w','load_skill',document,inputs=tmp_path/'inputs')
    path=Path(result['result']['skills'][0]['path'])
    assert path.read_text().startswith('---')
    assert path.stat().st_mode&0o222==0
    assert result['resource_version']==item['version']
    store.set_enabled(P,'w','example',False,item['version'])
    with pytest.raises(RuntimeError,match='unavailable'):
        resource_task_action(service,P,'w','load_skill',document,inputs=tmp_path/'inputs')
    for entry in [path.parent,*path.parent.rglob('*')]:entry.chmod(0o755 if entry.is_dir() else 0o644)


def test_task_cannot_load_other_workspace_resource(context,tmp_path):
    engine=installer(context);store,_,_=context
    item=engine.install(P,'w','install','example',request())['result']
    with pytest.raises(KeyError):resource_task_action(ManagedResourceService(store,engine),P,'other','load_skill',
        {'resource_id':'example','version':item['version']},inputs=tmp_path/'inputs')


def test_skill_directory_cycle_is_preserved_without_recursive_copy(context,tmp_path):
    engine=installer(context);store,source,_=context
    (source/'loop').symlink_to('.',target_is_directory=True)
    item=engine.install(P,'w','install','example',request())['result']
    result=resource_task_action(ManagedResourceService(store,engine),P,'w','load_skill',
        {'resource_id':'example','version':item['version']},inputs=tmp_path/'inputs')
    root=Path(result['result']['skills'][0]['path']).parent
    assert (root/'loop').is_symlink()
    assert len(list(root.iterdir()))==3
    for entry in [root,*root.rglob('*')]:
        if not entry.is_symlink():entry.chmod(0o755 if entry.is_dir() else 0o644)


def test_existing_partial_skill_copy_is_rejected(context,tmp_path):
    engine=installer(context);store,_,_=context
    item=engine.install(P,'w','install','example',request())['result']
    from capstone_agent.managed_resource_manifest import content_digest
    target=tmp_path/'inputs'/('managed-'+content_digest(['example',item['version']]).split(':')[1])
    target.mkdir(parents=True);(target/'SKILL.md').write_text('partial')
    with pytest.raises(ValueError,match='identity_changed'):
        resource_task_action(ManagedResourceService(store,engine),P,'w','load_skill',
            {'resource_id':'example','version':item['version']},inputs=tmp_path/'inputs')


def test_mcp_does_not_adopt_changed_contract_without_update(context,tmp_path):
    from unittest.mock import Mock
    from capstone_agent.managed_resource_installation import ManagedResourceInstaller,InstallRequest
    from capstone_agent.managed_resource_manifest import SourceIdentity
    from capstone_agent.managed_resource_mcp import ManagedMcpError
    store,_,_=context
    catalog={'tools':[],'instructions':'test','server_info':{},'revision':'sha256:'+'a'*64}
    engine=ManagedResourceInstaller(store,check_network=lambda _:None,probe_remote=lambda *a:catalog)
    item=engine.install(P,'w','install','remote',InstallRequest('mcp_remote',SourceIdentity('https://example.org/mcp','discover')))['result']
    service=ManagedResourceService(store,engine)
    service.invoke_mcp=Mock(return_value={**catalog,'revision':'sha256:'+'b'*64})
    with pytest.raises(ManagedMcpError,match='contract_changed'):
        resource_task_action(service,P,'w','discover',{'resource_id':'remote','version':item['version']},inputs=tmp_path)
    service.invoke_mcp.reset_mock()
    with pytest.raises(ManagedMcpError,match='contract_changed'):
        resource_task_action(service,P,'w','call',{'resource_id':'remote','version':item['version'],
            'name':'new_tool','arguments':{},'catalog_revision':'sha256:'+'b'*64},inputs=tmp_path)
    service.invoke_mcp.assert_not_called()


def test_completed_mcp_result_survives_policy_revocation_after_dispatch(context,tmp_path):
    from capstone_agent.managed_resource_installation import ManagedResourceInstaller,InstallRequest
    from capstone_agent.managed_resource_manifest import SourceIdentity
    store,_,policy=context
    catalog={'tools':[],'instructions':'test','server_info':{},'revision':'sha256:'+'a'*64}
    engine=ManagedResourceInstaller(store,check_network=lambda _:None,probe_remote=lambda *a:catalog)
    item=engine.install(P,'w','install','remote',InstallRequest('mcp_remote',SourceIdentity('https://example.org/mcp','discover')))['result']
    service=ManagedResourceService(store,engine)
    def invoke(*args,**kwargs):
        policy.write_text(policy.read_text().replace('"allow"','"deny"'))
        return {'content':[{'type':'text','text':'completed'}]}
    service.invoke_mcp=invoke
    result=resource_task_action(service,P,'w','call',{'resource_id':'remote','version':item['version'],
        'name':'one','arguments':{},'catalog_revision':catalog['revision']},inputs=tmp_path)
    assert result['result']['content'][0]['text']=='completed'
