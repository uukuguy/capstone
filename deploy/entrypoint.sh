#!/bin/sh
set -eu

case "${1:-}" in
  api)
    exec uv run --no-sync --project /app/packages/grid-agent python -m grid_agent.hosted
    ;;
  worker)
    exec uv run --no-sync --project /app/packages/capstone-agent capstone-agent work-hosted
    ;;
  *)
    echo 'usage: entrypoint.sh api|worker' >&2
    exit 64
    ;;
esac
