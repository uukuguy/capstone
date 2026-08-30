#!/usr/bin/env bash
set -euo pipefail

test_root=$(git rev-parse --show-toplevel)
default_output=$(make -C "$test_root" --no-print-directory -n application)
override_output=$(make -C "$test_root" --no-print-directory -n application APPLICATION=custom-domain INSTRUCTIONS=custom-questions.txt PROVIDER=deepseek MODEL=deepseek-v4-flash)

grep -Fq 'grid-agent analysis-generic --application "pandapower-static-analysis" --instructions "validation/questions/task.md.txt"' <<<"$default_output"
grep -Fq 'grid-agent analysis-generic --application "custom-domain" --instructions "custom-questions.txt" --provider "deepseek" --model "deepseek-v4-flash"' <<<"$override_output"
! grep -Fq 'grid-agent analysis-generic' < <(make -C "$test_root" --no-print-directory -n analysis)
