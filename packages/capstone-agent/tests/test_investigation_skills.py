from pathlib import Path

from capstone_agent.runtime_resources import resolve_resource_profile


NAMES = {
    'brainstorming', 'task-planning-and-tracking', 'systematic-debugging',
    'verification-before-completion', 'data-investigation',
    'data-quality-and-comparability',
}


def test_general_roles_publish_all_investigation_methods_without_professional_grants():
    root = Path(__file__).resolve().parents[3] / 'configs/runtime'
    for role in ('direct_pi', 'delegated_pi'):
        profile = resolve_resource_profile(root, role)
        methods = {r.native_name: r for r in profile.resources if r.native_name in NAMES}
        assert set(methods) == NAMES
        assert all(r.installed and r.ready and r.loaded_identity for r in methods.values())
        assert all(not r.required_tools for r in methods.values())
    professional = resolve_resource_profile(root, 'harness_engine')
    assert not NAMES.intersection(r.native_name for r in professional.resources)


def test_public_skill_activity_shows_load_and_report_without_promoting_verification():
    from capstone_agent.progress import project_native_tool_activity
    from capstone_agent.skill_activity import checked_skill_activity

    loaded = {'schema': 'capstone-skill-activity/1', 'name': 'data-investigation',
              'version': 'sha256:' + 'a' * 64, 'state': 'loaded', 'source': 'host'}
    event = {'toolName': 'agent_skill', 'result': {'details': {'skill_activity': loaded},
                                                 'content': [{'type': 'text', 'text': 'Private method body'}]}}
    activity = project_native_tool_activity(event)
    assert 'data-investigation' in activity['operation']
    assert '已加载' in activity['operation']
    assert 'Private method body' not in str(activity)
    reported = {**loaded, 'state': 'reported', 'source': 'model', 'phase': '对照复核',
                'summary': '已核对两份基线，覆盖仍不足。', 'refs': ['result:one'], 'tool_call_ids': ['read-1'],
                'verified': True}
    admitted = checked_skill_activity(reported)
    assert admitted is not None and 'verified' not in admitted
    event['result']['details']['skill_activity'] = reported
    activity = project_native_tool_activity(event)
    assert '模型报告' in activity['operation']
    assert 'result:one' in activity['output_excerpt']
    assert checked_skill_activity({**reported, 'source': 'host'}) is None
    assert checked_skill_activity({**reported, 'summary': 'password=hidden'}) is None
