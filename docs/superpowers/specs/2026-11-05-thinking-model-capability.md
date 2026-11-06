# Thinking model capability correction

The user confirms missing Thinking text during execution on63. Keep the accepted
design: show only supplied Thinking, push it promptly, batch required persistence,
reconcile once, and preserve model choice and Authority boundaries.

Two latest dsv4 gateway-catalog tasks have zero Thinking events. Intent-generated
models.json declares only the private model ID, so the SDK defaults to no reasoning
support. Native execution explicitly sets reasoning=false. The SDK clamps requested
thinking levels to off and omits reasoning_effort. Controlled256-token18804 calls
confirm omitted effort returns no reasoning, while low returns113 reasoning chars.
The server OpenAPI explicitly admits reasoning_effort and include_reasoning.

Register the verified18804 capability as optional boolean reasoning in the existing
application profile. Bind it to profile revision. Other profiles keep their existing
behavior. Do not infer capability from model names or call discovery on each task.
Use the selected frozen profile in both paths; a separate recognition override must
not inherit another model's capability. Keep Kernel/provider value objects unchanged.

Intent passes optional model_reasoning to its per-session builder, includes it in
engine configuration identity, and updates only the matching per-session provider
model entry. Native passes the admitted boolean to native_pi_launch. Existing low/
medium policy and SDK settings remain responsible for effort. No fake Thinking or
conversion of answer text into reasoning.75ms display and5s durable batching stay.

Acceptance requires actual SDK outbound effort fields, genuine incoming thinking
deltas, the original63 gateway-tools query with visible running-page text, durable
reconciliation and refresh recovery. Keep three development environments on one
verified source; use idle guards/backups and preserve stage credentials and data.
Latency must be measured again; earlier non-reasoning timings are not comparable.
