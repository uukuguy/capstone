# Thinking visibility follow-up

App source:`22be9e5cbe7c5f39aed521b3c725f60ebd32a877`,retained at
`refs/capstone/fixes/thinking-visibility-20261105`. It includes the UI fix129094a9
and an additional supplied-batch regression test. The backend remainscc50f8d8.

Buffering must change write frequency,not supplied text,ordering or visibility.
The previous repair also corrected model binding;the selected dsv4 now runs
dsv4 understanding instead of the previous Qwen default. That is an independent
change and can change the supplied reasoning stream.

The user's current dsv4 attempt,attempt_6c5f76e1424e5dd7,had text/tool activity
but no public assistant_thinking_delta events when inspected. The UI also
required a nonempty thinking string before rendering its Thinking component.
Therefore it gave no Thinking status while waiting for a model without supplied
reasoning text. The absence of a persisted event alone is not a raw-provider
stream audit;this repair does not assert that every provider returned no reasoning.

## Change and checks

- An active model request shows the existing Thinking component even before text
  arrives. The accessible status says the model is processing and no displayable
  reasoning fragment has arrived. No reasoning body is invented.
- Supplied batches replace the waiting state and remain available after settling.
- A finished call without supplied reasoning does not gain a fake historical
  thinking record. Tool-only activity does not keep a model-thinking timer alive.
-66 focused App tests passed,including waiting,supplied batches and completion.
  TypeScript and production build passed. Canonical local rebuild9ca32da2 and
  scoped cache maintenance passed. The initial test-only candidatee14ab7bc had
  an unavailable matcher in one test file;it was not deployed.
- The served bundle identifies22be9e5c and contains the waiting-state code.
  No browser connection was available,so runtime visual acceptance is pending.

## Safe deployment

Only the三区 App container was recreated with `--no-deps`. API,worker and native
executor were not restarted. Their image and start times were checked. New App
image:`sha256:992ea42215357b36f09ca81c22b5d56b13e97c7f8ee64477b6d2517a8bdc150a`.
Served script:`index-BVDAxmD1.js`. Label remainsdky3-dev. Previous App image and
private/backups/thinking-22be9e5c/runtime.env are retained for rollback.

The user-started benchmark attempt completed at2026-11-05 05:51:38 UTC while the
App update was prepared. It was not interrupted. report.html,benchmark.csv and
reproduce_results.csv were downloaded in the owning workspace;all three match
their admitted artifact hashes. The initial operator download used the wrong
workspace scope and correctly returned404;the check was repeated with the exact
owning scope. No permission boundary was relaxed.

This verifies task completion and saved-product transport,not independent
numerical review of the pathological11-bus case. The agent did not replay the
complete business task. Model and tool execution time remain part of whole-task
latency. No full-task speedup claim is made from the understanding-only probes.

Evidence:.capstone-agent/intent-backpressure-20261105/thinking-*.log and
runs/intent-backpressure-20261105/user-benchmark/download-receipt.json.
Normal index,main,.63 and cloud deployments remain unchanged. No CI ran.
