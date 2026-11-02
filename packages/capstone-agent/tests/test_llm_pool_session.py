"""Pinned SDK parent and independent model calls run through real tool wiring."""
import json
from pathlib import Path
import subprocess
from capstone_agent.native_llm_pool import LLM_CALL_POOL_POLICY
from capstone_agent.native_model_request_pool import MODEL_REQUEST_POOL_POLICY, checked_model_request_pool


def test_direct_session_keeps_tool_execution_and_model_timing_boundaries_without_pools():
    script = Path(__file__).parent / 'fixtures' / 'llm-pool-session-fixture.mjs'
    result = subprocess.run(['node', str(script), '--direct'], input='{"type":"prompt"}\n',
        capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr + result.stdout[-2000:]
    events = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
    assert not any(event.get('type') in {'llm_pool_call', 'model_request_pool'} for event in events)
    assert any(event.get('type') == 'tool_execution_end' and event.get('toolName') == 'write'
               and not event.get('isError') for event in events)
    responses = [event for event in events if event.get('type') == 'message_end'
                 and event.get('message', {}).get('role') == 'assistant']
    assert len(responses) == 2
    assert sum(event.get('type') == 'turn_start' for event in events) == 2
    assert all(event['message']['usage']['totalTokens'] == 2 for event in responses)
    assert events[-1]['type'] == 'agent_end'


def test_actual_parent_session_integrates_parallel_answers_without_dr():
    script = Path(__file__).parent / 'fixtures' / 'llm-pool-session-fixture.mjs'
    result = subprocess.run(['node', str(script)], input='{"type":"prompt"}\n',
        capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr + result.stdout[-2000:]
    events = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
    pool = [event for event in events if event.get('type') == 'llm_pool_call']
    assert sum(event['status'] == 'completed' for event in pool) == 2
    assert all('research_branch' not in event for event in pool)
    requests = [event for event in events if event.get('type') == 'model_request_pool']
    completed = [event for event in requests if event['status'] == 'completed']
    assert len(completed) >= 5
    assert sum(event['kind'] == 'analysis' for event in completed) == 2
    assert all(event['queued_at_ms'] <= event['started_at_ms'] <= event['finished_at_ms'] for event in completed)
    assert all(event['model_turn_number'] >= 1 for event in completed)
    record = {'llm_pool_submit_calls': {'submit'}}
    native = {'deep_research': False, 'llm_call_pool': LLM_CALL_POOL_POLICY,
              'policy': {'allowed_tools': ['agent_llm_submit']}}
    capability = {'model_request_pool': MODEL_REQUEST_POOL_POLICY, 'llm_call_pool': LLM_CALL_POOL_POLICY}
    for event in requests:
        checked_model_request_pool(event, native, capability, record)
    assert events[-1]['type'] == 'agent_end'
