#!/usr/bin/env bash
set -euo pipefail

test_root=$(git rev-parse --show-toplevel)
for target in run run-llm analysis analysis-generic application report trajectory; do
  if make -C "$test_root" --no-print-directory -n "$target" >/dev/null 2>&1; then
    echo "Retired target still exists: $target" >&2
    exit 1
  fi
done
grep -Fq 'CAPSTONE_APP_ENVIRONMENT="local-dev" npm run dev' < <(make -C "$test_root" --no-print-directory -n capstone-app-dev)
grep -Fq 'CAPSTONE_APP_ENVIRONMENT="local-demo" npm run dev' < <(make -C "$test_root" --no-print-directory -n capstone-app-dev CAPSTONE_APP_ENVIRONMENT=local-demo)
