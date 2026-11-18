# Enterprise workspace entry and session recovery

This delivery implements the first slice of the
[enterprise UI contract](2026-10-15-enterprise-task-ui-design.md).
Use the [accepted prototype](../../design/enterprise-workspace-prototype.html)
for the navigation, task title, conversation and product layout.

## Entry and ownership

Add a dedicated `/enterprise` entry with a workspace-scoped Thread URL.
Existing published conversation URLs retain their routing and presentation.
Enterprise navigation links preserve the enterprise route and workspace
scope when selecting, creating or restoring a Thread.

Reuse the workspace navigation frame, retained Thread activities,
conversation and composer, execution details, and product reader. The
enterprise route supplies the presentation layout and task title. Start with
the existing Thread transport and restore the current Thread through the
existing version-aware read path. A refresh or session switch does not
submit a command.

## Layout and first delivery

At 1440px the workspace shows the project navigation beside the conversation.
The adjacent product reader opens through its existing controls and shares
the same current Thread. A 390px viewport uses the existing navigation drawer
and product overlay. Preserve composer focus and available actions when a
panel opens or closes. Use the prototype order for title, controls and content.

The first delivery covers the entry, shell and session restoration. Dedicated
registered view types and a full Control workspace remain separately tracked
requirements.

## Acceptance

- Navigate to the enterprise entry, open or create a Thread, switch Threads,
  and refresh. Confirm the active Thread and existing saved products restore.
- Use the live composer to submit and stop a real task, then view an actual
  saved product. Check that refresh does not send a duplicate command.
- Compare actual screenshots at 1440px and 390px with the prototype.
  Check panel placement, focus recovery, scrolling, and composer access.
- Verify existing conversation routes and their supported protocol versions.
  Run the focused App checks and canonically rebuild before live acceptance.
