# Enterprise research with production data through MCP

Status: proposed integration contract, based on the user-approved delivery order.
No Capstone runtime integration is implemented by this document.

## Goal and delivery order

Enable an enterprise-research conversation to discover and retrieve production
data through data-gateway, analyse the returned data, save reader-facing products,
and continue with traceable sources after a follow-up or page refresh.

The first delivery uses the existing enterprise-research organisation and native
execution path. Unified conversations and grid model ingestion remain later
deliveries. “General question answering and task execution” is the working
description for LLM answers and non-professional tool execution; “ordinary chat”
is not the proposed enterprise-facing name.

## Ownership

Capstone consumes the gateway's published MCP contract. It does not select,
configure, classify or switch the gateway's database, snapshot, cache or upstream
service. Backend management belongs to data-gateway. Backend details returned in
provenance remain source facts, not a new Capstone user workflow or eligibility
gate. Connection readiness and the data returned for the requested window are
checked through MCP.

The gateway owns its eight business services, source records, reusable queries,
quality declarations and model export. Capstone owns task composition, analysis,
conversation context, products and faithful references. An enabled tool is not
proof that a particular requested dataset exists or is complete.

Application configuration selects the fixed gateway and permitted operations.
The Kernel continues to own neutral organisation, turns and artifacts. Domain
semantics do not move into the Kernel. Gateway observations do not become
simulator results or admitted professional evidence implicitly.

## Observed contract

On 2026-10-25, a real authenticated Streamable HTTP client completed initialize,
tools/list, discover_data_capabilities and discover_business_services at the
configured endpoint. Server version: 1.30.0. The server published 47 tools,
including six model tools. These are observations, not fixed tool-count gates.
The client used only the connection file and MCP, without reading gateway data
files. Ignored receipt: ROOT outputs/data-gateway-20261025/discovery.json.

The connection file is ../data-gateway/runtime/network-gateway/connection.json.
It is an operator input, not a tracked application configuration or a task
attachment. Its authorization value must never enter Git, App variables, task
arguments, model context, exported products or public diagnostics.

The gateway evolves independently. Capstone discovers actual tools, accepts a
schema revision and pins that revision for an admitted task. A later task can
accept a newer publication. Schema changes during execution fail explicitly;
they do not silently change a running task's tool contract.

## Protected host adapter

Add a host-owned remote MCP adapter beside the existing local PowerMCP adapter.
Do not modify the fixed local PowerMCP descriptor to accept arbitrary URLs.

The general Pi host reads an operator-selected connection file from protected
storage. A versioned, credential-free policy declares the gateway resource ID,
tool namespace and explicit permitted tools. Initial permission is limited to
research discovery and data retrieval, including the gateway's bounded semantic
table-query interface. The six model operations are excluded in this delivery.
Newly published tools require policy admission; discovery alone grants no access.

An immutable task catalog records accepted tool schemas, their hashes, a catalog
revision and the server identity. Public tool names use data_gateway_ followed by
the upstream tool name. Tool parameters cannot select an endpoint, authentication
header, executable or server-side file. The native process receives public
schemas and a short-lived, task-bound host relay grant, never gateway credentials.

The relay uses the existing deadline, cancellation and task ownership controls.
It validates the selected tool and arguments against the admitted schema before
calling MCP. It checks output schemas when supplied. Calls have bounded frames,
call counts and timeouts under application-capacity configuration. Errors are
bounded public codes, without raw HTTP requests or credential-bearing exceptions.
No automatic call replay follows an unknown outcome. Authentication failures,
schema drift and transport errors remain distinguishable from unavailable data.

An unconfigured optional gateway leaves the current research path usable. A
configured but unreachable gateway is explicitly unavailable; it must not be
reported as ready or silently replaced with synthetic data. Tasks that require
production data must report the blocker rather than assert unsupported findings.

## Research execution and provenance

