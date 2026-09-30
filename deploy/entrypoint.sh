#!/bin/sh
set -eu

case "${1:-}" in
  api)
    exec uv run --no-sync --project /app/packages/grid-agent python -m grid_agent.hosted
    ;;
  worker)
    exec uv run --no-sync --project /app/packages/grid-agent python -m grid_agent.hosted_worker
    ;;
  *)
    echo 'usage: entrypoint.sh api|worker' >&2
    exit 64
    ;;
esac
