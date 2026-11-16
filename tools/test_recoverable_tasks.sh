#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${CAPSTONE_TEST_DATABASE_URL:?A disposable PostgreSQL database is required}"
export PYTHONPATH=.
uv run --project packages/capstone-agent pytest \
  packages/capstone-agent/tests/test_attempt_lease_deadline.py \
  packages/capstone-agent/tests/test_delegated_runtime.py \
  packages/capstone-agent/tests/test_general_pi_executor.py \
  packages/capstone-agent/tests/test_general_pi_server.py \
  packages/capstone-agent/tests/test_native_execution_authority.py \
  packages/capstone-agent/tests/test_native_owned_execution.py \
  packages/capstone-agent/tests/test_pi_delegation.py \
  packages/capstone-agent/tests/test_thread_recovery_reaper.py \
  packages/capstone-agent/tests/test_attempt_failure_delivery.py \
  packages/capstone-agent/tests/test_continuation_file_capacity.py \
  packages/capstone-agent/tests/test_resource_range_policy.py \
  packages/capstone-agent/tests/test_resource_range_reads.py \
  packages/capstone-agent/tests/test_resource_range_transport.py \
  packages/capstone-agent/tests/test_thread_worker.py \
  packages/capstone-agent/tests/test_worker_wake.py \
  packages/capstone-agent/tests/test_worker_interruption_products.py \
  packages/capstone-agent/tests/test_thread_postgres.py \
  tools/tests/test_ci_recoverable_tasks.py -q
git diff --check
