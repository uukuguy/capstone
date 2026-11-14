#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${CAPSTONE_TEST_DATABASE_URL:?A disposable PostgreSQL database is required}"
export PYTHONPATH=.
uv run --project packages/capstone-agent pytest \
  packages/capstone-agent/tests/test_product_series*.py \
  packages/capstone-agent/tests/test_product_comparison.py \
  packages/capstone-agent/tests/test_thread_products.py \
  packages/capstone-agent/tests/test_thread_input.py \
  packages/capstone-agent/tests/test_thread_deliveries.py \
  packages/capstone-agent/tests/test_hosting.py -q
uv run --project packages/capstone-agent pytest \
  packages/capstone-agent/tests/test_artifacts.py \
  packages/capstone-agent/tests/test_artifact_transfer_recovery.py \
  tools/tests/test_ci_product_adoption.py -q
npm --prefix packages/capstone-app run check
npm --prefix packages/capstone-app test -- \
  src/productSeries.test.ts src/productSeriesTransport.test.ts \
  src/ProductComparison.test.tsx src/ThreadProductsWorkspace.test.tsx \
  src/threadProducts.test.ts src/threadProductsTransport.test.ts \
  src/threadInput.test.ts src/ProductReferenceChips.test.tsx
npm --prefix packages/capstone-app run build
