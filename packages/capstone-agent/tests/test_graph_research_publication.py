"""Graph execution is a new exact publication, never a legacy reinterpretation."""
import pytest


def test_autonomous_work_publication_is_new_with_exact_config_and_no_legacy_upgrade():
    from capstone_agent.native_task_context import registered_research_policy
    from capstone_agent.native_conversation import executor_binding
    from test_enterprise_normal_chat import native_executor
    from capstone_agent.native_task_context import research_policy_capabilities
    selected = registered_research_policy('1.12.0')
    assert selected.pack_version == '1.10.0'
    assert selected.work_edition == 'capstone-graph-work/1'
    assert selected.work_policy()['target_seconds'] == 240
    assert selected.work_policy()['integration_reserve_seconds'] == 60
    assert registered_research_policy('1.11.0').work_edition is None
    assert 'graph_work_policy_sha256' in selected.capability()
    executor = native_executor()
    executor.capability = {**executor.capability, 'research_bridge_schemas': ['capstone-research-bridge/1'],
        'research_graph_schemas': ['capstone-enterprise-graph/2'], 'research_policy_profiles': research_policy_capabilities()}
    assert executor_binding(executor)['application_profile']['profile_version'] == '1.19.0'
    from types import SimpleNamespace
    from capstone_agent.native_task_context import native_context_for, checked_native_context
    binding = executor_binding(executor, profile_version='1.12.0')
    with pytest.raises(ValueError, match='trusted attempt start'):
        native_context_for(SimpleNamespace(submission=None, selected_task_reader=None), binding)
    context = native_context_for(SimpleNamespace(submission=None, selected_task_reader=None, started_at='2026-10-21T06:00:00Z'), binding)
    assert checked_native_context(context) == context
    missing = {key: value for key, value in context.items() if key != 'graph_work'}
    with pytest.raises(ValueError, match='trusted attempt origin'):
        checked_native_context(missing)
    old_context = native_context_for(SimpleNamespace(submission=None, selected_task_reader=None), executor_binding(executor, profile_version='1.11.0'))
    assert 'graph_work' not in old_context
    with pytest.raises(ValueError, match='edition is not selected'):
        checked_native_context({**old_context, 'graph_work': context['graph_work']})
    executor.capability['research_policy_profiles'] = [item for item in research_policy_capabilities() if item['profile_version'] != '1.12.0']
    with pytest.raises(ValueError, match='policy profile is unavailable'):
        executor_binding(executor, profile_version='1.12.0')


def test_whole_chain_publication_is_new_and_all_prior_policy_entries_stay_exact():
    from hashlib import sha256
    from importlib.resources import files
    import json
    from capstone_agent.native_task_context import registered_research_policy
    from capstone_agent.native_conversation import executor_binding
    from test_enterprise_normal_chat import native_executor
    selected = registered_research_policy('1.11.0')
    assert selected.pack_version == '1.9.0' and selected.graph_schema == 'capstone-enterprise-graph/2'
    old = [item for item in json.loads(files('capstone_agent').joinpath('resources/research-policy-catalog.json').read_text())['policies'] if item['application_version'] not in {'1.12.0', '1.13.0', '1.14.0', '1.15.0', '1.16.0', '1.17.0', '1.18.0', '1.19.0'}]
    assert sha256(json.dumps([item for item in old if item['application_version'] != '1.11.0'], ensure_ascii=False, sort_keys=True).encode()).hexdigest() == '146788234e7783fab1fae644a418ddd7c33fd489aa489fed35f1df66f0425369'
    executor = native_executor()
    from capstone_agent.native_task_context import research_policy_capabilities
    executor.capability = {**executor.capability, 'research_bridge_schemas': ['capstone-research-bridge/1'],
        'research_graph_schemas': ['capstone-enterprise-graph/2'], 'research_policy_profiles': research_policy_capabilities()}
    assert executor_binding(executor)['application_profile']['profile_version'] == '1.19.0'
    executor.capability = {**executor.capability, 'research_policy_profiles': [item for item in executor.capability['research_policy_profiles'] if item['profile_version'] != '1.11.0']}
    with pytest.raises(ValueError, match='policy profile is unavailable'):
        executor_binding(executor, profile_version='1.11.0')


