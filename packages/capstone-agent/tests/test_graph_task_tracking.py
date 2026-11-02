from capstone_agent.task_steps import NativeStepTracker


def test_graph_tracking_preserves_concurrent_model_nodes_without_active_step_fallback():
    tracker = NativeStepTracker(prefix='attempt', objective_steps=True)
    tracker.annotate({'type': 'tool_execution_start', 'tool_name': 'agent_research_plan',
                      'tool_call_id': 'plan'})
    event = {'type': 'enterprise_graph_progress', 'graph': {
        'nodes': [{'id': 'A', 'phase': 'executing'}, {'id': 'B', 'phase': 'executing'},
                  {'id': 'C', 'phase': 'pending', 'depends_on': ['A']}],
        'actions': [{'id': 'execute-A', 'step_id': 'A'}, {'id': 'execute-B', 'step_id': 'B'}]},
        'events': [{'kind': 'node_started', 'step_id': 'B'}]}
    output = tracker.annotate(event)
    assert output['graph'] == event['graph']
    assert output['events'] == event['events']
    assert output['runtime_step_tracking'] is True
    assert not any(key in output for key in ('task_step', 'task_step_error', 'task_step_id'))
    tool = tracker.annotate({'type': 'tool_execution_start', 'tool_name': 'read', 'tool_call_id': 'read-A'})
    assert tool['runtime_step_tracking'] is True
    assert not any(key in tool for key in ('task_step', 'task_step_id'))
