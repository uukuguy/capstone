# Recognition latency and ordinary-answer repair

The user accepted stable preparation reuse, per-instruction LLM understanding,
separate recognition configuration and immediate waiting feedback. No keyword
routing or example-specific prompt changes. Current observed recognition19.48s
includes preparation and Provider work; component timing must identify the cause.

1. Add neutral Pi session reset with checked acknowledgement. Reuse one bounded,
   tool-free recognition process per application worker; reset between tasks and
   dispose on failure/shutdown. No implicit history across Threads. Cache verified
   worker runtime preparation; stable schemas precede changing request content.
2. Separate recognition Provider/model/thinking/timeout configuration. Default
   recognition thinking off, retain execution settings and all task validation,
   semantic gap review and two-call shared deadline. Record preparation/start,
   first-event/call/validation/cleanup timing, call count and safe model identity.
3. Show a compact waiting state from command acceptance before any tool event.
   Preserve one-action short window and completed collapse behavior.
4. Ordinary answers use standard scale by default. Restore structured overview
   with model facts and registered analysis purposes; never invent supply totals
   absent Authority facts. Concise requests remain concise. No incident hints.
5. Red/green focused tests, source review, canonical local rebuild, exact source
   proof, real overview latency samples plus whole-load/AC/history regression,
   browser waiting/window checks. Update control graph and issue receipts.

Opening a model in the API cannot directly warm another worker's process. This
iteration reuses worker preparation after its first task; opening-time cross-
process warmup requires a separate queued worker operation. Do not claim it is
implemented. Provider latency remains external; report measured distributions,
not an unconditional speed guarantee.
