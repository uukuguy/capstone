# Opened model work continuity

Status: user approved on 2026-10-08: switching an opened model returns to immediately after its latest instruction. This supersedes the fresh-Context-on-every-switch rule in the original opened-model design.

## Identities and ownership

Application owns stable opened entries, their unique current pointer and saved work positions. Each entry refers to one exact Authority model identity (family, model ID, revision). A work position holds the last usable ModelContextSnapshot. Context/selection snapshots already bound to Attempts remain immutable; newer selection snapshots do not rewrite earlier claims. Kernel and Domain Packs retain their existing ownership and evidence contracts.

Activate an opened entry by resuming its saved Context, selection revision and exact model revision. The next instruction remains a new Attempt and receives only admitted prior-result candidates belonging to that Context, Thread, Run and model revision. Global tool preferences are applied by the existing next-instruction admission path; switching does not silently enable tools. Only initial opening, closing then reopening, or explicit Context reset creates a new Context. Selecting the current entry is a no-op.

Save current work before leaving a model and on subsequent workspace synchronization. Persist it in the same bounded workspace transaction. Old workspaces acquire saved Contexts from retained typed activation/Attempt records; choose the latest valid exact-identity Context and retain the current Context. Preserve recorded closes. The original migration's public models/1 shape remains unchanged; private work-position fields are excluded from its projection.

The claim carries the latest terminal instruction and answer excerpt for the exact saved Context. Each excerpt is bounded to 4096 characters and is labeled historical reader text, not new instructions or admitted evidence. Memory and PostgreSQL read retained Context-scoped records; no Provider is needed for restoration. This is a bounded continuity bridge, not restoration of a private Pi scratchpad or an old live RPC process.

## Views and interaction

Opened membership is authoritative server state. Historical Context/Attempt views are independent replay records, never model members. Client projection exposes one model working page per opened identity and separate Context/Attempt views. The current model working page resolves its saved Context; history remains accessible from the associated answer, including closed models. Stop rendering the old Context-based model-history strip for current servers; do not turn Context counts into model counts. Legacy snapshot-only clients keep their compatibility view navigation.

Returning to a model restores its last admitted diagram/layer and labels the source instruction. Retained result display is historical evidence, not a newly calculated result. A missing view is restored through the bounded Context/Attempt replay API; do not substitute another Context's diagram. Camera state is keyed by exact model identity and view source, retained across switches and same-tab refresh. Model controls preserve message scroll, draft and focus. Explicit history viewing changes only the view pointer, not the execution target. Last model and active Attempt/Case locks remain enforced.

## Acceptance

- A -> B -> A retains A's Context and selection, keeps two members, restores A's view and admits its prior result references for the next new Attempt.
- Persist/restart/compaction retain work positions. Old current-only workspaces, exact versions and recorded closes remain compatible.
- Duplicate model identities or work Contexts belonging to another identity are rejected. Public models/1 does not expose private fields.
- Current close resumes the most recently used remaining entry; explicit reopen after close creates a fresh work position.
- Desktop/mobile controls, history replay, overlays, camera, labels, draft and message scroll are checked with no Provider calls and no changes to user conversations.
- Rebuild local API/worker/App; run focused checks, repository integration gates and report current image identity. Cloud release remains a separate acceptance step.
