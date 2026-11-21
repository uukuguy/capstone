#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${CAPSTONE_TEST_DATABASE_URL:?A disposable PostgreSQL database is required}"
export PYTHONPATH=.
uv run --project packages/capstone-agent pytest packages/capstone-agent/tests/test_capacity_contract.py packages/capstone-agent/tests/test_application_capacity.py packages/capstone-agent/tests/test_task_record_reader.py packages/capstone-agent/tests/test_instruction_queue_roundtrip.py packages/capstone-agent/tests/test_instruction_queue.py packages/capstone-agent/tests/test_enterprise_normal_chat.py packages/capstone-agent/tests/test_instruction_transport.py packages/capstone-agent/tests/test_thread_work_execution.py packages/capstone-agent/tests/test_native_instruction_transport.py packages/capstone-agent/tests/test_general_pi_executor.py packages/capstone-agent/tests/test_pi_delegation.py packages/capstone-agent/tests/test_harness.py packages/capstone-agent/tests/test_delegated_runtime.py -q
uv run --project packages/pandapower-application python -m pytest tools/tests/test_ci_instruction_admission.py tools/tests/test_ci_scope.py -q
node --test packages/capstone-agent/tests/general-sdk-steering.test.mjs
node --test --test-name-pattern='compaction transport' packages/capstone-agent/tests/fixtures/tool-composition.test.mjs
uv run --project packages/capstone-agent pytest -q packages/capstone-agent/tests/test_general_pi_server.py -k compaction
npm run check --prefix packages/capstone-app
npm test --prefix packages/capstone-app -- src/ExecutionDetails.test.tsx src/InstructionStatus.test.tsx src/threadWorkProtocol.test.ts src/threadHttpTransport.test.ts src/ThreadWorkExecution.test.tsx src/CapstoneAssistantThread.test.tsx
git diff --check
