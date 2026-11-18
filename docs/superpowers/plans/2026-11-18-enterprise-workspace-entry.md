# Enterprise workspace entry implementation plan

Follow the [approved entry design](../specs/2026-11-18-enterprise-workspace-entry-design.md)
and the [enterprise prototype](../../design/enterprise-workspace-prototype.html).
Capstone App owns the route and layout. The delivery target is dev.

- [ ] Extend the route test in `packages/capstone-app/src/App.threadRoute.test.tsx`.
  Verify that `/enterprise` opens the existing new-session entry, preserves
  the named workspace and does not change the root conversation shell.
- [ ] Route the entry in `App.tsx` and pass an enterprise presentation flag
  through `ThreadLiveEntry.tsx` to `WorkspaceNavigationFrame.tsx`.
  Apply prototype layout and color rules at the outer frame. Keep the existing
  navigation, composer, execution and product readers.
- [ ] Exercise session creation and restoration through the existing Thread
  transport. Test that the selected Thread and workspace remain in the
  enterprise route through navigation and refresh.
- [ ] Run App route, navigation, recovery and product checks and type checking.
  Rebuild the canonical local path. Verify real submit, stop, saved products
  and refresh without duplicate commands. Compare screenshots at 1440px and
  390px with the prototype.
- [ ] Record the accepted source and evidence in the control register and
  regenerate the overview. Run scoped macOS CI, integrate to dev, and
  verify the actual dev checkout.

## Acceptance receipt

PR #146 checked `fa68bf31` in the macOS App run `44236252574` and merged
as `68857937`. The focused local App suite passed 104 checks.

The live entry created a Thread and submitted real instructions. The stop
command received a cancellation event. After refresh the same three accepted
command IDs remained. A prior 2,007-byte product opened in the shared reader
and its download matched the saved digest.

The 1440px and 390px screenshots were compared with the accepted prototype.
On desktop the sidebar, conversation and product reader were all visible.
At 390px the history list scrolled independently. Closing the product reader
restored focus to its toggle and left the composer visible.

The actual dev backend used image `4ba1552b3b12`. Runtime and browser evidence
are in the local `runs/enterprise-workspace-entry-20261118/` directory.

## Main conversation correction

Each enterprise assistant turn shows an excerpt from its actual reply and a
summary of recorded progress or tool activity when available. The shared
execution reader retains the full answer and process. A terminal status is
displayed as status. It is never used as reply content.

PR #148 merged to dev `6d4bc023` after focused macOS CI `44239399878`.
The rebuilt App restored two real replies, two progress summaries and two
complete records at 390px. The local browser receipt is in
`runs/enterprise-inline-reply-20261118/dev-browser.json`.
