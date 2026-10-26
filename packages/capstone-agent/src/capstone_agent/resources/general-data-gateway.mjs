// The host supplies this task-bound relay and catalog. Upstream credentials
// and endpoint selectors are never tool parameters or native task inputs.
const publicErrors=new Set(['gateway_arguments_invalid','gateway_request_invalid',
  'gateway_tool_not_admitted','gateway_task_not_admitted','gateway_call_already_started',
  'gateway_publication_changed','gateway_authentication_failed','gateway_connection_failed',
  'gateway_call_failed_no_retry','gateway_timeout','gateway_transport_failed','gateway_output_invalid','gateway_catalog_invalid',
  'gateway_catalog_unavailable','gateway_unavailable','capacity_exceeded','unauthorized']);
const resourceErrors=new Set(['gateway_publication_changed','gateway_authentication_failed',
  'gateway_connection_failed','gateway_call_failed_no_retry','gateway_timeout','gateway_transport_failed','gateway_catalog_invalid',
  'gateway_catalog_unavailable','gateway_unavailable','gateway_task_not_admitted','unauthorized']);

export function createDataGatewayTools(config,{fetchImpl=globalThis.fetch}={}) {
  const gateway=config.dataGateway;
  if(!gateway)return [];
  let stopped;
  function failure(code,stop=false){
    const message=code+'; do not retry this call'+(stop?
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
        let code;
        try{code=(await response.json()).error;}catch{}
        signal?.throwIfAborted();
        if(!publicErrors.has(code))code='gateway_request_failed';
        throw failure(code,resourceErrors.has(code)||response.status>=500);
      }
      const value=await response.json(),receipt=value.observation;
      if(typeof value.result_json!=='string'||receipt?.kind!=='external_gateway_observation'||
          receipt.task_id!==gateway.taskId||receipt.tool_call_id!==callId||receipt.tool!==name||
          receipt.catalog_revision!==gateway.catalog.revision||
          receipt.tool_schema_sha256!==gateway.catalog.tool_hashes[name])throw new Error('gateway receipt identity changed');
      return {content:[{type:'text',text:value.result_json}],details:receipt,isError:value.is_error===true};
    }
  }));
}
