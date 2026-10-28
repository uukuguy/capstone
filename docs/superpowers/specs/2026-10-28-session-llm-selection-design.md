# Session LLM selection

User-approved behavior: the composer selects a backend LLM from application-owned
configuration. Local new sessions default to commercial deepseek-flash. Intranet
deployment new sessions default to dsv4 at port18804. Include all three registered
internal endpoints and one configurable OpenAI-compatible profile. Profiles live
in configs/runtime/workbench-llm-profiles.json, not frontend constants.

The backend exposes only admitted profile IDs, labels, model names and availability.
Endpoints and credentials are resolved by the backend, never supplied by the
browser or model. Internal profiles explicitly bypass environment proxies.
Startup selects the deployment preset; it must not rewrite saved session choices.

Store composer choices by session identity. LLM choice persists in that session;
the existing Deep Research flag remains next-instruction-only. Accepted commands
freeze the selected profile and resolved model identity in their attempt snapshot.
Changing sessions or selecting another model cannot mutate an in-flight attempt.
Unknown/disabled profiles fail before provider access; old sessions without a
selection use the deployment default. Custom profiles require configured values
and remain unavailable when configuration is incomplete.

The present native executor and provider relay have one fixed runner.model and
validate it at the relay. Selection must therefore extend executor admission and
task-bound relay routing together; a cosmetic dropdown alone is not delivery.
Resolve a registered profile through the protected backend for each accepted task,
retain exact executor/source identity and propagate the chosen configuration to
ordinary execution, DR workers and their model requests. Provider credentials
remain backend-only. Existing general GRID_AGENT_LLM_* compatibility aliases are
not the single current workbench model control.

Acceptance: two independent sessions retain different selections across switching
and refresh; new-session defaults differ between local/intranet presets; actual
provider responses and tool calls use the selected endpoint/model; changes after
submission affect later instructions only; custom missing configuration is clear;
the browser receives no secret and cannot select arbitrary endpoints. Test local
commercial and internal models, and repeat internal tests on the development
server before deployment acceptance.

Connectivity already measured: all three /models endpoints returned200 and exact
model IDs from both this Mac and dmdba@192.168.72.63 with explicit proxy bypass.
All six chat-completion probes returned one choice with finish_reason stop.
The server has curl but no python3 on its shell PATH; use available tools/containers
for further checks. These probes do not replace actual workbench/tool execution.

Implementation status: configuration and design prepared. Public catalog, session
selection UI/persistence, command snapshots, multi-profile runner/relay routing,
startup selector and end-to-end acceptance are still pending. Existing lightweight
regression and gateway diagnostics integration work remains active.
