#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${CAPSTONE_TEST_DATABASE_URL:?A disposable PostgreSQL database is required}"
export PYTHONPATH=.
uv run --project packages/capstone-agent pytest \
  packages/capstone-agent/tests/test_product_block*.py \
  packages/capstone-agent/tests/test_product_index_host.py \
  packages/capstone-agent/tests/test_product_index_http.py \
  packages/capstone-agent/tests/test_product_index_jobs.py \
  packages/capstone-agent/tests/test_product_index_process.py \
  packages/capstone-agent/tests/test_product_index_reader.py \
  packages/capstone-agent/tests/test_product_index_worker.py \
  packages/capstone-agent/tests/test_product_index_service.py \
  packages/capstone-agent/tests/test_thread_products.py \
  packages/capstone-agent/tests/test_thread_input.py \
  packages/capstone-agent/tests/test_thread_deliveries.py \
  packages/capstone-agent/tests/test_cli.py \
  packages/capstone-agent/tests/test_hosting.py \
  tools/tests/test_ci_product_references.py -q
npm --prefix packages/capstone-app test -- \
  src/ProductParagraphPicker.test.tsx src/ProductReferenceChips.test.tsx \
  src/productBlocks.test.ts src/threadProducts.test.ts src/threadProductsTransport.test.ts \
  src/threadInput.test.ts src/applicationCapacity.test.ts src/ThreadProductsWorkspace.test.tsx
npm --prefix packages/capstone-app run check
