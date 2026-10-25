// The host supplies this task-bound relay and catalog. Upstream credentials
// and endpoint selectors are never tool parameters or native task inputs.
export function createDataGatewayTools(config,{fetchImpl=globalThis.fetch}={}) {
  const gateway=config.dataGateway;
  if(!gateway)return [];
  return Object.entries(gateway.catalog.tools).map(([name,schema])=>({
    name,label:name,description:schema.description??name,parameters:schema.inputSchema,
    async execute(callId,args,signal){
      signal?.throwIfAborted();
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
        throw new Error('gateway request failed; do not retry this call');
      }
      if(!response.ok)throw new Error('gateway request refused or unavailable; do not retry this call');
      const value=await response.json(),receipt=value.observation;
      if(typeof value.result_json!=='string'||receipt?.kind!=='external_gateway_observation'||
          receipt.task_id!==gateway.taskId||receipt.tool_call_id!==callId||receipt.tool!==name||
          receipt.catalog_revision!==gateway.catalog.revision||
          receipt.tool_schema_sha256!==gateway.catalog.tool_hashes[name])throw new Error('gateway receipt identity changed');
      return {content:[{type:'text',text:value.result_json}],details:receipt,isError:value.is_error===true};
    }
  }));
}
