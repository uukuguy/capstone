# Registered skills for Mission Tasks

## Scope

The Mission organizer can select an exact version of a registered skill for a
delegated native Task. Use the existing skill registry, authorization and
native loader. The organizer receives bounded metadata for skills available
to the originating workspace and session.

## Admission and execution

The model selects a published equipment reference with a skill ID and exact
version. Before a plan change, `capstone-agent` checks the reference against
the originating session and the existing skill-use policy. Unknown versions
and unauthorized references fail before Control changes the plan revision.
Existing accepted operation receipts replay under their current contract.

`capstone-control` stores the accepted reference in the Task plan and applies
existing revision and active Task rules. At dispatch, `capstone-agent` binds
the selected version to the destination Work. The native loader materializes
that version in the private task workspace. The runner applies its current
tool and resource grants. Skill instructions carry no additional permission.

A retry uses the frozen reference. If the existing loader no longer permits
that version or cannot resolve it, surface the failure through Task status.
Changing the version requires a new admitted plan change.

## Acceptance

- Use a real Mission organizer to select one registered version. Verify that
  the delegated runtime loads that version and saves a product that uses the
  selected skill's method.
- Reject an unknown version and a skill outside the originating session's
  grants before changing the plan revision.
- Verify that a resumed or retried Task uses the frozen reference and cannot
  substitute the latest version. Check that unavailable versions fail closed
  and the skill cannot widen the existing child tool set.
- Run the focused Mission and native skill checks, then the canonical local
  rebuild and scoped macOS CI before dev integration.
