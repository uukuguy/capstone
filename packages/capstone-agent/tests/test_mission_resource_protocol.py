"""Frozen application resources keep only their registered bounded readers."""
from types import SimpleNamespace
from copy import deepcopy
import pytest

from capstone_agent.native_task_context import native_context_for,checked_native_context
from capstone_agent.native_mission import registry_revision
from capstone_agent.native_conversation import executor_binding
from capstone_agent.business_context import BusinessContext
from capstone_agent.pi_delegation import PiTaskRequest
from capstone_agent.resource_manifest import checked_resource
from test_enterprise_normal_chat import native_executor


@pytest.mark.parametrize('source_kind',['none','resource','delegated','denied'])
def test_actual_context_factory_and_immutable_task_keep_only_source_protocol_helpers(source_kind):
    binding=executor_binding(native_executor())
    resource=checked_resource(dict(schema='capstone-resource/1',resource_id='resource_'+'a'*32,version=1,
        thread_id='thread_1',file_name='source.txt',size_bytes=5,sha256='b'*64))
    selection=dict(schema='capstone-mission-tool-selection/1',allowed_tools=['write'],
        denied_tools=['agent_resource_open','agent_resource_read'] if source_kind=='denied' else [])
    submission={'_mission_equipment':selection,'_mission_equipment_binding_revision':registry_revision(binding)}
    if source_kind!='none':
        submission['_resource_manifests']=[resource]
    if source_kind=='delegated':
        submission['_delegation_resources']=[{'resource':resource}]
    context=native_context_for(SimpleNamespace(submission=submission,selected_task_reader=None),binding)
    expected={'write'}
    if source_kind in {'resource','delegated'}:expected.add('agent_resource_open')
    if source_kind=='resource':expected.add('agent_resource_read')
    assert set(context['policy']['allowed_tools'])==expected
    request=PiTaskRequest('task_resource','attempt_resource','direct','Inspect the admitted source',(),(),binding['identity'],30,
        business_context=BusinessContext.empty('thread_1',12),resource_profile={'profile_id':'general','revision':'test'},
        input={'kind':'text','text':'Inspect the admitted source'},native_context=context)
    assert not isinstance(request.native_context,dict)
    normalized=request.to_document()['native_context']
    assert set(checked_native_context(normalized)['policy']['allowed_tools'])==expected
    invalid=deepcopy(normalized);invalid['policy']['allowed_tools'].append('bash')
    with pytest.raises(ValueError):checked_native_context(invalid)
    if source_kind=='none':
        invalid=deepcopy(normalized);invalid['policy']['allowed_tools'].append('agent_resource_open')
        with pytest.raises(ValueError):checked_native_context(invalid)
