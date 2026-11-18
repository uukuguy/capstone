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

- [ ] Extend `packages/capstone-control/tests/test_missions.py` and
  `packages/capstone-agent/tests/test_native_mission.py` to cover a selected
  exact version, unknown and cross-workspace versions, replay after an access
  change, and an attempted edit of an active Task. Confirm new cases fail
  before adding support.
- [ ] Extend the equipment reference contract in
  `packages/capstone-control/src/capstone_control/mission.py` and the model
  schema in `packages/capstone-agent/src/capstone_agent/native_mission.py`.
  Use the published resource identifier and version for the equipment ID and
  revision. Keep resource references out of tool restriction handling.
- [ ] In `packages/capstone-agent/src/capstone_agent/mission_equipment.py`,
  resolve the exact pair through the existing authorized Thread resource
  projection. Keep discovery bounded. Use the same resolver for model plan
  preflight in `control_host.py` and readiness. Preserve the existing order
  of accepted replay and preflight. Store references with the plan.

## Bind the resource to the destination Work

- [ ] Extend `packages/capstone-agent/tests/test_agent_delegation.py` with
  a case that publishes a newer version between attempts, a case that
  revokes access before a new admission, and a destination-scope check.
  Confirm the new cases exercise the actual delegation entry point.
- [ ] In `packages/capstone-agent/src/capstone_agent/agent_delegation.py`,
  resolve the frozen resource references at delegation. Bind exact read grants
  before the start command. Reuse the grant path in `delegation_resources.py`
  where its contract applies, including its source identity and destination
  Work scope. Keep explicit tool denials in effect. Preserve current behavior
  for existing dependency grants and already-admitted replay.
- [ ] Verify that the child receives resource references with on-demand
  readers. Keep file bytes out of plan, command and model context envelopes.
  A missing version or denied access must surface through Task status.

## Verify and integrate

- [ ] Run the existing focused Mission gate described by the
  [Mission delivery plan](2026-11-18-mission-conversation.md).
- [ ] Run `make capstone-local-rebuild`. Submit a real Mission that uses a
  registered resource version. Compare the saved child product with the
  selected byte digest. Publish a newer version and repeat the Task through
  the supported retry path. Confirm the digest still matches the first version.
- [ ] Record the exact source, local acceptance and scoped macOS CI in the
  version register and control graph. Integrate through a PR to dev and repeat
  entry-point checks in the actual dev checkout.