The existing tool guard and research controller apply to gateway calls. Both
organisation-level work and isolated research nodes receive the same accepted
task catalog, scoped to their execution ownership. Tool publication must be
consistent across host capability discovery, native_context.allowed_tools,
actual Pi registration, SDK inventory and isolated node configuration.

Recommended model behaviour is to discover capabilities and services, identify
objects, inspect metrics and coverage, select an explicit source when needed,
then retrieve the requested window. Structured table queries use the gateway's
prepare_data_query/execute_data_query contract and preserve its validation
fingerprint; Capstone does not expose raw SQL or invent table relationships.

Preserve status, data, gaps, provenance and calculation. Missing values remain
missing; units and time semantics come from the service. Report conclusions must
fit the observed scope. A partial result can support a scoped conclusion but
cannot stand for full coverage.

The host records task/attempt/call identity, accepted catalog/schema hashes,
arguments hash, response hash and the gateway result in the existing source and
artifact contracts. Gateway-issued provenance is kept inside that response.
Source admission uses host-issued receipts, not model-authored identity fields.
The current external_mcp_observation check is PowerMCP-specific; introduce an
explicit gateway receipt path instead of weakening its descriptor checks.

Large query products use versioned saved artifacts and bounded slices. Do not
make full-result base64 model context or duplicate entire database tables into
the conversation. If a needed gateway result exceeds the current MCP contract,
record the gap and request a bounded result/export-reference contract upstream.

Existing conversation, task process, product preview, follow-up and recovery
components remain the presentation path. No new mandatory connection wizard or
backend-selection screen is part of this delivery.

## Verification and cooperation

1. Transport tests exercise a real local Streamable HTTP MCP server: discovery,
   schema pinning, authentication, argument/output validation, cancellation,
   bounded errors and refusal of unlisted/model tools. Test secrets must not
   appear in configs visible to task UIDs or in recorded events.
2. Integration tests prove the same published tools reach policy admission,
   actual SDK registration, research nodes and host source admission. Existing
   local PowerMCP and research execution stay covered by their focused checks.
3. Real gateway checks discover actual services and perform one bounded query
   with explicit discovered identities. Preserve the unmodified response and
   hashes. No assumption about gateway backend switching enters the check.
4. One real model-driven enterprise-research task must discover and obtain data,
   analyse it, save a readable report with sources, accept a follow-up, and restore
   its products after refresh. A second bounded task exercises semantic table
   exploration. Model tool use and saved bytes are required; fixtures alone do
   not pass acceptance.
5. Use the canonical local rebuild before actual App acceptance and the scoped
   cleanup helper after use. Verify API/worker source identity. Use the affected
   dev PR gate; no release workflow or cloud/demo promotion is implied.

Gateway issues receive reproducible requests, sanitized responses, expected
contract and measured impact. The user permits coordinated fixes; report an issue
before changing the sibling project, and preserve its unrelated work. Do not
contact other people or agents without authorization.

## Later model delivery

User decision, 2026-10-25: sibling projects use identical exact SDK versions;
do not build or test a cross-version compatibility matrix. The shared baseline
is Capstone's accepted pandapower 3.4.0 and PyPSA 1.3.0. Coordinate gateway
dependency locks and model rebuilds to this baseline. Future upgrades change
both projects together. This records the agreement, not a completed gateway
dependency update. Ordinary same-version model and calculation acceptance remains.

The new model service is tested separately at the user's request. Its published
contract currently delivers source-node topology, with explicit electrical data
gaps. Current formats are pandapower JSON and PyPSA NetCDF, not two JSON formats.
Download, integrity verification and native SDK loading do not prove power-flow
readiness. The gateway's quality declarations remain binding. Capstone model
registration, conversion, Authority admission and calculation are outside this
first research integration.

Large graph display must be supported by both scale-aware gateway projections
and a measured large-network renderer; raw model voltage filtering alone is not
sufficient. See [topology view requirements](2026-10-25-grid-topology-view-requirements.md).
