# Folded answer cue — local verification

The user reports that the folded state is unclear and asks for a downward expand arrow, paired with the upward collapse arrow. The follow-up asks for lighter preview text. The final design keeps the icon-only header control, adds no state text or background, and uses muted `#5d7b76` for the folded preview and its headings/emphasis. Expansion restores normal text styling.

- App328 and TypeScript/Vite build passed. Existing persistent-toggle regression verifies the down/up icons, one button, accessible names and retained focus.
- Actual local conversation checked headlessly at 1600x900, 375x812 and 812x375. Folded text computes to `rgb(93, 123, 118)`; expanded text returns to `rgb(41, 73, 72)`. Toggle x/y/width remain identical across both directions: 0px measured shift at all three sizes. Screenshots were inspected.
- No backend POST or Provider request was made. The user's history was read without modifying its model or instructions. Browser-only display state belongs to the isolated headless session.
- Doctor, current-source local rebuild and whitespace checks passed. API and workers share the rebuild image; Vite serves the current App source. No cloud deployment or release tag.

Ignored receipts and screenshots: `output/playwright/fold-cue-20261008/`. The temporary “展开” caption was superseded by the user's lighter-text suggestion before commit.
