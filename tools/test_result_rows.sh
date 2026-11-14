#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${CAPSTONE_TEST_DATABASE_URL:?A disposable PostgreSQL database is required}"
export PYTHONPATH=.
uv run --project packages/capstone-agent pytest \
  packages/capstone-agent/tests/test_result_row*.py \
  packages/capstone-agent/tests/test_result_table_store.py \
  packages/capstone-agent/tests/test_result_projection.py \
  packages/capstone-agent/tests/test_thread_products.py \
  packages/capstone-agent/tests/test_thread_input.py \
  packages/capstone-agent/tests/test_thread_work.py \
  packages/capstone-agent/tests/test_thread_work_execution.py \
  packages/capstone-agent/tests/test_thread_deliveries.py \
  packages/capstone-agent/tests/test_product_series_service.py \
  packages/capstone-agent/tests/test_hosting.py \
  tools/tests/test_ci_result_rows.py -q
npm --prefix packages/capstone-app run check
npm --prefix packages/capstone-app test -- \
  src/resultRowSelection.test.ts src/ResultRowTable.test.tsx \
  src/ThreadProductsWorkspace.test.tsx src/ProductReferenceChips.test.tsx \
  src/threadProducts.test.ts src/threadProductsTransport.test.ts src/ProductComparison.test.tsx
npm --prefix packages/capstone-app test -- \
  src/CapstoneAssistantThread.test.tsx src/ThreadWorkExecution.test.tsx \
  src/ThreadLiveEntry.test.tsx src/threadWorkProtocol.test.ts src/threadWorkTransport.test.ts
npm --prefix packages/capstone-app run build
