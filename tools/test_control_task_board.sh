#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHONPATH=. uv run --project packages/pandapower-application python -m pytest tools/tests/test_ci_control_task_board.py tools/tests/test_ci_scope.py -q
npm run check --prefix packages/capstone-app
npm test --prefix packages/capstone-app -- \
  src/controlEvents.test.ts src/ControlWorkspaceViews.test.tsx \
  src/ControlTaskBoard.test.tsx src/ControlGoals.test.tsx src/controlGoals.test.ts \
  src/threadHttpTransport.test.ts src/ThreadWorkEntry.test.tsx src/ThreadWorkExecution.test.tsx
git diff --check
