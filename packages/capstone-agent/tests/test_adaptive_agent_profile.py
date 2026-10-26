"""The adaptive profile is a new exact publication, not a legacy rewrite."""
import json
from hashlib import sha256
from importlib.resources import files

from capstone_agent.native_task_context import registered_research_policy, research_policy_capabilities
from capstone_agent.task_planning_policy import task_planning_policy


def test_adaptive_loop_is_explicit_and_preserves_escalated_contracts():
    entry = registered_research_policy('1.19.0')
    assert entry.pack_version == '1.16.0'
    assert entry.adaptive_agent_loop
    assert entry.isolated_task_execution and entry.goal_driven_execution and entry.lightweight_task_nodes
    assert entry.graph_schema == 'capstone-enterprise-graph/2'
    assert entry.work_edition == 'capstone-graph-work/1'
    assert entry.work_policy() == registered_research_policy('1.18.0').work_policy()
    assert not registered_research_policy('1.18.0').adaptive_agent_loop
    shared = task_planning_policy('1.6.0')
    assert shared.text in entry.system_policy
    assert 'At each reasoning and tool cycle' in shared.text
    assert 'Deep Research starts inactive by default' in shared.text
    assert 'autonomously activate Deep Research' in shared.text
    assert 'manual toggle' in shared.text
    assert 'explicitly host-admitted raw sources' in shared.text
    assert 'capstone-task-return/1' in entry.system_policy
    assert 'agent_research_plan' not in shared.text


def test_adaptive_publication_preserves_every_old_catalog_entry():
    catalog = json.loads(files('capstone_agent').joinpath('resources/research-policy-catalog.json').read_text())['policies']
    old = [item for item in catalog if item['application_version'] != '1.19.0']
    assert sha256(json.dumps(old, ensure_ascii=False, sort_keys=True).encode()).hexdigest() == '9ac1235c496698f3b76a7fe412cb497c8f8e9d4c22052d2c46fa25408254426d'


def test_published_adaptive_profile_is_default_but_frozen_older_binding_stays_old():
    from capstone_agent.native_conversation import executor_binding, binding_for_session, validate_binding
    from test_enterprise_normal_chat import native_executor
    executor = native_executor()
    executor.capability.update({
        'research_bridge_schemas': ['capstone-research-bridge/1'],
        'research_graph_schemas': ['capstone-enterprise-graph/2'],
        'research_policy_profiles': research_policy_capabilities(),
    })
    current = executor_binding(executor)
    assert current['application_profile']['profile_version'] == '1.19.0'
    assert validate_binding(current) == current
    assert binding_for_session(current, 'general-chat')['application_profile'] == current['application_profile']
    old = executor_binding(executor, profile_version='1.18.0')
    assert validate_binding(old) == old
    executor.capability['research_policy_profiles'] = [registered_research_policy('1.18.0').capability()]
    assert executor_binding(executor)['application_profile']['profile_version'] == '1.18.0'
