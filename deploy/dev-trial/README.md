# Fixed dev trial packaging

This folder contains operator templates. Users receive a source-free package, not this checkout. User steps are in the [runbook](../../docs/RUNBOOK.md#source-free-local-dev-trial). Current verification and distribution live in the [version register](../../docs/status/VERSION-CONTROL.md).

The backend image serves API and both workers. The App image serves a same-origin static client with public source identity. PostgreSQL and RustFS have separate persistent volumes. The local-only trial runtime profile permits DeepSeek or OpenAI; the existing cloud profile stays pinned.

## Prepare an exact source

Use a committed development candidate for validation. After normal PR integration, use the actual dev merge SHA for final artifacts. Prepare the managed runtime first; select the directory containing the six verified model assets. Do not copy authentication from another worktree.

```sh
CAPSTONE_TRIAL_REVISION=$(git rev-parse HEAD)
uv run --project packages/grid-agent python deploy/build_dev_trial.py \
  --source-revision "$CAPSTONE_TRIAL_REVISION" \
  --model-library "$CAPSTONE_PYPSA_MODEL_LIBRARY_DIR" \
  --output ".capstone-agent/trial-$CAPSTONE_TRIAL_REVISION"
```

The output must be new and ignored. Preparation exports the selected Git tree, uses its App helper, stages verified assets, and records source/input/asset checksums. It never copies credentials or user state. Build the backend context with `CAPSTONE_SOURCE_REVISION` set to the same full SHA; build `trial-app/` as the App context. Candidate builds select one platform and distinct local tags. Final registry builds select bothlinux/amd64 andlinux/arm64.

## Validate and publish

1. Generate a candidate package with `write_bundle(..., candidate=True)` or the CLI's `--image-manifest`, `--bundle-output`, and `--candidate-platform` arguments. Its image manifest must name the same source. Set `CAPSTONE_CANDIDATE_VALIDATION=1` only for operator validation. Use isolatedcapstone-user-* projects and ports.
2. Check actual source, App/API readiness, shared backend image, image architecture, registered cases, reports/evidence replay, restart persistence and browser behavior. Record native/emulated execution. Use scripted cases without Provider calls; test LLM configuration with synthetic values.
3. Complete independent review and all required PR gates, integrate normally into dev, then freeze its exact accepted merge source. Do not change cloud/demo stages or issue their acceptance tags for this trial.
4. Push both backend/App architectures to Aliyun. ACR does not accept the empty-config attestation encountered during validation: use `--provenance=false` and Docker media types for these registry outputs. Copy the actual PostgreSQL/RustFS platform images, preserve their config/layer identities, and assemble a compatible two-platform manifest. Never claim a rebuilt mirror has the original digest.
5. Verify all platform manifests and source identities. Pull anonymously with a separate empty Docker configuration. Run fresh source-free packages for the exact final source/digests, including persistence and browser checks.
6. Final `write_bundle()` requires `capstone-dev-trial-acceptance/1`: matching source/images, both platform receipts with readiness/cases/replay/restart/browser/anonymous_pull passed, and metadata binding all image references/platforms plus backend/App source. A platform list alone cannot authorize final package creation.

The user package contains onlycompose.yaml, start.sh, .env/.env.example, release.env, manifest.json and README.txt. Archive these files and publish a checksum plus a version-specific download/installation entry. Preserve all verification receipts, private instance directories and data. This distribution is temporary dev trial; Windows/WSL2 remains a target until actual validation.
