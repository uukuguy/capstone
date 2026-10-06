#!/bin/sh
set -eu

if [ -n "${CAPSTONE_RUNTIME_PROFILE:-}" ]; then
  exec uv run --no-sync --project /app/packages/capstone-agent python /app/deploy/launch_host_runtime.py "${1:-}"
fi

application="${CAPSTONE_HOSTED_APPLICATION:-pandapower}"

case "${application}:${1:-}" in
  pandapower:api)
    exec uv run --no-sync --project /app/packages/grid-agent python -m grid_agent.hosted
    ;;
  pandapower:worker)
    export CAPSTONE_THREAD_FAMILY=pandapower
    exec uv run --no-sync --project /app/packages/grid-agent python -m grid_agent.hosted_worker
    ;;
  pypsa:api)
    exec uv run --no-sync --project /app/packages/pypsa-agent python -m pypsa_agent.hosted
    ;;
  pypsa:worker)
    export CAPSTONE_THREAD_FAMILY=pypsa
    exec uv run --no-sync --project /app/packages/pypsa-agent python -m pypsa_agent.hosted_worker
    ;;
  capstone:api)
    exec uv run --no-sync --project /app/packages/capstone-agent python -m capstone_agent.federated_hosted
    ;;
  *)
    echo 'usage: CAPSTONE_HOSTED_APPLICATION=capstone|pandapower|pypsa entrypoint.sh api|worker' >&2
    exit 64
    ;;
esac
