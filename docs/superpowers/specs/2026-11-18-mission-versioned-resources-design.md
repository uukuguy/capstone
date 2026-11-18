# Versioned business resources for Mission Tasks

## Scope

Extend Mission equipment so the organizer can select a business resource
version that its originating Thread already has permission to read. The first
delivery covers read access from a delegated Task. Skill equipment is a separate
work package. The [enterprise resource contract](2026-10-15-enterprise-design-final.md#9-企业文件资源与任务上下文2026-10-18-用户确认)
governs storage and access budgets.

## Admission and execution

`capstone-agent` resolves model selections against resources available to the
originating workspace and Thread. Use the existing authorized resource
projection for discovery, with bounded metadata and exact resource and version
identifiers. Apply existing owner, lease and permission checks before a model
plan change reaches durable storage. Reject unknown references, unavailable
versions and unauthorized selections without changing the plan.

`capstone-control` owns the durable Task plan and freezes the admitted reference
with the Task. It enforces the existing revision, readiness and active Task
rules. Resource lookup and access decisions belong to the application resource
boundary. Preserve existing idempotent replay behavior for a request that was
already accepted.

When the Task starts, `capstone-agent` derives a destination-scoped read grant
from the frozen reference and the originating authorization. The delegated
runtime uses the existing bounded resource readers. Explicit denials take
precedence. If the exact version becomes unavailable or access is denied, report
the failure through the existing Task status path. Retry uses the frozen
version. A new version requires an admitted plan change under the existing
Mission rules.

Persist references and grant metadata. Read data on demand under the existing
processing and model-context budgets. Keep upload and storage quotas independent
so the design can support GB-scale and larger resources. Preserve dependency
grants and their source identities for existing Tasks.

## Acceptance

- A real Mission selects an authorized version, dispatches a delegated Task
  and saves a product that proves the Task read the selected bytes.
- After a new version is published, retry reads the original version. Check
  the saved result against the original digest.
- Focused checks show that cross-workspace, unauthorized and invalid version
  references fail before the plan revision changes. Check grant scope and
  failure when access is no longer available at execution.
- Focused checks cover prior plan replay, active Task immutability, and the
  existing dependency-resource path. Verify the local runtime after a canonical
  rebuild and use scoped macOS CI for dev integration.
