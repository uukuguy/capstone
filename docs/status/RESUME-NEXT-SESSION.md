# Live Session Checkpoint

Updated: 2026-10-28 00:48. Session remains active.

## Current task

Same-task summer comparison is DONE, commit5981a4e6. Both new conversations
completed with the exact same instruction/profiles/native binding; only DR flag
changed. Report docs/reports/2026-10-27-summer-lightweight-dr-comparison.md and
514-row execution-path.csv. Light383.658s/65responses/88tools/14slides; DR843.856s/
157responses/204tools/15slides. DR finds real2024typhoons and deeper checks but
semantic/unit/summary inconsistencies remain. Neither fully business accepted.
Do not change saved reports to improve comparison results. Raw evidence and
products in ignored runs/summer-comparison-20261027/{lightweight,dr}. Both PPT
covers rendered in Vivaldi; 56published artifact hashes matched. Doctor passed.

User NOW requests toolbar: remove Context; attachments beside owning instruction;
DR binary defaultOFF, mutedOFF/highlightedON, next submitted instruction ONLY,
resetOFF after acceptance; Settings FIRST or LAST (we choseLAST). Agreed order:
深度思考, 模型, 上传资料, 设置. No questions/approval needed.

UI changes implemented, tested265App tests/9.16s +TSC +diffcheck. New
InstructionAttachments.tsx joins accepted attachment_refs to existing stored
resource metadata; no file bodies. Per-instruction projection and reload tested.
Old slash contracts kept; material session subtitle/context shortcut removed.
Settings last in WorkAdapter and Fixture. Added deep_research to pending-command
recovery whitelist (previously missing); exactchoice roundtrip tests pass.
Uncertain send preserves draft/choice, successful send resetsOFF. Need commit
this UI unit, canonical rebuild, visible Vivaldi upload/attachment+toggle test,
update verification record and commit final evidence. No active attempts atlast
DB check. User may inspect browser or submit their own cases, so check again.

## Workspace/runtime

Implementation: .worktrees/electrical-diagrams, feat/provincial-electrical-view.
Latestcommitted source7b1d9c19; comparisondocs5981a4e6. CurrentdirtyAppunit+spec/
plan/journal are owned; preexisting .superpowers/sdd/task-1-report.md is NOTowned.
Preserve it. Rootactualdev has dirty control docs INDEX/JOURNAL/PROJECT-OVERVIEW/
RESUME/VERSION-CONTROL; preserve. Dev integration/control alignment stillpending,
no cloud/demo deployment. Do not claim these as merged/deployed acceptance.
Running backend source7b1d, image9ca5136edc64ba12e46e4681a34d06fc60b7fdbc6035bd8b35e07b23cbf1baaf;
canonical build log/tmp/capstone-dr-comparison-rebuild.log; cleanup234833-13755.
AppHMRalreadyusescurrentUI. For rebuild use rootdeploy/local.env and root
.grid-agent/runtime/pypsa-models via CAPSTONE_LOCAL_ENV_FILE and
CAPSTONE_PYPSA_MODEL_LIBRARY_DIR. Never copy auth. API8767/App5173.

## Vivaldi

Existing tab only; com.vivaldi.Vivaldi, pid53691/window137137 (may change).
Use computer-use via orca. Getfreshstate beforeactions; --element-index,
--restore-window. Omitstalewindowid. JSONresult.snapshot.treeText and
result.screenshot.path/scale. HugeAXtrees may omitrightpane; sometimes inputmethod
ABCdialog overridesAX; freshscreenshot coordinate fallback works (divide byscale).
User is actively browsing report pages; do not overwrite drafts. New UI trial in
one NEWconversation through NewSession button, same tab. Tiny benign upload
fixture through native filepicker (CmdShiftG path). Verify acceptedfile card stays
with instruction afterrefresh. ToggleON screenshot thenOFF; no need extra DR run.

## Earlier evidence and deferred scope

Old actualDRrevisionaa8e...220.509s with14slides only3/13changed is unequal-scope
prior evidence, not currentcontrolledcomparison. Both earliergatewaygrant trials
failed; report2026-10-27-dr-direct-delivery.md retains them. Graph/progressive
loading/camera acceptance and dev integration are separate pending work.
Sibling data-gateway is READONLY. No subagents. Focusedchecks only.
