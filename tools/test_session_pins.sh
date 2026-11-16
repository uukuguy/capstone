#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${CAPSTONE_TEST_DATABASE_URL:?A disposable PostgreSQL database is required}"
export PYTHONPATH=.
uv run --project packages/capstone-agent pytest \
  packages/capstone-agent/tests/test_session_pins.py \
  packages/capstone-agent/tests/test_thread_workspaces.py \
  packages/capstone-agent/tests/test_thread_http_api.py \
  tools/tests/test_ci_session_pins.py -q
npm run check --prefix packages/capstone-app
npm test --prefix packages/capstone-app -- \
  src/durableSessionPins.test.ts src/sessionPinsPersistence.test.ts \
  src/SessionNavigation.test.tsx src/SessionCleanup.test.tsx \
  src/threadHttpTransport.test.ts src/ThreadWorkspace.test.tsx
git diff --check
