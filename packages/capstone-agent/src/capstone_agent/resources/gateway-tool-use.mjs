// Gateway publications own selection policy. Hints never grant tools.
const ledgers=new WeakMap();
export function createGatewayUseLedger(){
  const observations=new Map();
  return {record(tool,ref){if(typeof tool==='string'&&typeof ref==='string'&&ref)observations.set(ref,tool);},
    has(tool,ref){return observations.get(ref)===tool;}};
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
 'Read the current discovery response and follow its provider, selection, preference and fallback rules. Reuse known exact contracts without repeating discovery. Do not infer policy from tool, provider or toolset names.',
 'Compose ordinary synchronous operations from exact published contracts. Pass observed results to dependent calls; batch independent calls only with validated arguments. Follow returned guidance and preserve actual observation references.',
 'Before batching a new call shape, validate one bounded call and its returned status. Correct invalid arguments before retrying. Stop a batch on a shared contract error. If no supported correction is available, retain the gap and continue other useful work.',
 'Discovery guidance is not authorization. Use only task-granted tools within current bounds. Do not invent tool defects or infer that other providers or operations are unavailable from one failed call.',
].join(' ');
// Compatibility helper only. Discovery and execution enforce grants and bounds;
// this client adds no toolset-specific policy gate.
export function checkGatewayToolUse(_names,_catalog,_explanation,_ledger){return {allowed:true};}
export function gatewayToolUseNotice(){return {};}
