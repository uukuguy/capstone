# Known issues and deferred work

## Demo startup and conversation recovery

- Recorded: 2026-10-10. User reports slow startup and long waits during an active conversation.
- The 10:57 screenshot shows “正在恢复连接”. Workspace, conversation history and PyPSA tools are ready; pandapower tools remain “准备中”. The visible attempt has run for 3m 56s. These are user-visible observations, not a confirmed cause.
- Investigate first entry, idle wake, active-conversation recovery and tool readiness separately. Correlate App requests, API/worker readiness, deployment or restart events and the Attempt timeline before attributing the wait to sleep.
- Evaluate sleep delay, minimum warm capacity, readiness checks and recovery feedback against measured waiting time and resource cost. Preserve accepted work and conversation state; do not repeat paid requests automatically.
- Deferred by the user. Complete the current demo outcome and failure-diagnostic repair first. This note does not authorize a sleep-policy or deployment change.

## Development and demo release lanes

- User requests a direct demo trial/fix lane and a local-development to cloud-dev lane. Align them at one accepted baseline, then allow parallel work.
- Deferred until the current demo repair is complete. Existing release and stage-isolation rules remain in force.
