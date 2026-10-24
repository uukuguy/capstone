"""Exact public resource snapshots preserve accepted tasks, never caller policy."""
import copy
import json
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest

from capstone_agent.native_task_context import checked_native_context


def registered_binding(version, variant='default'):
    from capstone_agent.native_conversation import executor_binding
    from capstone_agent.native_task_context import research_policy_capabilities
    from test_enterprise_normal_chat import native_executor
    executor = native_executor()
    executor.capability = {**executor.capability, 'research_bridge_schemas': ['capstone-research-bridge/1'],
        'delivery_review_schemas': ['capstone-delivery-review/1'],
        'research_policy_profiles': research_policy_capabilities()}
    return executor_binding(executor, profile_version=version, _policy_variant=variant)


def test_parallel_planning_publication_preserves_baseline_and_selects_existing_graph_runtime():
    from capstone_agent.native_task_context import registered_research_policy, research_policy_capabilities
    from capstone_agent.native_conversation import executor_binding, validate_binding
    from capstone_agent.native_research_bridge import research_tools_for_profile, GRAPH_CONTROL_TOOLS
    from test_enterprise_normal_chat import native_executor
    baseline = registered_research_policy('1.12.0')
    entry = registered_research_policy('1.13.0')
    assert entry.pack_version == '1.11.0'
    assert entry.graph_schema == baseline.graph_schema == 'capstone-enterprise-graph/2'
    assert entry.work_edition == baseline.work_edition == 'capstone-graph-work/1'
    assert entry.work_policy() == baseline.work_policy()
    assert 'Prefer cohesive execution when splitting repeats' in baseline.system_policy
    assert 'Prefer cohesive execution when splitting repeats' not in entry.system_policy
    assert 'Shared preparation is a producer dependency, not a reason to collapse' in entry.system_policy
    assert 'bounded delegated nodes' in entry.system_policy
    executor = native_executor()
    executor.capability = {**executor.capability, 'research_bridge_schemas': ['capstone-research-bridge/1'],
        'research_graph_schemas': ['capstone-enterprise-graph/2'], 'research_policy_profiles': research_policy_capabilities()}
    binding = executor_binding(executor)
    assert binding['application_profile']['profile_version'] == '1.18.0'
    assert validate_binding(binding) == binding
    assert set(GRAPH_CONTROL_TOOLS).issubset(research_tools_for_profile('enterprise-research', '1.13.0'))
    assert registered_research_policy('1.12.0') == baseline
    from importlib.resources import files
    old_entries = [item for item in json.loads(files('capstone_agent').joinpath('resources/research-policy-catalog.json').read_text())['policies'] if item['application_version'] not in {'1.13.0', '1.14.0', '1.15.0', '1.16.0', '1.17.0', '1.18.0'}]
    assert sha256(json.dumps(old_entries, ensure_ascii=False, sort_keys=True).encode()).hexdigest() == '1744bf335858b1d814e099a4780a7d37087c097d6fd0d9f2bdd8f5336a38560f'


def test_actually_deployed_review_context_roundtrips_without_policy_replacement():
    context = json.loads((Path(__file__).parent / 'fixtures/research-policy-deployed-context.json').read_text())
    assert sha256(context['policy']['system_policy'].encode()).hexdigest() == '6da560c3b1f12f7078585f030a1e4ae3fb2e4a12a76bb58183ebe640dd6085a1'
    assert checked_native_context(context) == context


def test_automatic_batch_policy_publishes_host_subtasks_without_replacing_frozen_manual_policy():
    from enterprise_research import ResearchGuides
    from capstone_agent.native_task_context import registered_research_policy
    from capstone_agent.native_research_bridge import research_tools_for_profile
    from capstone_agent.native_conversation import binding_for_session, validate_binding
    frozen = registered_binding('1.6.0')
    original = copy.deepcopy(frozen)
    entry = registered_research_policy('1.7.0')
    guide = ResearchGuides('1.6.0').open('research-method')['text']
    assert entry.pack_version == '1.6.0'
    assert entry.delivery_review and entry.graceful_execution_closure
    for text in (entry.system_policy, guide):
        assert 'objective.subtasks' in text
        assert 'host dispatches' in text
        assert 'one combined objective' in text
        assert 'do not solve the branches in the parent first' in text
    assert 'run one agent_delegate batch' not in guide
    current = binding_for_session(frozen, 'enterprise-research')
    assert current['application_profile']['profile_version'] == '1.9.0'
    assert validate_binding(current) == current
    assert frozen == original
    assert 'agent_delegate' in research_tools_for_profile('enterprise-research', '1.7.0')
    old = registered_research_policy('1.6.0')
    assert 'one\nagent_delegate call' in old.system_policy


