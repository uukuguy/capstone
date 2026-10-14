# Live Session Checkpoint

> Updated: 2026-10-14. Session remains active; recovery checkpoint.

## Current discussion: user-local dev trial

- PR #19 merged as c03277d; root dev and remote were aligned and clean, PR #17 and its superseded branch were closed. Recovery references and user data remain.
- The user requests installation/deployment commands in the CAPSTONE CLI design. Users have development/deployment skills; Linux/macOS first, Windows desirable. pip/npm or a deployment script are preferred entry forms.
- This delivery is a temporary trial of a frozen dev revision on the user's machine, not a stable release or a demo update. The CLI discussion records these requirements and proposed thin-script/Compose delivery; no installer, images or package publication has been implemented in this discussion.
- The owner is `docs/superpowers/specs/2026-09-29-agent-interaction-discussion.md`, section “2026-10-14：CAPSTONE CLI 安装与用户本地 dev 试用”. Packaging, registry name, precise command spelling and Windows verification remain proposals. Do not silently turn the proposal into an approved implementation plan or replace the existing autonomous business worklist.

## Current source

- PR #18 merged normally into dev `faa6af9b4a6fe567c559d0b68ab1c4e5aa1bd4fe`. Candidate2b6ae7b passed Linux/macOS PR and full-release checks; complete Git trees match. Post-merge dev CI38558756435 passed.
- Accepted runtime source is faa6af9. Control documentation uses a separate PR targeting dev; its commits do not replace the deployed source. Previous unpublished control commits survive at `recovery/dev-control-pre-faa6af9`; retained stash and the exact 20-file snapshot are recorded in `.capstone-agent/dev-integration-faa6af9/manifest.json`.
- local-dev5173/8767: faa6af9, App dirty=false, three roles share imaged999269d8b8a; all529 installed source files match the commit.
- cloud-demo: faa6af9, four roles SUCCESS. API6403a72d-a9bf-4a97-af9f-770ba94d12d4; App6a7f16ed-c90d-490e-8028-a2316c7b3712; pandapower aed302e7-6cf2-4e81-b4dc-661f082f60a1; PyPSA f30c96c7-7e15-4ada-ad59-9dd280737900. Three receipts agree, source275d02003c10/cloud installed621d77adddca. Three cases/nine turns, reports/evidence replay and original Thread diagram/Composer pass without Provider.
- local-demo15173/18767: faa6af9, canonical rebuild ready, three roles share image3a2d87862325. Receipts match local-dev; App dirty=false; six original Threads/event sequences preserved. Registered regression passed: three cases/nine turns/reports/evidence replay; log `runs/demo-n1-debug/local-demo-faa6af9-checks.log`.
- cloud-dev remains24d9a32 with user traffic; do not change it.

## Immediate action

1. Both demos passed regression and old Thread diagram/Composer browser checks. Annotated demo-20261014-2028-faa6af9 was pushed and remote source verified. Continue product gaps from dev; never formally tag candidate2b6ae7b.
2. Control graph and owning records are aligned locally; eight important nodes, centred vertical dev/main axis, four exact deployment references and actual in-research Pi branch. Both spacing limits passed reachability, overlap, crossing and arrow checks. Ordinary intermediate commits remain in history.
3. PR #19 carries all remaining root control/design/audit records into dev; its authoritative merge/check state is linked in VERSION-CONTROL. Closeout execution requires both platform checks, normal PR merge, root dev fast-forward and an empty Git status. PR #17 is superseded by this updated record. After closeout, continue the N−1 input/reference/closing investigation from dev. Preserve recovery references and data.
4. Merged autonomous branch was renamed recovery/autonomous-agent-merged-faa6af9 locally; remote feature branch was closed. The dirty worktree and all data remain. Pi38e19db is in research on old6ff7094; new-dev adaptation remains. Research Model R1 is a separate paused plan without implementation.

## Limits and rejected paths

- N−1 input growth, result references, closing latency, island interpretation, recovery/eviction and overall scientific acceptance remain open. Registered cases do not establish full scientific acceptance.
- Diagram action once hit footer pointer interception; do not claim its click path passed. Original cloud Thread diagram restores correctly.
- No Provider calls, auth copying or data/volume deletion. Temporary Railway SSH key/files were removed. Use secret-free startup receipt logs.
- Local-demo setup uses Python3.12 with setup/install-pi/doctor before canonical rebuild. Verified official model assets are shared read-only for builds; data/environment stores remain isolated.
- local-dev App now runs the exact faa6af9 clean source archive at `.capstone-agent/releases/faa6af9/backend/packages/capstone-app`, with a source receipt and local-dev environment. Its files match the accepted App source. This keeps runtime identity stable while control-only commits advance dev; the next product iteration uses the canonical local rebuild entrypoint. App PID/log stay under the root ignored `.capstone-agent/` directory.
