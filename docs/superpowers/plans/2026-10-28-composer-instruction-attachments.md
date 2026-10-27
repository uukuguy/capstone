# Composer and instruction attachments

User supplied the design: no context toolbar; per-instruction files; binary
next-instruction DR toggle, default off, highlighted on; settings last.
Use the existing conversation and upload components. No backend/gateway
contract change, full-file message payloads, or new grants.

1. Add assertions to `DeepResearchControl.test.tsx`: no context button,
   two-way toggle, true on one send then false on the next. Run before edits.
2. Test two accepted commands with separate resource IDs and an
   `InputCatalog.stored_resources` directory. Each file stays with its own user
   message after metadata reload; another instruction's files do not appear.
3. `ThreadCommandMenu.tsx`: remove context button and dead trigger prop;
   keep slash compatibility. `styles-light.css`: distinct off/on toggle styles.
4. Project accepted `attachment_refs` in `CapstoneAssistantThread.tsx`. Render
   bounded name/size/version cards beside the instruction using the stored
   resource directory. Keep draft upload cards in the composer. Do not load bytes.
5. `ThreadWorkAdapter.tsx`: settings after model/upload; remove global materials
   subtitle/context shortcut. Preserve resource binding. Settings last in the
   legacy `ThreadFixtureApp.tsx` toolbar too.
6. Existing context-panel tests use `/context`. Run affected App tests,
   TypeScript, diff check; canonical rebuild after checking active tasks;
   inspect toolbar order, toggle colors and instruction files in Vivaldi.

Comparison source7b1d is frozen. These changes follow the finished comparison
and do not alter either saved research product.
