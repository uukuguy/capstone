// The host supplies this task-bound relay and catalog. Upstream credentials
// and endpoint selectors are never tool parameters or native task inputs.
import {boundToolResult,readHistoricalObservation,savedToolObservation} from './tool-result-context.mjs';
import {createHash} from 'node:crypto';
import {gatewayUseLedger,gatewayToolDescription} from './gateway-tool-use.mjs';
import {setTimeout as wait} from 'node:timers/promises';
import {observedAction} from './observed-action.mjs';
import {createToolIdentityResolver} from './tool-identity.mjs';

export function createHistoricalGatewayFollow(observations,catalog,admittedNames,invoke,deadlineAt=Infinity){
  const identities=createToolIdentityResolver(catalog,admittedNames);
  return {
    name:'agent_gateway_follow',label:'Follow saved gateway action',executionRole:'orchestrator',
    description:'Execute one exact action from an admitted historical gateway receipt. Supply its historical call ID and action pointer, for example /provenance/agent_guidance/next_actions/0 if that action was observed. Use this for authorized continuation such as pagination or polling. Never reconstruct action arguments.',
    parameters:{type:'object',properties:{
      historical_call_id:{type:'string',minLength:1,maxLength:128},
      pointer:{type:'string',minLength:1,maxLength:512,pattern:'^/'},
    },required:['historical_call_id','pointer'],additionalProperties:false},
    async execute(callId,input,signal){
      signal?.throwIfAborted();
      if(!input||Object.keys(input).length!==2||typeof input.historical_call_id!=='string'||
          input.historical_call_id.length>128||typeof input.pointer!=='string'||
          !input.pointer.startsWith('/')||input.pointer.length>512)
        throw Error('Supply only the admitted historical call ID and action pointer');
      const item=observations.find(row=>row.tool_call_id===input.historical_call_id);
      if(!item)return {isError:true,content:[{type:'text',text:JSON.stringify({
        code:'historical_gateway_action_unavailable',executed:false,
        message:'The retained action is unavailable in the current gateway scope. Stop this continuation.',
      })}]};
      const source=await readHistoricalObservation(item);
      const records=new Map([[item.tool_call_id,{
        value:source,ok:['ok','success','partial'].includes(source.status),
      }]]);
      const action=observedAction(records,item.tool_call_id,input.pointer);
      const name=identities.resolve(action.name);
      if(action.waitMs>=deadlineAt-Date.now())throw Error('Returned wait exceeds the task deadline');
      if(action.waitMs)await wait(action.waitMs,undefined,{signal});
      signal?.throwIfAborted();
      const {content,isError}=await invoke(name,action.args,{callId:callId+':follow',signal});
      return {content,isError};
    },
  };
}

export const gatewayInvocationOptions=Symbol('gatewayInvocationOptions');
export const reusableGatewayRead=(schema,args)=>schema?.annotations?.readOnlyHint===true&&
  schema?.annotations?.idempotentHint===true&&schema?.annotations?.destructiveHint!==true&&
  !['job_ref','preparation_ref'].some(key=>Object.hasOwn(args??{},key));
const publicErrors=new Set(['gateway_arguments_invalid','gateway_request_invalid',
  'gateway_result_body_unavailable',
  'gateway_operation_retry_blocked',
  'gateway_tool_not_admitted','gateway_task_not_admitted','gateway_call_already_started',
  'gateway_publication_changed','gateway_authentication_failed','gateway_connection_failed',
  'gateway_call_failed_no_retry','gateway_timeout','gateway_transport_failed','gateway_output_invalid','gateway_catalog_invalid',
  'gateway_catalog_unavailable','gateway_unavailable','capacity_exceeded','unauthorized']);
const resourceErrors=new Set(['gateway_authentication_failed',
  'gateway_result_body_unavailable',
  'gateway_connection_failed','gateway_call_failed_no_retry','gateway_timeout','gateway_transport_failed','gateway_catalog_invalid',
  'gateway_catalog_unavailable','gateway_unavailable','gateway_task_not_admitted','unauthorized']);

