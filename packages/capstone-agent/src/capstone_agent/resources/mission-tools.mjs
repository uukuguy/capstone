// Application Control requests. The native process has no Control credentials.
export function createMissionTools(config,{fetchImpl=globalThis.fetch,channel=config.missionTools}={}){
 const debug=channel===config.debugTools;
 if(!channel)return [];
 return Object.entries(channel.catalog).map(([name,schema])=>({name,label:name,executionIdentity:'owner',
  description:schema.description,parameters:schema.inputSchema,
  async execute(callId,args,signal){
   const remaining=config.deadlineAt-Date.now();
   if(remaining<=0)throw new Error('Mission tool deadline exceeded');
   const deadline=AbortSignal.timeout(Math.ceil(remaining));
   const active=signal?AbortSignal.any([signal,deadline]):deadline;
   const body=JSON.stringify({call_id:callId,name,arguments:args});
   while(true){
    active.throwIfAborted();
    let response;
    try{response=await fetchImpl(channel.url,{method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer '+channel.grant},body,signal:active});}
    catch{active.throwIfAborted();throw new Error('Mission transport interrupted; do not invent a Control result');}
    const receipt=await response.json();
    if(!response.ok)throw new Error('Mission request was not admitted');
    if(receipt.pending===true){
     await new Promise((resolve,reject)=>{
      const stop=()=>{clearTimeout(timer);reject(active.reason)};
      const timer=setTimeout(()=>{active.removeEventListener('abort',stop);resolve()},100);
      active.addEventListener('abort',stop,{once:true});
     });continue;
    }
    if(receipt.call_id!==callId||typeof receipt.is_error!=='boolean'||!receipt.result||typeof receipt.result!=='object'||Array.isArray(receipt.result))throw new Error('Mission receipt identity is invalid');
    return {content:[{type:'text',text:JSON.stringify(receipt.result)}],isError:receipt.is_error,
     details:{ok:!receipt.is_error,...(debug?{debug_investigation:true}:{mission_control:true}),call_id:callId}};
   }
  }
 }));
}
