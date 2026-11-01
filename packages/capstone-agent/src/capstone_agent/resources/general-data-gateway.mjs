// The host supplies this task-bound relay and catalog. Upstream credentials
// and endpoint selectors are never tool parameters or native task inputs.
import {boundToolResult,savedToolObservation} from './tool-result-context.mjs';
import {createHash} from 'node:crypto';
import {gatewayUseLedger} from './gateway-tool-use.mjs';
const publicErrors=new Set(['gateway_arguments_invalid','gateway_request_invalid',
  'gateway_tool_not_admitted','gateway_task_not_admitted','gateway_call_already_started',
  'gateway_publication_changed','gateway_authentication_failed','gateway_connection_failed',
  'gateway_call_failed_no_retry','gateway_timeout','gateway_transport_failed','gateway_output_invalid','gateway_catalog_invalid',
  'gateway_catalog_unavailable','gateway_unavailable','capacity_exceeded','unauthorized']);
const resourceErrors=new Set(['gateway_authentication_failed',
  'gateway_connection_failed','gateway_call_failed_no_retry','gateway_timeout','gateway_transport_failed','gateway_catalog_invalid',
  'gateway_catalog_unavailable','gateway_unavailable','gateway_task_not_admitted','unauthorized']);

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
  if(!response.ok)throw Error('Batch preflight failed; no calls executed; '+(publicErrors.has(result.error)?result.error:'gateway_request_failed'));
  if(result.schema!=='capstone-gateway-preflight/1'||result.catalog_revision!==gateway.catalog.revision||
      result.executed!==false||typeof result.valid!=='boolean'||!Array.isArray(result.errors)||
      result.valid!==(result.errors.length===0))throw Error('Batch preflight receipt identity changed; no calls executed');
  if(!result.valid)throw Error('Batch preflight rejected; no calls executed; '+JSON.stringify(result.errors));
}

export function createDataGatewayTools(config,{fetchImpl=globalThis.fetch,cwd=config.toolResultCwd}={}) {
  const gateway=config.dataGateway;
  if(!gateway)return [];
  let stopped;
  function failure(code,stop=false,validation=[]){
    const types=new Set(['null','boolean','object','array','string','integer','number']);
    const details=Array.isArray(validation)?validation.slice(0,8).filter(item=>item&&typeof item.path==='string'&&item.path.length<=256&&typeof item.rule==='string'&&item.rule.length<=64&&types.has(item.actual_type)).map(item=>({path:item.path,rule:item.rule,actual_type:item.actual_type,...(types.has(item.expected)?{expected:item.expected}:{})})):[];
    const message=code+'; do not retry this call'+(details.length?'; not executed; correct arguments using the exact contract: '+JSON.stringify(details):'')+(stop?
      ' or probe other gateway tools in this task. Report this failure only; gateway-wide availability is unverified.':'');
    if(stop)stopped=message;
    return new Error(message);
  }
  return Object.entries(gateway.catalog.tools).map(([name,schema])=>({
    name,label:name,description:schema.description??name,parameters:schema.inputSchema,
    async execute(callId,args,signal){
      signal?.throwIfAborted();
      if(stopped)throw new Error(stopped);
      const remaining=Math.min(1800000,config.deadlineAt-Date.now());
      if(remaining<=0)throw new Error('gateway task deadline exceeded');
      const deadline=AbortSignal.timeout(Math.ceil(remaining));
      let response;
      try{
        response=await fetchImpl(gateway.url,{method:'POST',
          headers:{'Content-Type':'application/json',Authorization:'Bearer '+gateway.grant},
          body:JSON.stringify({call_id:callId,name,arguments:args}),
          signal:signal?AbortSignal.any([signal,deadline]):deadline});
      }catch(error){
        signal?.throwIfAborted();
        throw failure('gateway_connection_failed',true);
      }
      if(!response.ok){
        let code,validation;
        try{const body=await response.json();code=body.error;validation=body.validation_errors;}catch{}
        signal?.throwIfAborted();
        if(!publicErrors.has(code))code='gateway_request_failed';
        throw failure(code,resourceErrors.has(code)||response.status>=500,code==='gateway_arguments_invalid'?validation:[]);
      }
      const value=await response.json(),receipt=value.observation;
      if(typeof value.result_json!=='string'||receipt?.kind!=='external_gateway_observation'||
          receipt.task_id!==gateway.taskId||receipt.tool_call_id!==callId||receipt.tool!==name||
          receipt.catalog_revision!==gateway.catalog.revision||
          receipt.tool_schema_sha256!==gateway.catalog.tool_hashes[name])throw new Error('gateway receipt identity changed');
      const ledger=gatewayUseLedger(config);
      const result=await boundToolResult({content:[{type:'text',text:value.result_json}],details:receipt,isError:value.is_error===true},
        {cwd,toolName:name,callId,retain:true});
      const saved=savedToolObservation(result);
      let raw;try{raw=JSON.parse(value.result_json);}catch{}
      const source=raw?.structuredContent??raw;
      const observation=saved&&{...saved,receipt,observedAt:Date.now(),
        ok:value.is_error!==true&&!['error','failed','denied'].includes(source?.status)};
      ledger.record(name,callId,observation);
      if(typeof config.researchTaskId==='string')ledger.record(name,'native-observation:'+config.researchTaskId+':'+createHash('sha256').update(callId).digest('hex'),observation);
      if(saved)result.content=[...result.content,{type:'text',text:JSON.stringify({observation_ref:callId,
        base_pointer:saved.base_pointer,instruction:'Task-issued observation reference. In composition use tools.read or tools.inspect with this reference and exact JSON pointers relative to the saved root. Reuse this result; no source call is needed.'})}];
      return result;
    }
  }));
}
