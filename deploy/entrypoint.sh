#!/bin/sh
set -eu

application="${CAPSTONE_HOSTED_APPLICATION:-pandapower}"

case "${application}:${1:-}" in
  pandapower:api)
    exec uv run --no-sync --project /app/packages/grid-agent python -m grid_agent.hosted
    ;;
  pandapower:worker)
    exec uv run --no-sync --project /app/packages/grid-agent python -m grid_agent.hosted_worker
    ;;
  pypsa:api)
    exec uv run --no-sync --project /app/packages/pypsa-agent python -m pypsa_agent.hosted
    ;;
  pypsa:worker)
    exec uv run --no-sync --project /app/packages/pypsa-agent python -m pypsa_agent.hosted_worker
    ;;
  *)
    echo 'usage: CAPSTONE_HOSTED_APPLICATION=pandapower|pypsa entrypoint.sh api|worker' >&2
    exit 64
    ;;
esac
