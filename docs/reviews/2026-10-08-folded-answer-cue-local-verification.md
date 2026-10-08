# Folded answer cue — local verification

The user reports that the folded state is unclear and asks for a downward expand arrow, paired with the upward collapse arrow. The follow-up asks for lighter preview text. The final design keeps the icon-only header control, adds no state text or background, and uses muted `#5d7b76` for the folded preview and its headings/emphasis. Expansion restores normal text styling.

- App328 and TypeScript/Vite build passed. Existing persistent-toggle regression verifies the down/up icons, one button, accessible names and retained focus.
- Actual local conversation checked headlessly at 1600x900, 375x812 and 812x375. Folded text computes to `rgb(93, 123, 118)`; expanded text returns to `rgb(41, 73, 72)`. Toggle x/y/width remain identical across both directions: 0px measured shift at all three sizes. Screenshots were inspected.
- No backend POST or Provider request was made. The user's history was read without modifying its model or instructions. Browser-only display state belongs to the isolated headless session.
- Doctor, current-source local rebuild and whitespace checks passed. API and workers share the rebuild image; Vite serves the current App source. No cloud deployment or release tag.

Ignored receipts and screenshots: `output/playwright/fold-cue-20261008/`. The temporary “展开” caption was superseded by the user's lighter-text suggestion before commit.

## Follow-up: lighter body and separate heading tone

The user asks for a lighter body. Folded body, emphasis, code and links now use `#81958f`; headings and their inline emphasis use slightly deeper `#6b847c`. Controls keep only the arrow and hover hint. Expanded styling is unchanged.

Build, doctor, current-source rebuild and whitespace checks pass. Actual conversation checks at all three sizes verify body `rgb(129, 149, 143)`, heading `rgb(107, 132, 124)` and expanded body `rgb(41, 73, 72)`. Both toggle directions retain 0px shift, and screenshots were inspected. No backend POST or Provider requests. The isolated browser was closed after verification. Updated receipts: `lighter-browser.log` and `lighter-*.png` in the same ignored directory. This CSS-only revision does not require another full test suite.

## Correction: actual paragraph color

The user identifies that the body did not get lighter. The earlier color receipt measured the Markdown container, not its paragraph descendants. The independent `.capstone-chat-body p` rule kept actual paragraphs at `rgb(41, 73, 72)` even when the container was muted. The earlier paragraph-color claim is superseded by this receipt.

The folded rule now explicitly includes paragraphs, list items and blockquotes, retaining the separate heading tone. The real browser reproduces the old container/paragraph mismatch before the fix (`body-red.log`). After the fix, all four actual paragraphs and four inline emphasis/code elements use `rgb(129, 149, 143)`; expansion restores all four paragraphs to `rgb(41, 73, 72)`. Desktop, mobile and landscape checks retain 0px toggle shift and make zero backend POST requests. The expanded browser check now asserts descendant paragraph colors so it catches this regression. Screenshots were inspected; build, doctor and current-source local rebuild pass. Receipts: `body-fixed-browser.log` and updated `lighter-*.png`.
