#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${CAPSTONE_TEST_DATABASE_URL:?A disposable PostgreSQL database is required}"
export PYTHONPATH=.
uv run --project packages/capstone-agent pytest \
  packages/capstone-control/tests \
  packages/capstone-agent/tests/test_control_host.py \
  packages/capstone-agent/tests/test_agent_delegation.py \
  tools/tests/test_ci_control_events.py -q
git diff --check
