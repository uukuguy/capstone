# Structured tool batch validation

Source: `4ba178910b0916ec2a0f68593aa51e397ff74271`,
`refs/capstone/features/structured-batches-20261105`, parent design `a4e5173e`
and local runtime baseline `7387ef7f`. Dev HEAD remains `6c55e6ee`.
No CI, push, merge, intranet probe or cloud/demo change.

## Observation and change

User session attempt `attempt_3ab2a69641558eb6` had 121 query calls, maximum
recorded query overlap 1, across 14 programs with no `tools.batch`. One 26-call
fixed parameter set was independent. This proves unnecessary serialization in
that set, not that all 121 calls should run together or that all were necessary.

`agent_tools_execute` now accepts `calls:[{id,tool,arguments},...]` as an alternative
to `program`/`tools`. It derives admitted tools and reuses whole-batch preflight,
capacity reservations and issued observations. Invalid input invokes nothing.
Results retain IDs/input order; individual failures preserve other observations.
Transport failure is marked unknown execution status; no automatic retry.

A FIFO scheduler shares the existing maximum4 across this composition instance's
programs. Published read-only operations may overlap; unknown/mutating operations
execute exclusively. Lower per-program limits remain effective. Queue/start/end
timestamps describe actual composition invocation; IDs connect to existing events.
This is session-local capacity, not cross-process gateway capacity. Top-level calls
outside composition remain outside this scheduler. No JavaScript rewriting or
business keyword routing was introduced. Source observations remain non-Authority.

## Focused checks

- Initial six new tests failed before implementation, including missing calls mode
  and ambiguous input acceptance. The new batch/scheduler checks now pass11.
- Python direct consumers:141passed,33environment skips,8.84s. The gate includes
  composition, source packages, native SDK, server and Docker layer checks.
- Discovery/use integration:34Node tests passed. Pinned Pi SDK accepted both schema
  alternatives and rejected3invalid inputs.
- Without explicit loopback NO_PROXY,3HTTP tests received502 from the system proxy;
  with `NO_PROXY=127.0.0.1,localhost` the same focused suite passed.
- Independent review could not start: collaboration runtime rejected unavailable
  default model `gpt-6.1-luna`. Inline review completed; independent review is pending.

## Local deployment

Canonical `CAPSTONE_START_APP=0 make capstone-local-rebuild` completed with readiness
and scoped cache maintenance.1313runtime inputs matched the exact candidate.
Source metadata layers were attached to those canonical builds, then activated.
API/allworkers image:
`sha256:aeba082c73bf8f6308a5b0ed64c0d8d6a8d9e38e4608ff2f52a837d75df943a6`.
Native image:
`sha256:0eea01ff857c488a549369e7d5246dc7090818dc805d04b454a84223b2f0f80c`.
All roles healthy and labeled exact source4ba17891. App5173 uses fixed candidate
source, local-dev, dirty=false, Vite PID77708. Ledger backup and private environment
comparison preserved data/configuration. Active attempts were0before replacement.

Private receipts: `.capstone-agent/structured-batches-20261105/`.
## Real-model adoption and replay

Thread `thr_6e519364fa44fcc9e3d0`, attempt `attempt_1753d658f2d2bca7`,
profile `commercial-deepseek-flash`, completed in28.995s wall time. This includes
preparation and model requests; it is not the App's execution-only duration.
The model selected calls mode with two previously observed independent query
arguments, each limit1. Both source calls returned status=ok and one row, with
maximum recorded overlap2 and query span1.7953s. The configured local integration
gateway reported its database source; this is not intranet production acceptance.
No claim of overall121-query speedup or universal model adoption follows.

Browser5173 displayed4ba1789, both results and their limits. Correct workspace URL
`/?workspace=enterprise&thread=thr_6e519364fa44fcc9e3d0` restored the answer after
refresh. Opening this enterprise thread without its workspace produces an existing
409/error path; no unrelated frontend behavior was changed in this task.

An optional follow-up CSV instruction was rejected because the session had been
archived. No continuation model/source call ran, and no unarchive/replay was forced.
The first continuation harness also used an invalid new-work target; its commands
were rejected, not model executions. Export/continuation is therefore not accepted
by this trial. The focused tests cover observation reuse and dependent stages.

Final maintenance: scoped cleanup helper completed with exit0, preserving referenced
images and data; readiness/allrole source identity rechecked. Doctor,17local document
links, relative CLAUDE→AGENTS symlink and diff whitespace checks passed. The control
overview retains dev HEAD6c55e6ee and a distinct exact local source4ba17891 node.
