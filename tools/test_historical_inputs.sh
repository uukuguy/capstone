#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${CAPSTONE_TEST_DATABASE_URL:?A disposable PostgreSQL database is required}"
export PYTHONPATH=.
uv run --project packages/capstone-agent pytest \
  packages/capstone-agent/tests/test_historical_input_receipts.py \
  packages/capstone-agent/tests/test_native_resource_staging.py \
  packages/capstone-agent/tests/test_continuation_file_capacity.py \
  packages/capstone-agent/tests/test_harness.py \
  packages/capstone-agent/tests/test_native_resource_references.py \
  tools/tests/test_ci_historical_inputs.py -q
npm --prefix packages/capstone-app test -- src/taskProgress.test.ts src/threadProjectionStore.test.ts
npm --prefix packages/capstone-app run check
git diff --check
