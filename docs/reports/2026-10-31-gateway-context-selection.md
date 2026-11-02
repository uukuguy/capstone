# Context-based capability selection

The unrelated news continuation in `thr_2d39b11287be34f8aec3`, attempt
`attempt_498412ffebfca7d0`, called gateway discovery. The host did not execute it
automatically. The model selected it despite recognizing that the service was
grid-oriented. An unconditional startup prompt said to follow registered
initialization first. Unscoped service initialization guidance reinforced that
preference. This was a Capstone prompt-scoping defect.

Source `06743c84` preserves first-turn entry availability but lets the model
select tools and skills using the current instruction, context, descriptions
and grants. Service startup rules apply only after service relevance selection.
Missing access to another capability is not a reason to query an unrelated
service. Previous service use does not impose a workflow on a new instruction.
There is no topic keyword router or new external-network permission.

106 focused Python checks and 36 JavaScript checks passed. Final wording was
also checked by the 20 entry/discovery checks. Canonical rebuild passed with
image `7f5fa7034f3e422114673c974aa7bef18224c12bb653640b1015ad7f1d428662`;
scoped cache maintenance completed. No CI was started.

In the existing browser grid thread `thr_92b158ca824ba8f1d6fe`, the same news
question then completed as attempt `attempt_bc318ca7856b77bf`: 8.8 seconds,
one model response, zero tool calls and zero gateway calls. The model reported
the configured lack of an authorized current-news source. It did not claim
fresh news retrieval. This is one real context-switch check, not a guarantee
that model selection can never err.

Evidence: `runs/gateway-context-selection-20261031/international-records.json`,
`international-after.json` and `international-after.png`.

## Remaining business scope failure and gateway feedback

The earlier grid instruction still has a real failure in LLM06:

- Entry: `http://127.0.0.1:18001/mcp`.
- Instance: `3db5bb96-2c27-4d97-8584-346bc4a18656`.
- Tool: `resolve_region_scope` (registered as `data_gateway_resolve_region_scope`).
- Input: `{"scope":"北京"}`.
- Request ID: `160dc47c1c2446df96770367abfe8722`.
- Result: `status=error`, gap `invalid_arguments`, message
  `Unknown business scope; use discover_region_scopes; names are not guessed`.

That failure is not an unresolved tool alias. The model selected an unsupported
business scope and later recovered through grid object lookup. The current
published schema requires `scope` but declares only `type:string`.

Reconnected to the instance, read initialization guidance, called discovery,
then described the current scope contract. Contract request ID:
`f8b9438256b6407c96d342cc23f5447f`. The schema remains an unrestricted string.
Raw discovery and contract are saved as `current-discovery.json` and
`current-scope-contract.json` in the evidence directory above.

Concrete gateway request: generate the accepted scope IDs and aliases as an
input-schema enum from the provider's existing registered scope definitions.
Clarify that this resolver covers that finite business dictionary. Keep grid
object references on the existing object-directory route. No new semantic
registry or Beijing-specific behavior is required. Capstone can then apply
its existing generic schema validation, without a business value table or
special-case rewrite. Do not claim that an enum makes arbitrary model tool
selection error-free. No gateway modification was made in this task.
