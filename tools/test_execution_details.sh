#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHONPATH=. uv run --project packages/pandapower-application python -m pytest tools/tests/test_ci_execution_details.py tools/tests/test_ci_scope.py tools/tests/test_user_local_graph.py -q
uv run --project packages/capstone-agent pytest -q \
  packages/capstone-agent/tests/test_main_chain_context.py \
  packages/capstone-agent/tests/test_enterprise_normal_chat.py \
  packages/capstone-agent/tests/test_unscoped_research_intent.py \
  packages/capstone-agent/tests/test_pi_delegation.py
npm run check --prefix packages/capstone-app
npm test --prefix packages/capstone-app -- src/ExecutionDetails.test.tsx src/CapstoneAssistantThread.test.tsx src/ThreadWorkEntry.test.tsx src/ThreadWorkExecution.test.tsx src/threadViewRouting.test.ts
git diff --check