def test_explicit_subtask_schema_is_selected_only_by_the_new_publication():
    from capstone_agent.native_task_context import registered_research_policy
    entry = registered_research_policy('1.8.0')
    assert entry.pack_version == '1.7.0'
    assert entry.explicit_subtask_planning is True
    assert 'Every objective and assessment follow-up must explicitly declare subtasks' in entry.system_policy
    for version in ['1.1.0', '1.2.0', '1.3.0', '1.4.0', '1.5.0', '1.6.0', '1.7.0']:
        assert registered_research_policy(version).explicit_subtask_planning is False


def test_ready_graph_batching_is_versioned_and_does_not_change_older_execution():
    from capstone_agent.native_task_context import registered_research_policy
    current = registered_research_policy('1.9.0')
    assert current.pack_version == '1.7.0'
    assert current.explicit_subtask_planning and current.batch_ready_investigations
    assert 'identical downstream consumer sets' in current.system_policy
    assert registered_research_policy('1.8.0').batch_ready_investigations is False


def test_deployed_request_serialization_and_host_submission_keep_exact_context(tmp_path):
    import time
    from capstone_agent.business_context import BusinessContext
    from capstone_agent.general_pi_server import GeneralPiHost
    from capstone_agent.native_research_bridge import WorkerResearchBridge
    from capstone_agent.pi_delegation import PiTaskRequest
    from test_native_research_bridge import _cycle_progress_fixture, research
    context = json.loads((Path(__file__).parent / 'fixtures/research-policy-deployed-context.json').read_text())
    worker = research(tmp_path / 'worker')
    binding, _, _, _ = _cycle_progress_fixture(tmp_path / 'fixture', worker=worker)
    bridge = WorkerResearchBridge(worker.channel, owner_id='a' * 64, producer_binding=binding)
    received = []
    host = GeneralPiHost(root=tmp_path / 'host', identity={'engine': 'pi'},
        run_task=lambda request, *_: received.append(request) or ('Saved answer', {}))
    host.capability['native_tools'] = ['read', 'bash', 'edit', 'write']
    request = PiTaskRequest('deployed-policy', binding['attempt_id'], 'direct', 'Continue', (), (), host.identity, 2,
        business_context=BusinessContext.empty('workspace', 0),
        resource_profile={'profile_id': 'direct_pi', 'revision': 'test'},
        input={'kind': 'text', 'text': 'Continue'}, native_context=context, research_binding=binding)
    wire = request.to_document()
    restored = PiTaskRequest.from_document(wire)
    assert restored.to_document() == wire
    assert restored.to_document()['native_context'] == context
    host.submit(restored)
    host.research_mirror(request.task_id).bootstrap('a' * 64, bridge.bootstrap())
    deadline = time.monotonic() + 2
    while host.read(request.task_id)['status'] == 'running' and time.monotonic() < deadline:
        time.sleep(.005)
    assert host.read(request.task_id)['status'] == 'completed'
    assert received[0].to_document()['native_context'] == context


def test_review_profiles_select_only_an_exact_supported_new_policy():
    from capstone_agent.native_conversation import executor_binding
    from capstone_agent.native_task_context import research_policy_capabilities
    from test_enterprise_normal_chat import native_executor
    executor = native_executor()
    executor.capability = {**executor.capability, 'research_bridge_schemas': ['capstone-research-bridge/1'],
                          'delivery_review_schemas': ['capstone-delivery-review/1']}
    assert executor_binding(executor)['application_profile']['profile_version'] == '1.3.0'
    with pytest.raises(ValueError, match='policy.*unavailable|profile.*unavailable'):
        executor_binding(executor, profile_version='1.4.0')
    executor.capability['research_policy_profiles'] = research_policy_capabilities()
    current = executor_binding(executor)
    assert current['application_profile']['profile_version'] == '1.9.0'
    assert current['pack_bindings'][0]['pack_version'] == '1.7.0'
    executor.capability['research_policy_profiles'] = copy.deepcopy(research_policy_capabilities())
    selected = next(profile for profile in executor.capability['research_policy_profiles']
                    if profile['profile_version'] == '1.9.0' and profile.get('variant', 'default') == 'default')
    selected['system_policy_sha256'] = 'a' * 64
    assert executor_binding(executor)['application_profile']['profile_version'] == '1.8.0'
    with pytest.raises(ValueError, match='policy.*unavailable'):
        executor_binding(executor, profile_version='1.9.0')


