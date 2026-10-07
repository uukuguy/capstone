# Capstone M1–M11 status audit

Date: 2026-10-07. This is a document, history and source audit. It is not a new
independent code review or a fresh execution of historical release gates.

## Conclusion

Delivery reached M11. The completed milestones use their recorded bounded
acceptance scopes; they do not establish delivery of the entire interaction
discussion. Do not reopen M6 from stale unchecked plan rows. Its tasks have
implementation and review evidence, and its Task 9 closed with the explicitly
recorded lightweight demo boundary in `914461b`.

Later M10 and M11 ran complete release gates. The earlier M6 decision not to
rerun those gates at that checkpoint is not evidence that the current Case
engine has never passed the repository gates.

## Milestone ledger

| Stage | Recorded completion | Evidence and limit |
| --- | --- | --- |
| M1 application root | Approved after fixes | [M1 review](2026-10-01-capstone-m1-code-review.md); [M1–M5 independent follow-up](2026-10-02-capstone-m1-m5-independent-code-review.md) |
| M2 model catalog/runtime dispatch | Approved for registration/dispatch seams | [M2 review](2026-10-01-capstone-m2-code-review.md) explicitly leaves native skill/MCP/plugin materialization to a later Harness adapter step. The absence of that step does not reopen M2. |
| M3 ordinary conversation/TurnRouter | Approved after fixes | [M3 review](2026-10-01-capstone-m3-code-review.md); Jev remains optional/off, and experiment promotion is separate. |
| M4 Thread controls | Pass; no remaining Important/Critical findings in that review | [M4 review](2026-10-01-capstone-m4-code-review.md); [M1–M5 review](2026-10-02-capstone-m1-m5-independent-code-review.md) |
| M5 unified validation | Complete for provider-free protocol scope | [Final verification](../status/2026-10-01-capstone-m5-verification.md) supersedes the initial OPEN review's environment blockers. Interactive TUI/browser captures were left as operator-stage work; final TUI was not delivered by M5. |
| M6 Harness/Case | Implemented and closed for lightweight demo scope | `914461b`, JOURNAL and ignored `.superpowers/sdd/progress.md` record Tasks1–9 complete. Task1–8 review/fix records exist; Task9 has four boundary checks. A single versioned whole-M6 final review is not established by the lightweight record. Keep this documentation/acceptance limit explicit; do not claim missing Case implementation or absent later release gates. |
| M7 ResultProjection | Follow-up pass for demo scope | [Two-part independent review](2026-10-02-capstone-m7-independent-code-review.md), including isolated PostgreSQL execution. A remaining commit checkbox in the plan is not a missing result pipeline. |
| M8 unified dual-family Thread | Independent re-review pass for demo scope | [M8 review](2026-10-03-capstone-m8-independent-code-review.md), [catalog follow-up](2026-10-03-capstone-m8-catalog-context-follow-up.md). Remote dual-family activation was a successor item, completed by M11. |
| M9 PyPSA results/Web | Approve for bounded results/tables | [M9 review](2026-10-04-capstone-m9-independent-code-review.md). The plan's topology follow-up was delivered by M10; long-result-specific formatting remains deferred. |
| M10 PyPSA topology | Implementation and local verification closed | [Implementation plan](../superpowers/plans/2026-10-04-capstone-m10-pypsa-topology-provider-implementation.md), JOURNAL manual boundary review, `08f7366` full release gates and `a01c43d` closeout. No separate versioned independent M10 review report was found. Remote PyPSA Thread acceptance was subsequently delivered by M11. |
| M11 cloud federated Thread | Complete:13 required acceptance rows passed | [M11 acceptance](2026-10-05-capstone-m11-cloud-verification.md), with real cloud replay/focus/restart retention, source review and full gates. Its restricted scripted matrix is not a claim about all Provider natural-language behavior; later normal-path repairs have separate records. |

## Remaining design work outside these bounded closures

- Accepted pure Pi reference switching and context isolation: the mode name and
  adapter seam exist, but immutable Attempt authority mode, controlled switching,
  non-authoritative history and business-memory isolation are not fully wired.
  Source: [interaction discussion](../superpowers/specs/2026-09-29-agent-interaction-discussion.md#runtime-paths-and-comparison).
- Generic runtime capability execution: `RuntimeCapabilityRegistry` and assembly
  injection exist; the current factories retain the registry without compiling
  selected registrations into a runtime session. This is the explicitly deferred
  adapter work described by the M2 review, not a new core-evolution agenda.
- Formal terminal client: the 2026-10-01 [decision](../status/DECISIONS.md) freezes
  the present Textual client as a protocol reference. Production interaction
  design and framework evaluation precede its implementation.
- Real DSH, WebSocket human-in-the-loop, multi-Run and capability-parity reference
  execution remain deferred or proposed. Do not treat them as failed M6/M11
  acceptance requirements.

The Web answer-display/evidence-action gaps are smaller presentation work. The
current local changes have separate acceptance and no release claim.

## Record repairs

Keep historical plans and journals intact. The current worklist must distinguish
bounded milestone closure, deferred successor functionality, stale checkboxes,
and missing portable review records. Consolidating M6/M10 review evidence is useful,
but it does not authorize reimplementing closed milestones or rerunning billed
Provider checks.
