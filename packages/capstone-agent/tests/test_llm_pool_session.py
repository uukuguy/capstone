"""Pinned SDK parent and independent model calls run through real tool wiring."""
import json
from pathlib import Path
import subprocess


def test_actual_parent_session_integrates_parallel_answers_without_dr():
    script = Path(__file__).parent / 'fixtures' / 'llm-pool-session-fixture.mjs'
    result = subprocess.run(['node', str(script)], input='{"type":"prompt"}\n',
        capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr + result.stdout[-2000:]
    events = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
    pool = [event for event in events if event.get('type') == 'llm_pool_call']
    assert sum(event['status'] == 'completed' for event in pool) == 2
    assert all('research_branch' not in event for event in pool)
    assert events[-1]['type'] == 'agent_end'
