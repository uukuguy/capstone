# Gateway dynamic invocation and view bindings

Status: user-approved direction and gateway-confirmed returned-action contract.

## Ownership

Capstone retains generic execution, bounded discovery, typed presentation and
receipt validation. Concrete business tool names, provider names and toolset
names do not control client execution. Only the data-gateway MCP adapter may
know agreed gateway-level discovery and contract entry tools. Credentials stay
in protected backend connection state.

The model selects the initial business operation from current discovery and
exact tool contracts. A new semantic registry, a business-name alias table,
keyword guessing and per-view extra planning calls are not part of this design.

## Provider policy

Current discovery owns providers, selection, preference and fallback. Capstone
does not separately classify one named toolset as advanced exploration or impose
a global provider-independent fallback order. Application grants and exact
contract checks remain mandatory; gateway hints do not authorize execution.

## Continuation

After submission, copy the actual returned `data.next_action` or the relevant
`provenance.agent_guidance.next_actions` entry. Tool and arguments come from that
entry, not a compiled operation map. Wait at least the applicable
`poll_after_seconds` or `not_before_seconds`. Multiple actions are choices, not
an instruction to execute every branch. Client cancellation and budgets remain.

Tasks use preparing, queued, running, succeeded and failed. Successful inspection
returns `data.inspection` and no next action. Failure returns status error,
`data.error` and no next action. Direct views use a separate state, ready; their
stream reads are in `data.streams.*.read` and the default guidance action.

View payload dispatch uses supported `data.schema`, with `data.model_revision`
and source/view identities checked. Paging follows returned cursor actions;
file reads follow returned offsets and validate total bytes and full SHA256.
References remain instance-local. None of this creates Authority calculation
evidence from general source observations.

## Connection-scoped presentation

The protected native Pi host and its presentation providers share one gateway
access object. Observe only admitted, schema-validated calls. Learn actions and
supported model discovery payloads from these responses. Check returned actions
against current publication and exact input schemas; ambiguity fails closed.

Presentation endpoints use discovered actions and supported versioned data.
They do not guess the first business call. No observed applicable capability
means explicit unavailability until the model selects and observes it. Public
App request fields must still bind to admitted view identity. A caller page-size
preference cannot rewrite a returned action; restoration cannot silently create
a new source snapshot or select another revision.

A changed publication rejects the affected call before execution and requires
fresh admission. Connection replacement creates new binding state. A failed or
completed job does not retain an executable stale poll action. Saved source
descriptors are presentation references, never raw authority handles.

## Acceptance

- Arbitrary renamed business tools and provider/toolset labels do not change
  selection gates, receipt handling or supported view presentation.
- Real binding integration covers discovery, ready manifests, actual App read
  parameters, pagination and saved descriptor restoration.
- Invalid actions, ambiguous targets, publication drift and foreign references
  fail without widening grants or weakening typed results.
- Scoped macOS tests precede dev integration; canonical local rebuild and real
  conversation/product checks follow. Cloud/demo are separate and unchanged.

Gateway protocol verification: root `runs/gateway-next-action-20261031/receipt.md`.
Live tool-renaming and a second gateway instance remain separately recorded
acceptance limits. No changes to the sibling gateway repository are authorized.