export async function resolveGatewayContracts(config,names,{signal,fetchImpl=globalThis.fetch}={}){
  const gateway=config.dataGateway;
  const missing=names.filter(name=>gateway.catalog.tools[name]?.progressive&&!Object.hasOwn(gateway.catalog.tools[name],'inputSchema'));
  if(missing.length){
    const remaining=Math.min(1800000,config.deadlineAt-Date.now());
    if(remaining<=0)throw Error('gateway task deadline exceeded');
    const deadline=AbortSignal.timeout(Math.ceil(remaining));
    const response=await fetchImpl(gateway.url,{method:'POST',
      headers:{'Content-Type':'application/json',Authorization:'Bearer '+gateway.grant},
      body:JSON.stringify({operation:'resolve_contracts',names:missing}),
      signal:signal?AbortSignal.any([signal,deadline]):deadline});
    const result=await response.json();
    if(!response.ok||result.catalog_revision!==gateway.catalog.revision||result.executed!==false)
      throw Error('Selected contract load failed: '+(publicErrors.has(result.error)?result.error:'gateway_contract_invalid'));
    for(const name of missing){
      const original=gateway.catalog.tools[name],exact=result.tools?.[name];
      if(!exact||!Object.hasOwn(exact,'inputSchema')||exact.name!==original.name||
          exact.progressive?.tool_key!==original.progressive.tool_key||
          exact.progressive?.tool_contract_revision!==original.progressive.tool_contract_revision||
          result.tool_hashes?.[name]!==gateway.catalog.tool_hashes[name])throw Error('Selected contract identity changed');
    }
    Object.assign(gateway.catalog.tools,result.tools);
  }
  return Object.fromEntries(names.map(name=>[name,gateway.catalog.tools[name]]));
}

export async function validateGatewayBatch(config,calls,{signal,fetchImpl=globalThis.fetch}={}){
  const gateway=config.dataGateway;
  if(!gateway)throw Error('Batch preflight unavailable; no calls executed');
  const remaining=Math.min(1800000,config.deadlineAt-Date.now());
  if(remaining<=0)throw Error('gateway task deadline exceeded');
  const deadline=AbortSignal.timeout(Math.ceil(remaining));
  const response=await fetchImpl(gateway.url,{method:'POST',
    headers:{'Content-Type':'application/json',Authorization:'Bearer '+gateway.grant},
    body:JSON.stringify({operation:'validate_batch',calls}),
    signal:signal?AbortSignal.any([signal,deadline]):deadline});
  const result=await response.json();
  if(!response.ok){
    const capacity=result.capacity;
    const bounds=result.error==='capacity_exceeded'&&result.executed===false&&
      capacity?.dimension==='rpc_batch_requests'&&Number.isSafeInteger(capacity.actual)&&
      Number.isSafeInteger(capacity.limit)&&capacity.limit>0?
      `; rpc_batch_requests: actual=${capacity.actual}, limit=${capacity.limit}; split into smaller batches and validate again`:'';
    throw Error('Batch preflight failed; no calls executed; '+
      (publicErrors.has(result.error)?result.error:'gateway_request_failed')+bounds);
  }
  if(result.schema!=='capstone-gateway-preflight/1'||result.catalog_revision!==gateway.catalog.revision||
      result.executed!==false||typeof result.valid!=='boolean'||!Array.isArray(result.errors)||
      result.valid!==(result.errors.length===0))throw Error('Batch preflight receipt identity changed; no calls executed');
  if(!result.valid)throw Error('Batch preflight rejected; no calls executed; '+JSON.stringify(result.errors));
}

