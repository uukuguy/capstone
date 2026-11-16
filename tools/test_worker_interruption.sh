#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${CAPSTONE_TEST_DATABASE_URL:?A disposable PostgreSQL database is required}"
export PYTHONPATH=.
uv run --project packages/capstone-agent pytest \
  packages/capstone-agent/tests/test_worker_interruption_products.py \
  packages/capstone-agent/tests/test_continuation_file_capacity.py \
  packages/capstone-agent/tests/test_incremental_artifacts.py \
  packages/capstone-agent/tests/test_native_artifact_projection.py \
  packages/capstone-agent/tests/test_terminal_transition.py \
  packages/capstone-agent/tests/test_thread_postgres.py \
  packages/capstone-agent/tests/test_enterprise_normal_chat.py \
  tools/tests/test_ci_worker_interruption.py -q
git diff --check
