/** Application templates use a fixed private adapter and the current task grant. */
import {createHash} from 'node:crypto';
import {resolve} from 'node:path';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';

const executeFile=promisify(execFile);

export function createPresentationTools(config,{fetchImpl=globalThis.fetch,runRenderer=executeFile}={}){
 const binding=config.presentationLibrary;
 if(!binding||!config.applicationPolicy?.allowed_tools?.includes('agent_presentations'))return [];
 const tool={name:'agent_presentations',label:'PPT 模板库',
  description:'Use the presentation template library when relevant. catalog returns the current session selection, built-in State Grid template, immutable library versions and admitted PPTX uploads. add takes resource {resource_id,version,sha256} and name; it creates a session-only template. publish takes reference {template_id,version,sha256}; use it only when the user explicitly asks to save to the library. select takes reference and expected_revision from the catalog and persists for this conversation. materialize takes optional reference for a one-render override and returns a verified read-only template path without changing selection. Unknown mutations must not be replayed: operation with the original request_id reads the durable receipt. No workspace, thread, endpoint or host path can be supplied. The library does not grant source tools or Authority evidence.',
  parameters:{type:'object',properties:{operation:{type:'string',enum:['catalog','add','select','publish','materialize','render','operation']},document:{type:'object'}},required:['operation','document'],additionalProperties:false},
  async execute(callId,args,signal){
   if(!binding.url||!binding.grant)throw Error('Presentation library task binding is missing');
   if(!args||!['catalog','add','select','publish','materialize','render','operation'].includes(args.operation)||
      !args.document||typeof args.document!=='object'||Array.isArray(args.document))throw Error('Presentation request is invalid');
   const remaining=config.deadlineAt-Date.now();if(!(remaining>0))throw Error('Presentation task deadline expired');
   if(args.operation==='render'){
    const d=args.document;
    if(Object.keys(d).some(k=>!['spec','bundle','output','reference','pdf'].includes(k))||
       (typeof d.spec==='string')===(typeof d.bundle==='string')||typeof d.output!=='string'||
       d.pdf!==undefined&&typeof d.pdf!=='boolean')throw Error('Presentation render request is invalid');
    const frozen=await tool.execute(callId+'/template',{operation:'materialize',document:
      d.reference===undefined?{}:{reference:d.reference}},signal);
    if(frozen.isError)return frozen;
    const selected=frozen.details.result;
    const argv=[d.spec===undefined?'--bundle':'--spec',d.spec??d.bundle,'--output',d.output,
      '--template',selected.path,'--template-sha256',selected.template.sha256];
    if(d.pdf!==false)argv.push('--pdf');
    let receipt;
    try{
     const rendered=await runRenderer('/usr/local/bin/capstone-presentation',argv,{
       cwd:config.toolResultCwd??process.cwd(),signal,timeout:Math.max(1,config.deadlineAt-Date.now()),maxBuffer:1024*1024});
     receipt=JSON.parse(rendered.stdout);
     if(receipt.schema!=='capstone-presentation-library-render/1'||receipt.output!==d.output||
        receipt.template_sha256!==selected.template.sha256)throw Error('Receipt mismatch');
    }catch{
     signal?.throwIfAborted();
     return {isError:true,content:[{type:'text',text:'Presentation render failed. Inspect saved products before claiming delivery. Use a new output path for each version.'}],
       details:{capability:'agent_presentations',ok:false,code:'presentation_render_failed',evidence_refs:[]}};
    }
    const result={...receipt,template_reference:{template_id:selected.template.template_id,
      version:selected.template.version,sha256:selected.template.sha256}};
    return {content:[{type:'text',text:JSON.stringify(result)}],details:{capability:'agent_presentations',ok:true,result,evidence_refs:[]}};
   }
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
  }};
 tool.description+=' render takes either spec (saved capstone-presentation/1 or /2 JSON) or bundle (a previous .source.zip), output (a new relative .pptx path), optional reference and pdf (defaults true). It freezes exact content/dependencies, applies the session template or one-render override, registers products and returns PPTX, reproducible source bundle and conversion status. A failed or unavailable PDF is not PDF delivery. Rerender the bundle to change template without requerying source systems. Keep the existing capstone-report CLI for explicitly untemplated output.';
 return [tool];
}
