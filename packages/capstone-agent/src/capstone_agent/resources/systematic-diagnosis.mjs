import {createHash} from 'node:crypto';
import {open} from 'node:fs/promises';
import {constants} from 'node:fs';
import {isAbsolute,join} from 'node:path';
import {setTimeout as delay} from 'node:timers/promises';

export const diagnosisTools=['agent_diagnosis_record','agent_diagnosis_guide'];
const schema='capstone-systematic-diagnosis/1';
export const diagnosisGuide=`Use diagnosis for unexpected errors, conflicting results or attempts without new information.
Inspect actual evidence, form a falsifiable hypothesis, use a minimal probe through existing permitted tools,
then record the observed outcome. Compare with a working example when useful. Keep rejected hypotheses.
For ordinary work use ONE agent_diagnosis_record call. No IDs, hashes, begin or finish are required.
Example: {"issue":"Selected column is absent","hypothesis":"The header differs","minimal_probe":"Read the header",
"outcome":"passed","information_gained":"The saved probe found the actual column",
"evidence_refs":[],"next_disposition":"continue"}. Add actual references and limitations when available.
Required report fields: issue, outcome, information_gained, next_disposition. Other method details are advisory.
The host fills record identity. The tool records observations; it never executes a probe or grants access.
Use operation:"read" for recovery. An unfinished reserved probe remains unknown: inspect its existing receipt
before any repeat. A new report does not silently finish or certify that historic probe.
Legacy begin/finish are available only when an explicit reservation is useful. If you begin, wait for probe_reserved
before that probe; finish accepts ONLY probe_id, outcome, outcome_refs, information_gained, rejected_hypotheses,
next_disposition. Do not copy begin fields into finish. No optional proof is a delivery gate.
Known field errors return missing/extra field guidance. Three bad corrections exhaust that operation/host probe;
record an honest separate report or retain the gap. Reopening/renaming cannot reset this budget.
After exhaustion two ignored repeats stop the correction loop; a limited final answer remains available first.
Use outcome passed/failed/not_run/unknown and next_disposition continue/change_method/retain_gap/stop_dependent/request_input.
A transient failure, changed input, corrected call or new hypothesis can justify bounded repeated tool work.
These are reported observations, not host-certified facts or Authority evidence. Objective grid
model, solver, unit, revision and result admission remain enforced by their registered contracts.
Research checks are advisory by default: retain findings and gaps and deliver useful work.
Missing optional proof does not block delivery. A genuinely missing required input can block its dependent action.
If exhausted, keep useful work and the gap, change method, continue independent work or request required input.
Do not reset the budget by renaming an issue. Do not retry an unknown side effect: recover the exact receipt first.`;

// Hash a typed ASCII tree rather than each language's decimal JSON formatter.
// JSON numbers use IEEE 754 binary64 in the SDK. Normalize signed zero because
// JSON.stringify transmits both signs as 0. Strings/keys use exact UTF-8 bytes.
function wireString(value){
  if(/[\uD800-\uDFFF]/u.test(value))throw new TypeError('Diagnostic text contains an unpaired surrogate');
  return Buffer.from(value,'utf8').toString('hex');
}
function wireValue(value){
  if(value===null)return ['null'];
  if(typeof value==='boolean')return ['bool',value];
  if(typeof value==='string')return ['str',wireString(value)];
  if(typeof value==='number'){
    if(!Number.isFinite(value))throw new TypeError('Diagnostic numbers must be finite');
    const bytes=Buffer.alloc(8);bytes.writeDoubleBE(value===0?0:value);
    return ['num',bytes.toString('hex')];
  }
  if(Array.isArray(value))return ['array',value.map(wireValue)];
  if(value&&typeof value==='object')return ['object',Object.entries(value).map(([key,item])=>[wireString(key),wireValue(item)])
    .sort(([left],[right])=>left<right?-1:left>right?1:0)];
  throw new TypeError('Diagnostic values must be JSON data');
}
export const diagnosisDigest=value=>createHash('sha256').update(JSON.stringify(wireValue(value))).digest('hex');
const digest=diagnosisDigest;
const text={type:'string',maxLength:2000};
const texts={type:'array',maxItems:16,items:text};
const runtimeStates=new WeakMap();
function runtimeState(config){
  if(!runtimeStates.has(config))runtimeStates.set(config,{exhausted:new Map(),validationErrors:new Map(),
    knownProbes:new Set(),knownScopes:new Set(),failure:undefined});
  return runtimeStates.get(config);
}
function observeSuccess(state,event){
  const details=event.details??event.result?.details,diagnosis=details?.diagnosis;
  if(diagnosis?.scope_ref)state.knownScopes.add(diagnosis.scope_ref);
  for(const scope of diagnosis?.scopes??[])if(scope.scope_ref)state.knownScopes.add(scope.scope_ref);
  for(const record of [diagnosis?.record,...(diagnosis?.records??[])]){
    if(record?.probe_id)state.knownProbes.add(record.probe_id);
    if(record?.scope_ref)state.knownScopes.add(record.scope_ref);
  }
  if(event.isError===true||event.result?.isError===true||diagnosis?.category==='rejected'||details?.ok===false||details?.error?.category)return;
  if(event.toolName==='agent_diagnosis_guide'||event.toolName==='agent_diagnosis_record'&&diagnosis?.status!=='recorded')return;
  // Useful independent execution or a retained outcome ends the no-progress
  // sequence. It never changes the durable host correction allowance.
  for(const scope of state.exhausted.keys())state.exhausted.set(scope,0);
  state.validationErrors.clear();
}

