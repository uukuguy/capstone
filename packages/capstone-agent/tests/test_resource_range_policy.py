from types import SimpleNamespace

from capstone_agent.native_task_context import native_context_for
from capstone_agent.continuation_resources import artifact_resource
from test_research_policy_compatibility import registered_binding


def context(submission):
    return native_context_for(SimpleNamespace(submission=submission, selected_task_reader=None),
                              registered_binding('1.0.0'))


def test_uploaded_source_publishes_optional_range_tool_without_first_action():
    resource = {'schema':'capstone-resource/1','thread_id':'thr_test',
                'resource_id':'resource_'+'a'*32,'version':1,'file_name':'data.txt',
                'size_bytes':12,'sha256':'a'*64}
    value = context({'_resource_manifests':[resource]})
    assert 'agent_resource_read' in value['policy']['allowed_tools']
    assert 'agent_resource_open' in value['policy']['allowed_tools']


def test_range_tool_does_not_grant_unselected_or_historical_artifact_bytes():
    assert 'agent_resource_read' not in context({})['policy']['allowed_tools']
    source = {'thread_id':'thr_test','attempt_id':'attempt_old','artifact_id':'artifact_old',
              'work_id':'work_old','file_name':'old.txt','size_bytes':12,
              'sha256':'a'*64,'source_status':'completed'}
    value = context({'_resource_manifests':[artifact_resource(source)],
                     '_continuation_artifacts':[source]})
    assert 'agent_resource_open' in value['policy']['allowed_tools']
    assert 'agent_resource_read' not in value['policy']['allowed_tools']
