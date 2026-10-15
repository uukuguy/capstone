# User-local offline verification

## Scope

The user selected Linux AMD64 delivery and an internal OpenAI-compatible
service. The package defaults to `PROVIDER=openai` and `OPENAI_MODEL=deepseek-flash`.
Users set `OPENAI_BASE_URL`, `OPENAI_API_KEY`, and optionally `OPENAI_MODEL`.
The user has confirmed that `PROVIDER=openai` works with their service.

Packaging checks used no real Provider. The user later authorized a real
DeepSeek check through `OPENAI_*`; see the protocol section below. Registered scripted
cases test installation, execution, persistence and evidence transport. They
do not establish LLM answer quality or scientific acceptance.

## Code verification

- Provider/Kernel focused and adjacent checks: 172 passed.
- Offline transport/manager/runtime checks: 67 passed.
- Version-catalog preservation correction: 19 passed and independent review.
- Native Pi selected the custom model and internal endpoint in both worker
  families without sending a prompt.
- Local `make check-pr`, `make test-e2e` (39 + 3), and `make validate` passed.
- Offline capability validation covered 24/24 registered capabilities.
- The first macOS CI run lacked Docker. One new real Compose test had omitted
  its prerequisite. Commit `75af46a` added the same availability guard as the
  existing Compose tests. Eight tests passed with Docker; the diagnostic path
  without Docker passed five and skipped that one Compose test.
- Fresh Linux/macOS CI and accepted source identity: pending.

## OpenAI-compatible API protocol

Commit `927f08b` fixes two errors found by protocol verification: Pi inherited
Responses for custom OpenAI endpoints, and a bare credential variable name
was treated as a literal key. Local-trial custom OpenAI addresses now select
`openai-completions`; official OpenAI retains Responses. The Kernel writes
the explicit API and `${OPENAI_API_KEY}` reference, never the secret value.

- Four real pinned-Pi loopback SSE tests passed across both worker families:
  exact Chat Completions path, Bearer key, model, streamed text and split tool
  calls, tool-result return and final assistant completion.
- The expanded focused regression passed 129 checks. Independent review approved.
- The user-authorized real DeepSeek endpoint passed a text request and a
  harmless tool round trip with `PROVIDER=openai`, `OPENAI_MODEL=deepseek-flash`
  and `OPENAI_BASE_URL`/`OPENAI_API_KEY`. Credentials were absent from artifacts.
- Business samples through the OpenAI path: pending.

## Candidate installation

Candidate source `6b74397639e4c10b75bb90855c9dab863024da04` passed on the
local ARM64 host using Linux AMD64 containers:

- All four image archives loaded and all six running containers used AMD64.
- Backend source labels and API/worker image identities matched.
- Host download commands and Docker pull/build were blocked.
- Three registered cases completed nine turns. Reports and evidence replayed
  with matching hashes after restart and repeat installation.
- Missing endpoint or key rejected startup before stopping the active service.
- Private configuration and data-volume names remained stable.
- Browser checks covered topology, composer, source identity and overflow.

This candidate does not include the later catalog correction. It is retained
as test evidence and is not the final delivery.

## Final delivery

Pending the normal dev merge, exact-source rebuild, extracted archive
installation, replay, browser checks and canonical local-dev rebuild.
Existing user installations, local-demo, cloud-dev and cloud-demo remain on
their recorded sources during candidate acceptance.

Operator receipts are ignored files under
`.worktrees/dev-trial-deployment/.capstone-agent/`. Final user artifacts belong
under the main checkout's `runs/user-local-offline/` directory.
