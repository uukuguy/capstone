# Bounded investigation repair

Approved design: docs/superpowers/specs/2026-11-09-bounded-investigation-repair-design.md
Base:5f6a5d92, tested runtime4a638740. Preserve unrelated state edits.

1. Add failing research-guidance event-hook tests for a finite configured
   checkpoint, coalescing, reset, unchanged context roles and composition counting.
2. Implement instruction-local advisory scope review in research-guidance.mjs,
   selected through general-research.mjs. Use host composition receipt counts;
   count completed dispatches, not wrapper calls or reused observations. Keep
   ordinary answers and the non-lightweight research path unchanged.
3. Add source-scope and skill-scope guidance. Explicitly deny budget guarantees.
4. Run focused Node tests and direct consumers. Rebuild local-dev from the exact
   committed candidate; preserve private runtime state and clean scoped cache.
5. Run separate exact-reference and zero-sample live acceptances if the gateway
   supplies a verified source record. Check all ten final-answer source values.
   Record unavailable source evidence as blocked, never passed. Inspect complete
   arguments and call correlation when assessing repetition.
6. Record code, verification and acceptance limits in journal, checkpoint and dev
   control register. No CI or integration push without explicit CI approval.
