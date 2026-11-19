#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${CAPSTONE_TEST_DATABASE_URL:?A disposable PostgreSQL database is required}"
export PYTHONPATH=.
uv run --project packages/capstone-agent pytest \
  packages/capstone-control/tests \
  packages/capstone-agent/tests/test_control_host.py \
  packages/capstone-agent/tests/test_agent_delegation.py \
  packages/capstone-agent/tests/test_delegation_resources.py \
  packages/capstone-agent/tests/test_mission_continuation.py \
  packages/capstone-agent/tests/test_thread_work_execution.py \
  packages/capstone-agent/tests/test_thread_worker.py \
  packages/capstone-agent/tests/test_worker_interruption_products.py \
  packages/capstone-agent/tests/test_historical_input_receipts.py \
  packages/capstone-agent/tests/test_native_graph_context.py \
  tools/tests/test_ci_control_delegation.py \
  tools/tests/test_user_local_graph.py -q
npm run check --prefix packages/capstone-app
npm test --prefix packages/capstone-app -- \
  src/controlGoals.test.ts src/ControlGoals.test.tsx \
  src/GoalControls.test.tsx src/ThreadWorkExecution.test.tsx \
  src/threadHttpTransport.test.ts src/threadWorkTransport.test.ts src/taskProgress.test.ts
git diff --check
