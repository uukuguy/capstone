#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHONPATH=. uv run --project packages/pandapower-application python -m pytest tools/tests/test_ci_session_navigation.py -q
npm run check --prefix packages/capstone-app
npm test --prefix packages/capstone-app -- \
  src/SessionNavigation.test.tsx src/SessionCleanup.test.tsx \
  src/WorkspaceSessionEntry.test.tsx src/workspaceSessionCache.test.tsx \
  src/durableSessionPins.test.ts src/sessionPinsPersistence.test.ts \
  src/ThreadWorkEntry.test.tsx src/ThreadWorkExecution.test.tsx \
  src/ThreadLiveEntry.test.tsx src/ThreadWorkspace.test.tsx
git diff --check
