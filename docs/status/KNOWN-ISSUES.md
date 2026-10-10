# Known issues and deferred work

## Goal-based answers and response scale: manual acceptance fails

- 2026-10-10 13:04: local-demo trial still shows baseline tables in place of answers to generator N−1 ranking and bus31 load scaling. Line7 has verified violations but lacks a concise direct conclusion and includes unrelated baseline detail. Generic partial diagnostics do not explain the remaining user-goal gap.
- Do not treat projection rendering, accepted result counts or passing integration tests as formal answer acceptance. Requested goal, scenario and coverage must be checked separately; facts must be relevant to that goal.
- Default basic introductions should give a brief overview with optional detail. The observed 1m14s response requires timing analysis and avoidance of unrequested calculations; its cause is not yet confirmed.
- Design discussion is pending. Preserve local-only deployment scope and cloud rollback. Do not implement per-question template patches or automatically repeat paid questions.

## Demo startup and conversation recovery

- Recorded: 2026-10-10. User reports slow startup and long waits during an active conversation.
- The 10:57 screenshot shows “正在恢复连接”. Workspace, conversation history and PyPSA tools are ready; pandapower tools remain “准备中”. The visible attempt has run for 3m 56s. These are user-visible observations, not a confirmed cause.
- Investigate first entry, idle wake, active-conversation recovery and tool readiness separately. Correlate App requests, API/worker readiness, deployment or restart events and the Attempt timeline before attributing the wait to sleep.
- Evaluate sleep delay, minimum warm capacity, readiness checks and recovery feedback against measured waiting time and resource cost. Preserve accepted work and conversation state; do not repeat paid requests automatically.
- Deferred by the user. Complete the current demo outcome and failure-diagnostic repair first. This note does not authorize a sleep-policy or deployment change.

## Development and demo release lanes

- User requests a direct demo trial/fix lane and a local-development to cloud-dev lane. Align them at one accepted baseline, then allow parallel work.
- Accepted policy: dev environments may enable isolated experiments; main is the integration line; demo is a verified release subset. Functional work, public fixes and nonfunctional hardening use managed branches and a serial merge queue. Demo hotfixes must return to main and affected branches.
- Current priority: minimal alignment from existing cloud demo ed2524f, then a stronger repaired baseline. Preserve pure Pi/skills development separately and adjust main without rewriting history. The fixed [version-control register](VERSION-CONTROL.md) owns branch and stage identities. Existing release and stage-isolation rules remain in force; no new cloud deployment in this task.

## Local demo validation lane

- Requested after the framework repair: run the exact demo source locally in an isolated deployment before release.
- Keep its PostgreSQL, object storage, ports and runtime state separate from the existing local development deployment.
- Do not copy user-trial data or cloud credentials. Preserve existing main-worktree data.
- Priority update: the user reports broad demo regressions. Restore the previous demo release first; use local demo to validate the repair.
- Local demo now runs the minimum common runtime baseline `2540bdc`, App15173/API18767, separately from local-dev App5173/API8767. Both pass registered cases, reports/evidence replay and identical runtime contract/source/installed artifact identities. The failed `3e3bbfb` answer-repair candidate is retained on its own branch and is no longer the running local demo.
- The user limits this iteration to local deployment and verification, then discussion of the two development lanes. Do not promote this candidate to either cloud stage.

## Environment label on version displays

- Requested: 2026-10-10. The user refines the generic “开发中” label into four explicit environment labels: `local-dev`, `local-demo`, `cloud-dev`, `cloud-demo`. Keep the product version and source revision separately visible.
- Record as a future release requirement. The user explicitly says not to update hosted display in this iteration.
