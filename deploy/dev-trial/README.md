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

The revised user-local package adds capstone.sh, the selection bootstrap and a source-bound data-contract.env to the frozen Compose runner and configuration. The fixed installer template is install-version.sh; stamp its source, version, archive URL and checksum after acceptance. Default App port is 19173. Store frozen packages under ~/capstone/versions/<full-Git-SHA>; keep the user's .env at the installation root. Preserve existing configuration, receipts and volumes. The root manager starts the selected version after compatibility and configuration checks; its completion output shows URL, directory, Git revision and management commands. Pull all four exact images in the foreground with Docker layer progress.

Versions share one installation's PostgreSQL ledger and artifact volumes. Data declarations conservatively hash backend sources, dependency inputs, schemas/capability contracts, the private-state helper and exact storage images. Equal fingerprints permit the currently supported same-format path; changed fingerprints block switching until a verified migration path is implemented. This guard does not prove that old data works: final bundle creation also requires matching old-data upgrade, read, evidence replay and separate rollback receipts. Perform these checks in isolated installations and preserve the real user installation.

For an original 7832134 installation, generate legacy-data-contract.env from that exact Git archive and its accepted image mapping using deploy/user_data_compatibility.py. Include it in the checksum-protected revised archive. The manager checks the original manifest/receipt before binding this declaration; never edit an old source receipt to attach new images. Publish the immutable user-local-SHA release first, then register its full source, release URL, installer checksum and date in docs/status/USER-LOCAL-VERSIONS.tsv. Only verified published entries are installable. Existing dev-trial releases remain recovery references. Windows/WSL2 remains a target until actual validation.
