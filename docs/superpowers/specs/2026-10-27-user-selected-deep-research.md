# User-selected Deep Research

The user chose explicit per-instruction control after observing that prose
requests for DR were not reliably honored. This supersedes autonomous escalation
for instructions submitted by the current workspace composer.

- The existing compact input toolbar shows 深度思考, default off. Its tooltip
  explains that it selects Deep Research task organization, not the Thinking
  transcript or a model reasoning-budget setting.
- The skill picker button is removed. Existing skill invocations/resources and
  historical commands remain valid.
- Submission captures a typed `deep_research` boolean. The admitted instruction,
  native context and execution configuration retain that same choice. A successful
  send resets the next draft to off. Refresh preserves an unsent selection.
- Off keeps ordinary authorized native/gateway tools and removes research-control
  tools from the model menu. It cannot activate DR by guessing from user prose.
- On uses the existing organization-only role from the first model request.
  The parent plans and integrates; isolated executors do the actual work.
  A direct answer without an admitted plan cannot silently satisfy this choice.
- Existing persisted requests without this optional field retain their old
  contract. The toggle grants no additional data, tools or Authority access.
- Thinking display remains independent and keeps the existing compact behavior.

Verification includes typed input rejection, actual SDK publication overlay,
tool admission in both modes, draft reset, missing skill-button regression,
and real Vivaldi submissions in both modes. The user subsequently requested a
full comparison: submit the same summer research task in two new conversations,
one with this option off and one on. Keep model and grants equal and compare
the complete paths and saved products, not only elapsed time.

## Composer refinement accepted 2026-10-28

Remove the context toolbar button. Uploaded files belong beside their submitted
instruction; draft files remain with the unsent input. Resolve accepted resource
IDs against stored resource metadata, without putting file bodies in messages.
Preserve historical/slash contracts. Remove the session-wide material subtitle
and its context-button shortcut from the unified conversation view.

Toolbar order: 深度思考, 模型, 上传资料, 设置. Settings is last. Deep Research
is a binary pressed button: muted off, highlighted on, with keyboard focus
retained. It defaults off and affects the next submitted instruction only;
acceptance resets the next draft off. Failed/uncertain sends retain the original
draft and exact choice. No change to admitted old tasks.
