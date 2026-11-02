# Workspace entry recovery

The normal root entry no longer stops at a new-session button.

- With no workspace or thread selector, assign a short name such as
  `空间-4a9f2c81` and store it in the URL before mounting the workspace.
- With a workspace but no thread, read its active history. Open its last selected
  active thread, including one on a later page. Otherwise open its newest thread.
- When that workspace has no active history, create one session through the
  existing v2 path. Strict Mode must not duplicate creation.
- Preserve explicit thread selection and legacy thread links. Do not migrate a
  thread into another workspace. Do not override navigation made during a read.
- A failed history read shows a retry action. It never means empty history.

The existing origin/workspace-scoped selection storage and session UI are reused.
There is no new conversation layout, server workspace registry, or business tool.
Existing `enterprise` history remains at `/?workspace=enterprise`.

Verification: 38 focused App checks passed in 3.70 seconds; TypeScript checks
passed. These cover entry routing, explicit creation, saved selection, pagination,
empty history, failed reads, concurrent navigation, and short workspace names.
No CI or cloud deployment was requested or started.

Real browser verification reused the existing Vivaldi tab. Opening
`?workspace=enterprise` restored `thr_5bd702a75df2e3de832e`. Opening the bare root
created `空间-b239d9bf` and one empty session, `thr_57a1254e28950cdd0877`, with
the existing composer. The tab was then returned to the user's directory export
session. No business query was submitted. Screenshots and state are saved under
`runs/workspace-entry-20261031/`.
