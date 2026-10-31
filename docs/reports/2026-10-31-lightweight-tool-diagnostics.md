# Lightweight tool call diagnostics

The native activity projection now retains `activity.input_excerpt` before a
tool runs. The existing thread event ledger stores it with the attempt, task,
call ID, tool name and timestamp. The delegated runtime preserves this field
after task completion and workspace cleanup. The excerpt is limited to 4,000
characters, five nested levels and 32 entries per collection. It masks credential
fields and omits file, code and message bodies. Truncation has an explicit marker.
This is diagnostic data, not Authority evidence or an additional execution ledger.

Rejected tool activation now lists the unmatched names and states that no tools
were activated. No business names or provider names are added to runtime policy.
Historical missing inputs cannot be restored by this change.

## Local verification

- New projection and selection tests failed before the change and passed after it.
- Projection, progress, graph, delegated runtime and host: 230 passed, 32 skipped
  in 5.26 seconds. Localhost checks require `NO_PROXY=127.0.0.1,localhost` in the
  operator environment; the first run had three proxy-generated HTTP 502 errors.
- Native tool discovery, including the pinned SDK: 15 passed in 0.99 seconds.
- A worker test confirms input retention in saved thread events after completion.
- No CI, push, PR, merge or cloud deployment was started for this change.

## Confirmed contract lookup failure

Thread `thr_fce15d08b820aadb1072`, attempt `attempt_c0a46ca298fe91d8`:

| Calls | Input | Arguments SHA-256 | Outcome |
| --- | --- | --- | --- |
| `call_00_vaV9EQjXQ38Xru7ycDKs3240`, `call_01_cjjclw9RkiMweH1zEiSC8945` | `{"tool_name":"data_gateway_list_region_objects"}` | `7c1c23b6f4d08993f26886687d536cc908c2ce8a126245ef3cc50f78e2c07a86` | Unknown or disabled tool |
| `call_01_s2AiX3fxzWiOAbf87IYc2143` | `{"tool_name":"list_region_objects"}` | `ac33effa9b742102e6745701557d6814437ce62fc7d8752ab22f7fbb17557daf` | Contract returned |

Both inputs above match the original gateway observation receipt hashes exactly.
The model used the Capstone transport name as a gateway contract lookup parameter,
then repeated the same invalid input once. The later unprefixed lookup succeeded.
The target business tool was enabled. The adapter correction below resolves
this contract target conversion. General model recovery behavior is unchanged.
The names in this table are incident evidence, not standing runtime rules.

Local evidence: `runs/gateway-dynamic-product-20261031/latest-task-records.json`.

## Deterministic adapter correction

The MCP adapter converts a registered contract-lookup target to its exact source
name using the accepted catalog for the current connection. Original source
names pass through. Unknown targets are not guessed, unrelated arguments and
business calls are unchanged, and ambiguous source/transport collisions are
rejected before sending. No business tool names, provider names or prefix slicing
rules are introduced. The only fixed protocol is the agreed gateway contract
lookup entry and its `tool_name` parameter, within the MCP adapter.

Adapter and relay checks: 89 passed in 2.93 seconds. Tests cover prefixed and
original targets, unknown names, collisions, unchanged business arguments and
caller input preservation. Reconnected to instance
`3db5bb96-2c27-4d97-8584-346bc4a18656`, read initialization instructions, called
discovery, then successfully described the same incident target using its
Capstone name. Gateway request ID: `2e5d0ddd29544dc6b2ed02500d75eb75`.
Receipt: `runs/gateway-dynamic-product-20261031/contract-name-normalization.json`.
This protocol check calls no business data tool. No CI was started.
