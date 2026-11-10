/** Application templates use a fixed private adapter and the current task grant. */
import {createHash} from 'node:crypto';
import {resolve} from 'node:path';

export function createPresentationTools(config,{fetchImpl=globalThis.fetch}={}){
 const binding=config.presentationLibrary;
 if(!binding||!config.applicationPolicy?.allowed_tools?.includes('agent_presentations'))return [];
 return [{name:'agent_presentations',label:'PPT 模板库',
  description:'Use the presentation template library when relevant. catalog returns the current session selection, built-in State Grid template, immutable library versions and admitted PPTX uploads. add takes resource {resource_id,version,sha256} and name; it creates a session-only template. publish takes reference {template_id,version,sha256}; use it only when the user explicitly asks to save to the library. select takes reference and expected_revision from the catalog and persists for this conversation. materialize takes optional reference for a one-render override and returns a verified read-only template path without changing selection. Unknown mutations must not be replayed: operation with the original request_id reads the durable receipt. No workspace, thread, endpoint or host path can be supplied. The library does not grant source tools or Authority evidence.',
  parameters:{type:'object',properties:{operation:{type:'string',enum:['catalog','add','select','publish','materialize','operation']},document:{type:'object'}},required:['operation','document'],additionalProperties:false},
  async execute(callId,args,signal){
   if(!binding.url||!binding.grant)throw Error('Presentation library task binding is missing');
   if(!args||!['catalog','add','select','publish','materialize','operation'].includes(args.operation)||
      !args.document||typeof args.document!=='object'||Array.isArray(args.document))throw Error('Presentation request is invalid');
   const remaining=config.deadlineAt-Date.now();if(!(remaining>0))throw Error('Presentation task deadline expired');
   const request_id='presentation_'+createHash('sha256').update(config.taskId+'\0'+callId).digest('hex');
   let response,value;
   try{
    response=await fetchImpl(binding.url,{method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer '+binding.grant},
      body:JSON.stringify({call_id:callId,operation:args.operation,document:args.document}),
      signal:signal?AbortSignal.any([signal,AbortSignal.timeout(remaining)]):AbortSignal.timeout(remaining)});
    const raw=await response.text();if(Buffer.byteLength(raw)>128*1024)throw Error('Presentation response exceeds bounds');
    value=JSON.parse(raw);
   }catch{
    signal?.throwIfAborted();
    const result={code:'presentation_operation_outcome_unknown',executed:null,request_id,
      recovery:'Do not repeat an uncertain mutation. Read operation with this original request_id first.'};
    return {isError:true,content:[{type:'text',text:JSON.stringify(result)}],details:result};
   }
   if(args.operation==='materialize'&&response.ok&&value.ok===true){
    const result=value.result,t=result?.template;
    if(!t||!/^([a-f0-9]{64})$/.test(t.sha256)||t.version!=='sha256:'+t.sha256||
       !/^(state-grid|tpl_[a-f0-9]{32})$/.test(t.template_id)||!binding.inputRoot||
       result.path!==resolve(binding.inputRoot,'presentation-templates',t.template_id,t.sha256+'.pptx'))
      throw Error('Presentation template input identity changed');
   }
   const isError=!response.ok||value?.ok!==true;
   return {isError,content:[{type:'text',text:JSON.stringify(value)}],
     details:{capability:'agent_presentations',ok:!isError,result:value.result,request_id,evidence_refs:[]}};
  }}];
}
