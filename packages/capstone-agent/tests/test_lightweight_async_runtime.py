"""Run actual JavaScript pool and pinned SDK seams in the scoped Python gate."""
from pathlib import Path
import subprocess


def test_lightweight_async_runtime_contracts():
    fixtures = Path(__file__).parent / 'fixtures'
    result = subprocess.run(['node', '--test', *(str(fixtures / name) for name in (
        'async-call-pool.test.mjs', 'llm-call-tools.test.mjs',
        'llm-pool-runtime.test.mjs', 'model-request-pool.test.mjs', 'tool-result-context.test.mjs'))],
        capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
