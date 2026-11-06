# Direct native entry implementation plan

Approved direction: remove the default independent recognition model call.
Use existing native conversation execution and admitted capability discovery.

1. Add failing regression checks in native worker/runtime tests: default factory
   must not initialize or invoke the recognizer; ordinary, gateway and domain-tool
   instructions enter the same direct execution path. Frozen legacy input/decision
   retries retain their accepted path. Explicit skill/context selections survive.
2. Update native_hosted_worker.py and intent_runtime.py only as needed to make
   that default real. Preserve permission checks, frozen profile/model identity,
   current-run evidence and semantic domain tool access. No keyword routing.
3. Independently inspect actual execution SDK capability/skill menu. Add focused
   regression tests for missing summaries and fix only proven omissions. Do not
   inject full catalogs or expose protected service configuration.
4. Run focused runtime/worker/context/SDK checks and independent code review.
   Save scoped source on a recovery ref without touching the mixed normal index.
5. Canonical local rebuild; run real ordinary answer, gateway inventory and
   professional tool checks. Measure first model request and visible Thinking;
   confirm no recognition call, actual tools and saved/refresh-restored outputs.
6. Idle-guard/back up each intranet stage, align all three to verified source,
   verify API/worker/native/App identity and default dsv4, then repeat original
   gateway question on63. Do not cancel user tasks, run CI or merge without approval.
7. Update report/journal/baton/register/generated overview. Visually inspect graph
   and real application; commit only scoped verified changes and receipt refs.
