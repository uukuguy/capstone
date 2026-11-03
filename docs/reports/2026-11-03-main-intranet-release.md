# Main integration and intranet release preparation

## State

The user requested a tag, main integration, and then the latest intranet deployment.
Tag `milestone-managed-resources-20261103-771259a7` is pushed at `771259a7`.
PR87 targets main. It is not merged. Intranet remains `70c42dab`.

## CI attempts

- `41563425683`: both platforms failed stale workflow contract tests.
- `41564504216`: governance passed; both platforms reported 51 backend type errors.
- `41566986778`: cancelled after a local run identified a frozen-clock legacy test
  that could never leave its retry wait. Each attempt had separate user approval.
- Another CI run requires new approval. No failure has been bypassed.

## Repairs

- `9a3f75db`: select the scoped workflow job in contract tests and restore PR target filters.
- `6c7722e8`: declare runtime interfaces, narrow optional values, preserve diagnostic
  queue identity, and remove an invalid event constructor argument.
- `263bad9f`, `ee625f38`: migrate stale fixtures to bounded soft recovery,
  reference-first resources, and per-response thinking. Public runtime behavior
  is not changed by these fixture migrations. Hard deadlines, redaction,
  immutable ownership and exact activity counts remain checked.
- `3c923666`: align the protected simulator tree digest with the existing accepted
  main tree `6596fbbaaa971a98539b8566e345dc24ee11b7b0`. Simulator source is unchanged.

## Local evidence

The original aggregate stopped on failures and was later interrupted for diagnosis;
it is not a passing aggregate receipt. Its remaining targets were rerun after repair.
Do not add counts from overlapping runs.

- Grid-agent: 997 passed, 3 skipped, 453.35 seconds.
- Full capstone-agent: 3016 passed, 191 skipped, 147.62 seconds.
- Kernel: 663 passed, 11.68 seconds.
- App: 131 files and 1502 tests passed, 16.75 seconds. App types passed.
- E2E: 39 passed, 133.72 seconds; registered workers: 3 passed, 58.12 seconds.
- Simulator, tool, client, rebuild orchestration, verification target, Domain Pack,
  inventory, PyPSA and workbench targets passed in the split release run.
- Offline, scripted Pi and application validation passed; capability matrix 24/24.
- Package artifact installation and fresh source setup passed.
- Backend types: zero errors. Doctor and whitespace checks passed.

Local HTTP tests require `NO_PROXY=127.0.0.1,localhost`, as configured in CI.
The initial proxy-induced 502 responses are not product acceptance evidence.

The canonical local rebuild completed. API/worker image:
`sha256:b0402ca2bfeddc966ce3818130f94f53b01ef11d57c1a363d9460250c0b4c9a7`.
Backend source identity:
`9a1083e92a2436c9632be28a4c1bc0b488cf0feb9d05890e85ccc0a7ac2d7243`.
Native image:
`sha256:cd364dbf9b105eddb561437f80b1b2b321b8bb16e6020a7c6e858fb9e394761d`.
Readiness and App reachability passed. Scoped cache maintenance completed.
This is local validation, not intranet deployment acceptance.

## Pending sequence

1. Obtain approval for another macOS/Linux main release CI and update PR87.
2. Merge only after passing checks. Keep the existing milestone tag fixed.
3. Build and deploy the exact accepted source to the existing intranet project.
4. Preserve volumes and private configuration. Keep resource management disabled
   in API and executor. Verify readiness, image identity, App, a real task, products,
   hashes and refresh recovery before deployment acceptance.
5. Return the accepted main history and control records to dev through a PR;
   that PR's CI also requires explicit approval.

The server is reachable through the existing SSH account and sudo Docker.
No fourth CI, main merge, or intranet update has occurred at this checkpoint.
