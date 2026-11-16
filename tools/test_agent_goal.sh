#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${CAPSTONE_TEST_DATABASE_URL:?A disposable PostgreSQL database is required}"
export PYTHONPATH=.
uv run --project packages/capstone-agent pytest \
  packages/capstone-agent/tests/test_goal_mode.py \
  packages/capstone-agent/tests/test_goal_receipts.py \
  packages/capstone-agent/tests/test_goal_continuation.py \
  packages/capstone-agent/tests/test_thread_work.py \
  packages/capstone-agent/tests/test_thread_work_execution.py \
  packages/capstone-agent/tests/test_thread_gateway_http.py \
  packages/capstone-agent/tests/test_thread_worker.py \
  packages/capstone-agent/tests/test_harness.py -q
npm run check --prefix packages/capstone-app
npm test --prefix packages/capstone-app -- \
  src/goalMode.test.ts src/GoalControls.test.tsx \
  src/threadWorkProtocol.test.ts src/ThreadWorkExecution.test.tsx
git diff --check
