"""Exercise the real native worker/package path in the ordinary Python gate."""
from pathlib import Path
import subprocess


def test_real_tool_composition_and_semantic_package_contracts():
    fixtures = Path(__file__).parent / 'fixtures'
    result = subprocess.run(['node', '--test', str(fixtures / 'tool-composition.test.mjs'),
        str(fixtures / 'semantic-data-context.test.mjs')], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
