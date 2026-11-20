#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
uv run --project packages/capstone-agent pytest -q \
  packages/capstone-agent/tests/test_deep_research_control.py \
  packages/capstone-agent/tests/test_enterprise_normal_chat.py \
  packages/capstone-agent/tests/test_general_pi_server.py \
  packages/capstone-agent/tests/test_native_llm_pool.py \
  packages/capstone-agent/tests/test_unscoped_research_intent.py \
  packages/capstone-agent/tests/test_goal_mode.py \
  packages/capstone-agent/tests/test_mission_continuation.py \
  packages/capstone-agent/tests/test_model_request_pool_events.py \
  packages/capstone-agent/tests/test_llm_pool_events.py \
  packages/capstone-agent/tests/test_llm_pool_session.py
node --test packages/capstone-agent/tests/fixtures/{general-sdk-graph-errors,enterprise-graph-runtime}.test.mjs
npm run check --prefix packages/capstone-app
npm test --prefix packages/capstone-app -- \
  src/DeepResearchControl.test.tsx src/threadWorkProtocol.test.ts src/ThreadLiveEntry.test.tsx \
  src/ThreadSharedWorkspace.test.tsx src/CapstoneAssistantThread.test.tsx
git diff --check
