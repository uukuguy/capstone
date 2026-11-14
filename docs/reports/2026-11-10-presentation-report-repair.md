# PPT report generation repair

The user limited this task to fixing PPT generation and updating local-dev and
dky3-dev. Both updates and bounded real-model acceptance passed. No CI or new PR.
Runtime source: `139c97004f2e14c53bcf34cc5a95c87285302703`;
`1bf44c99` adds only a positive saved-byte regression test.

## Repair

- `agent_presentations` now exposes `contract` through the fixed renderer's
  `--contract`. It includes role defaults and a complete agenda/content example.
- Invalid fields identify missing/unknown names and their location. Chapter
  mismatch errors include accepted sections and explain the default content role.
- The application host tracks actual render attempts. Required output receipts
  must match collected artifact hashes. Missing requested outputs fail with
  `native_product_delivery_incomplete`; data and drafts stay available.
- The application propagates that required-product failure to `attempt_failed`.
  Ordinary data/tool limitations keep their existing behavior. No Kernel or
  business routing change, new ledger, or repeated business retrieval was added.

## Verification

Renderer/baseline82 checks pass; SDK8 pass; host/delivery127 pass,32 environment
checks skip; application/delivery88 pass; added saved-byte positive/negative2 pass.
Scoped types report zero errors. The real model checks use synthetic content:

| Stage | Rejection followed by successful repair | Missing report remains failed |
| --- | --- | --- |
| local-dev | 27.65s; PPTX/PDF, four pages, hashes/receipt pass | 10.24s; expected named failure, no product |
| dky3-dev | 51.02s; PPTX/PDF, four pages, hashes/receipt pass | 61.50s; expected named failure, no product |

Both paths made zero gateway calls. Browser inspection confirms the failure
message and execution-failed state. The original business session's saved files
also render as an eight-page structural recovery sample, with history/data gaps
explicit. That sample does not establish current-year business completeness.
Original session and failed attempt history remain intact.

## Deployment identity

local-dev API and three workers: `5a78674c6a199ed9bada8f2eafea1ef431a3e0fb1e7cb507cad57c8493fc4ab0`.
Native: `393b8ca6a3018e6f3a246a41b78a83b1b0076ebf92e53e79aba827e728872449`.
Canonical rebuild/readiness and458 backend/275 native byte checks pass.
The user allowed interruption of the existing local download; it was already
cancelled when checked. Saved data and runtime records were preserved.

dky3-dev API/worker: `4e6abf716ddcd0c42f51d52d0f65e9aed8d79c5b4b9e469196f5ff8ddd1e29e8`.
Native: `0f68d5a3c9117e6a467b30910de699a85f2d111b9b95cc79bd70c982e2dcaa2b`.
App: `0bde8f995e6df0dfd70bac97a1063dd5677a56d0fe1104edcc13eee187f6bc4d`.
All four roles are healthy with exact139c9700 source labels.458/275 byte checks
pass. Backup: `private/backups/deploy-139c9700/`; old images, private settings,
gateway and Provider defaults remain. Other stages were not updated.

Private receipts and downloaded products:
`.capstone-agent/dky3-summer-report-20261110/`. Local scoped cache cleanup passed.
This is development acceptance, not release or full business-report acceptance.

Acceptance tag: `dky3-dev-20261110-1842-139c9700`, pointing to the exact deployed
source. Control graph browser check: 28 edges, no card intersections or horizontal
overflow; both development deployment edges point to `139c9700`.
