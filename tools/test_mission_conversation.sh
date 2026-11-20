#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${CAPSTONE_TEST_DATABASE_URL:?A disposable PostgreSQL database is required}"
export PYTHONPATH=.
uv run --project packages/capstone-agent pytest packages/capstone-control/tests -q
uv run --project packages/capstone-agent python -m pytest -q \
  packages/capstone-agent/tests/test_enterprise_normal_chat.py \
  packages/capstone-agent/tests/test_instruction_queue.py \
  packages/capstone-agent/tests/test_goal_continuation.py
uv run --project packages/capstone-agent pytest packages/capstone-agent/tests/test_mission_origin.py packages/capstone-agent/tests/test_mission_equipment.py packages/capstone-agent/tests/test_mission_continuation.py packages/capstone-agent/tests/test_mission_delivery_verification.py packages/capstone-agent/tests/test_native_mission.py packages/capstone-agent/tests/test_agent_delegation.py packages/capstone-agent/tests/test_native_graph_context.py packages/capstone-agent/tests/test_pi_delegation.py packages/capstone-agent/tests/test_general_pi_server.py packages/capstone-agent/tests/test_general_pi_executor.py packages/capstone-agent/tests/test_delegation_resources.py packages/capstone-agent/tests/test_intent_runtime.py packages/capstone-agent/tests/test_delegation_resource_alias.py packages/capstone-agent/tests/test_mission_resource_protocol.py packages/capstone-agent/tests/test_mission_model_admission.py packages/capstone-agent/tests/test_thread_resources.py packages/capstone-agent/tests/test_resource_range_transport.py -q
uv run --project packages/pandapower-application python -m pytest tools/tests/test_ci_mission_conversation.py tools/tests/test_ci_scope.py tools/tests/test_host_runtime_contract.py -q
node --test packages/capstone-agent/tests/general-mission-tools.test.mjs packages/capstone-agent/tests/fixtures/tool-discovery.test.mjs packages/capstone-agent/tests/general-sdk-steering.test.mjs
npm run check --prefix packages/capstone-app
npm test --prefix packages/capstone-app -- src/threadWorkProtocol.test.ts src/ThreadInputControls.test.tsx src/missions.test.ts src/ThreadWorkExecution.test.tsx src/ControlGoals.test.tsx src/ControlTaskBoard.test.tsx src/controlGoals.test.ts src/ControlWorkspaceViews.test.tsx src/threadHttpTransport.test.ts src/threadWorkMessages.test.ts src/threadResourceTransport.test.ts
git diff --check
