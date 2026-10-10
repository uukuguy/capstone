# Minimal demo baseline alignment

## Scope

Preserve development work, align the local development and demo foundation with
the current verified cloud demo, and establish controlled branch management.
Cloud stages are unchanged. This work does not repair the failed formal answers.

The runtime foundation is `ed2524f`, the existing cloud-demo rollback source.
Preparation `94b5d40` restores that runtime without resetting main or deleting
history. Correction `2540bdc` adds only five-file history/diagram contract
guards and typed empty credential leases. It removes 13 inherited type errors;
no numerical model, calculation, evidence rule or new Pi feature is added.
Local demo management remains separate from application semantics.

## Source preservation

- Original development commit `ca062df` is retained at
  `archive/dev-before-baseline-20261010`.
- `feat/pi-skills-integration` at `fba1f51` reapplies the pre-incident `e9aca89`
  runtime after baseline restoration. It remains experimental, with no new
  deployment or acceptance claim. Three test files only lose trailing blank
  lines. This creates real mergeable work; an ancestor-only snapshot would be
  reported by Git as already merged.
- `fix/framework-answer-chain` retains `3e3bbfb`. Existing
  `fix/demo-n1-outcome` is unchanged. Its manual answer acceptance remains failed.
- Existing historical feature branches are retained. They are ancestors of the
  previous main; their names alone do not prove separation from main.
- Original dirty user documents were saved as an ignored diff and hash receipt.
  No authentication state was copied. State documents receive explicit current
  policy and experimental ownership annotations; unrelated content is retained.

## Verification before main integration

- Fresh isolated setup, managed Pi installation and doctor pass.
- Types: zero errors after the minimal contract repair.
- Focused checks: Thread 46, pandapower diagram/hosted 5, PyPSA diagram/hosted 7;
  offline walking skeleton 13 and answer admission 12 pass.
- Integration gate passes: compatibility E2E39, registered worker checks3,
  runtime-risk and protected-path checks, static-analysis validation and
  application-instantiation validation. Pi capture checks use local loopback
  responses; no external paid Provider call is made.
- Package and frozen-source setup checks pass, including installed authority,
  typed PyPSA handoff, operations, planning and sector checks.
- Full offline gate passes. Key suites include grid-agent928, simulator189,
  Capstone580, App348, Kernel567 and pandapower Domain Pack105. Forty-five
  Capstone tests are skipped under the offline test configuration;
  actual local PostgreSQL preservation and API/history checks run separately.
  Main integrates the verified `2540bdc` candidate by fast-forward, preserving
  history. After focused guard checks, `release/demo-baseline-1` freezes
  `a076b04`, which adds only the protected-file ignore rule to the same tested
  runtime. It is not a cloud acceptance tag.

## Local demo candidate

Canonical rebuild passes for source `2540bdc`, using the separate
`capstone-demo-local` project, App15173/API18767. API and both workers share
image `sha256:64884e997d0aaba013932cf77484df01cb71ee1ef8138cf359df259071af9869`.
All 505 declared backend source/manifest files match the selected checkout in
each role; App build identity matches the clean checkout.

Three registered cases pass nine turns, report generation and evidence replay.
Both retained Thread snapshots and history can be read. All 362 pre-existing
local-demo event digests and both stored-volume names remain intact.

Main canonical rebuild also passes, with API/worker image
`sha256:746d610f17792b4f47f73d423a623537249805bdd1d762da9cb5c7866be1eae0`.
Its three registered cases pass nine turns, reports and evidence replay. All
510 retained dev Thread snapshots/history can be read. All 8,682 original dev
event digests and all five volume names remain. The unused old general-Pi
container has zero unresolved receipts and is stopped; its private volumes
remain for future experimental work.

Both local environments have identical `aarch64` runtime identities across
all six roles, despite separate locally built image digests:

- Contract: `48d470f5626f3b2abfd8a7c483f569f7e32721384dd343142b71cafdb80fa5ef`.
- Source artifact: `85a296c878f628b330ae1b940f55fef43252137086022b289b68e629a410d8eb`.
- Installed artifact: `5ff3107a580fa4281a3cadc7768a344576ac360ffacc8e4f0ffc04823cbb1b17`.

Repair branch `fix/local-demo-secret-ignore` at `a076b04` retains the protected
demo environment path alongside the separate local-demo management tooling.
Its focused checks pass; the repair is merged into main, baseline preparation
and the affected Pi/skills branch. No secret value enters source or logs.
Documentation/register commits after the runtime baseline do not imply a new
deployment; record the actual rebuilt source and artifact receipts separately.

Exact identities and final outcomes are recorded in ignored receipts under
`runs/version-baseline-alignment/`: `local-demo-source-identity.json`,
`local-demo-checks.json`, `local-dev-source-identity.json`, `local-dev-checks.json`,
`runtime-contract-identities.json`, `data-before.json`, `data-after.json`,
and each stage's retained-history receipt.

## Acceptance limits

This is minimum-impact source and infrastructure alignment, not acceptance of
new answer behavior. Generator N−1 ranking, scenario-specific conclusions,
partial-result explanation and response scale remain open for baseline two.
No cloud deployment, acceptance tag, paid question replay or remote push occurs
in this task. Environment labels remain a future release requirement.

The fixed [version register](../status/VERSION-CONTROL.md) records branch,
public-fix, release and rollback rules. A feature merge requires current main
synchronization and its own integration/experimental-isolation checks; source
preservation does not waive those gates.
