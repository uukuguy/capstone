# Mission versioned resources implementation plan

**Goal**
Let delegated Mission Tasks read an exact business resource version already
authorized for the originating Thread.

**Architecture**
The application resolves and authorizes references. Control stores exact
references in Task equipment. The application binds reads to the child Work
before it starts execution.

**Stack**
Python, PostgreSQL, the native Pi runtime and the existing resource readers.

**Design**
[Versioned business resources for Mission Tasks](../specs/2026-11-18-mission-versioned-resources-design.md)

## Admit exact references before storing a plan

- [x] Check exact historical version resolution and reject an unknown version in
  `packages/capstone-agent/tests/test_native_mission.py`. Keep existing plan
  replay and active Task checks in the focused gate.
- [x] Extend the equipment reference contract in
  `packages/capstone-control/src/capstone_control/mission.py` and the model
  schema in `packages/capstone-agent/src/capstone_agent/native_mission.py`.
  Use the published resource identifier and version for the equipment ID and
  revision. Keep resource references out of tool restriction handling.
- [x] In `packages/capstone-agent/src/capstone_agent/mission_equipment.py`,
  resolve the exact pair through the existing authorized Thread resource
  projection. Keep discovery bounded. Use the same resolver for model plan
  preflight in `control_host.py` and readiness. Preserve the existing order
  of accepted replay and preflight. Store references with the plan.

## Bind the resource to the destination Work

- [x] Exercise the actual delegation entry point in
  `packages/capstone-agent/tests/test_agent_delegation.py`. Check a replacement
  after admission and rejection of a cross-workspace origin.
- [x] In `packages/capstone-agent/src/capstone_agent/agent_delegation.py`,
  resolve the frozen resource references at delegation. Bind exact read grants
  before the start command. Reuse the grant path in `delegation_resources.py`
  where its contract applies, including its source identity and destination
  Work scope. Keep explicit tool denials in effect. Preserve current behavior
  for existing dependency grants and already-admitted replay.
- [x] Verify that the child receives resource references with on-demand
  readers. Keep file bytes out of plan, command and model context envelopes.
  A missing version or denied access must surface through Task status.

## Verify and integrate

- [x] Run the focused Mission gate described by the
  [Mission delivery plan](2026-11-18-mission-conversation.md).
- [x] Run `make capstone-local-rebuild`. Submit a real Mission that uses a
  registered resource version. Compare the saved child product with the
  selected byte digest. Publish a newer version and repeat the Task through
  the supported retry path. Confirm the digest still matches the first version.
- [x] Record the exact source, local acceptance and scoped macOS CI in the
  version register and control graph. Integrate through a PR to dev and repeat
  entry-point checks in the actual dev checkout.

## Local verification receipt

The real organizer selected the first version. The downloaded 40-byte
product matched that version after the second version was published.
In a separate pause and resume case, delegation generation 2 downloaded the
first version and saved an exact 31-byte copy. Control accepted the generation
2 delivery after a rebuild with the observation sequence fix. The rebuilt API
also rejected a missing version, and both Mission and plan revisions matched
their values before the request.

The local receipt is in `runs/mission-versioned-resources-20261118/`.
The backend source was `f7de9f68` and the four backend roles used image
`c3cabc920795`. PR #142 checked `d251f400` in macOS run `44223654353`
and merged as `8d402bed`. The actual dev checkout was rebuilt with image
`b9459f681b2d`. The live API returned both verified Tasks and the downloaded
products still matched their original versions. See the local
`dev-runtime-receipt.json` for exact digests.