// Apply the same correction stop to organizers and authorized native children.
export function configureDiagnosisCorrectionGuard(pi,config){
  const state=runtimeState(config);
  if(isAbsolute(config.diagnosisContextPath??'')&&config.applicationPolicy?.allowed_tools?.includes('agent_diagnosis_record')){
    pi.on('tool_result',event=>{
      observeSuccess(state,event);
      if(event.toolName!=='agent_diagnosis_record')return;
      const error=event.details?.diagnosis;
      if(error?.category==='rejected'){
        if(error.status==='exhausted'){
          const scope=error.correction_scope??'legacy-'+error.operation;
          // The first exhaustion notice is not an ignored repeat.
          state.exhausted.set(scope,state.exhausted.has(scope)?state.exhausted.get(scope)+1:0);
        }
        return {isError:true};
      }
    });
    pi.on('before_model_request',()=>{
      if(state.failure)throw state.failure;
      if([...state.exhausted.values()].some(count=>count>=2)||[...state.validationErrors.values()].some(count=>count>=4)){
        state.failure=new Error('Diagnostic correction attempts repeated an exhausted operation. Useful work and the unresolved metadata gap remain retained.');
        state.failure.code='diagnosis_correction_no_progress';throw state.failure;
      }
    });
  }
  return {failure:()=>state.failure};
}

export function watchDiagnosisValidation(session,config){
  if(!isAbsolute(config.diagnosisContextPath??'')||!config.applicationPolicy?.allowed_tools?.includes('agent_diagnosis_record'))
    return ()=>{};
  const state=runtimeState(config);
  return session.subscribe(event=>{
    if(event.type==='tool_execution_end')observeSuccess(state,event);
    if(event.type==='tool_execution_end'&&event.toolName==='agent_diagnosis_record'&&
      (event.isError===true||event.result?.isError===true)&&!event.result?.details?.diagnosis&&!state.failure){
      const call=[...session.messages].reverse().flatMap(message=>message.role==='assistant'&&Array.isArray(message.content)?message.content:[])
        .find(item=>item.type==='toolCall'&&item.id===event.toolCallId);
      const args=call?.arguments??{},record=args.record??args;
      const operation=args.operation===undefined?'report':['read','begin','finish','report'].includes(args.operation)?args.operation:'unknown';
      const scope=diagnosisDigest({operation,probe:state.knownProbes.has(record?.probe_id)?record.probe_id:'unresolved',
        input_scope:state.knownScopes.has(record?.scope_ref)?record.scope_ref:'unbound'});
      state.validationErrors.set(scope,(state.validationErrors.get(scope)??0)+1);
    }
  });
}