def test_graph_research_publication_keeps_legacy_assets_and_selects_exact_tools():
    from capstone_agent.enterprise_application import resolve_native_profile
    from capstone_agent.native_research_bridge import research_tools_for_profile
    from capstone_agent.native_task_context import registered_research_policy
    old = registered_research_policy('1.9.0')
    assert old.pack_version == '1.7.0'
    assert old.policy_sha256 == '11a8ded88137ebf4124d552fd2b67ebd891607efcc932b5d844c3165de23ca0d'
    assert old.guides_sha256 == 'c811c01914ee1e1010dd7614e6ce0e0d10af4ffa4a0c3a98dd0ac6ac68372ab4'
    selected = registered_research_policy('1.10.0')
    from enterprise_research import ResearchPolicy
    assert ResearchPolicy('1.8.0').load() in selected.system_policy
    assert selected.pack_version == '1.8.0'
    assert selected.graph_schema == 'capstone-enterprise-graph/2'
    assert old.graph_schema is None
    assert resolve_native_profile('enterprise-research', '1.10.0').manifest.version == '1.10.0'
    tools = research_tools_for_profile('enterprise-research', '1.10.0')
    assert {'agent_research_plan', 'agent_research_start', 'agent_research_record',
            'agent_research_assess', 'agent_research_revise', 'agent_research_resolve',
            'agent_research_inspect', 'agent_research_finish'} <= set(tools)
    assert not {'agent_research_update', 'agent_delegate', 'agent_research_cycle'} & set(tools)
    assert 'agent_delegate' in research_tools_for_profile('enterprise-research', '1.9.0')


def test_graph_profile_requires_the_explicit_host_graph_protocol():
    from capstone_agent.native_conversation import executor_binding
    from capstone_agent.native_task_context import registered_research_policy
    from test_enterprise_normal_chat import native_executor
    executor = native_executor()
    executor.capability = {**executor.capability,
        'research_bridge_schemas': ['capstone-research-bridge/1'],
        'research_policy_profiles': [registered_research_policy('1.10.0').capability()]}
    with pytest.raises(ValueError, match='graph'):
        executor_binding(executor, profile_version='1.10.0')
    executor.capability['research_graph_schemas'] = ['capstone-enterprise-graph/2']
    binding = executor_binding(executor, profile_version='1.10.0')
    assert binding['application_profile']['profile_version'] == '1.10.0'
    assert binding['pack_bindings'][0]['pack_version'] == '1.8.0'


def test_native_host_publishes_the_explicit_graph_protocol(tmp_path):
    from capstone_agent.general_pi_server import GeneralPiHost
    host = GeneralPiHost(root=tmp_path, identity={'engine': 'pi'},
        run_task=lambda *_: ('unused', {}))
    assert host.capability['research_graph_schemas'] == ['capstone-enterprise-graph/2']


@pytest.mark.parametrize('version', ['1.10.0', '1.9.0', '1.12.0', '1.13.0', '1.14.0', '1.15.0', '1.16.0', '1.17.0', '1.18.0', '1.19.0'])
def test_real_worker_request_keeps_selected_graph_or_legacy_research_binding(tmp_path, version):
    from dataclasses import replace
    from capstone_agent.intent_runtime import IntentRuntimeFactory
    from capstone_agent.native_task_context import registered_research_policy, resolve_research_policy
    from capstone_agent.thread_service import InMemoryThreadService
    from capstone_agent.thread_worker import run_pending_attempt
    from test_enterprise_normal_chat import native_executor
    from test_thread_postgres import _snapshot
    from test_thread_work_execution import command

    thread_id = 'thread_publication'
    store = InMemoryThreadService(replace(_snapshot(thread_id), active_model_context=None,
        active_grid_page_id=None, minimum_protocol_version=2))
    executor = native_executor()
    executor.capability = {**executor.capability,
        'research_bridge_schemas': ['capstone-research-bridge/1'],
        'delivery_review_schemas': ['capstone-delivery-review/1'],
        'research_graph_schemas': ['capstone-enterprise-graph/2'] if version in {'1.10.0', '1.12.0', '1.13.0', '1.14.0', '1.15.0', '1.16.0', '1.17.0', '1.18.0', '1.19.0'} else [],
        'research_policy_profiles': [registered_research_policy(version).capability()]}
    executor.execute_with_research = lambda request, control, emit, bridge: executor.execute(request, control, emit)
    store.set_native_executor(executor)
    receipt = store.submit_command(command(store, thread_id, 'send_message', 'publication',
        payload={'text': 'Inspect the admitted sources and report limitations.'}))
    assert receipt.status == 'accepted'
    result = run_pending_attempt(store, IntentRuntimeFactory(None, None, None,
        general_executor=executor, native_research_root=tmp_path),
        worker_id='publication-worker', implementation_family='native')
    assert result.status == 'completed'
    assert len(executor.requests) == 1
    request = executor.requests[0].to_document()
    selected = resolve_research_policy(request['native_context']['policy']['system_policy'])
    assert selected.application_version == version
    assert request['research_binding']['cycle_owner']['thread_id'] == thread_id
    assert request['research_binding'].get('graph_schema') == selected.graph_schema
    if version in {'1.12.0', '1.13.0', '1.14.0', '1.15.0', '1.16.0', '1.17.0', '1.18.0', '1.19.0'}:
        assert request['research_binding']['graph_work_edition'] == selected.work_edition
        assert request['native_context']['graph_work']['started_at_ms'] > 0
    else:
        assert 'graph_work' not in request['native_context']
