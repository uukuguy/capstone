#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHONPATH=. uv run --project packages/pandapower-application python -m pytest tools/tests/test_ci_execution_details.py tools/tests/test_ci_scope.py tools/tests/test_user_local_graph.py -q
npm run check --prefix packages/capstone-app
npm test --prefix packages/capstone-app -- src/ExecutionDetails.test.tsx src/CapstoneAssistantThread.test.tsx src/ThreadWorkEntry.test.tsx src/ThreadWorkExecution.test.tsx
git diff --check
