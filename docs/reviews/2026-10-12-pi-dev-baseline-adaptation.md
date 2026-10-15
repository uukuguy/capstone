# Pi experiment — recovered dev baseline adaptation

Status: branch-local source adaptation synchronized to accepted dev `6ff7094e79f654abb24e626b2cdd1e593337efcb`. This record does not certify full Pi business answers or a deployment.

## Source and recovery

The work stays on `feat/pi-skills-integration` in its own worktree. Original head `749e0b8` remains at `archive/pi-before-dev-baseline-20261012`.

- `fb2bcf0` merges recovery candidate `17debfbc38b46ae4eb3b7acf47fe3820593dbea8` with the scoped adaptations below. Its restored common product is `82b243c`.
- `e9825df` merges root lazy-credential fix `bc081695bebb18b0e2f330c474cea1e50d343f7d`. The shared lightweight route accepts a lazy resolver; the experiment keeps its own lazy intent runtime.
- Accepted dev `6ff7094e79f654abb24e626b2cdd1e593337efcb` comes from PR #14, merged by the bot after exact-source `bc08169` Linux/macOS CI success in run `38181053709`. Its tree matches `bc08169`. The final ancestry merge has no runtime-source change from Pi `41fabee`; only this report and branch recovery records change.
- The independent source adaptation review approved `e9825df`. No additional source review is required for the source-equal ancestry merge.

The primary agent owns dev integration, canonical control records and the graph. The adaptation worker made no push, deployment, live Provider call or authentication copy. The primary agent subsequently pushed the accepted branch head38e19db and its recovery reference. Existing local-dev and local-demo data were not changed by this branch.

## Preserved experiment and adapted boundaries

Native and delegated Pi tools, skills/MCP profiles, `pi_reference`, frozen `request_intent`, conversation/input/context selection, accepted decisions and retries remain present. Selected skills and public business context still cross the existing explicit contracts. General products remain separate from Authority results and evidence.

Both hosted roots retain `with_intent_runtime`. Provider configuration remains lazy, and missing credentials produce the bounded configuration failure without changing selected context. The restored lightweight binary classifier is a separate shared path; no keyword fallback or question-specific policy was added.

Ordinary paths remain distinct. Hosted experimental ordinary work uses the native/delegated runtime. The new baseline lightweight no-domain return applies to ordinary prepared sessions with nonempty profiles. The existing empty-selection adapter still has its own context and history policy. This report does not claim that every Pi ordinary path is lightweight or tool-free.

The conflict resolution keeps frozen conversation/submission fields in both ledgers and moves catalog preparation before the execution lease. The auto-merged Kernel still loads the source-bound semantic execution projection, accepted skills, typed external observations and admitted business dependencies. Harness keeps its goal admission hooks and adopts diagnostic process events plus the final-only collector.

One direct/delegated event bypass needed a narrow fix: intermediate `assistant_delta` and `message_update` text now emits `assistant_process_delta` with diagnostic visibility. The final `PiTaskResult.answer` remains the formal answer. Eight new tests reproduced the public process leak before the fix and passed after it, across both entry points, both event forms and completed/failed child outcomes. Real loopback host replay tests also verify this boundary.

The App keeps accepted input metadata and conditional draft reset, using the restored `returnToLatest` scroll API. It preserves the three-action preview, small text and scroll area. Vite combines the four-environment receipt with Pi's local product/repository identity, including both labels in the development hover detail. The README pair keeps the dev/main lifecycle and the experiment warning.

## Verification

All checks use this worktree. `make setup`, `make install-pi` and `make doctor` completed; no ignored authentication was copied.

| Check | Result |
| --- | --- |
| Pi intent/runtime/frozen decision/conversation/input/native/delegation seams, shared worker/Harness/Kernel session and lightweight route; actual managed loopback Pi and isolated PostgreSQL enabled | 305 passed; 1 Docker-native test disabled |
| Delegated runtime, general server and relay, including the 8 process-stream regressions | 72 passed |
| Business/execution contexts, context matrices, model-context ownership, professional/native resource installation and delegation contracts | 239 passed; 2 old public-stream assertions required adaptation |
| Delegated review after adapting those old assertions to diagnostic process text and unchanged final answer | 23 passed |
| Full App: `npm test` | 417 passed in 37 files |
| App: `npm run build` | Type check and build passed |
| Full source: `uv run --project packages/grid-agent pyright` | 0 errors, 0 warnings |
| Pandapower hosted plus real prepared capability integration | 10 passed on the combined repeat |
| PyPSA hosted plus prepared capability integration | 10 passed |
| Lazy-route merge: classifier, intent runtime and delegated runtime | 69 passed, 1 PostgreSQL test skipped in this smaller run |
| Lazy-route merge: hosted roots | Pandapower 5 passed; PyPSA 5 passed |
| Conflict markers, relative `CLAUDE.md` link and `git diff --check` | Passed |

The test groups overlap. Their counts are separate receipts, not one aggregate total. The larger frozen-state group used an isolated local PostgreSQL cluster; the smaller lazy-route check did not set its database flag. Managed Pi tests used loopback fixture responses, not a live Provider.

An initial pandapower combined run had 9 passes and one `environment.describe` transport failure. Its original cause is unconfirmed. The registered transport, copied binding transport, failing test in isolation and a complete 10-test repeat all passed. No source change was made to conceal that failure.

## Remaining scope

The Pi branch now includes the exact accepted dev commit above. Git ancestry is checked against that fixed baseline, not a moving branch name. The final merge does not repeat the heavy 305/417 suites because runtime source is unchanged; local documentation links, the relative agent-contract symlink, `git diff --check` and `make doctor` are checked again.

The opt-in Docker-native execution test, paid Provider acceptance and a deployment from this experimental branch remain outside this source adaptation. A local rebuild or cloud release was not performed from the Pi branch. The accepted demo feature scope remains separate.
