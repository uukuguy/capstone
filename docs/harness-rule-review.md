# Harness rule review

A validation archive contains private task input. Keep its local copy and review
receipt in protected operator storage. The archive key and SHA-256 come from the
original validation diagnostic.

Select the original trusted source revision and the candidate revision from
reviewed Git history. Check out each in a separate clean worktree. Install the
project dependencies for the review environment. The baseline runtime must
contain the original engine and handlers. Its replay checks the archived rule
bundle and processor digests before evaluating the input.

Run `tools/review_harness_rules.py` with the archive file, archive digest,
thread and attempt IDs, both worktree paths and exact refs, a tracked candidate
rule file from the candidate worktree, and a new private output path. The tool
checks that each worktree is clean and matches its ref. It runs the installed
code in each worktree in a separate process. The archive is input data and does
not provide executable code. The present runner supports the installed
`markdown_table_row_breaks` handler. Other handlers need explicit integration.

Review the original and candidate decisions, both processor identities, the
archive digest and candidate bundle digest. The receipt contains answer text.
A receipt records the selected worktree identities. Its trust depends on the
operator selecting trusted refs and protecting the local environment and output.

For publication, run `tools/review_harness_rules.py publish` with `--review`,
`--current`, `--desired`, and a new `--output` path. Commit the checked output
through a normal dev PR. Keep the baseline commit and review receipt available.
For rollback, use the same arguments with the `rollback` subcommand, then
submit the checked baseline output in a new PR. Review the affected handler source changes as well
as the rule JSON. This check does not itself approve or publish a change.
