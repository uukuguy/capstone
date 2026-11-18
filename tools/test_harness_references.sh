#!/usr/bin/env bash
set -euo pipefail

make check-package-boundaries

agent=packages/capstone-agent/tests
uv run --project packages/capstone-agent python -m pytest -q \
  packages/capstone-control/tests \
  "$agent"/test_{agent_delegation,answer_presentation,continuation_file_capacity,control_host}.py \
  "$agent"/test_{data_gateway_relay,data_gateway_views,grid_electrical_view,gateway_progressive}.py \
  "$agent"/test_{delegated_runtime,general_pi_executor,general_pi_server,goal_mode,goal_receipts,harness}.py \
  "$agent"/test_{main_chain_context,mission_continuation,pi_delegation,thread_http_api,thread_work_execution,thread_worker}.py \
  tools/tests/test_ci_scope.py tools/tests/test_host_runtime_contract.py tools/tests/test_image_layer_order.py

uv run --project packages/pandapower-domain-pack python -m pytest -q \
  packages/pandapower-domain-pack/tests/test_authority.py \
  packages/pandapower-domain-pack/tests/test_execution.py

uv run --project packages/pandapower-application python -m pytest -q \
  packages/pandapower-application/tests/test_domain_execution_lifecycle.py \
  packages/pandapower-application/tests/application/test_hosted.py

npm --prefix packages/capstone-app run check
npm --prefix packages/capstone-app test -- src/ExecutionDetails.test.tsx src/InstructionStatus.test.tsx src/ThreadWorkExecution.test.tsx src/ThreadWorkspace.test.tsx src/CapstoneAssistantThread.test.tsx src/threadHttpTransport.test.ts \
  src/ThreadProductsWorkspace.test.tsx src/ProductComparison.test.tsx src/ResourceReadSources.test.tsx
