/** Published model-owned graph contract. No scheduling, I/O or domain policy.
 * Operation is bound by the application; payload never contains operation.
 * All capacities are explicit positive integers. The host can use the exported
 * JSON schemas for tools; validateGraphOperation also enforces text/item limits.
 */
import {EnterpriseCycleError,requireCycle} from './enterprise-cycle-contract.mjs';
export {EnterpriseCycleError};
export const GRAPH_SCHEMA='capstone-enterprise-graph/2';
export const RESULT_SCHEMA='capstone-task-result/1';
export const GRAPH_WORK_EDITION='capstone-graph-work/1';
const text={type:'string',minLength:1};
const id={...text,maxLength:128,pattern:'^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$'};
// References are opaque handles, never private paths, URLs or bucket handles.
const ref={...text,maxLength:256,pattern:'^[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}$'};
const array=items=>({type:'array',items});
const object=(properties,optional=[])=>({type:'object',additionalProperties:false,properties,
  required:Object.keys(properties).filter(key=>!optional.includes(key))});
const choice=(...values)=>({type:'string',enum:values});
const refs=array(ref),texts=array(text),ids=array(id);
const input={oneOf:[object({name:id,result_ref:ref}),object({name:id,from:object({step_id:id,slot:id})})]};
export const graphNodeSchema=object({id,purpose:text,questions:texts,checks:texts,depends_on:ids,
  expected_outputs:texts,mode:choice('execute','synthesis'),execution:choice('parent','delegated'),instruction:text,
  source_refs:{...refs,description:'Explicit unique subset of plan source_refs for raw sources this node needs. Use [] for a retained-result-only consumer; dependencies grant no raw sources. Selected admitted versions are frozen into its action.'},
  outputs:array(object({slot:id,kind:choice('observation','artifact'),description:text})),inputs:array(input)});
export const graphRecomputeReasonSchema=object({kind:choice('source_changed','method_changed','missing_result','discrepancy'),
  refs,diagnostic:text},['diagnostic']);
/** Exact operation payloads. revise supplies the complete accepted node set.
 * rerun requests another execution of a settled, previously started node and
 * permits an explicit changed definition, including its raw source selection.
 * A graph revision reselects future inputs only for unstarted/rerun nodes.
 * execution_settled is host-only. record/assess require their own action IDs.
 */
export const graphOperationToolParameters={
  plan:object({goal:text,output_mode:choice('text','files'),nodes:array(graphNodeSchema),source_refs:refs}),
  revise:object({nodes:array(graphNodeSchema),reason:text,rerun:array(object({step_id:id,reason:graphRecomputeReasonSchema,supersedes:refs}))}),
  start:object({step_id:id,kind:choice('execute','assess')},['kind']),
  execution_settled:object({action_id:ref,status:choice('completed','failed','cancelled','unknown')}),
  record:object({action_id:ref,outcome:choice('completed','limited','failed'),proposal_ref:ref,outputs:array(object({slot:id,
    observation_refs:refs,artifact_refs:refs,summary:text,scope:text})),limitations:texts},['proposal_ref','outputs']),
  assess:object({action_id:ref,outcome:choice('success','limited','failure'),checks:array(object({description:text,
    status:choice('passed','failed','not_run'),refs,explanation:text})),proposal_ref:ref,summary:text},['proposal_ref','checks']),
  // resolve returns an approved public result view. Exact private manifests are
  // available only through the explicitly named host resolver, never this tool.
  resolve:object({result_ref:ref}),
};
export function graphOperationParameters(edition){
  requireCycle(edition===undefined||edition===GRAPH_WORK_EDITION,'Unsupported graph work edition');
  if(edition===undefined)return graphOperationToolParameters;
  const parameters=structuredClone(graphOperationToolParameters);
  const accepted=object({name:id,result_ref:ref,accept_limited:object({assessment_ref:ref,rationale:text})});
  for(const operation of ['plan','revise']){
    parameters[operation].properties.nodes.items=structuredClone(graphNodeSchema);
    parameters[operation].properties.nodes.items.properties.inputs.items.oneOf.push(accepted);
  }
  return parameters;
}
export function graphCapacity(dimension,actual,limit) {
  if(actual<=limit)return;
  const error=new EnterpriseCycleError('research_capacity_exceeded',`${dimension} exceeds configured capacity`);
  error.capacity={dimension,actual,limit,unit:dimension.endsWith('_bytes')?'bytes':'items'};throw error;
}
export function graphLimits(limits) {
  requireCycle(limits&&['maxNodes','maxItems','maxText','maxExecutions','snapshotBytes','publicBytes']
    .every(key=>Number.isSafeInteger(limits[key])&&limits[key]>0),'Explicit graph capacities are required');
  requireCycle(limits.resultBytes===undefined||Number.isSafeInteger(limits.resultBytes)&&limits.resultBytes>0,
    'Optional resultBytes must be a positive integer');
  return limits;
}
function validate(value,schema,limits,path) {
  if(schema.oneOf){
    const matches=schema.oneOf.filter(branch=>{try{validate(value,branch,limits,path);return true;}catch{return false;}});
    requireCycle(matches.length===1,`${path}: expected exactly one published input binding`);return;
  }
  if(schema.type==='string'){
    requireCycle(typeof value==='string'&&value.trim().length>0,`${path}: expected nonempty text`);
    graphCapacity('graph_text',value.length,Math.min(schema.maxLength??limits.maxText,limits.maxText));
    requireCycle(!schema.enum||schema.enum.includes(value),`${path}: choose a published value`);
    requireCycle(!schema.pattern||new RegExp(schema.pattern).test(value),`${path}: invalid identifier or opaque reference`);
  }else if(schema.type==='array'){
    requireCycle(Array.isArray(value),`${path}: expected array`);graphCapacity('graph_items',value.length,limits.maxItems);
    value.forEach((item,index)=>validate(item,schema.items,limits,`${path}[${index}]`));
  }else if(schema.type==='object'){
    requireCycle(value!==null&&typeof value==='object'&&!Array.isArray(value)&&Object.getPrototypeOf(value)===Object.prototype,`${path}: expected plain object`);
    requireCycle(Object.keys(value).every(key=>Object.hasOwn(schema.properties,key))&&schema.required.every(key=>Object.hasOwn(value,key)),`${path}: unexpected or missing fields`);
    for(const [key,child]of Object.entries(schema.properties))if(Object.hasOwn(value,key))validate(value[key],child,limits,`${path}.${key}`);
  }
}
/** Strict validation returns a detached payload. Semantic graph/grant checks
 * occur in reduceEnterpriseGraph with the admitted host context and state.
 */
export function validateGraphOperation(operation,payload,limits,edition) {
  graphLimits(limits);const schema=graphOperationParameters(edition)[operation];
  requireCycle(Object.hasOwn(graphOperationToolParameters,operation)&&schema,'Unknown graph operation');
  validate(payload,schema,limits,operation);
  if(operation==='record'||operation==='assess')requireCycle(Object.hasOwn(payload,'proposal_ref')!==Object.hasOwn(payload,operation==='record'?'outputs':'checks'),
    'Use exactly one proposal_ref or explicit '+(operation==='record'?'outputs':'checks'));
  if(payload.nodes){
    requireCycle(payload.nodes.length>0,'Graph needs at least one model node');
    graphCapacity('graph_nodes',payload.nodes.length,limits.maxNodes);
  }
  return structuredClone(payload);
}
