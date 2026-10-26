"""Shared planning policy has no application or domain dependency."""
from hashlib import sha256


def test_research_turn_publication_selects_user_judgment_and_limited_delivery():
    from capstone_agent.native_task_context import registered_research_policy
    from capstone_agent.task_planning_policy import task_planning_policy
    entry = registered_research_policy('1.18.0')
    assert entry.pack_version == '1.15.0'
    assert entry.lightweight_task_nodes and entry.goal_driven_execution and entry.isolated_task_execution
    selected = task_planning_policy('1.5.0')
    assert selected.text in entry.system_policy
    assert 'user judges' in selected.text
    assert 'Choose limited' in selected.text
    assert 'Do not automatically repeat' in selected.text
    for term in ('enterprise-research', 'pandapower', 'PyPSA', 'CSV', 'report.html'):
        assert term not in selected.text
    assert 'Required missing work cannot be' not in entry.system_policy
    assert 'Required missing work cannot be' in registered_research_policy('1.17.0').system_policy


def test_research_turn_publication_preserves_all_prior_catalog_bytes():
    import json
    from importlib.resources import files
    catalog = json.loads(files('capstone_agent').joinpath('resources/research-policy-catalog.json').read_text())['policies']
    old = [item for item in catalog if item['application_version'] not in {'1.18.0', '1.19.0'}]
    assert sha256(json.dumps(old, ensure_ascii=False, sort_keys=True).encode()).hexdigest() == '2e0b1944a4d8facf1b5d2d963749237d154545c88f08095dde22626f23b6820d'


def test_lightweight_nodes_are_a_new_exact_publication():
    from capstone_agent.native_task_context import registered_research_policy
    from capstone_agent.task_planning_policy import task_planning_policy
    entry = registered_research_policy('1.17.0')
    assert entry.lightweight_task_nodes and entry.goal_driven_execution and entry.isolated_task_execution
    assert entry.pack_version == '1.14.0'
    assert entry.work_policy()['mode'] == 'off'
    assert task_planning_policy('1.4.0').text in entry.system_policy
    assert not registered_research_policy('1.16.0').lightweight_task_nodes
    assert 'capstone-task-return/1' in entry.system_policy


def test_shared_planning_publication_is_domain_neutral_and_versioned():
    from capstone_agent.task_planning_policy import task_planning_policy
    policy = task_planning_policy('1.0.0')
    assert policy.version == '1.0.0'
    assert policy.sha256 == sha256(policy.text.encode()).hexdigest()
    assert 'Shared preparation is a producer dependency, not a reason to collapse' in policy.text
    assert 'bounded delegated nodes' in policy.text
    for app_term in ('enterprise-research', 'pandapower', 'PyPSA', 'agent_research_plan', 'CSV', 'report.html'):
        assert app_term not in policy.text


def test_research_adapter_uses_exact_shared_policy_without_changing_baseline():
    from capstone_agent.task_planning_policy import task_planning_policy
    from capstone_agent.native_task_context import registered_research_policy
    policy = task_planning_policy('1.0.0')
    assert policy.text in registered_research_policy('1.13.0').system_policy
    assert policy.text not in registered_research_policy('1.12.0').system_policy


def test_incremental_task_pool_policy_is_selected_without_replacing_old_policy():
    from capstone_agent.task_planning_policy import task_planning_policy
    from capstone_agent.native_task_context import registered_research_policy
    old = task_planning_policy('1.0.0')
    selected = task_planning_policy('1.1.0')
    assert 'Commit only the next evidence-supported task or batch' in selected.text
    assert 'An empty task pool is not proof of goal completion' in selected.text
    assert 'Every executable task uses an independent context' in selected.text
    assert 'Global context is read-only to task executors' in selected.text
    assert 'Planning is incremental, not a complete speculative workflow' in selected.text
    for term in ('enterprise-research', 'pandapower', 'PyPSA', 'CSV', 'report.html'):
        assert term not in selected.text
    publication = registered_research_policy('1.14.0')
    assert selected.text in publication.system_policy
    assert publication.isolated_task_execution is True
    assert registered_research_policy('1.13.0').isolated_task_execution is False
    assert old.text in registered_research_policy('1.13.0').system_policy


