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
- Three real OpenAI-configured business samples completed nine turns. IEEE-39
  and AC/DC structure passed current-run admission, successful tool-source and
  exact read-only replay checks. Regional modeling/derivation worked, but dispatch
  remained limited: Polars crashed before the solver in AMD64 emulation without
  AVX/AVX2. The original failed receipt is preserved.
- The initial validator incorrectly required every evidence reference to appear
  in a calculation result projection. The contract only requires projection
  references to be admitted. An independent read-only validator checks actual
  tool sources and terminal admissions, preserving the real regional failure.
- Commit `39b1658` adds same-version Polars `rtcompat` only for Linux x86_64.
  Six lock files add only that runtime; existing versions remain unchanged.
  A fresh isolated AMD64 container completed registered dispatch without network
  access. Five dispatch regressions, six lock checks and independent review pass.
  New-image, Ubuntu VM and regional revalidation remain pending.

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

## Cross-daemon installation correction

The real Ubuntu VM installation at `39b1658` passed archive checksums but
safely rejected image lookup before starting services. Docker 29 containerd
exposes an image manifest digest as `.Id`, while the source daemon uses the
config digest. Removing the OCI index did not restore config-ID lookup.
The failed receipt is retained; this package is not accepted for delivery.

Commit `916271f` exports fixed-tag archives and binds both config and AMD64 leaf
manifest digests from the final archive. It verifies metadata and complete layer
chains, including raw/gzip DiffIDs, before freezing delivery. The loader checks
the actual imported ID against those two identities, then verifies platform and
source. A private temporary deployment projection selects that ID consistently
for manifest, release settings and installation receipt. The static data contract
is unchanged. Repeat installation compares the projected package. All starts
use exact IDs and forbid image pulls.

The combined archive/installer/manager/runtime/Provider gate passed160 checks;
independent review and19 extra layer-focused checks passed. `make doctor`,
script syntax, links/symlink and diff checks passed. Source916 VM installation
then found public metadata mode0600 blocked the runtime UID. The correction
preserves original mode and ownership; credentials remain0600. Focused20 tests
and independent review passed. User cancelled further VM validation.
Host Docker source916 passed fresh install, nine scripted turns, report/evidence
replay, restart, repeat installation and private configuration/data retention.

Source698e2a9 passed the same complete host installation acceptance. API and both
workers used one verified Linux AMD64 image. Real OPENAI_* DeepSeek requests
completed all nine registered IEEE39, regional-six-bus and AC/DC turns. Independent
read-only replay verified current-run tool provenance, authority admission,
history and bounded projections for all three groups. Regional dispatch returned
optimal base and growth solutions; the earlier CPU-runtime failure is retained.
Both required Linux/macOS checks passed for698e2a9 (run38692022505).

## User instructions

Both package and installed-directory README include the frozen user sample
guide. It uses the formal project instructions, grouped in user language and
ordered from short information queries to calculations, scenario changes and
advanced exploration. It replaces the earlier three representative demos.
The complete preview is `runs/user-local-offline/README-preview.txt` in the main
checkout.
Online and offline packages now provide README.md in both the version package
and installation root, while retaining README.txt compatibility. Shared examples
include the original mv_oberrhein island request before the long generation
research example. Online first-install commands follow the credential setup.
Builder, installer, manager and offline checks passed97 tests with independent
review; the final first-install wording passed three focused checks.

## Cloud installation scope

The user cancelled cloud-dev validation and further local Ubuntu VM validation.
No cloud service was stopped, created or deployed. Remaining acceptance uses
the existing local Docker environment with Linux AMD64 containers emulated on
Apple ARM. This is not native AMD64 hardware or cloud acceptance.

## Final delivery

Pending the normal dev merge, exact-source rebuild, extracted archive
installation, replay, browser checks and canonical local-dev rebuild.
Existing user installations, local-demo, cloud-dev and cloud-demo remain on
their recorded sources during candidate acceptance.

Operator receipts are ignored files under
`.worktrees/dev-trial-deployment/.capstone-agent/`. Final user artifacts belong
under the main checkout's `runs/user-local-offline/` directory.
