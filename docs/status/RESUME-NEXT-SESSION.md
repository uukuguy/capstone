# Live checkpoint — Research Model baseline adaptation

Date: 2026-10-12. Branch: feat/research-model.
Accepted development baseline: 6ff7094e79f654abb24e626b2cdd1e593337efcb.
PR #14 candidate bc08169 passed both protected GitHub checks before merge.

The branch fast-forwarded from 50d8ebc; its previous root remains at
archive/research-before-dev-baseline-20261012. R0 experiment/autonomous-research
stays at bf678f2 with its original evidence. R1 has no code yet.

This change adapts the owning design and R1–R5 plan. Use existing Thread,
Attempt, ModelContextSnapshot, selected semantic tools and Authority evidence.
The binary LLM router only chooses a chain. Do not restore task compilation,
coverage, answer rewriting, frozen reuse or prewarm. Research state requires its
own lifecycle; ordinary questions do not require a full Research Model.
Known load admission, AC identity and overview latency problems remain open.
Affected research steps require a repair or an explicit block.

The independent plan review approved these dependencies. Product source,
configuration and tests are unchanged from the accepted baseline.
Own make setup/install-pi/doctor passed without authentication copies.
Before the document commit, check links, CLAUDE symlink and git diff --check.
See docs/reviews/2026-10-12-research-baseline-adaptation.md.

Next implementation: R1 neutral state/dependencies/lifecycle contracts and R4
actual capability-gap inventory, under the accepted research evolution plan.
No R1 completion, Provider acceptance or deployment is claimed.
Global branch and deployment facts belong to dev/docs/status/VERSION-CONTROL.md;
do not overwrite that register with this branch's older snapshot.
