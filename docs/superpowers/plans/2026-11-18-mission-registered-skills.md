# Mission registered skills implementation plan

The [approved design](../specs/2026-11-18-mission-registered-skills-design.md)
uses the registered delegated Pi profile and native skill invocation.
Capstone Agent owns admission and execution. Capstone Control owns the frozen
equipment reference on the Task. The target branch is dev.

## Select and validate equipment

- [ ] Add focused tests to `packages/capstone-agent/tests/test_mission_equipment.py`
  for a ready skill at its exact version, an unavailable version, and a skill
  whose required tools are denied or absent from the effective Task selection.
- [ ] In `packages/capstone-agent/src/capstone_agent/mission_equipment.py`,
  resolve only ready skills in the registered delegated profile. Apply the
  current session's skill exclusions. Publish bounded display metadata with
  exact equipment references. Preserve the existing application plan preflight.
- [ ] Validate at most one selected skill per Task and forbid a skill as a
  tool restriction. In `native_mission.py`, advertise the registered kind
  after the child path is ready.

## Bind execution

- [ ] In `packages/capstone-agent/tests/test_agent_delegation.py`, cover the
  actual child Work command, exact skill and role versions, replay, and an
  unavailable frozen selection.
- [ ] In `packages/capstone-agent/src/capstone_agent/agent_delegation.py`,
  pass the admitted selection through the existing `skill_invocation`
  contract. Check `thread_input.py`, `intent_runtime.py` and
  `delegated_runtime.py` for the normal command-to-runner path. Limit the
  invocation to the selected native goal.
- [ ] Check the native runner retains the effective Task tool set and explicit
  denials. Keep the existing skill invocation behavior for ordinary callers.

## Verify and integrate

- [ ] Run focused native skill and Mission gates with disposable PostgreSQL.
- [ ] Rebuild with `make capstone-local-rebuild`. Run a real Mission whose
  organizer selects the skill. Verify actual loading and a saved product,
  then exercise retry and denial.
- [ ] Record source and verification in the canonical worklist and version
  register. Regenerate and inspect the control graph. Run scoped macOS CI,
  integrate into dev, and verify the actual dev entry point.
