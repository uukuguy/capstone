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
