# Execution process reading implementation plan

## 2026-10-24 call-round extension

- [ ] Emit request starts and exact response-to-tool IDs; test batch/no-tool cases.
- [ ] Admit optional metadata and project exact action-bound associations; old
  missing links remain unknown, including shuffled/replayed parallel events.
- [ ] Reusable model/tool timeline, live timing, four-character sections/chevrons;
  preserve task/detail folding and independent unknown/system action records.
- [ ] Focused backend/SDK/App checks, canonical rebuild, runtime/source checks.
- [ ] ONE original sequential run and UI/product inspection;300s review only.
  Record gaps before parallel comparison; no hard call-count or elapsed cutoff.

**Goal:** Make embedded process records concise and provide a larger reading view.

**Architecture:** Reuse the current AttemptActivity process renderer and the existing
AnswerDetailSheet modal container. Keep event/store ownership unchanged. Embedded
research fields use small accessible icon toggles. The reader defaults research
fields open, with tools and full errors still folded. Separate reader state must
not alter embedded folding or scroll position.

**Constraints:** Keep formal/process/metadata at 12 / 11 / 10 px. No Provider calls,
new runtime, second event store or fabricated process metadata. Preserve all dirty
work. User design approved; do not reopen design questions.

- [x] Test compact research toggles and detailed reader defaults.
- [x] Implement shared step research rendering with accessible icon controls.
- [x] Test and implement modal process reading, Escape/focus/scroll restoration.
- [x] Hide zero business objects; move all business objects and lazy original-record reader into the modal auxiliary area.
- [x] Run focused components, npm check and actual desktop/mobile browser checks.

## Verification — 2026-10-19

Final recovery rebuild exited zero at 03:44 CST. API and all worker roles share
03e64818fe5b88d4df7e83541e55fd563c30d5e2d741c57c1218e83cb7339f90;
general-pi is ef50fbc936b4218793423912e100347c428c2c8de0cc8eea5a1133c5e3d51730.
Readiness and an actual v2 stream read returned HTTP 200. Effective default
1024 / 8 and absent legacy overrides were checked through the container's actual
initialization path. The preceding failed startup is recovered, not accepted as
a successful receipt. No Provider task was sent for this verification.
Log: /tmp/process-reader-recovery-rebuild.log. Durable receipt:
ROOT/outputs/research-round-efficiency/native-environment-verification/process-reader-recovery-receipt.json.
Latest post-recovery images /tmp/process-reader-0345-verified-desktop.png and
/tmp/process-reader-0345-verified-mobile.png show the final unassigned-tool fold;
failure summaries stay outside that fold. The only console error was the
expected read-only v1-to-v2 negotiation 409; no repeated stream 503 remained.

Four focused component files passed 123 tests in 5.66 s. npm check passed. Logs:
/tmp/process-reading-final-tests-frozen.log and /tmp/process-reading-final-check-frozen.log.
Tests cover changing live steps, non-success outcomes, reader/embedded tool-state
isolation, embedded scroll restoration, Escape/focus return, hidden nested
summaries outside the focus cycle, zero and real business objects, explicit lazy
record reads, empty feedback and read failures. No record read runs automatically.

Actual historical Thread thr_941f851498fdd8791023 was inspected without sending
an instruction. Portal step title/body are 11 px, metrics 10 px; formal answer
paragraphs remain 12 px. At 390 px the reader is full width with no horizontal
overflow. Desktop screenshots /tmp/process-reader-0322-desktop.png and
/tmp/process-embedded-0323-desktop.png; mobile /tmp/process-reader-0325-mobile.png.
These precede the final shallow step-heading emphasis. Final desktop screenshots:
/tmp/process-embedded-final-0330-desktop.png and
/tmp/process-reader-final-0330-desktop.png. Final 390 × 700 screenshots:
/tmp/process-embedded-final-0331-mobile.png and
/tmp/process-reader-final-0331-mobile.png. The emphasis changes only shallow
background, border and weight, not font size or line height. Reader header keeps
total state and duration. Missing historical step response_ms is explicitly
shown as “LLM 未记录”; no duration is inferred.

Actual bottom-case verification found the old remaining-height calculation could
compress the process to one line. The readable region is now 160–320 px with the
outer message viewport retaining its own scroll. Desktop measured 320 px;
390 × 700 measured 169 px with the composer fully visible at y=580..684 and no
horizontal overflow. The reader is full-width on narrow screens. All verification
App browser sessions were closed; user chat-latency was not controlled.
Unassigned tool details are also folded in the reader; failed calls retain a
visible short summary outside the fold. No parent step is guessed.

The initial canonical rebuild attempt stopped before any build because this
worktree has no ignored deploy/local.env. The authorized explicit ROOT env and
model library overrides were then used by /tmp/process-reader-rebuild.log.
That rebuild exited zero with API/worker image
a01edf589cec379e6c6f2b95e68594c54b440d6ed9fc1dcf4273ddeb1e575567,
readiness and App checks passed. Final backend timing / stream configuration
changes need the next serial canonical rebuild before current image acceptance.
That final rebuild failed startup at 03:37 CST: worker-native candidate
b165eb3c3cf2c1c6caa1502f129100f4c345c5a7d5b9afdedda4fa5226b22885 was
unhealthy because runtime preflight rejected an empty stream-limit default.
The backend owner fixed that configuration regression, followed by the successful
serial recovery rebuild recorded above. This does not establish research acceptance.
Read-only SSE checks exposed the existing two-connections-per-Thread Compose
override, not a UI failure. Backend owner is correcting that configuration drift;
do not claim the connection issue resolved before the effective configuration is
checked. No Provider research task or new quality/performance baseline is part
of this UI change.

Original records stay unknown until read. Never infer empty data from their name
or request every historical record automatically. Keep error/retry feedback.
