#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=.
checks=(
  packages/pandapower-application/tests/trajectory
  packages/pandapower-application/tests/runtime
  packages/pandapower-application/tests/analysis
  packages/pandapower-application/tests/contract
  packages/pandapower-application/tests/validation
  packages/pandapower-application/tests/test_answer_contract.py
  packages/capstone-agent/tests/test_thread_resources.py
  packages/capstone-agent/tests/test_auth_store.py
  packages/capstone-agent/tests/test_auth_service.py
  tools/tests/test_ci_scope.py tools/tests/test_check_package_boundaries.py
  tools/tests/test_verification_targets.py tools/tests/test_ci_retirement_scope.py
)
uv run --project packages/pandapower-application pytest "${checks[@]}" -q
python tools/check_package_boundaries.py
node --test packages/capstone-agent/tests/fixtures/general-sdk-graph.test.mjs packages/capstone-agent/tests/fixtures/general-sdk-graph-errors.test.mjs packages/capstone-agent/tests/fixtures/tool-discovery.test.mjs
npm --prefix packages/capstone-app test -- src/InstructionAttachments.test.tsx src/attachmentMemory.test.ts src/ThreadFixtureApp.test.tsx
