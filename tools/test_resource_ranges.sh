#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${CAPSTONE_TEST_DATABASE_URL:?A disposable PostgreSQL database is required}"
export PYTHONPATH=.
uv run --project packages/capstone-agent pytest \
  packages/capstone-agent/tests/test_resource_range_reads.py \
  packages/capstone-agent/tests/test_resource_range_transport.py \
  packages/capstone-agent/tests/test_resource_range_policy.py \
  packages/capstone-agent/tests/test_deep_research_control.py \
  packages/capstone-agent/tests/test_native_resource_references.py \
  packages/capstone-agent/tests/test_native_resource_staging.py \
  packages/capstone-agent/tests/test_thread_resources.py \
  packages/capstone-agent/tests/test_general_pi_server.py \
  packages/capstone-agent/tests/test_pi_delegation.py \
  packages/capstone-agent/tests/test_application_capacity.py \
  packages/capstone-agent/tests/test_capacity_contract.py \
  tools/tests/test_ci_resource_ranges.py -q
node --test packages/capstone-agent/tests/fixtures/resource-reference-tools.test.mjs
node --test packages/capstone-agent/tests/resource-range-sdk.test.mjs
npm --prefix packages/capstone-app run check
npm --prefix packages/capstone-app test -- \
  src/resourceReads.test.ts src/ResourceReadSources.test.tsx \
  src/ThreadProductsWorkspace.test.tsx src/ProductComparison.test.tsx \
  src/threadProducts.test.ts src/threadProductsTransport.test.ts src/threadHttpTransport.test.ts
npm --prefix packages/capstone-app run build
