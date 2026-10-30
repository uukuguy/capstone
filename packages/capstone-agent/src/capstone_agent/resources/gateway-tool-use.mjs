// Application use policy over the gateway's published semantic toolset tag.
// This does not grant tools, change their contracts, or judge data coverage.
const advancedToolsets=new Set(['readonly_sql']);
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
export function gatewayToolAccess(publication){
  return advancedToolsets.has(gatewayToolGroup(publication))?'advanced_exploration':'published_operation';
}
export const gatewayToolUseGuidance=[
  'Choose tools by the required business operation and published semantics, not by familiarity with a generic query schema. Use applicable business tools and legal combinations first; reuse known contracts without repeating discovery.',
  'Structured table queries and native SQL are fallback paths when business tools cannot express the necessary operation or an observed suspected tool defect blocks it. Explain the uncovered operation or retain the failing tool and actual observation reference; do not invent a diagnosis.',
  'One unavailable tool does not make other business tools unavailable. Inspect the stated scope and relevant alternatives; a dataset-search failure does not establish that object, series, statistics or weather access is unavailable. Do not probe every tool or force a fixed discovery sequence.',
  'Read exact input contracts and returned guidance. Correct invalid arguments before retrying. After a timeout, change the access path or selection using published evidence; merely changing a limit or fanning out equivalent queries is not progress. If no justified correction is available, keep the gap and continue other useful work.',
  'Before batching a new query shape, validate one bounded call and its business status. Batch only independent calls with validated arguments; stop that batch on a shared contract error rather than repeat it for every object. Missing data, pagination and limits alone are not defects.',
  'Declarations are agent reports, not verified diagnoses or new permissions. Make these choices in the current reasoning loop, without a separate approval or review model call.',
].join(' ');
export const advancedExplorationSchema={type:'object',properties:{reason:{type:'string',enum:['capability_gap','tool_defect']},
  detail:{type:'string',minLength:1,maxLength:1000},tool_issue:{type:'object',properties:{tool:{type:'string',minLength:1,maxLength:256},observation_ref:{type:'string',minLength:1,maxLength:512}},required:['tool','observation_ref'],additionalProperties:false}},
  required:['reason','detail'],additionalProperties:false,description:'Explain the uncovered operation, or report the suspected tool defect and an actual observation reference. No separate approval or model call is needed.'};
const bounded=(value,limit)=>typeof value==='string'&&value.trim().length>0&&value.length<=limit;
export function checkGatewayToolUse(names,catalog,explanation,ledger){
  const advanced=names.filter(name=>gatewayToolAccess(catalog.tools[name])==='advanced_exploration');
  if(!advanced.length)return {allowed:true};
  if(explanation&&typeof explanation==='object'&&!Array.isArray(explanation)&&bounded(explanation.detail,1000)){
    if(explanation.reason==='capability_gap'&&explanation.tool_issue===undefined){
      return {allowed:true,declaration:{tools:advanced,reason:explanation.reason,detail:explanation.detail.trim(),basis:'agent_declared'}};
    }
    const issue=explanation.tool_issue;
    if(explanation.reason==='tool_defect'&&issue&&typeof issue==='object'&&bounded(issue.tool,256)&&bounded(issue.observation_ref,512)&&
      Object.hasOwn(catalog.tools,issue.tool)&&gatewayToolAccess(catalog.tools[issue.tool])!=='advanced_exploration'&&ledger?.has(issue.tool,issue.observation_ref)){
      return {allowed:true,declaration:{tools:advanced,reason:explanation.reason,detail:explanation.detail.trim(),
        tool_issue:{tool:issue.tool,observation_ref:issue.observation_ref},basis:'agent_reported_suspected_defect'}};
    }
  }
  return {allowed:false,error:{code:'advanced_exploration_requires_basis',tools:advanced,
    guidance:gatewayToolUseGuidance,
    recovery:'Use the applicable published operation, or provide advanced_exploration in this same selection/program call: capability_gap with detail; or tool_defect with detail and tool_issue {tool,observation_ref}. Preserve actual failures without inventing references.'}};
}

export function gatewayToolUseNotice(declaration){
  return declaration?{execution_notice:{code:declaration.reason==='tool_defect'?'suspected_tool_defect':'advanced_exploration',summary:declaration.detail}}:{};
}
