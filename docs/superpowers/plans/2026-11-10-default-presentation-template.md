# Default presentation template repair

The user confirmed that PPT generation must use the State Grid template by
default. The latest real task bypassed the library through capstone-report.
Enforce the default at that renderer boundary, not only in model instructions.
Explicit admitted uploaded selections keep their existing behavior. A deliberate
`template: null` retains the baseline layout for explicit unbranded requests and
baseline regression checks; omission always selects State Grid. No silent fallback
on overflow or template failure. HTML is unchanged.

1. Add CLI regression for an omitted template and assert its receipt digest,
   preserved cover artwork and master layout. Confirm it fails before the fix.
2. Apply the renderer default and align CLI help plus native model instructions.
   Keep independent baseline tests explicit and cover invalid/explicit selections.
3. Run renderer, native environment and build-smoke checks. Commit this unit.
4. Canonical local rebuild; run a real model request without naming a template,
   inspect its saved PPTX and receipt. Deploy the exact revision to dky3-dev and
   repeat the same check. Preserve active tasks and saved user data.
5. Record identities, receipts and deployment source. No CI or new PR.
