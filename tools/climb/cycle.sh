#!/usr/bin/env bash
set -euo pipefail

ROOT=$(git rev-parse --show-toplevel)
HYPOTHESIS_ID=${1:?usage: cycle.sh H-NNN}
RELEASE_HYPOTHESIS_ID=$(python3 - "$ROOT/docs/status/climb/config.yaml" <<'PY'
import json
import sys

print(json.load(open(sys.argv[1], encoding="utf-8")).get("release_hypothesis_id", ""))
PY
)
RUN_DIR=$("$ROOT/tools/climb/train.sh" "$HYPOTHESIS_ID")
if [ "$HYPOTHESIS_ID" = "$RELEASE_HYPOTHESIS_ID" ]; then
  "$ROOT/tools/climb/release-closure.py" "$RUN_DIR" >"$RUN_DIR/local-eval.json"
  chmod 400 "$RUN_DIR/local-eval.json"
else
  "$ROOT/tools/climb/eval-local.sh" "$RUN_DIR" >"$RUN_DIR/local-eval.json"
fi
"$ROOT/tools/climb/decision-gate.py" --local-eval-json "$RUN_DIR/local-eval.json" >"$RUN_DIR/decision.json"
if [ "$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["decision"])' "$RUN_DIR/decision.json")" = "PUSH" ]; then
  "$ROOT/tools/climb/push.sh" "$RUN_DIR" >"$RUN_DIR/push.json"
fi
"$ROOT/tools/climb/sync-cycle.py" \
  "$HYPOTHESIS_ID" \
  "$RUN_DIR" \
  "$RUN_DIR/local-eval.json" \
  "$RUN_DIR/decision.json"
if [ "$HYPOTHESIS_ID" = "$RELEASE_HYPOTHESIS_ID" ]; then
  chmod 400 "$RUN_DIR/decision.json" "$RUN_DIR/manifest.json"
  if [ -f "$RUN_DIR/push.json" ]; then
    chmod 400 "$RUN_DIR/push.json"
  fi
fi
printf '%s\n' "$RUN_DIR"