export function createDataGatewayTools(config,{fetchImpl=globalThis.fetch,cwd=config.toolResultCwd}={}) {
  const gateway=config.dataGateway;
  if(!gateway)return [];
  let stopped;
  function failure(code,stop=false,validation=[],gatewayStatus){
    const types=new Set(['null','boolean','object','array','string','integer','number']);
    const bounds=new Set(['minimum','maximum','exclusiveMinimum','exclusiveMaximum','minItems','maxItems','minLength','maxLength']);
    const details=Array.isArray(validation)?validation.slice(0,8).filter(item=>item&&typeof item.path==='string'&&item.path.length<=256&&typeof item.rule==='string'&&item.rule.length<=64&&(types.has(item.actual_type)||item.actual_type==='missing'&&item.rule==='required')).map(item=>({path:item.path,rule:item.rule,actual_type:item.actual_type,...(types.has(item.expected)?{expected:item.expected}:{}),...(bounds.has(item.rule)&&typeof item.bound==='number'&&Number.isFinite(item.bound)?{bound:item.bound}:{})})):[];
    const observedStatus=code==='gateway_result_body_unavailable'&&['ok','partial','unavailable','error','failed','cancelled'].includes(gatewayStatus)
      ? ' 网关回执确认的执行状态：'+gatewayStatus+'。业务响应体不可用。' : '';
    const message=(code==='gateway_result_body_unavailable'?'原业务响应不可用，请查回原调用记录。 code='+code:
      code==='gateway_operation_retry_blocked'?'当前操作禁止自动重放；请先核对原失败诊断、连接和源端执行状态。 code='+code:code)+observedStatus+'; do not retry this call'+(details.length?'; not executed; correct arguments using the exact contract: '+JSON.stringify(details):'')+(stop?
      ' or probe other gateway tools in this task. Report this failure only; gateway-wide availability is unverified.':'');
    if(stop)stopped=message;
    return new Error(message);
  }
  return Object.entries(gateway.catalog.tools).map(([name,schema])=>({
    name,label:name,description:gatewayToolDescription(schema,config.runtimeLimits?.tool_summary_chars)??name,parameters:schema.inputSchema,
    async execute(callId,args,signal,_onUpdate,context){
      await resolveGatewayContracts(config,[name],{signal,fetchImpl});
      const observationPolicy=context?.[gatewayInvocationOptions];
      signal?.throwIfAborted();
      if(stopped)throw new Error(stopped);
      const remaining=Math.min(1800000,config.deadlineAt-Date.now());
      if(remaining<=0)throw new Error('gateway task deadline exceeded');
      const deadline=AbortSignal.timeout(Math.ceil(remaining));
      let response;
      try{
        response=await fetchImpl(gateway.url,{method:'POST',
          headers:{'Content-Type':'application/json',Authorization:'Bearer '+gateway.grant},
          body:JSON.stringify({call_id:callId,name,arguments:args,...(observationPolicy?{observation_policy:observationPolicy}:{})}),
          signal:signal?AbortSignal.any([signal,deadline]):deadline});
      }catch(error){
        signal?.throwIfAborted();
        throw failure('gateway_connection_failed',true);
      }
      if(!response.ok){
        let code,validation,gatewayStatus;
        try{const body=await response.json();code=body.error;validation=body.validation_errors;gatewayStatus=body.gateway_observed_status;}catch{}
        signal?.throwIfAborted();
        if(!publicErrors.has(code))code='gateway_request_failed';
        throw failure(code,resourceErrors.has(code)||response.status>=500,code==='gateway_arguments_invalid'?validation:[],gatewayStatus);
      }
      const value=await response.json(),receipt=value.observation;
      if(typeof value.result_json!=='string'||receipt?.kind!=='external_gateway_observation'||
          receipt.task_id!==gateway.taskId||receipt.tool_call_id!==callId||receipt.tool!==name||
          receipt.catalog_revision!==gateway.catalog.revision||
          receipt.tool_schema_sha256!==gateway.catalog.tool_hashes[name])throw new Error('gateway receipt identity changed');
      const ledger=gatewayUseLedger(config);
      const result=await boundToolResult({content:[{type:'text',text:value.result_json}],details:receipt,isError:value.is_error===true},
        {cwd,toolName:name,callId,storageCallId:receipt.reused_from??callId,retain:true});
      const saved=savedToolObservation(result);
      let raw;try{raw=JSON.parse(value.result_json);}catch{}
      const source=raw?.structuredContent??raw;
      const observation=saved&&{...saved,receipt,observedAt:receipt.observed_at?Date.parse(receipt.observed_at):Date.now(),
        ok:value.is_error!==true&&!['error','failed','denied'].includes(source?.status)};
      ledger.record(name,callId,observation);
      if(typeof config.researchTaskId==='string')ledger.record(name,'native-observation:'+config.researchTaskId+':'+createHash('sha256').update(callId).digest('hex'),observation);
      if(saved)result.content=[...result.content,{type:'text',text:JSON.stringify({observation_ref:callId,
        ...(receipt.reused_from?{reused:true,original_observation_ref:receipt.reused_from,observed_at:receipt.observed_at}:{}),
        base_pointer:'',instruction:'Task-issued observation reference. Composition tools.read and tools.inspect expose the structured result at the root, as tools.call and full_result reads do. Use exact returned fields. Reuse this result; no source call is needed.'})}];
      return result;
    }
  }));
}