def test_decision_bounded_discovery_is_new_shared_publication_with_exact_legacy_bytes():
    import json
    from importlib.resources import files
    from capstone_agent.task_planning_policy import task_planning_policy
    from capstone_agent.native_task_context import registered_research_policy
    selected = task_planning_policy('1.2.0')
    guidance = ' '.join(selected.text.split())
    assert 'Discovery has a decision stop condition' in guidance
    assert 'Do not turn discovery into a full investigation' in guidance
    assert 'Relevant quality checks belong to the tasks that use the data' in guidance
    assert 'A full-source scan is justified when the next decision needs it' in guidance
    for term in ('enterprise-research', 'pandapower', 'PyPSA', 'CSV', 'report.html'):
        assert term not in selected.text
    publication = registered_research_policy('1.15.0')
    assert publication.pack_version == '1.12.0'
    assert publication.isolated_task_execution is True
    assert selected.text in publication.system_policy
    assert task_planning_policy('1.1.0').text in registered_research_policy('1.14.0').system_policy
    assert task_planning_policy('1.0.0').sha256 == 'f20fe61bd9b6edf9a2836194e54f41a60ed5214af8b3ba15858e40e97e8ad905'
    assert task_planning_policy('1.1.0').sha256 == '7fc08cc4058864f22f375f57cd7870a4f06896117b833948836c57843abae5ba'
    catalog = json.loads(files('capstone_agent').joinpath('resources/research-policy-catalog.json').read_text())['policies']
    old = [item for item in catalog if item['application_version'] not in {'1.15.0', '1.16.0', '1.17.0', '1.18.0', '1.19.0'}]
    assert sha256(json.dumps(old, ensure_ascii=False, sort_keys=True).encode()).hexdigest() == 'c4e8ec81e325e34383786063f4bdabe3ba33003fa078a4dbb613e55966adb371'


def test_whole_goal_lifecycle_publication_disables_soft_deadline_without_upgrading_old_tasks():
    import json
    from importlib.resources import files
    from capstone_agent.native_task_context import registered_research_policy
    from capstone_agent.task_planning_policy import task_planning_policy
    entry = registered_research_policy('1.16.0')
    assert entry.goal_driven_execution and entry.isolated_task_execution
    assert entry.pack_version == '1.13.0'
    assert entry.work_policy()['mode'] == 'off'
    assert task_planning_policy('1.3.0').text in entry.system_policy
    assert registered_research_policy('1.15.0').work_policy()['mode'] == 'usable_draft'
    assert not registered_research_policy('1.15.0').goal_driven_execution
    catalog = json.loads(files('capstone_agent').joinpath('resources/research-policy-catalog.json').read_text())['policies']
    old = [item for item in catalog if item['application_version'] not in {'1.16.0', '1.17.0', '1.18.0', '1.19.0'}]
    assert sha256(json.dumps(old, ensure_ascii=False, sort_keys=True).encode()).hexdigest() == '2b4db9e6ca58a0e880733f8d5011f1170288d9463966d32c956425b0340039f1'


def test_lightweight_publication_preserves_every_previous_catalog_entry():
    import json
    from importlib.resources import files
    catalog = json.loads(files('capstone_agent').joinpath('resources/research-policy-catalog.json').read_text())['policies']
    old = [item for item in catalog if item['application_version'] not in {'1.17.0', '1.18.0', '1.19.0'}]
    assert sha256(json.dumps(old, ensure_ascii=False, sort_keys=True).encode()).hexdigest() == '69af13ea8823b0c901dbc8f135c7f701ca78ec427574109434bc965d6757a46c'
