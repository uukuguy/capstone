# Reference execution research

Independent research branch based on dev 651e4cd3. No automatic dev integration or deployment.
Continuously track dev through ordinary merges; see RESEARCH-BASELINE.md. Isolation applies to experimental delivery, not dependency evolution.
Efficiency first: server computation, reference orchestration, bounded model feedback. Evaluate disclosure separately.
Read docs/reports/2026-11-06-reference-execution-feasibility.md and the two 2026-11-06 design documents.
Reference composition test migrated from ee3c9123; prior 41-test receipt is historical, not a fresh-worktree test.
Local gateway exposed 57 tools, no measurement analysis; 63/66 had no route. No real performance claim.
Next: prepare isolated runtimes before tests, then use an isolated gateway publication to validate the reference pipeline.
Do not copy credentials, modify main development services or mix gateway compatibility fixes into this research.
