# Live Session Checkpoint

Updated: 2026-10-17. Active work; no final handoff.

## Current action

- LATEST USER CORRECTION supersedes remaining checkpoint: new task = new conversation; enterprise-research/grid-analysis only preconfigure ApplicationProfile; unified shared execution between messages. No save/start flow or extra start button. Full existing dialogue area/features must be adapted, not simplified by props/text-only composer. Saved Work is internal progress, not delivery. Design/plan corrections are dirty in root and must be retained.
- PR50 is now DRAFT; CI38941770837 cancellation requested, never count as accepted. Backend assets retained. Frontend acceptance withdrawn in review report. Root branch feat/work-attempt-binding at5e7fccc1, local-dev stilla8b4e578 old candidate. Do not merge PR50 until full normal dialogue/feature parity corrected.
- CI policy a5142dc7 on chore/dev-macos-ci in .worktrees/dev-macos-ci; PR51 targetsdev, macOS-only CI38945218238 running. 119tests/2skipped,doctor,independent review passed. Remote dev protection already macOS-only by explicit user instruction; main still both. Merge PR51 after mac pass, preserve product branch and all dirty work.
- Backend worker work_protocol_backend IMPLEMENTING normal dialogue in ROOT worktree, owns Python/backend tests plus needed runtime/deploy configs. Does not own App/docs/CI. Canonical plan docs/superpowers/plans/2026-10-17-enterprise-normal-conversation.md (new dirty). Shared send_message must atomically input+Attempt; no fake model; same queue/worker/Harness/general Pi. Native current_attempt neutral with nullable model and work_id. Must preserve original InputSubmission/skills/context contract; text-only would repeat rejected simplification. No Provider authorization.
- UI audit /tmp/enterprise-normal-chat-ui-scope.md lists full component feature parity and conflicting old design. UI worker currently completed read-only; start implementation after backend wire/foundation freeze (skill sequential implementation), using mature single render tree/controller, no independent enterprise chat.
- Next: merge CI policy, align control on dev; finish backend and independent review, complete shared full UI, tests/rebuild/browser; actual Provider dialogue acceptance needs explicit authorization only after concrete ready implementation. Do not claim full application delivery based on offline fixtures or save/restore.

## Earlier checkpoint (superseded by latest corrections)

- PR50 targets dev from feat/work-attempt-binding, head5e7fccc1. Product implementation1af3c52a, fixture correctioneb51d354, lease fixa8b4e578. Linux/macOS product CI38941770837 running. No further product changes planned before merge.
- Independent backend/UI/lease reviews approve. Full backend1465 passed/2 skipped, App552 passed, professional938 passed/3 skipped, simulator244 passed/2 skipped. All other make check-pr targets passed in segmented runs. Logs /tmp/work-attempt-backend-final.log, /tmp/work-attempt-remaining-clean-env.log. Tests require loopback NO_PROXY/no_proxy and no inherited GRID_AGENT_LLM_MODEL/PROVIDER.
- Final canonical rebuild ready. API and both workers1153 files matcha8b4e578, image6aa4d1901cdc; App build identitya8b4e578. Receipt runs/work-attempt-binding/local-identity.json.
- Actual browser acceptance passed: professional v1 read unchanged, first Work save upgradesv2; supplement/reload retains two messages, Work revision2/goal_revision1; start enabled with real model but not clicked. Thread thr_ff5128f155a022d6e65a, Work work_9e5baab14671da22c2c3. Model-free thr_c32d0f45308b7340e885 stays readable and cannot start. No Provider or task execution. Desktop/390px no overflow, console clean. Report output/playwright/work-attempt-browser-acceptance.md and screenshots work-attempt-work-ready-desktop.png/work-attempt-work-restored-mobile.png.
- Next: await CI, verify merge tree equals tested head, merge normally, fast-forward dev and both application preparation branches, close merged source branch, update report/register/plan and regenerate graph on dev. Preserve977601f9/d4600ddc and exact deployment sources. No cloud/demo/main release.

## Scope and baseline

- Accepted dev885b2c14 includes PR48d86cc4ef and PR49 control. Both preparation branches feat/business-analysis and feat/model-decision remain885b2c14 until integration.
- Enterprise workspace uses existing ThreadWorkspace, CapstoneAssistantThread and ComposerSurface under the accepted graphite/warm-white design. Do not restore the rejected standalone frontend.
- enterprise-research is 企业研究与分析, intranet default with public web off unless explicitly enabled; grid-analysis is 电网分析与决策, retaining existing pandapower/PyPSA assets. New Profile assemblies remain pending.
- Current slice binds Work to existing professional Attempt execution/cancel/recovery. Task3 model-free continuous Pi organization and Task5 full artifacts workspace remain. No Demo1/Demo2 or business-quality completion claim.
- maincf72393b, cloud-dev24d9a325, local/cloud-demo faa6af9 and user e2eaee2 remain unchanged.

## Control and recovery

- Current register/graph belong on dev. Important commits need nodes; use ui-ux-pro-max, verified ancestry, source edges, geometry and screenshots. Regenerate after final branch synchronization; avoid an infinite self-SHA control loop.
- Preserve original stash a91a148494f520e973f5d63158916b42a5df6773 and /tmp/capstone-pre-convergence-root-work.tar.gz; detached Pi worktreeabf2f797 and all var/data remain. Temporary control stash93d02be8e1a2e4e1afc53601bf0ff9d7626102da was applied, made durable in PR47 and dropped; original recovery stash remains.
- Git network: http.proxy=http://127.0.0.1:7897, HTTP/1.1, gh auth git-credential. Rebuild uses process-local HTTP_PROXY/HTTPS_PROXY/ALL_PROXY at that proxy and NO_PROXY=127.0.0.1,localhost; no system proxy change.
- Final generated snapshot and recovery log may remain dirty on dev to show the actual final HEAD without creating another control loop.
