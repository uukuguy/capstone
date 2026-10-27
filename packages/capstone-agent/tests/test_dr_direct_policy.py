def test_direct_delivery_publication_preserves_old_policy_and_selects_adaptive_runtime():
    from capstone_agent.native_task_context import registered_research_policy
    from capstone_agent.enterprise_application import resolve_native_profile
    old = registered_research_policy('1.19.0')
    current = registered_research_policy('1.20.0')
    assert current.pack_version == '1.17.0'
    assert current.adaptive_agent_loop and current.goal_driven_execution and current.lightweight_task_nodes
    assert 'registered and settled automatically' in current.system_policy
    assert 'reader-facing delivery summary' in current.system_policy
    assert 'Use agent_research_record with the issued' in old.system_policy
    assert resolve_native_profile('enterprise-research', '1.20.0').manifest.version == '1.20.0'
