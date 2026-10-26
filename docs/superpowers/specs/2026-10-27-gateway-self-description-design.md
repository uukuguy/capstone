# Gateway self-description consumption

Status: user-approved direction, 2026-10-27. Wire-level integration follows the
gateway's actual publication; this document does not invent unpublished fields.

## Outcome

An agent receives a host-configured MCP connection and authentication. It can
discover available data and business capabilities, request semantic details,
select tools and compose valid calls without reading gateway repository docs.
This applies to all gateway tools, not just electrical diagrams. The sibling
data-gateway project owns publication changes and is not edited by this work.

## Ownership and admission

The Application owns connection trust, permissions and task grants. Gateway
publication supplies business tool descriptions and input/output schemas. The
Kernel does not gain business semantics. Registered calculation Authorities
retain calculation results, model revisions and evidence admission.

Replace the checked-in business-tool name list with a generic admission policy
over the trusted service's published operation contracts and application grants.
MCP annotation hints alone are not authorization. Unknown or ungranted effects
remain unavailable with an explicit reason; they must not silently gain write,
arbitrary endpoint, host filesystem or execution access. Building an external
model artifact does not by itself register it as a local Authority model.

Task grants are host-issued and bound to the current attempt. Publishing a tool
does not alter an already running task's grant implicitly. Catalog refresh and
tool activation must be explicit host operations at an agent-loop boundary.
Revocation and terminal task isolation continue to apply.

## Discovery and context

Use standard MCP discovery and the gateway's published discovery interfaces.
Keep a bounded global summary in context; fetch capability, object and tool
details on demand. Do not inject every detailed definition into every model
request. The published description, input schema, output schema and semantic
contract references are retained with version identity. Do not fabricate missing
units, permissions, preconditions or contract references.

Generic registration already exists in general-mcp.mjs. Reuse it, and remove
business-name admission dependencies instead of adding a second invocation path.
New ordinary capabilities that satisfy existing grants require no Capstone code
change. A new display format or new permission class can still require support.

## Composition and results

The lightweight agent loop chooses its next call, answer or Deep Research
escalation. Gateway next-actions are suggestions, not a fixed workflow or grants.
Composition must check applicable object identity, version, time window, unit,
granularity and statistical definition conditions. Display names are not keys.
Missing conditions remain unknown; the agent must request clarification or report
the limit rather than infer that two datasets can be joined.

Preserve published provenance, completeness, quality gaps and error semantics in
bounded observations. Host-issued call receipts bind actual arguments, contract
identity and returned content. These receipts establish what was returned, not
that the result is complete or that a scientific conclusion is valid. Large
results stay behind references and bounded pages.

Specialized views consume supported versioned result contracts. They must not
control general tool availability. Existing electrical v1 presentation support
is an adapter, not a universal business workflow. Existing view-job ownership
checks must move to published resource-scope contracts before being generalized;
do not remove them and expose other tasks' jobs.

## Publication changes

An unrelated tool addition, removal or update must not stop an unchanged tool.
Before a call, compare that tool's complete admitted publication with the live
publication. A change or removal of the called tool stops before execution and
requires fresh admission. Do not automatically repeat a call after execution may
have started. Do not infer schema compatibility from a tool name.

## Acceptance

Use fresh agent tasks with no repository documentation in their context:

1. Discover data coverage and complete more than one business task.
2. Execute different valid combinations rather than a prescribed sequence.
3. Discover a newly published ordinary tool without a Capstone name-list edit.
4. Reject invalid joins: same name/different identity, incompatible versions,
   time windows, units or statistical definitions.
5. Report partial coverage and evidence gaps without inventing complete results.
6. Keep an unchanged tool callable when unrelated catalog entries change; reject
   changed called contracts, forged grants and cross-task references.
7. Verify ordinary calls remain in the lightweight loop and record their real
   tool chain. Deep Research does not become mandatory for discovery.

Use focused unit and MCP transport checks, then real local agent tasks in the
existing Vivaldi tab. Record measured durations. Full release gates are not part
of this local development unit. New semantic wire fields await actual gateway
publication; runtime support is not claimed from this design alone.