// This client reads only host-owned receipts, never model-writable workspace files.
export function createDiagnosisTools(config,{emit=frame=>process.stdout.write(JSON.stringify(frame)+'\n')}={}){
  const grants=config.applicationPolicy?.allowed_tools??[];
  if(!isAbsolute(config.diagnosisContextPath??''))return [];
  const sent=new Map(),confirmed=new Map();
  async function request(callId,args,signal){
    const id='diag-'+digest({namespace:config.diagnosisNamespace??'parent',callId});
    const {operation='report',record,...report}=args;
    const frame={type:'systematic_diagnosis_request',schema,request_id:id,operation,record:record??report};
    const hash=digest(frame);
    if(sent.has(id)&&sent.get(id)!==hash)throw new Error('Diagnostic request identity changed. Recover the original call.');
    if(confirmed.has(id))return confirmed.get(id);
    signal?.throwIfAborted();
    if(!sent.has(id)){sent.set(id,hash);await emit(frame);}
    const deadline=Math.min(config.deadlineAt??Infinity,Date.now()+15000);
    while(true){
      signal?.throwIfAborted();
      let file;
      try{
        file=await open(join(config.diagnosisContextPath,'responses',id+'.json'),constants.O_RDONLY|constants.O_NOFOLLOW|constants.O_NONBLOCK);
        const info=await file.stat();
        if(!info.isFile()||info.size>524288)throw new Error('Diagnostic receipt is invalid');
        const receipt=JSON.parse(await file.readFile('utf8'));
        if(receipt.schema!==schema||receipt.request_id!==id||receipt.request_sha256!==hash)throw new Error('Diagnostic receipt identity changed');
        if(receipt.ok!==true){
          const rejection=receipt.error??(receipt.code==='diagnosis_record_invalid'?{
            category:'rejected',status:'rejected',operation,
            message:'This saved field rejection changed no outcome. Read the guide for exact legacy fields, or use a one-shot report without probe IDs.'}:undefined);
          if(!['read','begin','finish','report'].includes(operation)||rejection?.category!=='rejected')
            throw new Error('Host rejected the internal diagnostic receipt. Required persistence remains enforced.');
          const result={isError:true,content:[{type:'text',text:JSON.stringify(rejection)}],
            details:{diagnosis:rejection,error:{category:'rejected',code:receipt.code}}};
          confirmed.set(id,result);return result;
        }
        const result={content:[{type:'text',text:JSON.stringify(receipt.result)}],details:{diagnosis:receipt.result}};
        confirmed.set(id,result);return result;
      }catch(error){if(error.code!=='ENOENT')throw error;}
      finally{await file?.close();}
      if(Date.now()>=deadline)throw new Error('Diagnostic outcome is unknown. Recover request '+id+' before executing or repeating a probe.');
      await delay(10,undefined,{signal});
    }
  }
  return [
    {name:'agent_diagnosis_guide',label:'Diagnosis guide',description:'Read the built-in systematic diagnosis method on demand.',
      parameters:{type:'object',properties:{},additionalProperties:false},
      execute:async()=>({content:[{type:'text',text:diagnosisGuide}]})},
    {name:'agent_diagnosis_record',label:'Systematic diagnosis',
      description:'Record an observed diagnosis in one call: issue, outcome, information_gained, next_disposition. Add hypothesis, minimal_probe, references and limitations when useful. Host fills identity; no IDs or begin/finish needed. Never executes probes or certifies evidence. operation read and legacy begin/finish support recovery.',
      parameters:{type:'object',additionalProperties:false,properties:{
        operation:{type:'string',enum:['report','read','begin','finish']},
        record:{type:'object',additionalProperties:true,description:'Legacy nested operation fields. Prefer flat report fields. Finish accepts only probe_id, outcome, outcome_refs, information_gained, rejected_hypotheses, next_disposition.'},
          issue:text,input_version:text,evidence_refs:texts,hypothesis:text,minimal_probe:text,retry_reason:text,comparison:text,
          rejected_hypotheses:texts,acceptance:{type:'string',enum:['advisory','objective']},probe_id:text,scope_ref:text,
          outcome:{type:'string',enum:['passed','failed','not_run','unknown']},outcome_refs:texts,information_gained:text,limitations:texts,
          next_disposition:{type:'string',enum:['continue','change_method','retain_gap','stop_dependent','request_input']}}},
      execute:async(...args)=>{
        try{return await request(...args);}
        catch(error){runtimeState(config).failure=error;throw error;}
      }}
  ].filter(tool=>grants.includes(tool.name));
}
