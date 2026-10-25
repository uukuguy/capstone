# Streamed thinking and task presentation

Local candidate verified; dev PR integration pending. This is an affected-scope
development check, not a release or professional-solver acceptance.

## Behavior

Every instruction shows initial thinking during submission/queueing. Actual
SDK displayable thinking deltas stream in a separate public attempt-bound channel.
Signatures, encrypted/replay metadata, diagnostics and answer text remain separate;
trajectory capture stays redacted. No extra model call or reasoning flag is forced.

Actual admitted task organization selects task steps whether or not resources are
uploaded. Direct tools without organization select the tool chain. Goal notes and
host lifecycle timing do not create task organization. Initial thinking disappears
from the main view on takeover; its archive remains in the execution reader.
Direct replies fold thinking on completion and permit reopening. Cancelled/failed
records retain their status; late thinking never resumes the old phase.

## Verification

- Backend176focused tests passed3.91s; actual pinned SDK SSE fixture passed0.14s.
  It verifies supplied reasoning_content, no forced reasoning_effort and redacted
  trajectory capture. Python types report zero errors/warnings.
- Frontend138focused checks passed6.43s. Subsequent targeted transition/replay
  checks passed17tests1.61s; TypeScript and diff checks pass. Counts overlap.
- Canonical local rebuild succeeded. API/threeworkers share imagec5eb1817e993;
  native imaged5c9e90243ca. Seventy-seven runtime-file comparisons against98c9dc58
  match all roles. Later changes are frontend/document-only and use the same
  verified backend image. Main App5173 serves the candidate, with its source
  identity exposed by the existing build receipt. Scoped cache cleanup passed.
- Real DeepSeek response attempt2698ed35c0f1aaaf completed6.079s and produced
  14public thinking deltas/823characters. They are not answer text or Authority
  evidence. Saved source/event/product receipts remain in ignored operator outputs.
- The user's report history was replayed without rerunning analysis: the exact
  visible record again shows5task steps,59tool calls and5m37s. Frozen data bindings
  helped diagnose the regression but do not determine the final presentation rule.
- A no-upload organized task and an unorganized direct tool chain are covered
  separately. No complete solver/professional suite was repeated.

## Limits

Models that return no displayable thinking retain an honest status indicator.
Legacy professional raw message updates remain diagnostic; Authority and evidence
contracts are unchanged. Cloud/demo/user-local deployments are not part of this
local change.