def test_usable_draft_profile_is_versioned_and_preserves_exact_older_policy():
    from capstone_agent.native_task_context import registered_research_policy
    from capstone_agent.native_conversation import binding_for_session
    old = registered_binding('1.4.0')
    latest = binding_for_session(old, 'enterprise-research')
    assert latest['application_profile']['profile_version'] == '1.9.0'
    assert old['application_profile']['profile_version'] == '1.4.0'
    entry = registered_research_policy('1.5.0')
    assert entry.pack_version == '1.4.0'
    assert entry.graceful_execution_closure is True
    assert registered_research_policy('1.4.0').graceful_execution_closure is False
    assert 'first usable draft' in entry.system_policy
    assert 'human review' in entry.system_policy
    assert 'not a delivery gate' in entry.system_policy


def test_parallel_planning_publication_is_exact_versioned_and_preserves_older_snapshots():
    from enterprise_research import ResearchGuides
    from capstone_agent.native_task_context import registered_research_policy
    from capstone_agent.native_research_bridge import research_tools_for_profile
    from capstone_agent.native_conversation import binding_for_session
    entry = registered_research_policy('1.6.0')
    assert entry.pack_version == '1.5.0'
    assert entry.delivery_review and entry.graceful_execution_closure
    assert 'prefer one accepted research objective' in entry.system_policy
    assert 'two or more substantial independent questions' in entry.system_policy
    assert 'not an execution gate' in entry.system_policy
    guide = ResearchGuides('1.5.0').open('research-method')['text']
    assert 'shared source profile' in guide
    assert 'follow_ups' in guide and 'supersedes' in guide
    assert 'agent_delegate' in research_tools_for_profile('enterprise-research', '1.6.0')
    old = registered_binding('1.5.0')
    frozen = copy.deepcopy(old)
    assert binding_for_session(old, 'enterprise-research')['application_profile']['profile_version'] == '1.9.0'
    assert old == frozen
    assert sha256(registered_research_policy('1.5.0').system_policy.encode()).hexdigest() == '8864223a8bbadd4082d28584c63cb8bd9a3d3d1f7db8f67e0f8bdd27f91391b3'


def test_known_variants_bind_exact_policy_and_pack_resources_and_reject_mixed_hashes():
    from capstone_agent.native_conversation import executor_binding, validate_binding
    from capstone_agent.native_task_context import native_context_for, registered_research_policies, resolve_research_policy
    from test_enterprise_normal_chat import native_executor
    executor = native_executor()
    executor.capability = {**executor.capability, 'research_bridge_schemas': ['capstone-research-bridge/1'],
                          'delivery_review_schemas': ['capstone-delivery-review/1']}
    from capstone_agent.native_task_context import research_policy_capabilities
    executor.capability['research_policy_profiles'] = research_policy_capabilities()
    for entry in registered_research_policies():
        executor.capability['research_graph_schemas'] = [entry.graph_schema] if entry.graph_schema else []
        binding = executor_binding(executor, profile_version=entry.application_version, _policy_variant=entry.variant)
        assert validate_binding(binding) == binding
        context = native_context_for(SimpleNamespace(submission=None, selected_task_reader=None, started_at='2026-10-21T06:00:00Z'), binding)
        assert context['policy']['system_policy'] == entry.system_policy
        assert resolve_research_policy(context['policy']['system_policy']) == entry
        assert resolve_research_policy(entry.system_policy + '\n') is None
        mixed = copy.deepcopy(binding)
        mixed['pack_bindings'][0]['guides_sha256'] = 'b' * 64
        with pytest.raises(ValueError):
            validate_binding(mixed)
