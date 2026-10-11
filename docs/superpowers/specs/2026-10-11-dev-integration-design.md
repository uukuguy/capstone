# Dev integration and release baseline design

Status: accepted by the user on 2026-10-11. Implementation is tracked separately.

`dev` is the default development integration branch. `main` holds accepted
release baselines. A branch head is not a deployment receipt. The actual
cloud-demo source remains the exact verified demo tag until explicit promotion.

Feature, fix, documentation and maintenance branches start from dev and target
dev. Experiments retain their original evidence; accepted work is reviewed as
a scoped feature PR. Existing branches are not rebased or merged in bulk.
Release branches are optional and freeze a dev candidate for complete validation.
Release PRs target main. Hotfixes start from the actual accepted deployment tag;
accepted fixes flow to main and back to dev without rewriting shared history.

The current project register and generated overview live on dev. Copies on main
are release snapshots. Feature branches own their designs, plans and validation
records. A project-wide decision must update the canonical dev worklist and
affected branch copies. The register remains the source of the generated HTML.

Both permanent branches require PRs and the existing Linux/macOS Actions checks,
with zero mandatory approvals and no force push or deletion. An administrator
emergency bypass is retained and must be recorded when used. Development checks
are scoped: documentation checks, narrowly identified governance checks, or
formal application regression. Unknown paths select product regression. Main
PRs and explicit release dispatches always run the complete release aggregate.
Neither branch push automatically promotes a user-trial deployment.

The command-driven Issue tool reads trusted committed dev policy and source;
it never trusts uncommitted policy or falls back to main. Normal repair PRs
target dev. Existing immutable task receipts remain valid records, but changed
source/policy or a mismatched recovered PR requires reassessment. Its bounded
governance gate runs the complete Issue tool suite. Hotfix release work remains
explicit and separate from this ordinary repair publisher.

Local-dev normally follows a recorded dev revision; a selected feature candidate
may temporarily lead it. Cloud-dev validates a selected development candidate.
Local-demo and cloud-demo follow the accepted demo source, with isolated data.

Migration starts dev at main 723b8e8, which contains merged PRs #9 and #10.
PR #11 moves to dev. The exact deployed and fully tested answer source 2473e48
can receive a local technical baseline tag with explicit pending human acceptance.
The Research Model implementation branch starts from accepted dev after this
governance and documentation integration. The R0 experiment stays unchanged.
