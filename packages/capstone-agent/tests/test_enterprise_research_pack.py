def test_formal_research_pack_is_public_native_spi_and_has_consumable_methods():
    from enterprise_research import build_profile, ResearchAcceptance
    from capability_agent.domain.profile import NativeDomainRuntimeProfile
    profile = build_profile()
    assert isinstance(profile, NativeDomainRuntimeProfile)
    assert profile.manifest.domain_id == 'enterprise-research-methods'
    assert profile.missing_application_components() == ()
    assert 'agent_research_update' in profile.policy_provider.load()
    guides = profile.guide_provider.load()
    assert guides and all(profile.guide_provider.open(item['resource_id']) for item in guides)
    assert 'source-contradiction-revision' in ResearchAcceptance().cases()


def test_research_preset_selects_new_version_only_with_real_control_transport():
    from capstone_agent.native_conversation import executor_binding, validate_binding
    from capstone_agent.native_task_context import native_context_for
    from test_enterprise_normal_chat import native_executor
    from types import SimpleNamespace
    executor = native_executor()
    old = executor_binding(executor)
    assert old['application_profile']['profile_version'] == '1.0.0'
    executor.capability = {**executor.capability, 'research_bridge_schemas': ['capstone-research-bridge/1']}
    current = executor_binding(executor)
    assert current['application_profile']['profile_version'] == '1.2.0'
    assert current['binding_id'] == 'research-methods'
    assert current['pack_bindings'][0]['pack_id'] == 'enterprise-research-methods'
    assert current['pack_bindings'][0]['pack_version'] == '1.1.0'
    legacy = executor_binding(executor, profile_version='1.1.0')
    assert legacy['pack_bindings'][0]['pack_version'] == '1.0.0'
    assert validate_binding(legacy) == legacy
    legacy_context = native_context_for(SimpleNamespace(submission=None, selected_task_reader=None), legacy)
    assert 'agent_research_cycle' in legacy_context['policy']['allowed_tools']
    assert 'agent_research_plan' not in legacy_context['policy']['allowed_tools']
    assert validate_binding(old) == old
    assert validate_binding(current) == current
    context = native_context_for(SimpleNamespace(submission=None, selected_task_reader=None), current)
    assert 'agent_research_update' in context['policy']['allowed_tools']
    assert {'agent_research_plan', 'agent_research_record', 'agent_research_assess'} <= set(context['policy']['allowed_tools'])
    assert 'agent_research_cycle' not in context['policy']['allowed_tools']
    assert 'agent_research_cycle' not in context['policy']['system_policy']
    assert 'sources conflict' in context['policy']['system_policy']
    ordinary = executor_binding(executor, session_type='general-chat')
    assert ordinary['application_profile'] == {'profile_id': 'general-chat', 'profile_version': '1.0.0'}
    assert 'agent_research_update' not in native_context_for(
        SimpleNamespace(submission=None, selected_task_reader=None), ordinary)['policy']['allowed_tools']


def test_existing_thread_new_instruction_can_accept_research_upgrade_without_changing_old_attempt():
    from dataclasses import replace
    from capstone_agent.thread_service import InMemoryThreadService
    from test_thread_postgres import _snapshot
    from test_enterprise_normal_chat import native_executor, command
    from capstone_agent.thread_worker import run_pending_attempt
    from capstone_agent.native_hosted_worker import native_runtime_factory
    snapshot = replace(_snapshot('thr_upgrade'), active_model_context=None, active_grid_page_id=None, minimum_protocol_version=2)
    store = InMemoryThreadService(snapshot)
    old_executor = native_executor()
    store.set_native_executor(old_executor)
    store.submit_command(command(store, snapshot.thread_id, 'send_message', 'old', payload={'text': 'Hello'}))
    claim = store.claim_attempt('old-worker', 30, implementation_family='native')
    assert claim.submission['_native_execution']['application_profile']['profile_version'] == '1.0.0'
    store.finish_attempt(claim, phase='failed', payload={'error_code': 'test_failure'})
    current_executor = native_executor()
    current_executor.capability = {**current_executor.capability, 'research_bridge_schemas': ['capstone-research-bridge/1']}
    store.set_native_executor(current_executor)
    work = store.snapshot(snapshot.thread_id).works[0]
    store.submit_command(command(store, snapshot.thread_id, 'send_message', 'new',
        work_id=work['work_id'], revision=work['revision'], payload={'text': 'Continue with source checks'}))
    current = store.claim_attempt('new-worker', 30, implementation_family='native')
    assert current.submission['_native_execution']['application_profile']['profile_version'] == '1.2.0'
    assert claim.submission['_native_execution']['application_profile']['profile_version'] == '1.0.0'
    assert current.task_context.binding == claim.task_context.binding


def test_isolated_context_validation_does_not_import_application_composition(monkeypatch):
    import builtins
    from types import SimpleNamespace
    from capstone_agent.native_conversation import executor_binding
    from capstone_agent.native_task_context import native_context_for, checked_native_context
    from test_enterprise_normal_chat import native_executor
    executor = native_executor()
    executor.capability = {**executor.capability, 'research_bridge_schemas': ['capstone-research-bridge/1']}
    contexts = [native_context_for(SimpleNamespace(submission=None, selected_task_reader=None),
                executor_binding(executor, profile_version=version)) for version in ('1.1.0', '1.2.0')]
    original_import = builtins.__import__

    def isolated_import(name, *args, **kwargs):
        if name.endswith('enterprise_application') or name.startswith('capability_agent'):
            raise ModuleNotFoundError('Application composition is not installed in the isolated executor')
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, '__import__', isolated_import)
    for context in contexts:
        assert checked_native_context(context) == context


def test_delivery_review_profile_requires_host_support_and_preserves_split_profile():
    import pytest
    from types import SimpleNamespace
    from capstone_agent.native_conversation import executor_binding, validate_binding
    from capstone_agent.native_task_context import native_context_for, checked_native_context
    from test_enterprise_normal_chat import native_executor
    executor = native_executor()
    executor.capability = {**executor.capability, 'research_bridge_schemas': ['capstone-research-bridge/1']}
    old = executor_binding(executor)
    with pytest.raises(ValueError, match='review.*unavailable'):
        executor_binding(executor, profile_version='1.3.0')
    executor.capability = {**executor.capability, 'delivery_review_schemas': ['capstone-delivery-review/1']}
    current = executor_binding(executor)
    assert current['application_profile']['profile_version'] == '1.3.0'
    assert current['pack_bindings'][0]['pack_version'] == '1.2.0'
    assert validate_binding(current) == current
    assert validate_binding(old) == old
    explicit_old = executor_binding(executor, profile_version='1.2.0')
    context = native_context_for(SimpleNamespace(submission=None, selected_task_reader=None), current)
    previous = native_context_for(SimpleNamespace(submission=None, selected_task_reader=None), explicit_old)
    assert checked_native_context(context) == context
    assert 'review_products' in context['policy']['system_policy']
    assert 'not visual inspection' in context['policy']['system_policy']
    assert 'review_products' not in previous['policy']['system_policy']
    assert context['policy']['allowed_tools'] == previous['policy']['allowed_tools']
