# Progress graph alignment

Canonical VERSION-CONTROL and PROJECT-OVERVIEW now record dev a4efea0e,
main22cd1728, PR94/95, development snapshot tag and all three dev deployments
at22cd1728. Old6c55e6ee is a historical baseline, not current HEAD.
Current graph update uses focused local document/doctor/browser checks only.

# Latest deployment result

All three dev services now run22cd1728. Readiness, exact App source and API/worker
image parity passed. Real short tasks completed local3.10s,63 8.86s,66 9.61s.
Report: docs/reports/2026-11-06-three-dev-deployment.md.
Private receipt: .capstone-agent/deploy-20261106/receipt.json.
Local App PID stored in .capstone-agent/app-dev.pid; Vite preview serves exact bundle.
No CI or production deployment. Existing data/configuration preserved.

Previous recovery notes (superseded deployment status):
# Current closeout result

PR94 merged dev a4efea0e; macOS CI42147526730 passed.
User explicitly authorized lightweight development exception. PR95 merged main
22cd17287c97659bd487008be087b0948009d67c using administrator bypass.
Duplicate release CI42153874461 cancellation requested. Annotated remote tag
dev-snapshot-20261106-22cd1728 points to that main commit. Not a release acceptance.
Git HTTPS fetch failed; original local checkout and mixed work preserved.
Local branch synchronization/control graph refresh remains deferred; no deployment.

Previous recovery details:
# Live Session Checkpoint

Updated 2026-11-06. Active main/tag closeout; not a final handoff.

User authorized closeout, annotated tag and main integration. Two dev PR macOS product/governance runs were explicitly approved. First failed;
second run42147526730 is active at c9be2193b64951545e207398faedebcd7d78ac31.
No third or main CI approval. Do not push updates or rerun without new approval.

PR94 https://github.com/uukuguy/capstone/pull/94 still OPEN, base dev, remote head
c9be2193b64951545e207398faedebcd7d78ac31. CI42137611817 FAILED after about28m44s:
applications938/3skip, simulator279/2skip, governance61/2skip passed; backend3142
passed/197skip,1failure quiet-provider idle count. No merge/tag/deployment occurred.

Local candidate branch uukuguy/native-execution-release-20261106 at Orca checkout:
/Users/sujiangwen/orca/workspaces/capstone/native-execution-release-20261106
Code/test fix1a0fc847 and docs c9be2193 were pushed under second CI approval. It changes only test_general_pi_executor:
fixed200ms child quiet period replaced with marker handshake after2idle callbacks;
original count assertion and5s deadline retained. Controlled300ms callback delay
reproduced2failures with old test; new handshake passes92related checks in16.13s.
No production code changed. Earlier code repairs faa9bcc0/6c54b077/a8fbf683 retained.

12original historical receipts existed only in root and were omitted from candidate.
They are now copied to child with unchanged content; candidate/control and own links
pass. Include these with final control docs in the next candidate commit. No secrets
found in copied reports. Local doc/doctor/diff checks must finish before asking approval.

Earlier local release scope passed as split components (not one clean aggregate):
backend3143/197skip,App1527,Kernel663,E2E39,workers3,workbench156,
static7/10/8,application2,matrix24/24,package-artifacts/source-setup/build/doctor pass.
Two original local failed receipts remain; first CI failure remains separate.
Independent review P2 unbounded diagnostics fixed6c54; followup no new finding.

Root checkout remains dev6c55e6ee and main0b68c607; remote dev/main unchanged.
Root mixed work preserved, normal index empty. root-alignment-audit.json identifies
128paths matching candidate+incoming,17matching incoming before repairs,5candidate
only,18independent historical documents/template paths. Recompute before any sync.
Do NOT stash/apply blindly or overwrite old source onto new repairs. On successful
future dev merge, preserve complete recovery snapshot and independent paths before
fast-forwarding actual dev. Ignored runtimes,var,data,auth must remain untouched.

Private logs in root .capstone-agent/release-closeout-20261106/:
dev-ci-receipt.json,dev-ci-failed.log,idle-scheduling-red.log (2fail),
idle-scheduling-green.log (92pass),ci-authorization.json,missing-receipts-paths.json,
local-summary.json, earlier failed/passing gate logs and PR body drafts.

Docs/control snapshot updated in actual dev root and child; links/symlink,
diff,doctor and1920px browser/source edges verified. Final documentation commit
follows1a0fc847 and includes12unchanged receipts. Only append-only commit journal
receipt may remain uncommitted until next state commit. Temporary server stopped;
browser restored to5173. Root dev source/HEAD still unchanged.
Next monitor second dev PR macOS CI42147526730 (watch log dev-ci-second-watch.log).
No new CI or PR update is authorized. After it passes, merge
through PR without bypass, synchronize actual dev preserving mixed work and record
actual merge/control. Main PR full macOS+Linux release CI needs separate explicit
approval. Tag exact accepted main merge only after passing main gate; suggested
milestone-native-execution-20261106-<short-main-merge-sha>, no deployment tag.

Root local-dev stays984131e3 (API/workerscb6678d6,native200f8447),AppPID91545 fixed
batch-regression app5173→8767. 63/66 lastknown367374aa+overlay255c8855,disconnected,
untouched. Gateway missing grid_database external assistance stays open.
Current own browser sessionoffapp tab on5173; reuse it for control snapshot and
restore it afterwards. Original temporary18976server was stopped. No user tabs close.
