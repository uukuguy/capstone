// Gateway publications own selection policy. Hints never grant tools.
const ledgers=new WeakMap();
export function createGatewayUseLedger(){
  const observations=new Map();
  return {record(tool,ref,observation){
      if(typeof tool!=='string'||typeof ref!=='string'||!ref)return;
      const old=observations.get(ref);
      if(old&&(old.tool!==tool||observation&&old.observation&&
          old.observation.reference.sha256!==observation.reference.sha256))throw Error('Observation reference identity changed');
      observations.set(ref,{tool,observation:old?.observation??(observation?structuredClone(observation):undefined)});
    },
    has(tool,ref){return observations.get(ref)?.tool===tool;},
    resolve(ref){return structuredClone(observations.get(ref)?.observation);}};
}
export function gatewayUseLedger(config){
  if(!ledgers.has(config))ledgers.set(config,createGatewayUseLedger());
  return ledgers.get(config);
}
export function gatewayToolGroup(publication){
  const group=publication?._meta?.['data-gateway/toolset'];
  return typeof group==='string'&&group.length>0&&group.length<=128?group:undefined;
}
// Compatibility projection: names do not imply an access class.
export function gatewayToolAccess(){return 'published_operation';}
export const gatewayToolUseGuidance=[
 'The following service rules apply only when this service is relevant to the current instruction.',
 'When the current instruction requires this service, read its current discovery response and follow its provider, selection, preference and fallback rules. Reuse known exact contracts without repeating discovery. Do not infer policy from tool, provider or toolset names.',
 'Compose ordinary synchronous operations from exact published contracts. When multiple independent requests have complete known arguments, submit agent_tools_execute with calls:[{id,tool,arguments},...] together; no program or tools fields are needed. This applies to any independent parameter set, not a particular business topic. Process returned refs and construct dependent requests in a later stage or program. In program mode use tools.batch for independent requests and tools.call for genuine dependencies. Follow returned guidance and preserve actual observation references.',
 'Before expanding a retrieval, relate each selected object, time window and resolution to a requested comparison or output. A discovered catalog is not a requirement to retrieve every entry. Use published overview or aggregate capabilities when they can establish coverage; then retrieve detail for the selected scope. Keep any needed baseline or event windows explicit. If selected objects or windows each need sequential pagination, use tools.map over the independent chains and await each chain\'s actual returned cursor inside its mapper. Do not run the entire cross-object retrieval as an outer serial await loop. Read tools.help() in the program for exact helper signatures; do not invent helper names or source fields.',
 'Reuse saved observations for inspection, calculations and product construction. Saving or inspecting an existing result does not require repeating its source query. Read bounded fields or array pages by their issued references instead of copying whole results into model context.',
 'Within this instruction, composition reuses an exact successful status=ok request only when the published tool declares both readOnlyHint and idempotentHint. The result carries reused=true, its original ref and observed_at; it is not a new source observation. tools.call(name,args,{refresh_reason:reason}) or tools.batch(calls,{refresh_reason:reason}) explicitly rereads when newer data is required. tools.follow always executes the returned action, including polling. Failures and partial results are not reused. Unknown tool semantics do not imply reuse eligibility.',
 'Every completed composition exposes completed_calls, including successful and reused references. When local transformation or export is wrong, repair it from these observations rather than rebuilding the retrieval. Large manifests remain readable through the issued full_result object. A composition observation contains result and completed_calls; it is not the underlying business response.',
 'Use one source-processing path: tools.inspect(ref,pointer) establishes the actual structure; tools.read selects fields or bounded array pages; tools.table prepares typed CSV data without shell or jq. Do not guess file-envelope paths. tools.table({name,sources:[{ref,pointer}],columns:[{name,pointer,type,nullable?}],minimum_rows?}) takes pointers to source arrays and row-relative column pointers. Types are string, number, integer, boolean, date (YYYY-MM-DD), datetime (ISO timestamp with timezone). No implicit coercion, missing fields, invalid dates or silent row drops. It returns path, manifest_path, rows and source hashes only after all rows pass; failures preserve the source refs and publish no table. Use this before calculations, charts or report construction.',
 'For a new retrieval scope, tools.plan(calls,{purpose,output,basis_refs}) checks the exact call list and available successful observations without executing or reserving calls. Put the same optional plan on tools.batch. It reports distinct requests, duplicates and existing refs. Explain how the chosen scope supports the requested output; inspect availability evidence before expanding a new measurement. The host checks references and contracts, not the truth of a business selection. Do not infer that every catalog object must be retrieved.',
 'Direct calls return observation_ref. Composition read, inspect and saveContext use that task-issued call/source reference with the structured result at the root, as tools.call and full_result reads do. Original evidence files keep their bytes but the access helpers normalize the transport envelope. Reuse returned identifiers unchanged. References not issued by this task are unavailable, even if their text looks valid.',
 'For unfamiliar business semantics, validate one bounded call and its returned status before expanding retrieval; reuse an existing successful observation when it establishes the same shape and scope. Do not execute a probe merely to check input schema: composition tools.describe reads the frozen contract and batch preflight validates all arguments before invocation. Correct invalid arguments before retrying. Stop a batch on a shared contract error. If no supported correction is available, retain the gap and continue other useful work.',
 'Discovery guidance is not authorization. Use only task-granted tools within current bounds. Do not invent tool defects or infer that other providers or operations are unavailable from one failed call.',
].join(' ');
// Compatibility helper only. Discovery and execution enforce grants and bounds;
// this client adds no toolset-specific policy gate.
export function checkGatewayToolUse(_names,_catalog,_explanation,_ledger){return {allowed:true};}
export function gatewayToolUseNotice(){return {};}
