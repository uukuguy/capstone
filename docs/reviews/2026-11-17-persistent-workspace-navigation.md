# Persistent workspace navigation verification

Owner capstone-app. Product source6eb7c637; baseline dev3ef7d5b2.
PR131 is merged into actualdev8d5fa71d. Exact-head macOS CI44026102168 passed.

## Required behavior and root cause

The user rejected PR128's metadata-only acceptance. Session selection must keep
the same sidebar/list DOM and geometry, update only selection highlight, and
load conversation/products independently. Counts alone do not prove this.
Each retained session previously owned a complete navigation frame; cold and
warm selection therefore changed navigation owners. The route now owns one
frame, catalog, global controls and fixed gateway footer. Activities retain
conversation/products. Legacy per-session records remain with their content.

The old scroll checkpoint also locked out compositor wheel events that arrived
after routing. A99→87 regression reproduced it. The persistent list now keeps
its live gesture through selection; standalone frames retain their recovery
behavior. Access changes reset the workspace scope. A new-entry authentication
regression also failed first and passed after namespace rotation.

## Local checks and real browser evidence

132 App checks across12 direct consumers and TypeScript pass. The scoped
classifier/governance checks pass190 with1 existing skip. Navigation identity,
row identity, selected highlight during cold preparation, no list request on
selection, delayed background catalog, new-entry authentication, retained
conversation/products, cache eviction and queued wheel events are covered.

Candidate canonical rebuild10795 completed0 at6eb7c637. API and three workers
use image84aab658c7056e77a5e289d13e0c277f37d6d0d4f0797fb241a2b2b470763905;
readiness and scoped cache maintenance passed. Candidate5174 is the initialized
implementation checkout. Actual5173 still uses dev until integration; this is
a temporary, explicit role split.

Reused the existing Capstone browser automation tab with its matching cached
Playwright CLI1.64. No new tab/profile or copied authentication. At1920×1050,
three real cold switches and one warm switch retained identical navigation,
list, scroll-container, footer and row nodes. All row/navigation/scroll bounds
and scroll offsets match; MutationObserver recorded0 row child-list changes;
selection caused0 catalog requests. Real snapshot reads were delayed1200ms,
then continued to the actual server. Highlight updated during preparation;
the requested conversation then loaded. No answer/result fixture replaced data.

The separate scroll trial uses a real wheel gesture to100px, then three switches
without waiting out the gesture. All node identities and row bounds remain;
scrollTop stays100, row mutations0, catalog GET0. Screenshots were inspected.
Original10 exact pin IDs match the durable baseline. Existing saved PPT preview
and historical conversations remain available; no model instruction was sent.

New entry automatically creates a Thread by existing design. Its real trial
created empty thr_7f864f18c01f505b3268; zero events/works were verified and only that
owned empty trial was deleted. Creation legitimately refreshes the catalog, so
its request is not classified as a selection request. Original failure receipts
are retained. A1200px probe timed out on an existing zero-width heading layout;
the accepted desktop probe uses the user's desktop width. The earlier top-only
pass did not cover the scroll race and is not final acceptance.

Evidence root: ignored runs/persistent-navigation-20261117. Candidate2 browser/
scroll proof JSON contains exact identities, bounds assertions, selected titles,
request counts and adjacent screenshots. Independent reviewer dispatch failed
Unknown model gpt-6.1-luna; direct source review was performed, no independent
review pass is claimed. Vivaldi Apple Events JavaScript remains disabled.

## Actual dev acceptance

Canonical actualdev rebuild11444 completed0 at8d5fa71d. API and three workers
run imagef3bb77d2bf23689a742818fa046f54eba1e189acda62a492fbc99ffedaa6d31b;
readiness and scoped cache maintenance passed. App5173 reports product6eb7c637,
repository8d5fa71d and clean source.

The same strict real-browser probes passed on actual localhost5173: three cold
switches, one warm switch, then three switches at scrollTop100. Navigation/list/
scroll/footer/row identities remain equal; coordinates and offsets remain equal;
row child-list mutations0, catalog requests0. Cold highlight precedes content
readiness. Original10 exact pin IDs still match. Screenshots and existing saved
PPT preview were inspected. Existing Vivaldi5173 tab also passed four switches;
its separate snapshots remain in the same ignored evidence directory.

The canonical register includes fixed source8d5fa71d before the control-only HEAD
advances. Only docs/persistent-navigation-closeout-20261117 remains for acceptance
record integration; its own PR/CI/merge/HEAD and clean receipts stay ignored.
No new feature, cloud/demo release or model task is selected.
