#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
STATE_DIR=${CLIMB_STATE_DIR:-"$ROOT/docs/status/climb"}
HYPOTHESIS_ID=${1:?usage: train.sh H-NNN}
STAMP=${CLIMB_FIXED_TIMESTAMP:-$(date -u +%Y%m%dT%H%M%SZ)}
LOWER_HYPOTHESIS_ID=$(printf '%s' "$HYPOTHESIS_ID" | tr '[:upper:]' '[:lower:]')

ARTIFACT_DIR=$(python3 - "$ROOT" "$STATE_DIR" "${CLIMB_ARTIFACT_DIR:-}" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
state_dir = Path(sys.argv[2])
override = sys.argv[3]
if override:
    artifact_dir = Path(override)
else:
    config = json.loads((state_dir / "config.yaml").read_text(encoding="utf-8"))
    artifact_dir = Path(config.get("artifact_dir", "runs/climb"))
if not artifact_dir.is_absolute():
    artifact_dir = root / artifact_dir
print(artifact_dir)
PY
)

RUN_DIR="$ARTIFACT_DIR/${STAMP}-${LOWER_HYPOTHESIS_ID}"
mkdir -p "$RUN_DIR"
python3 - "$STATE_DIR" "$RUN_DIR/manifest.json" "$HYPOTHESIS_ID" "$STAMP" <<'PY'
import json
import sys
from pathlib import Path

state_dir = Path(sys.argv[1])
manifest_path = Path(sys.argv[2])
hypothesis_id = sys.argv[3]
stamp = sys.argv[4]
config = json.loads((state_dir / "config.yaml").read_text(encoding="utf-8"))
manifest_path.write_text(
    json.dumps(
        {
            "hypothesis_id": hypothesis_id,
            "kind": "workstream-b-package-extraction-gate",
            "session": config["session"],
            "started_at": stamp,
        },
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)
PY
printf '%s\n' "$RUN_DIR"
