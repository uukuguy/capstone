# State Grid default for the ordinary PPT entry point

The user's latest real task generated an unbranded 18-page PPT through
`capstone-report`, bypassing the template library. The former renderer and model
instructions explicitly treated an omitted template as unbranded. The previous
library-only verification did not cover this ordinary task path.

Source `c051a8322cb6ad9efa630602923a450e6f91a804` includes the deterministic
default fix `cfbc394d` and corrected content examples. Both presentation schema
versions now use State Grid when `template` is omitted. Explicit admitted uploaded
template selection still works. Only an explicit `template: null` selects the
unbranded baseline; model instructions reserve it for explicit user requests,
never overflow recovery. Overflow or template failures never trigger fallback.
HTML behavior is unchanged.

## Verification

Focused renderer/library/route checks: 87 passed. Environment instructions: 19
passed. The regression failed before the fix with a missing template receipt;
after the fix it checks the template digest, original cover image bytes and body
layout. Additional cases cover version two, no silent overflow fallback, explicit
baseline and uploaded templates. The image smoke now exercises the default.

local-dev canonical rebuild/readiness passed. API/three workers share
`sha256:13fb47b1c537cad47eab36347d0bf3e2ddef75324ac3e0d7c2fece5f67a2b597`;
native image is
`sha256:6ebf0495512744498de20cf80fe9aa37430748359445945a1ac5283bb066649d`.
Changed runtime bytes match the exact source in API and native containers.
The App identity reports `c051a832` and local-dev.

Real model verification `thr_94841a406e9a57423ed7` completed in 14.64 seconds.
The saved content has no template field. The ordinary CLI generated a three-page
PPT with a matching State Grid digest; all downloaded product hashes pass. The
actual deck was converted to PDF and its cover inspected: original State Grid
logo and green cover artwork are visible. No business data or gateway call was
needed. Original business reports and their history remain unchanged.

## dky3-dev acceptance

The existing task ended before deployment; its terminal failure remains in the
ledger. No running task was interrupted. Backup:
`private/backups/deploy-c051a832/`. Source and images are staged at
`/data/capstone-dky3-dev/builds/c051a832/`.

All four roles are healthy and labelled with the exact `c051a832` source.
API/worker image:
`sha256:6f661c9a8ba63046a6fec67d9790e21cc0db6625e3d3076facacb17423523ea0`.
Native image:
`sha256:450f0fb9310800d403d6c8e5a66ac69f323e18b69193872b2cb56dec05449529`.
App image:
`sha256:9879cfa50ba48f5698916ff24078d73ef27d11d7be2c2273eecc7b9267671a8c`.
Backend488 and native275 file-byte comparisons pass. The served App asset
`/assets/index-D75__l-r.js` matches the staged build and exact source.

Real model task `thr_6f54800767f5e103b7e6` passed in 34.85 seconds. Its unchanged
spec omits template; the ordinary CLI produced three pages, a matching State Grid
template digest and downloaded product hashes. The source binding also matches.
Both real tests used only bash/write and made no gateway calls. Both browser
previews show the original logo and green artwork.

Private verification inputs, receipts and actual products:
`.capstone-agent/dky3-summer-report-20261110/default-template/`.
No CI, new PR, main/dev merge or unrelated stage update.

Exact-source acceptance tag: `dky3-dev-20261110-1919-c051a832`.
