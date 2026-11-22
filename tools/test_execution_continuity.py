"""Run the owning continuity tests against a disposable PostgreSQL database."""
import json
import os
from pathlib import Path
import subprocess


def main() -> None:
    if not os.environ.get('CAPSTONE_TEST_DATABASE_URL'):
        raise SystemExit('CAPSTONE_TEST_DATABASE_URL must name a disposable PostgreSQL database')
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / 'configs/development/execution-continuity-gate.json').read_text())
    subprocess.run(['uv', 'run', '--project', 'packages/capstone-agent', 'python', '-m', 'pytest',
                    '-q', *manifest['backend_tests']], cwd=root, check=True)
    subprocess.run(['npm', 'run', 'check', '--prefix', 'packages/capstone-app'], cwd=root, check=True)
    subprocess.run(['npm', 'test', '--prefix', 'packages/capstone-app', '--', '--run',
                    *manifest['app_tests']], cwd=root, check=True)


if __name__ == '__main__':
    main()
