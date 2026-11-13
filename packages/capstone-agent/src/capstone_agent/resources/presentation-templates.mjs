/** Application templates use a fixed private adapter and the current task grant. */
import {createHash} from 'node:crypto';
import {resolve} from 'node:path';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';

const executeFile=promisify(execFile);
const referenceSchema={type:'object',properties:{template_id:{type:'string'},version:{type:'string'},sha256:{type:'string'}},
 required:['template_id','version','sha256'],additionalProperties:false};

export function createPresentationTools(config,{fetchImpl=globalThis.fetch,runRenderer=executeFile}={}){
 const binding=config.presentationLibrary;
 if(!binding||!config.applicationPolicy?.allowed_tools?.includes('agent_presentations'))return [];
 const tool={name:'agent_presentations',label:'PPT 模板库',
  description:'Use the presentation template library when relevant. catalog returns the current session selection, built-in State Grid template, immutable library versions and admitted PPTX uploads. add takes resource {resource_id,version,sha256} and name; it creates a session-only template. publish takes reference {template_id,version,sha256}; use it only when the user explicitly asks to save to the library. select takes reference and expected_revision from the catalog and persists for this conversation. materialize takes optional reference for a one-render override and returns a verified read-only template path without changing selection. Unknown mutations must not be replayed: operation with the original request_id reads the durable receipt. No workspace, thread, endpoint or host path can be supplied. The library does not grant source tools or Authority evidence.',
  parameters:{type:'object',properties:{operation:{type:'string',enum:['contract','catalog','add','select','publish','materialize','render','operation']},
   document:{type:'object',properties:{reference:referenceSchema,
    resource:{type:'object',properties:{resource_id:{type:'string'},version:{type:'integer',minimum:1},sha256:{type:'string'}},
     required:['resource_id','version','sha256'],additionalProperties:false},
    name:{type:'string'},expected_revision:{type:'integer',minimum:0},after:{type:'string'},limit:{type:'integer',minimum:1,maximum:128},
    request_id:{type:'string'},spec:{type:'string'},bundle:{type:'string'},output:{type:'string'},pdf:{type:'boolean'}},additionalProperties:false}},
   required:['operation','document'],additionalProperties:false},
  async execute(callId,args,signal){
   if(!binding.url||!binding.grant)throw Error('Presentation library task binding is missing');
   if(!args||!['contract','catalog','add','select','publish','materialize','render','operation'].includes(args.operation)||
      !args.document||typeof args.document!=='object'||Array.isArray(args.document))throw Error('Presentation request is invalid');
   const remaining=config.deadlineAt-Date.now();if(!(remaining>0))throw Error('Presentation task deadline expired');
   if(args.operation==='contract'){
    if(Object.keys(args.document).length)throw Error('contract requires an empty document');
    try{
     const rendered=await runRenderer('/usr/local/bin/capstone-presentation',['--contract'],{
       cwd:config.toolResultCwd??process.cwd(),signal,timeout:Math.max(1,remaining),maxBuffer:128*1024});
     const result=JSON.parse(rendered.stdout);
     if(result.schema!=='capstone-presentation-content-contract/1')throw Error('Invalid contract');
     return {isError:false,content:[{type:'text',text:JSON.stringify(result)}],details:{capability:'agent_presentations',ok:true,result,evidence_refs:[]}};
    }catch{signal?.throwIfAborted();return {isError:true,content:[{type:'text',text:'Presentation content contract is unavailable.'}],details:{capability:'agent_presentations',ok:false}};}
   }
   if(args.operation==='render'){
    const d=args.document;
    if(Object.keys(d).some(k=>!['spec','bundle','output','reference','pdf'].includes(k))||
       (typeof d.spec==='string')===(typeof d.bundle==='string')||typeof d.output!=='string'||
       d.pdf!==undefined&&typeof d.pdf!=='boolean')throw Error('render document requires exactly one spec or bundle path, output (.pptx), optional reference {template_id,version,sha256}, and optional pdf boolean. No template path or renderer command is accepted.');
    const frozen=await tool.execute(callId+'/template',{operation:'materialize',document:
      d.reference===undefined?{}:{reference:d.reference}},signal);
    if(frozen.isError)return frozen;
    const selected=frozen.details.result;
    const argv=[d.spec===undefined?'--bundle':'--spec',d.spec??d.bundle,'--output',d.output,
      '--template',selected.path,'--template-sha256',selected.template.sha256,'--template-id',selected.template.template_id];
    if(d.pdf!==false)argv.push('--pdf');
    let receipt;
    try{
     const rendered=await runRenderer('/usr/local/bin/capstone-presentation',argv,{
       cwd:config.toolResultCwd??process.cwd(),signal,timeout:Math.max(1,config.deadlineAt-Date.now()),maxBuffer:1024*1024});
     receipt=JSON.parse(rendered.stdout);
     if(receipt.schema!=='capstone-presentation-library-render/1'||receipt.output!==d.output||
        receipt.template_sha256!==selected.template.sha256)throw Error('Receipt mismatch');
    }catch(error){
     signal?.throwIfAborted();
     let diagnostic;
     try{
      if(typeof error?.stderr==='string'&&Buffer.byteLength(error.stderr)<=16384){
       const parsed=JSON.parse(error.stderr);
       if(parsed.schema==='capstone-presentation-render-error/1'&&parsed.code==='presentation_render_rejected'&&
          typeof parsed.message==='string'&&parsed.message.length<=600&&parsed.delivery_confirmed===false)diagnostic=parsed;
      }
     }catch{}
     if(diagnostic)return {isError:true,content:[{type:'text',text:JSON.stringify(diagnostic)}],
       details:{capability:'agent_presentations',ok:false,code:diagnostic.code,diagnostic,evidence_refs:[]}};
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
 tool.description+=' render takes either spec (saved capstone-presentation/1 or /2 JSON) or bundle (a previous .source.zip), output (a new relative .pptx path), optional reference and pdf (defaults true). Minimal /1 content: {"schema":"capstone-presentation/1","title":"Title","slides":[{"title":"Point","blocks":[{"type":"paragraph","text":"Supported text"}]}]}. Version /2 additionally requires argument:{explanation:"Visible reasoning"} on each content slide. Table blocks require csv (workspace-relative CSV), columns and max_rows; figure blocks require path and caption. It freezes exact content/dependencies, applies the session template or one-render override, registers products and returns PPTX, reproducible source bundle and conversion status. A failed or unavailable PDF is not PDF delivery. Rerender the bundle to change template without requerying source systems. Keep the existing capstone-report CLI for explicitly untemplated output.';
 tool.description+=' contract with document:{} returns the exact content fields and a complete agenda/content/closing example without rendering. Read it when authoring a deck or resolving field/chapter errors. Missing slide role defaults to content; with an agenda, each content section must exactly match a chapter title in agenda order. Use this render operation rather than invoking the low-level CLI without its host-selected template arguments.';
 return [tool];
}
