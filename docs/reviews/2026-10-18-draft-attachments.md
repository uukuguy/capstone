# Draft attachments and skill selection

User decision: files stay in the composer until the user sends an instruction.
Users can add files in several uploads and remove individual draft files. Refresh
must restore stored drafts. Skill names retain their published native names;
Chinese text describes their purpose. The current selection contract is single-skill.

## Contract

- New composer uploads use the bounded chunk transport with `draft: true`.
- A completed draft is private stored data, not session context. The draft resource
  directory restores it after refresh. File bytes do not enter browser storage.
- `send_message.attachment_refs` selects exact immutable resource identities.
  Admission verifies those identities and freezes manifests. The accepted command
  event records the references in the same transaction as the new attempt.
- Rejected commands do not attach drafts. Retrying the same accepted command is
  idempotent. A lost response keeps the original command and draft until confirmed.
- Removing a completed draft writes a cancellation event and deletes its chunks.
  A resource already submitted cannot be deleted through draft cancellation;
  historical evidence remains readable. Existing published resources remain valid.
- The composer shows compact file cards with name, size, pending state and remove
  control. The skill button shows a selection count; its panel shows the original
  name, short purpose, remove control and optional source details.

## Verification

- 39 backend checks passed, including memory and isolated PostgreSQL stores.
  Covers staged visibility, rejected/accepted sends, duplicate commands, deletion,
  immutable manifests and existing normal conversation behavior.
- 48 App checks passed across upload, skill selection, resource transfer, work
  command recovery and existing conversation behavior. TypeScript passed.
- 87 further backend checks passed for legacy materials, work execution and input.
- Local rebuild is ready; API and worker use image
  `b453261e19d73984fd5da8a8082d6b38d9a5be8ce9d9141166b7c58afe2c9965`.
- Browser thread `thr_ad38d31949d60c884202`: actual file chooser uploaded
  `spot-prices.csv` (1,473,876 bytes), then drag/drop added a disposable text file.
  Both cards survived refresh. Removing the text card removed only that draft.
  Before sending, `/resources` was empty and `?draft=true` listed the CSV.
  After one short research instruction was accepted, the lists reversed.
  The CSV identity is `resource_2fd3513ac9ff277a6775d244f2ccba91`.
  Screenshot: `/tmp/capstone-draft-composer.png`. The selected skill retained
  native name `explore-data`, shown on hover and inside the picker.

## Real research and natural revision

One short request produced an HTML data-quality report in 52.8 seconds / 11 tools
(`attempt_63006f023edec0bd`). A natural feedback message asked for cautious wording
about negative-price causes and preservation of existing results. Revision
`attempt_0e7a956ab5713c98` completed in 37.0 seconds / 7 tools, without a further
continuation. The revised download has 11,562 bytes and SHA-256
`a139e19cf8613ace742058f264754bed0f39ad30e5debf8aee3dda18b0f501f5`.
All four HTML tables are byte-identical to the original. No external asset URLs
are present. Refresh restores both report versions. Root output:
`outputs/draft-upload-acceptance/report.html`.

Download verification exposed a stale-version link while locating a newly selected
product. The App now hides the prior view during that lookup and binds each blob
URL to its exact product reference. Seven product-view checks, including delayed
version switching, passed; TypeScript passed. Real UI download then matched the
revised artifact. Total focused App checks: 55.

Final canonical rebuild is ready at image
`c9cf89e58442fc97d124d7506e92890a95d6a78293d3de1bd80f665678c9a4ad`.
Report preview and refresh were checked again after this rebuild. No test attempt
is active. External access remains disabled and enforced. Control graph browser
check: 30 nodes, 40 edges, no overlaps, crossings, through-node edges or overflow.

This change does not establish research execution reliability. The preceding
research revision was cancelled by the execution chain without its original
exception reaching the user. Bounded failure reasons have been added separately;
the root cause and autonomous recovery still need a real-run verification.
